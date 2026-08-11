"""
Genius Intelligence Library
===========================

코딩 어시스턴트 CLI 도구(claude code, omp, opencode, codex 등)에
플러그인 가능한 프로젝트 단위 지식화 라이브러리

핵심 기능:
1. 코딩 어시스턴트 CLI가 프로젝트에서 실행되면 자동 감지
2. 프로젝트별 .genius_intelligence 폴더에 지식 저장
3. SQLite DB로 메타데이터 관리 + .md 파일로 문서화
4. 2-depth 그래프 노드 기반 지식 구조
5. 실패/반복 시 자동 지식화 루프
6. 미사용 지식 자동 삭제
7. 로그인 정보 요청 및 지식화

사용법:

    # 1. 기본 사용
    from genius_intelligence import GeniusIntelligence

    genius = GeniusIntelligence.for_current_project()

    # 이벤트 감지
    genius.on_user_message("JWT 인증 API 만들어줘")
    genius.on_assistant_message("완료했습니다...")
    genius.on_command_executed("npm install", success=True)
    genius.on_error_occurred("Error: module not found")

    # 세션 종료 시
    genius.flush()

    # 2. 지식 검색
    results = genius.search_knowledge("JWT 인증")
    for node in results:
        print(f"{node.name}: {node.description}")

    # 3. 후크 시스템
    hooks = genius.get_hooks()
    # 코딩 어시스턴트에 hooks["on_message"] 등을 연결

    # 4. CLI 사용
    # $ genius status
    # $ genius search "JWT"
    # $ genius tree
    # $ genius cleanup

저장소 구조::

    .genius_intelligence/
    ├── memory.sqlite.db          # 메타데이터 DB
    ├── login_information/
    │   └── user_information.md
    ├── knowledge_graph/
    │   ├── _index.md
    │   ├── api/
    │   │   ├── _index.md
    │   │   ├── jwt-auth.md
    │   │   └── jwt-auth.meta.json
    │   ├── database/
    │   └── etc/
    │       ├── _index.md
    │       └── failed-task.md
    └── .config/
        └── config.json

"""

__version__ = "0.1.2"
__author__ = "Genius Intelligence Team"

from .core.manager import GeniusIntelligence
from .types.knowledge import KnowledgeNode, KnowledgeGraph, KnowledgeDomain
from .types.session import CodingSession, AttemptRecord
from .types.config import GeniusConfig
from .memory.db import MemoryDB, get_memory_db
from .knowledge.store import KnowledgeStore, create_knowledge_store
from .hooks.adapter import HookAdapter, ClaudeCodeAdapter, OMPAdapter, GenericAdapter
from .scheduler.cleaner import AutoCleaner
from .plan import (
    PlanTracker,
    PlanDocument,
    PlanStatus,
    PlannedTask,
    TaskStatus,
    PlanContentAnalyzer,
    PlanScore,
)
from .utils.helpers import (
    setup_logging,
    find_project_root,
    is_genius_project,
    format_tree,
    pretty_print_stats,
)


from .auto import (
    AutoWatcher,
    create_watcher,
    OutputParser,
    get_parser_for_tool,
    AgentWrapper,
    wrap_cli,
)

__all__ = [
    # Main
    "GeniusIntelligence",
    # Auto Integration
    "AutoWatcher",
    "create_watcher",
    "AgentWrapper",
    "UniversalWrapper",
    "wrap_cli",
    "OutputParser",
    "UniversalWrapper",
    "get_parser_for_tool",
    # Types
    "KnowledgeNode",
    "KnowledgeGraph",
    "KnowledgeDomain",
    "CodingSession",
    "AttemptRecord",
    "GeniusConfig",
    # Storage
    "MemoryDB",
    "get_memory_db",
    "KnowledgeStore",
    "create_knowledge_store",
    # Hooks
    "HookAdapter",
    "ClaudeCodeAdapter",
    "OMPAdapter",
    "GenericAdapter",
    # Scheduler
    "AutoCleaner",
    # Plan Tracking
    "PlanTracker",
    "PlanDocument",
    "PlanStatus",
    "PlannedTask",
    "TaskStatus",
    "PlanContentAnalyzer",
    "PlanScore",
    # Utils
    "setup_logging",
    "find_project_root",
    "is_genius_project",
    "format_tree",
    "pretty_print_stats",
]