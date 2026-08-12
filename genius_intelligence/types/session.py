"""
코딩 세션 및 이벤트 추적 타입
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    """세션 이벤트 유형"""
    USER_MESSAGE = "user_message"           # 사용자 메시지
    ASSISTANT_MESSAGE = "assistant_message" # AI 응답
    COMMAND = "command"                     # 명령어 실행
    FILE_CREATED = "file_created"           # 파일 생성
    FILE_MODIFIED = "file_modified"         # 파일 수정
    FILE_DELETED = "file_deleted"           # 파일 삭제
    CODE_EXECUTION = "code_execution"        # 코드 실행
    ERROR_OCCURRED = "error_occurred"       # 에러 발생
    COMMAND_FAILED = "command_failed"       # 명령 실패
    SUCCESS = "success"                     # 성공적으로 완료
    USER_CORRECTION = "user_correction"      # 사용자 수정
    LOGIN_REQUEST = "login_request"          # 로그인 정보 요청
    LOGIN_INFO_STORED = "login_info_stored"  # 로그인 정보 저장
    KNOWLEDGE_CREATED = "knowledge_created"  # 지식 생성


@dataclass
class SessionEvent:
    """세션 내 개별 이벤트"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.USER_MESSAGE
    timestamp: datetime = field(default_factory=datetime.now)

    # 콘텐츠
    content: str = ""           # 이벤트 내용
    raw_message: str = ""       # 원본 메시지 (있을 경우)

    # 컨텍스트
    current_file: str = ""      # 현재 작업 파일
    current_directory: str = "" # 현재 디렉토리
    event_metadata: dict = field(default_factory=dict)  # 추가 메타데이터

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "current_file": self.current_file,
            "current_metadata": self.event_metadata,
        }


@dataclass
class AttemptRecord:
    """특정 태스크에 대한 시도 기록"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_description: str = ""

    # 시도와 결과
    attempts: int = 0
    successes: int = 0
    failures: int = 0

    # 상세 기록
    events: list[SessionEvent] = field(default_factory=list)
    error_traces: list[str] = field(default_factory=list)
    solution: str = ""
    final_status: str = "pending"  # pending, success, failed, partial

    # 시간 추적
    first_attempt_at: datetime | None = None
    last_attempt_at: datetime = field(default_factory=datetime.now)
    resolved_at: datetime | None = None

    # 실패 원인 분석
    failure_pattern: str = ""  # 반복되는 실패 패턴
    root_cause: str = ""

    def add_attempt(self, event: SessionEvent | None = None, 
                    error: str | None = None) -> None:
        """시도 추가"""
        self.attempts += 1
        self.last_attempt_at = datetime.now()

        if self.first_attempt_at is None:
            self.first_attempt_at = self.last_attempt_at

        if event:
            self.events.append(event)

        if error:
            self.error_traces.append(error)

    def mark_success(self, solution: str = "") -> None:
        """성공으로 표시"""
        self.successes += 1
        self.final_status = "success"
        self.solution = solution
        self.resolved_at = datetime.now()

    def mark_failure(self, reason: str = "") -> None:
        """실패로 표시"""
        self.failures += 1
        self.last_attempt_at = datetime.now()
        if reason:
            self.error_traces.append(reason)

    @property
    def should_knowledgeize(self) -> bool:
        """
        지식화해야 하는가?
        - threshold 이상 시도 OR
        - 1번이라도 실패하고 사용자가 비슷한 요청을 반복한 경우

        threshold 기본값 3은 config.auto_knowledge_threshold와 일치.
        """
        return self._should_knowledgeize_with_threshold(3)

    def _should_knowledgeize_with_threshold(self, threshold: int = 3) -> bool:
        """지식화 판정 (config에서 threshold 주입 가능)"""
        return self.attempts >= threshold or (
            self.final_status == "failed" and
            self.failures > 0
        )

    @property
    def is_repeated(self) -> bool:
        """반복 패턴 감지 (동일 태스크가 여러 번 요청됨)"""
        return self.attempts > 1


@dataclass
class CodingSession:
    """
    하나의 코딩 세션 (CLI 시작 ~ 종료까지)

    세션 내의 모든 활동을 추적하여 지식화 후보를 식별합니다.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_path: str = ""
    cli_tool: str = ""  # claude, omp, opencode, codex 등

    # 시간
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None

    # 이벤트 추적
    events: list[SessionEvent] = field(default_factory=list)

    # 태스크 추적 (attempt_id -> AttemptRecord)
    active_tasks: dict[str, AttemptRecord] = field(default_factory=dict)
    completed_tasks: list[AttemptRecord] = field(default_factory=list)

    # 세션 요약
    total_messages: int = 0
    total_errors: int = 0
    total_commands: int = 0

    # 지식화 대상
    knowledge_candidates: list[AttemptRecord] = field(default_factory=list)

    def add_event(self, event: SessionEvent) -> None:
        """이벤트 추가"""
        self.events.append(event)

        # 카운터 업데이트
        if event.event_type == EventType.USER_MESSAGE:
            self.total_messages += 1
        elif event.event_type == EventType.ERROR_OCCURRED:
            self.total_errors += 1
        elif event.event_type == EventType.COMMAND:
            self.total_commands += 1

    def track_attempt(self, task_id: str, description: str) -> AttemptRecord:
        """태스크 시도 추적 시작 또는 갱신"""
        if task_id in self.active_tasks:
            record = self.active_tasks[task_id]
            record.add_attempt()
        else:
            record = AttemptRecord(task_description=description)
            record.add_attempt()
            self.active_tasks[task_id] = record

        return record

    def resolve_task(self, task_id: str, success: bool = True,
                     solution: str = "",
                     knowledge_threshold: int = 3) -> AttemptRecord | None:
        """태스크 해결 표시

        knowledge_threshold: config.auto_knowledge_threshold에서 주입.
        should_knowledgeize gate를 통과한 record만 knowledge_candidates에 추가.
        """
        if task_id not in self.active_tasks:
            return None

        record = self.active_tasks.pop(task_id)

        if success:
            record.mark_success(solution)
        else:
            record.mark_failure()

        if record._should_knowledgeize_with_threshold(knowledge_threshold):
            self.knowledge_candidates.append(record)

        self.completed_tasks.append(record)
        return record

    def detect_repeated_failures(self) -> list[AttemptRecord]:
        """반복 실패 패턴 감지

        동일 태스크 ID로 접힌 AttemptRecord를 active_tasks에서 순회하되,
        각 record의 attempts가 threshold 이상이면 반복 실패로 간주.
        (동일 task_id의 시도가 track_attempt에서 attempts에 누적되므로,
        별도의 description 기반 그룹핑 없이 attempts 카운트로 판정.)
        """
        repeated = []
        for task_id, record in self.active_tasks.items():
            if record.attempts >= 3 or (
                record.final_status == "failed" and record.failures > 0
            ):
                record.failure_pattern = f"repeated_{record.attempts}x"
                repeated.append(record)
        return repeated

    def get_session_summary(self) -> dict:
        """세션 요약 반환"""
        return {
            "session_id": self.id,
            "project": self.project_path,
            "cli_tool": self.cli_tool,
            "duration_seconds": (
                (self.ended_at or datetime.now()) - self.started_at
            ).total_seconds(),
            "total_events": len(self.events),
            "total_messages": self.total_messages,
            "total_errors": self.total_errors,
            "total_commands": self.total_commands,
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "knowledge_candidates": len(self.knowledge_candidates),
        }
