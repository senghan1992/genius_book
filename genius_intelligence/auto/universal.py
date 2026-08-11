"""
UniversalWrapper
================
모든 코딩 어시스턴트 CLI에 범용으로 동작하는 래퍼

핵심:
1. 실제 stdin/stdout/stderr를 가로챔 (파이프 리다이렉션)
2. 텍스트 패턴 매칭으로 이벤트 추출
3. 파서에 의존하지 않음 - 어떤 CLI든 동작
"""

from __future__ import annotations

import os
import re
import select
import shlex
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


# 범용 이벤트 패턴
GENERIC_PATTERNS = {
    "error": [
        # 에러 키워드
        r"\berror\b",
        r"\bError\b",
        r"\bERROR\b",
        r"\bfailed\b",
        r"\bFailed\b", 
        r"\bFAIL\b",
        r"\bexception\b",
        r"\bException\b",
        r"\btraceback\b",
        r"\bTraceback\b",
        r"\bfatal\b",
        r"\bFATAL\b",
        r"^panic:",
        r"^panic\b",
        r"^Error:",
        r"^ERROR:",
        r"warning:\s*deprecated",
        r"deprecated:",
    ],
    "command": [
        # 명령어 실행 패턴
        r"^\s*\$\s+(.+)",
        r"^\s*>\s+(.+)",
        r"^\s*#\s+(.+)",
        r"Running:\s+(.+)",
        r"Executing:\s+(.+)",
        r"Executing command:\s+(.+)",
        r"shell:\s+(.+)",
        r"bash.*\$",
    ],
    "file_change": [
        # 파일 변경 패턴
        r"(create|created|write|wrote|new)\s+(\S+\.(?:py|js|ts|jsx|tsx|go|rs|java|cpp|c|h|md|json|yaml|yml|toml|xml|html|css|scss|sass|sql|sh|bash))",
        r"(modify|modified|update|updated|edit|edited)\s+(\S+\.(?:py|js|ts|jsx|tsx|go|rs|java|cpp|c|h|md|json|yaml|yml|toml|xml|html|css|scss|sass|sql|sh|bash))",
        r"(delete|deleted|remove|removed)\s+(\S+\.(?:py|js|ts|jsx|tsx|go|rs|java|cpp|c|h|md|json|yaml|yml|toml|xml|html|css|scss|sass|sql|sh|bash))",
        r"(Created|New)\s+(file|dir|folder):?\s*(\S+)",
        r"(Modified)\s+(file):?\s*(\S+)",
        r"(Deleted)\s+(file|dir):?\s*(\S+)",
    ],
    "success": [
        # 성공 키워드
        r"\bsuccess\b",
        r"\bSuccess\b",
        r"\bSUCCESS\b",
        r"\bsuccessfully\b",
        r"\bSuccessfully\b",
        r"\bdone\b",
        r"\bDone\b",
        r"\bcomplete\b",
        r"\bComplete\b",
        r"\bcompleted\b",
        r"\bCompleted\b",
        r"\bfinished\b",
        r"\bFinished\b",
        r"\bOK\b",
        r"\bok\b",
        r"\ball\s+good\b",
    ],
    "agent_message": [
        # AI 에이전트 메시지 패턴
        r"(Assistant|Claude|GPT|Gemini|Copilot):\s*",
        r"^(Human|User|You):\s*",
        r"^\[Agent\]\s*",
        r"^\[AI\]\s*",
        r"^\[Assistant\]\s*",
    ],
}


class UniversalWrapper:
    """
    범용 CLI 래퍼

    특정 CLI에 종속되지 않고, 모든 코딩 어시스턴트 CLI에
    범용으로 동작합니다.

    사용법:
        wrapper = UniversalWrapper.for_project()
        wrapper.run(["claude", "--no-input"])
    """

    # 기본 지원 CLI 목록
    DEFAULT_SUPPORTED_CLIS = {
        # 코딩 어시스턴트
        "claude", "claude-code", "claude-code-bin",
        "omp", "opencode", "opencode-cli",
        "aider", "aider-chat",
        "codex", "openai-codex",
        "cursor", "cursor-ai",
        "copilot", "github-copilot",
        "openai",
        # AI CLI 도구
        "llm", "llm-cli",
        "mistral", "mistral-cli",
        "gemini-cli",
        "ollama",  # 로컬 LLM CLI
        "llama", "llama-cli",
        # 기타 코딩 도우미
        "devin", "devin-cli",
        "swe-agent",
        "autogpt", "auto-gpt",
        "gptme",
        "continue",  # Continue.dev
        "zed",  # Zed AI
        "windsurf",
    }

    def __init__(
        self,
        project_root: str,
        on_event: Optional[Callable[[dict], None]] = None,
        supported_clis: Optional[set] = None,
    ):
        from ..core.manager import GeniusIntelligence
        from ..plan.tracker import PlanTracker

        self.project_root = Path(project_root).resolve()
        self.on_event_callback = on_event

        # 지원 CLI 목록 (사용자 지정 또는 기본값)
        self.supported_clis = supported_clis or self.DEFAULT_SUPPORTED_CLIS

        # GeniusIntelligence 연결
        self.genius = GeniusIntelligence.for_current_project(str(self.project_root))

        # 플랜 추적
        self.plan_tracker = PlanTracker(str(self.project_root), genius_instance=self.genius)
        self.plan_tracker.start_monitoring()

        # 상태
        self._running = False
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None

        # 버퍼
        self._output_buffer = ""
        self._last_event_time = time.time()

    @classmethod
    def for_project(cls, project_root: Optional[str] = None) -> "UniversalWrapper":
        """프로젝트용 래퍼 생성"""
        if project_root is None:
            from ..core.manager import GeniusIntelligence
            project_root = GeniusIntelligence.find_project_root() or os.getcwd()
        return cls(project_root)

    def run(self, args: list[str], **kwargs) -> int:
        """
        CLI 명령 실행 (지정된 CLI만 감싸기)

        Args:
            args: 실행할 명령 (예: ["claude", "--no-input"])

        Raises:
            ValueError: 지원되지 않는 CLI일 경우
        """
        if not args:
            raise ValueError("args cannot be empty")

        cmd = args[0]

        # 지원 CLI 체크
        if not self._is_supported_cli(cmd):
            print(f"[genius] Skipping: '{cmd}' is not in supported CLIs", file=sys.stderr)
            print(f"[genius] Supported: {', '.join(sorted(self.supported_clis))}", file=sys.stderr)
            print(f"[genius] Run directly without wrapping, or add it to config.", file=sys.stderr)
            # 지원되지 않으면 일반 명령으로 실행 (감싸지 않음)
            return subprocess.run(args, cwd=str(self.project_root)).returncode

        cmd_path = self._find_command(cmd)
        if cmd_path is None:
            cmd_path = cmd

        actual_args = [cmd_path] + list(args[1:])

        print(f"[genius] Running: {' '.join(shlex.quote(a) for a in actual_args)}", 
              file=sys.stderr)

        # 환경 변수
        env = os.environ.copy()
        env["GENIUS_INTELLIGENCE_ENABLED"] = "1"
        env["GENIUS_PROJECT_ROOT"] = str(self.project_root)

        try:
            # 실제 I/O 가로채기
            self._process = subprocess.Popen(
                actual_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=str(self.project_root),
                text=True,
                bufsize=1,  # 라인 버퍼링
            )

            self._running = True

            # 출력 리더 스레드 시작
            self._reader_thread = threading.Thread(
                target=self._read_output,
                args=(self._process.stdout, False),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._read_output,
                args=(self._process.stderr, True),
                daemon=True,
            )

            self._reader_thread.start()
            stderr_thread.start()

            # stdin 처리
            if self._process.stdin:
                self._handle_stdin(self._process.stdin)

            # 프로세스 종료 대기
            returncode = self._process.wait()

            # 중요: 프로세스가 빨리 끝나도, 파이프에 남아있는 마지막 출력을
            # 리더 스레드가 다 읽어서 화면에 전달할 시간을 반드시 줘야 합니다.
            # (여기서 join을 안 하면 마지막 몇 줄의 출력이 잘려서 사라질 수 있음)
            self._reader_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

            return returncode

        except FileNotFoundError:
            print(f"[genius] Error: Command not found: {cmd}", file=sys.stderr)
            return 127
        finally:
            self._running = False
            # 세션 플러시
            if self.genius:
                self.genius.flush()

    def _is_supported_cli(self, cmd: str) -> bool:
        """CLI가 지원 목록에 있는지 확인"""
        cmd_lower = cmd.lower()

        # 정확한 이름
        if cmd_lower in self.supported_clis:
            return True

        # 경로에서 명령 이름 추출
        if "/" in cmd or "\\" in cmd:
            import os
            basename = os.path.basename(cmd_lower)
            if basename in self.supported_clis:
                return True

        return False

    def _find_command(self, cmd: str) -> Optional[str]:
        """명령어 경로 찾기"""
        if os.path.isabs(cmd) and os.path.exists(cmd):
            return cmd

        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            full = os.path.join(path_dir, cmd)
            if os.path.isfile(full) and os.access(full, os.X_OK):
                return full
            for ext in [".exe", ".cmd", ".bat"]:
                if os.path.isfile(full + ext):
                    return full + ext
        return None

    def _read_output(self, stream, is_stderr: bool) -> None:
        """
        출력 스트림 읽기, 사용자 터미널로 즉시 전달(중요!), 그리고 이벤트 파싱

        주의: 감싸는 대상 CLI(claude, omp 등)의 실제 출력을 여기서 즉시
        원래 스트림(stdout/stderr)으로 그대로 흘려보내야 합니다. 그렇지 않으면
        사용자는 감싸인 도구의 응답을 전혀 볼 수 없게 되어(UniversalWrapper가
        출력을 삼켜버리는 상태) 실사용이 불가능해집니다. 이벤트 파싱/버퍼링은
        "부가 기능"이고, 출력 전달이 "핵심 기능"입니다.
        """
        out_stream = sys.stderr if is_stderr else sys.stdout

        for line in iter(stream.readline, ""):
            if not line:
                break

            # 1. 사용자에게 즉시 그대로 전달 (가장 중요)
            out_stream.write(line)
            out_stream.flush()

            # 2. 버퍼에 추가 (지식화용)
            self._output_buffer += line

            # 3. 범용 파싱 -> 이벤트 추출
            events = self._parse_line(line, is_stderr=is_stderr)

            for event in events:
                self._emit_event(event)

            # 버퍼 플러시 (너무 길어지면)
            if len(self._output_buffer) > 10000:
                self._output_buffer = self._output_buffer[-5000:]

    def _parse_line(self, line: str, is_stderr: bool) -> list[dict]:
        """
        범용 라인 파싱

        파서에 의존하지 않고, 범용 패턴으로 이벤트 추출
        """
        events = []
        line = line.strip()

        if not line:
            return events

        # 에러 감지
        if is_stderr or self._is_error_line(line):
            events.append({
                "type": "error",
                "content": line[:500],
                "raw": line[:1000],
                "timestamp": datetime.now().isoformat(),
            })
            return events

        # 명령어 감지
        for pattern in GENERIC_PATTERNS["command"]:
            match = re.search(pattern, line)
            if match:
                cmd = match.group(1) if match.groups() else line
                events.append({
                    "type": "command",
                    "content": cmd.strip(),
                    "timestamp": datetime.now().isoformat(),
                })
                break

        # 파일 변경 감지
        for pattern in GENERIC_PATTERNS["file_change"]:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # 파일명 추출
                groups = match.groups()
                filepath = groups[-1] if groups else line
                action = "modified"
                if any(kw in line.lower() for kw in ["create", "new", "wrote"]):
                    action = "created"
                elif any(kw in line.lower() for kw in ["delete", "remove"]):
                    action = "deleted"

                events.append({
                    "type": "file_change",
                    "action": action,
                    "path": filepath.strip(),
                    "raw": line[:500],
                    "timestamp": datetime.now().isoformat(),
                })
                break

        # 성공 감지
        for pattern in GENERIC_PATTERNS["success"]:
            if re.search(pattern, line):
                events.append({
                    "type": "success",
                    "content": line[:200],
                    "timestamp": datetime.now().isoformat(),
                })
                break

        return events

    def _is_error_line(self, line: str) -> bool:
        """에러 라인인지 판별"""
        line_lower = line.lower()

        # 에러 키워드 체크
        for pattern in GENERIC_PATTERNS["error"]:
            if re.search(pattern, line, re.IGNORECASE):
                return True

        # ANSI 색상 코드로 에러 표시 (빨간색)
        if "\\x1b[" in line and ("31m" in line or "[1;31m" in line or "[91m" in line):
            return True

        return False

    def _handle_stdin(self, stdin) -> None:
        """stdin 처리"""
        while self._running and self._process and self._process.poll() is None:
            try:
                # 논블로킹 입력 체크
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    line = sys.stdin.readline()
                    if not line:
                        break

                    stdin.write(line)
                    stdin.flush()

                    # 사용자 입력 추적
                    self._emit_event({
                        "type": "user_input",
                        "content": line.strip(),
                        "timestamp": datetime.now().isoformat(),
                    })

                    if self.genius:
                        self.genius.on_user_message(line.strip())

            except (EOFError, BrokenPipeError, OSError):
                break
            except KeyboardInterrupt:
                self._handle_interrupt()
                break

    def _handle_interrupt(self) -> None:
        """SIGINT 처리"""
        print("\\n[genius] Interrupted, flushing session...", file=sys.stderr)
        if self._process:
            self._process.send_signal(signal.SIGINT)

    def _emit_event(self, event: dict) -> None:
        """이벤트 방출"""
        # 콜백이 있으면 호출
        if self.on_event_callback:
            self.on_event_callback(event)

        # GeniusIntelligence에 전달
        if self.genius:
            self._forward_to_genius(event)

        # 디버그 출력
        if os.environ.get("GENIUS_DEBUG"):
            print(f"[genius:event] {event}", file=sys.stderr)

    def _forward_to_genius(self, event: dict) -> None:
        """이벤트를 GeniusIntelligence에 전달"""
        if not self.genius or not self.genius.current_session:
            return

        etype = event.get("type", "")

        if etype == "error":
            self.genius.on_error_occurred(
                event.get("content", ""),
                stack_trace=event.get("raw", ""),
            )
            # 플랜 추적에도 전달
            self.plan_tracker.on_error(event.get("content", ""))
        elif etype == "command":
            self.genius.on_command_executed(
                event.get("content", ""),
                success=True,
            )
            # 플랜 추적에도 전달
            self.plan_tracker.on_command_executed(event.get("content", ""))
        elif etype == "file_change":
            action = event.get("action", "")
            path = event.get("path", "")
            if action == "created":
                self.genius.on_file_created(path)
                self.plan_tracker.on_file_created(path)
            else:
                self.genius.on_file_modified(path)
                self.plan_tracker.on_file_modified(path)
        elif etype == "success":
            self.genius.on_assistant_message(event.get("content", ""))
        elif etype == "user_input":
            pass  # 이미 on_user_message에서 처리됨

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._running = False
        if self._process and self._process.poll() is None:
            self._process.terminate()
        if self.genius:
            self.genius.flush()

"""
UniversalWrapper CLI Entry Point
================================

사용법:
    python -m genius_intelligence.auto.universal claude --no-input
    python -m genius_intelligence.auto.universal omp
    python -m genius_intelligence.auto.universal any-unknown-cli

이 모듈은 파서에 의존하지 않고, 범용 패턴 매칭으로
어떤 CLI든 자동 감시합니다.
"""

import sys
from pathlib import Path


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Genius Intelligence UniversalWrapper",
        prog="python -m genius_intelligence.auto.universal",
    )
    parser.add_argument("cli", help="CLI tool to wrap")
    parser.add_argument("args", nargs="*", help="CLI arguments")
    parser.add_argument("--force", "-f", action="store_true", 
                       help="Force wrap even if CLI is not in default list")
    parser.add_argument("--add-cli", dest="add_cli", action="append",
                       help="Add CLI to supported list")

    args = parser.parse_args()

    # UniversalWrapper 사용
    from .universal import UniversalWrapper
    from ..core.manager import GeniusIntelligence
    # 프로젝트 루트 감지
    project_root = GeniusIntelligence.find_project_root()
    if project_root is None:
        project_root = Path.cwd()

    # 지원 CLI 목록 구성
    supported = None
    if args.add_cli:
        supported = UniversalWrapper.DEFAULT_SUPPORTED_CLIS | set(args.add_cli)
    elif not args.force:
        supported = UniversalWrapper.DEFAULT_SUPPORTED_CLIS

    wrapper = UniversalWrapper(project_root, supported_clis=supported)

    # 실행
    try:
        returncode = wrapper.run([args.cli] + args.args)
        sys.exit(returncode)
    except KeyboardInterrupt:
        print("\n[genius] Interrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
