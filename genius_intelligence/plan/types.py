"""
Plan Types
==========
플랜 문서 추적 및 Planned vs Executed 비교 분석
"""

from __future__ import annotations

import uuid
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PlanStatus(str, Enum):
    """플랜 상태"""
    DRAFT = "draft"           # 초안
    ACTIVE = "active"        # 진행 중
    COMPLETED = "completed"   # 완료
    PARTIAL = "partial"      # 일부만 완료
    FAILED = "failed"        # 실패
    CANCELLED = "cancelled"  # 취소


class TaskStatus(str, Enum):
    """태스크 상태"""
    PENDING = "pending"      # 대기
    PLANNED = "planned"      # 계획됨
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlannedTask:
    """계획된 태스크"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    order: int = 0

    # 시간
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 결과
    actual_action: str = ""      # 실제로 수행한 행동
    result: str = ""             # 결과
    error: str = ""             # 에러 메시지
    is_completed: bool = False
    completion_rate: float = 0.0  # 0.0 ~ 1.0

    # 관련 파일
    files: list[str] = field(default_factory=list)

    def mark_started(self) -> None:
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def mark_completed(self, result: str = "") -> None:
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.is_completed = True
        self.completion_rate = 1.0
        if result:
            self.result = result

    def mark_failed(self, error: str = "") -> None:
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error
        self.is_completed = False

    def mark_skipped(self, reason: str = "") -> None:
        self.status = TaskStatus.SKIPPED
        self.completed_at = datetime.now()
        self.is_completed = False
        self.actual_action = reason or "Skipped"


@dataclass
class PlanDocument:
    """
    플랜 문서

    코딩 어시스턴트가 생성한 작업 계획 문서를 추적합니다.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""

    # 출처
    source: str = ""           # 파일 경로 (예: CLAUDE.md, PLAN.md)
    source_type: str = ""      # 파일 유형 (md, txt, json)
    created_by: str = ""       # 어떤 CLI로 생성

    # 상태
    status: PlanStatus = PlanStatus.DRAFT

    # 시간
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 콘텐츠
    raw_content: str = ""      # 원본 마크다운 내용
    parsed_tasks: list[PlannedTask] = field(default_factory=list)

    # 분석
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0

    # 비교 분석
    execution_notes: str = ""  # 실행 중 메모
    workarounds: list[str] = field(default_factory=list)  # 해결책
    learnings: list[str] = field(default_factory=list)   # 배운 점

    # 파일 경로
    file_path: str = ""

    @property
    def completion_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.completed_tasks / self.total_tasks

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.completed_tasks / (self.total_tasks - self.skipped_tasks) if (self.total_tasks - self.skipped_tasks) > 0 else 0.0

    def recalculate_stats(self) -> None:
        """통계 재계산"""
        self.total_tasks = len(self.parsed_tasks)
        self.completed_tasks = sum(1 for t in self.parsed_tasks if t.is_completed)
        self.failed_tasks = sum(1 for t in self.parsed_tasks if t.status == TaskStatus.FAILED)
        self.skipped_tasks = sum(1 for t in self.parsed_tasks if t.status == TaskStatus.SKIPPED)
        self.updated_at = datetime.now()

    def to_markdown(self) -> str:
        """마크다운 형식으로 변환"""
        status_icons = {
            PlanStatus.DRAFT: "📝",
            PlanStatus.ACTIVE: "🔄",
            PlanStatus.COMPLETED: "✅",
            PlanStatus.PARTIAL: "⚠️",
            PlanStatus.FAILED: "❌",
            PlanStatus.CANCELLED: "🚫",
        }

        task_icons = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.PLANNED: "📋",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.SKIPPED: "⏭️",
        }

        lines = [
            f"# {self.title or 'Untitled Plan'}",
            "",
            f"**상태:** {status_icons.get(self.status, '')} {self.status.value}",
            f"**출처:** `{self.source}`",
            f"**생성:** {self.created_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            f"## 진행률",
            "",
            f"| 항목 | 값 |",
            f"|------|-----|",
            f"| 전체 태스크 | {self.total_tasks} |",
            f"| 완료 | {self.completed_tasks} |",
            f"| 실패 | {self.failed_tasks} |",
            f"| 건너뜀 | {self.skipped_tasks} |",
            f"| 완료율 | {self.completion_rate:.0%} |",
            "",
        ]

        if self.parsed_tasks:
            lines.extend([
                f"## 태스크 목록",
                "",
            ])

            for task in self.parsed_tasks:
                icon = task_icons.get(task.status, "📋")
                lines.append(f"### {icon} {task.title}")
                if task.description:
                    lines.append(f"**설명:** {task.description}")
                lines.append(f"**상태:** {task.status.value}")

                if task.actual_action:
                    lines.append(f"**실제 행동:** {task.actual_action}")
                if task.result:
                    lines.append(f"**결과:** {task.result}")
                if task.error:
                    lines.append(f"**에러:** `{task.error}`")
                if task.completion_rate > 0 and task.completion_rate < 1:
                    lines.append(f"**완료율:** {task.completion_rate:.0%}")

                lines.append("")

        if self.workarounds:
            lines.extend([
                "## 해결책 (Workarounds)",
                "",
            ])
            for w in self.workarounds:
                lines.append(f"- {w}")
            lines.append("")

        if self.learnings:
            lines.extend([
                "## 배운 점 (Learnings)",
                "",
            ])
            for l in self.learnings:
                lines.append(f"- {l}")
            lines.append("")

        if self.execution_notes:
            lines.extend([
                "## 실행 메모",
                "",
                self.execution_notes,
                "",
            ])

        lines.extend([
            "---",
            f"*Plan ID: `{self.id}` | 마지막 업데이트: {self.updated_at.strftime('%Y-%m-%d %H:%M')}*",
        ])

        return "\n".join(lines)
