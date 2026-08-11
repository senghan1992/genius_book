"""
AgentWrapper
============
코딩 어시스턴트 CLI를 투명하게 감싸는 모듈

사용자가 일반적으로 CLI를 실행하면 자동으로:
1. 백그라운드 감시 시작
2. 출력 파싱 및 이벤트 추출
3. 세션 종료 시 지식화

사용법:
    # 1. 코드에서 사용
    wrapper = AgentWrapper.for_current_project()
    wrapper.run(["claude"])  # claude를 투명하게 실행

    # 2. CLI에서 사용
    # $ genius run claude
    # $ genius run omp --project .
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from .watcher import AutoWatcher
from .parser import get_parser_for_tool


class AgentWrapper:
    """
    코딩 어시스턴트 CLI 래퍼

    실행 중인 CLI의 출력을 실시간으로 파싱하여
    GeniusIntelligence에 자동으로 이벤트를 전달합니다.

    사용법:
        wrapper = AgentWrapper.for_current_project()
        wrapper.run(["claude", "--no-input"])
    """

    def __init__(
        self,
        project_root: str,
        cli_tool: Optional[str] = None,
        auto_watch: bool = True,
    ):
        from ..core.manager import GeniusIntelligence

        self.project_root = Path(project_root).resolve()
        self.cli_tool = cli_tool or AutoWatcher.detect_running_cli() or "claude"
        self.auto_watch = auto_watch

        # GeniusIntelligence
        self.genius = GeniusIntelligence.for_current_project(str(self.project_root))

        # 백그라운드 감시
        self.watcher: Optional[AutoWatcher] = None

        # 프로세스
        self.process: Optional[subprocess.Popen] = None

        # 이벤트 버퍼
        self._event_buffer: list[dict] = []
        self._buffer_lock = threading.Lock()

    @classmethod
    def for_current_project(cls, cli_tool: Optional[str] = None) -> "AgentWrapper":
        """현재 프로젝트용 래퍼 생성"""
        from ..core.manager import GeniusIntelligence

        project_root = GeniusIntelligence.find_project_root() or os.getcwd()
        return cls(project_root, cli_tool=cli_tool)

    @classmethod
    def auto_detect(cls) -> Optional["AgentWrapper"]:
        """자동 탐지 후 래퍼 생성"""
        cli_tool = AutoWatcher.detect_running_cli()
        if cli_tool is None:
            return None
        return cls.for_current_project(cli_tool=cli_tool)

    # ── CLI 실행 ───────────────────────────────────────────────────

    def run(self, args: list[str], **kwargs) -> int:
        """
        CLI 명령 실행

        Args:
            args: 실행할 명령 (예: ["claude", "--no-input"])
            **kwargs: subprocess.run 인자

        Returns:
            종료 코드
        """
        if not args:
            args = [self.cli_tool]

        # 첫 인자가 CLI 도구 이름인지 확인
        cmd = args[0]

        # 절대 경로 또는 PATH에서 찾기
        cmd_path = self._find_command(cmd)
        if cmd_path is None:
            # PATH에 없으면 직접 실행 시도
            cmd_path = cmd

        actual_args = [cmd_path] + list(args[1:])

        print(f"[genius] Running: {' '.join(shlex.quote(a) for a in actual_args)}", 
              file=sys.stderr)

        # 환경 변수 설정
        env = os.environ.copy()
        env["GENIUS_INTELLIGENCE_ENABLED"] = "1"
        env["GENIUS_PROJECT_ROOT"] = str(self.project_root)

        # 출력 캡처 모드
        capture = kwargs.pop("capture_output", True)

        try:
            # Popen으로 실행 (출력 실시간 캡처)
            self.process = subprocess.Popen(
                actual_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if not sys.stdin.isatty() else None,
                env=env,
                cwd=str(self.project_root),
                text=True,
                bufsize=1,
            )

            # 백그라운드 감시 시작
            if self.auto_watch:
                self._start_watching()

            # 출력 읽기 스레드
            stdout_thread = threading.Thread(
                target=self._read_stdout,
                args=(self.process.stdout,),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._read_stderr,
                args=(self.process.stderr,),
                daemon=True,
            )

            stdout_thread.start()
            stderr_thread.start()

            # 메인 스레드에서 stdin 처리
            if self.process.stdin:
                self._handle_stdin(self.process.stdin)

            # 프로세스 종료 대기
            returncode = self.process.wait()

            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)

            return returncode

        except FileNotFoundError:
            print(f"[genius] Error: Command not found: {cmd}", file=sys.stderr)
            print(f"[genius] Try installing {self.cli_tool} or specify path", file=sys.stderr)
            return 127

    def _find_command(self, cmd: str) -> Optional[str]:
        """명령어 경로 찾기"""
        # 절대 경로
        if os.path.isabs(cmd) and os.path.exists(cmd):
            return cmd

        # PATH에서 검색
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            full_path = os.path.join(path_dir, cmd)
            if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                return full_path

            # Windows 확장자
            for ext in [".exe", ".cmd", ".bat"]:
                full_path_ext = full_path + ext
                if os.path.isfile(full_path_ext):
                    return full_path_ext

        return None

    def _read_stdout(self, stdout) -> None:
        """stdout 읽기"""
        parser = get_parser_for_tool(self.cli_tool)

        for line in iter(stdout.readline, ""):
            if not line:
                break

            # 파서로 처리
            events = parser.parse(line, is_error=False)
            for event in events:
                self._handle_event(event)

            # 원본 출력
            sys.stdout.write(line)
            sys.stdout.flush()

    def _read_stderr(self, stderr) -> None:
        """stderr 읽기"""
        parser = get_parser_for_tool(self.cli_tool)

        for line in iter(stderr.readline, ""):
            if not line:
                break

            # 에러로 처리
            events = parser.parse(line, is_error=True)
            for event in events:
                self._handle_event(event)

            # 원본 출력
            sys.stderr.write(line)
            sys.stderr.flush()

    def _handle_stdin(self, stdin) -> None:
        """stdin 처리"""
        while True:
            try:
                line = input()
                stdin.write(line + "\n")
                stdin.flush()

                # 사용자 입력도 추적
                self.genius.on_user_message(line)

            except EOFError:
                break
            except KeyboardInterrupt:
                break

    def _handle_event(self, event: dict) -> None:
        """이벤트 처리"""
        with self._buffer_lock:
            self._event_buffer.append(event)

        event_type = event.get("type", "")

        if event_type == "error":
            self.genius.on_error_occurred(
                event.get("content", ""),
                stack_trace=event.get("raw", ""),
            )
        elif event_type == "command":
            self.genius.on_command_executed(
                event.get("content", ""),
                success=event.get("success", True),
            )
        elif event_type == "file_changed":
            path = event.get("path", "")
            action = event.get("action", "")
            if "create" in action:
                self.genius.on_file_created(path)
            else:
                self.genius.on_file_modified(path)
        elif event_type == "success":
            self.genius.on_assistant_message(event.get("content", ""))

    def _start_watching(self) -> None:
        """백그라운드 감시 시작"""
        self.watcher = AutoWatcher(
            str(self.project_root),
            genius_instance=self.genius,
        )
        self.watcher._detected_cli = self.cli_tool
        self.watcher.start()

    def _stop_watching(self) -> None:
        """백그라운드 감시 중지"""
        if self.watcher:
            self.watcher.stop()
            self.watcher = None

        # 세션 플러시
        self.genius.flush()

    # ── 컨텍스트 매니저 ───────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_watching()


def wrap_cli(
    args: list[str],
    project_root: Optional[str] = None,
) -> int:
    """
    CLI 명령 투명하게 실행

    사용법:
        # Python
        wrap_cli(["claude", "--no-input"])

        # Shell
        # $ python -m genius_intelligence.auto wrap claude
    """
    from ..core.manager import GeniusIntelligence

    if project_root is None:
        project_root = GeniusIntelligence.find_project_root() or os.getcwd()

    wrapper = AgentWrapper(project_root)

    try:
        return wrapper.run(args)
    finally:
        wrapper._stop_watching()