"""
GeniusIntelligence Manager
==========================
라이브러리의 중앙 조정자

코딩 어시스턴트 CLI의 각 후크에 연결되어:
1. 프로젝트 자동 감지
2. 세션 모니터링
3. 지식화 루프 실행
4. 자동 정리 스케줄링
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from ..types.knowledge import (
    KnowledgeNode, KnowledgeGraph, KnowledgeType, KnowledgeStatus, KnowledgeDomain
)
from ..types.session import (
    CodingSession, AttemptRecord, SessionEvent, EventType
)
from ..types.config import GeniusConfig
from ..memory.db import MemoryDB, get_memory_db
from ..knowledge.store import KnowledgeStore, create_knowledge_store
from ..scheduler.cleaner import AutoCleaner
from ..plan.tracker import PlanTracker

if TYPE_CHECKING:
    pass


logger = logging.getLogger("genius_intelligence")


class GeniusIntelligence:
    """
    코딩 어시스턴트용 프로젝트 단위 지식화 라이브러리

    사용법:

    1) 라이브러리로 직접 사용:
        genius = GeniusIntelligence.for_current_project()
        genius.on_user_message("POST /api/users API 만들어줘")
        genius.on_assistant_message("API를 생성했습니다...")
        genius.on_command_executed("npm install", success=True)
        genius.on_error_occurred("Error: Cannot find module...")
        genius.flush()  # 세션 종료 시

    2) 후크 시스템:
        hooks = genius.get_hooks()  # 딕셔너리 반환
        # hooks["on_message"] = your_handler

    3) 자동 감지:
        genius = GeniusIntelligence.auto_detect()  # 프로젝트 자동 탐색
    """

    def __init__(
        self,
        project_root: str,
        config: GeniusConfig | None = None,
        auto_init: bool = True,
    ):
        self.project_root = str(Path(project_root).resolve())
        self.config = config or GeniusConfig.load(self.project_root)
        self.config.project_root = self.project_root
        self.config.genius_root = str(Path(self.project_root) / self.config.genius_dir_name)

        # 컴포넌트
        self.db: MemoryDB = get_memory_db(self.project_root, self.config)
        self.store: KnowledgeStore = create_knowledge_store(self.project_root, self.config)
        self.graph: KnowledgeGraph = self.db.load_all_nodes()
        self.cleaner: AutoCleaner = AutoCleaner(self)

        # 세션 상태
        self.current_session: Optional[CodingSession] = None
        self._cli_tool: str = self._detect_cli_tool()
        self._initialized: bool = False
        self._pending_knowledgeize: list[AttemptRecord] = []

        if auto_init:
            self._initialize()

    # ── 팩토리 ────────────────────────────────────────────────────────

    @classmethod
    def for_current_project(
        cls,
        project_root: str | None = None,
        auto_init: bool = True,
    ) -> "GeniusIntelligence":
        """현재 프로젝트용 인스턴스 생성"""
        if project_root is None:
            project_root = cls.find_project_root()
        return cls(project_root, auto_init=auto_init)

    @classmethod
    def auto_detect(cls) -> "GeniusIntelligence | None":
        """자동 프로젝트 감지"""
        project_root = cls.find_project_root()
        if project_root:
            return cls.for_current_project(project_root)
        return None

    @staticmethod
    def find_project_root(start: str | None = None) -> str | None:
        """git 루트 또는 프로젝트 루트 탐색"""
        if start is None:
            start = os.getcwd()

        current = Path(start).resolve()
        markers = [
            ".git",
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "Cargo.toml",
            "go.mod",
            "pom.xml",
            "Makefile",
            ".claude",
            ".cursor",
            ".vscode",
        ]

        while True:
            for marker in markers:
                if (current / marker).exists():
                    return str(current)
            parent = current.parent
            if parent == current:
                break
            current = parent

        return str(Path(start).resolve())

    # ── 초기화 ────────────────────────────────────────────────────────

    def _initialize(self) -> None:
        """초기화"""
        if self._initialized:
            return

        # 디렉토리 구조 생성
        self._ensure_genius_structure()

        # 설정 저장
        self.config.save()

        # 세션 시작
        self._start_session()

        self._initialized = True
        logger.info(f"[GeniusIntelligence] Initialized at: {self.project_root}")

    def _ensure_genius_structure(self) -> None:
        """디렉토리 구조 생성"""
        Path(self.config.genius_root).mkdir(parents=True, exist_ok=True)
        Path(self.config.genius_root, "knowledge_graph", "etc").mkdir(
            parents=True, exist_ok=True
        )
        Path(self.config.genius_root, "login_information").mkdir(
            parents=True, exist_ok=True
        )
        Path(self.config.genius_root, ".config").mkdir(parents=True, exist_ok=True)

    def _start_session(self) -> None:
        """새 세션 시작"""
        self.current_session = CodingSession(
            project_path=self.project_root,
            cli_tool=self._cli_tool,
        )

    def _detect_cli_tool(self) -> str:
        """현재 CLI 도구 감지"""
        # 환경 변수 기반 감지
        env_markers = {
            "CLAUDE_CLI": "claude",
            "OMP_CLI": "omp",
            "OPENCODE_CLI": "opencode",
            "AIDER_CLIENT": "aider",
        }

        for env, tool in env_markers.items():
            if os.environ.get(env):
                return tool

        # 부모 프로세스 이름 기반
        try:
            import psutil
            parent = psutil.Process().parent()
            if parent:
                name = parent.name().lower()
                for tool in self.config.supported_cli_tools:
                    if tool in name:
                        return tool
        except ImportError:
            pass

        # sys.argv 기반
        for arg in sys.argv:
            for tool in self.config.supported_cli_tools:
                if tool in arg.lower():
                    return tool

        return "unknown"

    # ── 세션 이벤트 ──────────────────────────────────────────────────

    def on_user_message(
        self,
        message: str,
        current_file: str = "",
        metadata: dict | None = None,
    ) -> None:
        """사용자 메시지 이벤트"""
        if not self.current_session:
            self._start_session()

        event = SessionEvent(
            event_type=EventType.USER_MESSAGE,
            content=message[:500],
            current_file=current_file,
            current_directory=os.getcwd(),
            event_metadata=metadata or {},
        )

        self.current_session.add_event(event)

        # 태스크 시도 추적 시작 (첫 메시지에서 태스크 ID 추출)
        task_id = self._extract_task_id(message)
        if task_id:
            self.current_session.track_attempt(task_id, message[:100])

    def on_assistant_message(
        self,
        message: str,
        current_file: str = "",
        metadata: dict | None = None,
    ) -> None:
        """AI 응답 이벤트"""
        if not self.current_session:
            return

        event = SessionEvent(
            event_type=EventType.ASSISTANT_MESSAGE,
            content=message[:1000],
            current_file=current_file,
            current_directory=os.getcwd(),
            event_metadata=metadata or {},
        )

        self.current_session.add_event(event)

        # 최근 사용자 메시지에서 태스크 ID 추출
        user_events = [
            e for e in self.current_session.events[-5:]
            if e.event_type == EventType.USER_MESSAGE
        ]
        if user_events:
            task_id = self._extract_task_id(user_events[-1].content)
            if task_id and task_id in self.current_session.active_tasks:
                record = self.current_session.active_tasks[task_id]
                # 응답에서 해결 여부 판단
                if any(ok in message.lower() for ok in ["완료", "success", "done", "created", "implemented"]):
                    record.mark_success(message[:500])

    def on_command_executed(
        self,
        command: str,
        success: bool = True,
        output: str = "",
        error: str = "",
        current_file: str = "",
    ) -> None:
        """명령어 실행 결과"""
        if not self.current_session:
            return

        event_type = EventType.COMMAND
        if not success:
            event_type = EventType.COMMAND_FAILED

        event = SessionEvent(
            event_type=event_type,
            content=command,
            current_file=current_file,
            event_metadata={"output": output[:200], "error": error[:200]},
        )

        self.current_session.add_event(event)

        # 에러 추적
        if error:
            self.on_error_occurred(error, command=command)

        # 태스크 레코드 업데이트
        user_events = [
            e for e in self.current_session.events[-3:]
            if e.event_type == EventType.USER_MESSAGE
        ]
        if user_events:
            task_id = self._extract_task_id(user_events[-1].content)
            if task_id and task_id in self.current_session.active_tasks:
                record = self.current_session.active_tasks[task_id]
                if not success:
                    record.mark_failure(error[:200])

    def on_error_occurred(
        self,
        error_message: str,
        command: str = "",
        current_file: str = "",
        stack_trace: str = "",
    ) -> None:
        """에러 발생 이벤트"""
        if not self.current_session:
            return

        event = SessionEvent(
            event_type=EventType.ERROR_OCCURRED,
            content=error_message[:500],
            current_file=current_file,
            event_metadata={
                "command": command,
                "stack_trace": stack_trace[:500],
            },
        )

        self.current_session.add_event(event)
        self.current_session.total_errors += 1

        # 태스크 레코드 업데이트
        user_events = [
            e for e in self.current_session.events[-3:]
            if e.event_type == EventType.USER_MESSAGE
        ]
        if user_events:
            task_id = self._extract_task_id(user_events[-1].content)
            if task_id and task_id in self.current_session.active_tasks:
                record = self.current_session.active_tasks[task_id]
                record.mark_failure(error_message[:200])
                record.error_traces.append(stack_trace[:300])

    def on_file_created(self, file_path: str, content: str = "") -> None:
        """파일 생성 이벤트"""
        if not self.current_session:
            return
        event = SessionEvent(
            event_type=EventType.FILE_CREATED,
            content=file_path,
            current_file=file_path,
            event_metadata={"size": len(content)},
        )
        self.current_session.add_event(event)

    def on_file_modified(self, file_path: str, change_summary: str = "") -> None:
        """파일 수정 이벤트"""
        if not self.current_session:
            return
        event = SessionEvent(
            event_type=EventType.FILE_MODIFIED,
            content=file_path,
            current_file=file_path,
            event_metadata={"change": change_summary[:100]},
        )
        self.current_session.add_event(event)

    def on_user_correction(self, correction: str, original_attempt: str = "") -> None:
        """사용자 수정 이벤트"""
        if not self.current_session:
            return

        event = SessionEvent(
            event_type=EventType.USER_CORRECTION,
            content=correction,
            event_metadata={"original": original_attempt[:200]},
        )
        self.current_session.add_event(event)

        # 수정 횟수 추적
        user_events = [
            e for e in self.current_session.events[-5:]
            if e.event_type == EventType.USER_MESSAGE
        ]
        if user_events:
            task_id = self._extract_task_id(user_events[-1].content)
            if task_id and task_id in self.current_session.active_tasks:
                record = self.current_session.active_tasks[task_id]
                record.add_attempt(error=f"User correction: {correction[:100]}")

    def on_login_request(
        self,
        service: str,
        description: str,
        fields: dict,
    ) -> Optional[bool]:
        """
        로그인 정보 요청 이벤트

        Returns:
            True: 사용자 승인 → 저장
            False: 사용자 거부
            None: 자동 모드 → 저장 안 함
        """
        if not self.config.enable_login_tracking:
            return None

        event = SessionEvent(
            event_type=EventType.LOGIN_REQUEST,
            content=f"{service}: {description}",
            event_metadata={"service": service, "fields": list(fields.keys())},
        )

        self.current_session.add_event(event)

        # 사용자 승인 여부 확인
        if self.config.ask_before_login_save:
            # 여기서는 None 반환 (실제 CLI에서 사용자에게 물어봄)
            return None

        # 자동 저장
        return self._save_login_info(service, description, fields)

    def _save_login_info(
        self,
        service: str,
        description: str,
        fields: dict,
    ) -> bool:
        """로그인 정보 저장"""
        try:
            file_path, authorized = self.store.save_login_info(
                service, fields, description
            )
            self.db.save_login_info(
                service, description, fields, authorized, file_path
            )

            if self.current_session:
                event = SessionEvent(
                    event_type=EventType.LOGIN_INFO_STORED,
                    content=f"Login info stored: {service}",
                    event_metadata={"service": service, "file": file_path},
                )
                self.current_session.add_event(event)

            return authorized
        except Exception as e:
            logger.error(f"Failed to save login info: {e}")
            return False

    # ── 지식 검색 ────────────────────────────────────────────────────

    def search_knowledge(
        self,
        query: str,
        limit: int = 5,
    ) -> list[KnowledgeNode]:
        """
        지식 검색

        쿼리와 관련된 저장된 지식 노드를 반환합니다.
        접근 시 last_accessed_at이 갱신됩니다.
        """
        results = self.graph.find_similar(query, limit=limit)

        # 접근 시간 업데이트
        for node in results:
            self.graph.mark_access(node.node_key)
            self.db.touch_node(node.node_key)

        return results

    def suggest_knowledge(self, message: str) -> list[str]:
        """
        현재 메시지와 관련된 지식 파일 경로 제안

        Returns:
            관련 .md 파일 경로 목록
        """
        nodes = self.search_knowledge(message, limit=3)
        return [self.project_root + "/" + self.config.genius_dir_name + "/" + n.file_path
                for n in nodes if n.file_path]

    # ── 지식화 루프 ──────────────────────────────────────────────────

    def knowledgeize(
        self,
        attempt_record: AttemptRecord,
        force: bool = False,
    ) -> Optional[KnowledgeNode]:
        """
        AttemptRecord를 기반으로 지식 노드 생성 및 저장

        조건:
        - force=True 이거나
        - attempt_record.should_knowledgeize=True (3회 이상 시도 또는 반복 실패)
        """
        if not force and not attempt_record.should_knowledgeize:
            return None

        # 이미 지식화된 것인지 확인
        task_key = self._extract_task_id(attempt_record.task_description)
        existing = self.graph.find_node("etc", task_key) if task_key else None
        if existing and not force:
            return None

        # 도메인 자동 감지
        domain = KnowledgeDomain.detect_domain(
            attempt_record.task_description,
            self.config.custom_domains,
        )

        # 토픽 추출
        topic = self._extract_topic(attempt_record.task_description)

        # 실패 여부 판단
        is_failure = (
            attempt_record.final_status == "failed" or
            attempt_record.failures > 0
        )

        # KnowledgeNode 생성
        node = KnowledgeNode(
            name=topic or attempt_record.task_description[:50],
            domain=domain if not is_failure else "etc",
            topic=topic,
            depth=2 if topic else 1,
            knowledge_type=(
                KnowledgeType.FAILURE if is_failure
                else KnowledgeType.SUCCESS
            ),
            raw_input=attempt_record.task_description,
            solution=attempt_record.solution,
            error_trace="\n".join(attempt_record.error_traces[:3]),
            attempt_count=attempt_record.attempts,
            success_count=attempt_record.successes,
            fail_count=attempt_record.failures,
            description=self._summarize(
                attempt_record.task_description,
                attempt_record.solution,
            ),
        )

        if is_failure:
            node.status = KnowledgeStatus.ACTIVE
            node.name = f"[미해결] {topic or attempt_record.task_description[:40]}"

        # 그래프에 추가
        self.graph.add_node(node)

        # 파일로 저장
        self.store.save_node(node, self.db)

        # 세션 이벤트 기록
        if self.current_session:
            event = SessionEvent(
                event_type=EventType.KNOWLEDGE_CREATED,
                content=f"지식 생성: {node.node_key}",
                event_metadata={
                    "node_id": node.id,
                    "domain": node.domain,
                    "type": node.knowledge_type.value,
                },
            )
            self.current_session.add_event(event)

        logger.info(f"[GeniusIntelligence] Knowledge created: {node.node_key}")
        return node

    def flush(self) -> list[KnowledgeNode]:
        """
        세션 종료 시 호출 - 미처리 지식화 후보 처리

        Returns:
            이번 세션에서 생성된 지식 노드 목록
        """
        if not self.current_session:
            return []

        # 반복 실패 패턴 감지
        repeated = self.current_session.detect_repeated_failures()
        for record in repeated:
            if record not in self.current_session.knowledge_candidates:
                self.current_session.knowledge_candidates.append(record)

        # 모든 지식화 후보 처리
        created_nodes = []
        for record in self.current_session.knowledge_candidates:
            node = self.knowledgeize(record, force=True)
            if node:
                created_nodes.append(node)

        # 세션 종료
        self.current_session.ended_at = datetime.now()
        self.db.save_session(self.current_session)

        logger.info(
            f"[GeniusIntelligence] Session ended. "
            f"Knowledge created: {len(created_nodes)}"
        )

        # 자동 정리 체크
        if self.config.auto_cleanup_enabled:
            self.cleaner.maybe_cleanup()

        self._start_session()  # 새 세션 시작
        return created_nodes

    # ── 후크 시스템 ──────────────────────────────────────────────────

    def get_hooks(self) -> dict[str, Callable]:
        """
        후크 딕셔너리 반환

        코딩 어시스턴트가 이 딕셔너리를 사용하여
        해당 이벤트에 자동으로 연결할 수 있습니다.

        사용 예:
            hooks = genius.get_hooks()
            your_cli.on("message", hooks["on_message"])
        """
        return {
            "on_message": self.on_user_message,
            "on_response": self.on_assistant_message,
            "on_command": self.on_command_executed,
            "on_error": self.on_error_occurred,
            "on_file_created": self.on_file_created,
            "on_file_modified": self.on_file_modified,
            "on_user_correction": self.on_user_correction,
            "on_login_request": self.on_login_request,
            "on_flush": self.flush,
        }

    def install_hooks(self, target: Any) -> None:
        """
        대상 객체에 후크 자동 설치

        target은 다음 속성을 가져야 합니다:
        - on_message(message, ...)
        - on_response(response, ...)
        - etc.
        """
        hooks = self.get_hooks()
        for name, handler in hooks.items():
            method = getattr(target, name, None)
            if method is not None:
                method(handler)

    # ── 유틸리티 ─────────────────────────────────────────────────────

    def _extract_task_id(self, text: str) -> str:
        """텍스트에서 태스크 ID 추출 (간단한 해시)"""
        import hashlib
        import base64
        words = text.lower().split()[:5]
        key = " ".join(words)
        return base64.urlsafe_b64encode(
            hashlib.sha256(key.encode()).digest()[:12]
        ).decode()

    def _extract_topic(self, text: str) -> str:
        """텍스트에서 토픽 키워드 추출"""
        # 제거할 단어들
        stop_words = {
            "만들어줘", "만드는데", "해주세요", "이거", "그거", "것",
            "어떻게", "뭐", "무엇", "给我", "帮我", "make", "create",
            "帮我", "please", "can you", "could you", "want to",
        }

        words = text.lower().split()
        meaningful = [
            w.strip(".,!?;:()[]{}") for w in words
            if w not in stop_words and len(w) > 2
        ]

        # 핵심 키워드 3개 조합
        if len(meaningful) >= 3:
            topic = "-".join(meaningful[:3])
        elif meaningful:
            topic = "-".join(meaningful)
        else:
            topic = text[:30].lower().replace(" ", "-")

        import re
        topic = re.sub(r"[^\w-]", "", topic)
        return topic[:50]

    def _summarize(self, task: str, solution: str) -> str:
        """요약 생성"""
        task_clean = task[:80].strip()
        if solution:
            return f"사용자 요청: {task_clean} → 해결됨"
        return f"사용자 요청: {task_clean}"

    def get_stats(self) -> dict:
        """통계 반환"""
        db_stats = self.db.get_stats()
        return {
            **db_stats,
            "current_session": (
                self.current_session.get_session_summary()
                if self.current_session else None
            ),
            "project_root": self.project_root,
            "cli_tool": self._cli_tool,
        }

    def get_tree(self) -> dict:
        """폴더 트리 반환"""
        return self.store.get_tree_structure()