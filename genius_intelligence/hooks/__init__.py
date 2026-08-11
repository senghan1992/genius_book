"""
genius_intelligence.hooks
=========================
코딩 어시스턴트 CLI 통합을 위한 후크 시스템

각 CLI 도구별 통합 어댑터를 제공합니다.
"""

from .adapter import HookAdapter, ClaudeCodeAdapter, OMPAdapter, GenericAdapter

__all__ = ["HookAdapter", "ClaudeCodeAdapter", "OMPAdapter", "GenericAdapter"]
