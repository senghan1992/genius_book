"""
genius_intelligence.knowledge
=============================
지식을 파일 시스템에 마크다운으로 저장하는 모듈
그래프 구조 → 디렉토리/파일 트리 변환
"""

from .store import KnowledgeStore, create_knowledge_store

__all__ = ["KnowledgeStore", "create_knowledge_store"]
