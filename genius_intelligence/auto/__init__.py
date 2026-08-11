"""
genius_intelligence.auto
========================
기존 코딩 어시스턴트 CLI에 자동 통합하는 모듈

- CLI 프로세스 출력을 파싱하여 이벤트 자동 추출
- 파일 시스템 감시로 코드 변경 자동 추적
- 환경 변수/프로세스 감지로 CLI 도구 자동 탐지
- 백그라운드에서 투명하게 동작
"""

from .watcher import AutoWatcher, create_watcher
from .parser import OutputParser, get_parser_for_tool
from .wrapper import AgentWrapper, wrap_cli
from .universal import UniversalWrapper

__all__ = [
    "AutoWatcher",
    "create_watcher",
    "OutputParser",
    "get_parser_for_tool",
    "AgentWrapper",
    "wrap_cli",
]
