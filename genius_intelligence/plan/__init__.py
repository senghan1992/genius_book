"""
genius_intelligence.plan
========================
Plan document tracking and Planned vs Executed comparison analysis.

핵심: 파일명이 아닌 "문서 내용"을 분석하여 플랜 문서를 감지합니다.
따라서 CLAUDE.md, PLAN.md 같은 고정된 이름뿐 아니라
2024-01-15-refactor-plan.md, sprint3-tasks.md 같이 매번 이름이
달라지는 문서도 자동으로 인식됩니다.
"""

from .types import (
    PlanDocument,
    PlannedTask,
    PlanStatus,
    TaskStatus,
)
from .tracker import PlanTracker
from .content_analyzer import PlanContentAnalyzer, PlanScore

__all__ = [
    "PlanDocument",
    "PlannedTask",
    "PlanStatus",
    "TaskStatus",
    "PlanTracker",
    "PlanContentAnalyzer",
    "PlanScore",
]
