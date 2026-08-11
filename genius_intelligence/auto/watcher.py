"""
AutoWatcher
===========
백그라운드에서 자동으로 CLI 세션을 감시하는 모듈

1. CLI 프로세스 출력 스트림 리다이렉션
2. 파일 시스템 감시 (inotify/FSEvents)
3. 로그 파일 파싱
4. 환경 변수/프로세스 감지
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("genius_intelligence")




def create_watcher(project_root: Optional[str] = None) -> AutoWatcher:
    """AutoWatcher 팩토리 함수"""
    if project_root is None:
        project_root = os.getcwd()
    return AutoWatcher(project_root)


class AutoWatcher:
    """
    자동 감시管理器

    백그라운드에서 코딩 어시스턴트 CLI의 활동을 감시하고
    GeniusIntelligence에 자동으로 이벤트를 전달합니다.

    사용법:
        watcher = AutoWatcher.for_current_project()
        watcher.start()
        # 이제 백그라운드에서 자동으로 모든 CLI 활동 추적
        # ...
        watcher.stop()
    """

    def __init__(
        self,
        project_root: str,
        genius_instance=None,
        poll_interval: float = 0.5,
    ):
        from ..core.manager import GeniusIntelligence

        self.project_root = Path(project_root).resolve()
        self.genius = genius_instance or GeniusIntelligence.for_current_project(str(self.project_root))
        self.poll_interval = poll_interval

        # 감시 대상
        self._watched_process: Optional[subprocess.Popen] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._running = False
        self._parsers: dict[str, OutputParser] = {}

        # 파일 감시 (마지막 확인 시간)
        self._last_file_check = time.time()

        # 현재 감지된 CLI 도구
        self._detected_cli: Optional[str] = None

        # 콜백
        self._event_callbacks: list[Callable] = []

    @classmethod
    def for_current_project(cls, project_root: Optional[str] = None) -> "AutoWatcher":
        """현재 프로젝트용 감시기 생성"""
        from ..core.manager import GeniusIntelligence

        if project_root is None:
            project_root = GeniusIntelligence.find_project_root() or os.getcwd()

        return cls(project_root)

    @classmethod
    def auto_start(cls) -> Optional["AutoWatcher"]:
        """
        자동으로 감시 시작

        현재 실행 중인 코딩 어시스턴트 CLI가 있으면
        감시자를 시작하고 해당 프로세스에 연결합니다.
        """
        cli_tool = cls.detect_running_cli()
        if cli_tool is None:
            logger.info("[AutoWatcher] No coding assistant CLI detected")
            return None

        project_root = cls.detect_project_from_cli(cli_tool)
        if project_root is None:
            project_root = os.getcwd()

        watcher = cls(project_root)
        watcher._detected_cli = cli_tool

        # 연결 가능한 경우 프로세스에 연결
        if watcher._attach_to_process(cli_tool):
            watcher.start()
            logger.info(f"[AutoWatcher] Attached to {cli_tool}")
        else:
            # 프로세스에 연결할 수 없으면 폴링 모드로 시작
            watcher.start()
            logger.info(f"[AutoWatcher] Started in polling mode for {cli_tool}")

        return watcher

    # ── CLI 탐지 ────────────────────────────────────────────────────

    @staticmethod
    def detect_running_cli() -> Optional[str]:
        """현재 실행 중인 코딩 어시스턴트 CLI 탐지"""
        import psutil

        cli_markers = {
            "claude": ["claude-code", "claude-code-bin"],
            "omp": ["omp"],
            "opencode": ["opencode"],
            "codex": ["codex", "openai-codex"],
            "aider": ["aider"],
            "cursor": ["cursor"],
            "copilot": ["github-copilot"],
        }

        try:
            current_proc = psutil.Process()

            # 현재 프로세스와 부모 프로세스 탐색
            for proc in [current_proc] + current_proc.parents() + current_proc.children(recursive=True):
                try:
                    name = proc.name().lower()
                    cmdline = " ".join(proc.cmdline()).lower()

                    for cli_name, markers in cli_markers.items():
                        for marker in markers:
                            if marker in name or marker in cmdline:
                                return cli_name
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            pass

        # 환경 변수 기반 탐지
        env_markers = {
            "CLAUDE_API_KEY": "claude",
            "OMP_CLI": "omp",
            "OPENCODE_CLI": "opencode",
        }

        for env, cli in env_markers.items():
            if os.environ.get(env):
                return cli

        return None

    @staticmethod
    def detect_project_from_cli(cli_tool: str) -> Optional[str]:
        """CLI 도구에서 프로젝트 경로 추출"""
        from ..core.manager import GeniusIntelligence
        return GeniusIntelligence.find_project_root()

    def _attach_to_process(self, cli_tool: str) -> bool:
        """실행 중인 프로세스에 연결 시도"""
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
                try:
                    name = proc.info["name"].lower()
                    cmdline = " ".join(proc.info["cmdline"] or []).lower()

                    if cli_tool in name or cli_tool in cmdline:
                        self._watched_process = psutil.Process(proc.info["pid"])

                        # 작업 디렉토리 설정
                        try:
                            self.project_root = Path(proc.info["cwd"]).resolve()
                        except Exception:
                            pass

                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            pass

        return False

    # ── 백그라운드 감시 ─────────────────────────────────────────────

    def start(self) -> None:
        """감시 시작"""
        if self._running:
            return

        self._running = True
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

        # 자동 정리 스케줄러 시작
        if self.genius:
            self.genius.cleaner.start()

        logger.info(f"[AutoWatcher] Started in {self.project_root}")

    def stop(self) -> None:
        """감시 중지"""
        self._running = False

        if self._watch_thread:
            self._watch_thread.join(timeout=2)
            self._watch_thread = None

        # 세션 플러시
        if self.genius:
            self.genius.flush()
            self.genius.cleaner.stop()

        logger.info("[AutoWatcher] Stopped")

    def _watch_loop(self) -> None:
        """감시 루프"""
        while self._running:
            try:
                self._poll_events()
                self._poll_files()
                self._poll_environment()
            except Exception as e:
                logger.error(f"[AutoWatcher] Poll error: {e}")

            time.sleep(self.poll_interval)

    def _poll_events(self) -> None:
        """이벤트 폴링"""
        if self._watched_process is None:
            return

        try:
            # 프로세스 출력 감시 (stdout/stderr 파이프)
            proc = self._watched_process

            # 종료된 프로세스 체크
            if not proc.is_running():
                self._on_cli_exit()
                return

            # stderr/stdout 읽기
            try:
                conn = proc.connection_info()
                if conn.get("stdout"):
                    # stdout에서 데이터 읽기
                    pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self._watched_process = None

    def _poll_files(self) -> None:
        """파일 시스템 폴링"""
        # 프로젝트 내 .md, .py, .js 등 주요 파일 변경 감시
        if not self.genius or not self.genius.current_session:
            return

        # 마지막 체크 이후 수정된 파일 탐색
        project_files = list(self.project_root.rglob("*.py"))[:100]  # 샘플링

        for f in project_files:
            try:
                mtime = f.stat().st_mtime
                if mtime > self._last_file_check:
                    rel_path = f.relative_to(self.project_root)
                    self.genius.on_file_modified(str(rel_path))
            except OSError:
                continue

        self._last_file_check = time.time()

    def _poll_environment(self) -> None:
        """환경 변수/상태 폴링"""
        # 새로운 CLI 감지
        current_cli = self.detect_running_cli()

        if current_cli and current_cli != self._detected_cli:
            logger.info(f"[AutoWatcher] CLI changed: {self._detected_cli} -> {current_cli}")
            self._detected_cli = current_cli

            # 새 CLI에 대한 파서 설정
            self._setup_parser(current_cli)

    def _on_cli_exit(self) -> None:
        """CLI 종료 핸들러"""
        logger.info("[AutoWatcher] CLI process exited")

        # 플러시
        if self.genius:
            self.genius.flush()

        # 연결 해제
        self._watched_process = None

    def _setup_parser(self, cli_tool: str) -> None:
        """CLI 도구용 파서 설정"""
        from .parser import get_parser_for_tool

        parser = get_parser_for_tool(cli_tool)
        if parser:
            self._parsers[cli_tool] = parser

    # ── 외부 이벤트 주입 ───────────────────────────────────────────

    def on_output(self, output: str, is_error: bool = False) -> None:
        """CLI 출력을 파싱하여 이벤트 추출"""
        if not self.genius:
            return

        cli_tool = self._detected_cli or "generic"

        if cli_tool in self._parsers:
            events = self._parsers[cli_tool].parse(output, is_error=is_error)
        else:
            # 범용 파서
            events = self._parse_generic(output, is_error=is_error)

        for event in events:
            self._dispatch_event(event)

    def on_input(self, text: str) -> None:
        """사용자 입력을 이벤트로 처리"""
        if self.genius:
            self.genius.on_user_message(text)

    def _parse_generic(self, text: str, is_error: bool) -> list[dict]:
        """범용 출력 파싱"""
        events = []

        if is_error:
            # 에러 패턴 감지
            error_patterns = [
                r"Error:\s*(.+)",
                r"error:\s*(.+)",
                r"Error\s+\d+:\s*(.+)",
                r"Traceback\s+\(most recent call last\):",
                r"Exception:\s*(.+)",
            ]

            for pattern in error_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    events.append({
                        "type": "error",
                        "content": match.group(1) if match.groups() else text[:200],
                        "raw": text[:500],
                    })
                    break

            if not events:
                events.append({"type": "error", "content": text[:200], "raw": text[:500]})
        else:
            # 일반 출력 - 명령어/파일 생성 패턴
            cmd_patterns = [
                r"Running:\s*(.+)",
                r"Executing:\s*(.+)",
                r"Command:\s*(.+)",
                r"\$ (.+)",
            ]

            for pattern in cmd_patterns:
                match = re.search(pattern, text)
                if match:
                    events.append({
                        "type": "command",
                        "content": match.group(1),
                        "success": True,
                    })
                    break

        return events

    def _dispatch_event(self, event: dict) -> None:
        """이벤트를 GeniusIntelligence에 전달"""
        if not self.genius:
            return

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
                output=event.get("output", ""),
            )
        elif event_type == "message":
            self.genius.on_assistant_message(event.get("content", ""))
        elif event_type == "file_created":
            self.genius.on_file_created(event.get("path", ""))
        elif event_type == "file_modified":
            self.genius.on_file_modified(event.get("path", ""))

    def register_callback(self, callback: Callable) -> None:
        """이벤트 콜백 등록"""
        self._event_callbacks.append(callback)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()