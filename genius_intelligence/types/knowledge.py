"""
지식 그래프 관련 타입 정의
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class KnowledgeType(str, Enum):
    """지식 유형"""
    SUCCESS = "success"
    FAILURE = "failure"
    LOGIN_INFO = "login_info"
    PATTERN = "pattern"
    WORKAROUND = "workaround"
    BEST_PRACTICE = "best_practice"


class KnowledgeStatus(str, Enum):
    """지식 상태"""
    ACTIVE = "active"
    VERIFIED = "verified"
    STALE = "stale"
    DELETED = "deleted"
    PENDING = "pending"


# 도메인 자동 감지를 위한 키워드 매핑
_DOMAIN_KEYWORDS = {
    "api": ["api", "rest", "graphql", "endpoint", "http", "request", "response"],
    "database": ["db", "database", "sql", "query", "migration", "postgres", "mysql", "mongodb"],
    "auth": ["auth", "login", "jwt", "oauth", "password", "session", "token", "permission"],
    "deployment": ["deploy", "docker", "kubernetes", "ci", "cd", "pipeline", "server"],
    "testing": ["test", "unit", "integration", "e2e", "mock", "fixture", "pytest"],
    "frontend": ["react", "vue", "angular", "css", "html", "ui", "component"],
    "backend": ["server", "backend", "api", "route", "controller", "service"],
    "config": ["config", "env", "setting", "yaml", "json", "ini"],
    "devops": ["docker", "ci", "cd", "pipeline", "k8s", "container", "nginx"],
    "security": ["security", "vulnerability", "xss", "csrf", "injection", "ssl"],
    "performance": ["performance", "optimize", "cache", "slow", "bottleneck"],
    "error": ["error", "exception", "bug", "crash", "fix", "issue"],
}


@dataclass
class KnowledgeNode:
    """
    지식 그래프의 노드 (2-depth 구조)

    구조:
        depth=0: 프로젝트 루트 (domain 없이)
        depth=1: 도메인 (예: api, database, auth, deployment)
        depth=2: 토픽 (예: api/jwt-auth, database/postgres-migration)

    etc 폴더는 depth=1에 위치하며, 미해결/반복 실패 지식의 영역.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    domain: str = ""
    topic: str = ""
    depth: int = 0
    knowledge_type: KnowledgeType = KnowledgeType.SUCCESS

    # 콘텐츠
    content: str = ""
    raw_input: str = ""
    solution: str = ""
    error_trace: str = ""

    # 메타데이터
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    attempt_count: int = 0
    success_count: int = 0
    fail_count: int = 0

    # 추적
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_accessed_at: datetime = field(default_factory=datetime.now)
    accessed_count: int = 0

    # 태그
    tags: list = field(default_factory=list)
    file_path: str = ""
    related_nodes: list = field(default_factory=list)

    def is_etc(self) -> bool:
        return self.domain == "etc"

    def is_stale(self, max_days: int = 30) -> bool:
        delta = datetime.now() - self.last_accessed_at
        return delta.days > max_days

    def touch(self) -> None:
        self.last_accessed_at = datetime.now()
        self.accessed_count += 1

    @property
    def node_key(self) -> str:
        if self.depth == 0:
            return "root"
        elif self.depth == 1:
            return f"{self.domain}"
        else:
            return f"{self.domain}/{self.topic}"

    def to_markdown(self) -> str:
        lines = [
            f"# {self.name or self.topic or 'Untitled'}",
            "",
            f"**도메인:** `{self.domain}` | **유형:** `{self.knowledge_type.value}` | **상태:** `{self.status.value}`",
            "",
            f"**생성일:** {self.created_at.strftime('%Y-%m-%d %H:%M:%S')} | **접근:** {self.accessed_count}회 | **성공:** {self.success_count}회 | **실패:** {self.fail_count}회",
            "",
        ]

        if self.description:
            lines.extend(["## 개요", "", f"{self.description}", ""])

        if self.raw_input:
            lines.extend(["## 원본 요청", "", "```", f"{self.raw_input}", "```", ""])

        if self.error_trace:
            lines.extend(["## 에러 트레이스", "", "```", f"{self.error_trace}", "```", ""])

        if self.solution:
            lines.extend(["## 해결책", "", f"{self.solution}", ""])

        if self.content:
            lines.extend(["## 상세 내용", "", f"{self.content}", ""])

        if self.tags:
            lines.extend(["## 태그", ""] + [f"- `{tag}`" for tag in self.tags] + [""])

        lines.extend([
            "---",
            f"*노드 ID: `{self.id}` | 마지막 접근: {self.last_accessed_at.strftime('%Y-%m-%d %H:%M:%S')}*",
        ])
        return "\n".join(lines)

    def to_index_line(self) -> str:
        icon = {
            KnowledgeType.SUCCESS: "✅",
            KnowledgeType.FAILURE: "❌",
            KnowledgeType.LOGIN_INFO: "🔑",
            KnowledgeType.PATTERN: "🔄",
            KnowledgeType.WORKAROUND: "⚠️",
            KnowledgeType.BEST_PRACTICE: "⭐",
        }.get(self.knowledge_type, "📄")
        return f"{icon} [{self.name or self.topic}]({self.file_path}) — {self.description[:60]}"


@dataclass
class KnowledgeDomain:
    """도메인 그룹 (depth=1)"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    path: str = ""
    nodes: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    is_etc: bool = False

    def add_node(self, node: KnowledgeNode) -> None:
        node.domain = self.name
        node.depth = 2
        self.nodes.append(node)

    @staticmethod
    def detect_domain(text: str, custom_domains: list | None = None) -> str:
        """텍스트 내용에서 도메인 자동 감지"""
        text_lower = text.lower()
        all_domains = dict(_DOMAIN_KEYWORDS)

        if custom_domains:
            for cd in custom_domains:
                all_domains[cd.lower()] = [cd.lower()]

        best_match = "etc"
        best_score = 0

        for domain, keywords in all_domains.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_match = domain

        return best_match


@dataclass
class KnowledgeGraph:
    """전체 지식 그래프 관리자"""
    nodes: dict = field(default_factory=dict)
    domains: dict = field(default_factory=dict)

    def add_node(self, node: KnowledgeNode) -> str:
        key = node.node_key
        self.nodes[key] = node

        if node.domain not in self.domains:
            self.domains[node.domain] = KnowledgeDomain(
                name=node.domain,
                is_etc=(node.domain == "etc"),
            )

        if node.depth == 2:
            self.domains[node.domain].add_node(node)

        return key

    def find_node(self, domain: str, topic: str = "") -> Optional[KnowledgeNode]:
        key = f"{domain}/{topic}" if topic else domain
        return self.nodes.get(key)

    def find_similar(self, query: str, limit: int = 5) -> list:
        query_lower = query.lower()
        results = []

        for node in self.nodes.values():
            score = 0
            for word in query_lower.split():
                if word in node.raw_input.lower():
                    score += 1
                if word in node.name.lower() or word in node.topic.lower():
                    score += 2
                if word in node.solution.lower():
                    score += 1

            if score > 0:
                results.append((score, node))

        results.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in results[:limit]]

    def get_stale_nodes(self, max_days: int = 30) -> list:
        return [n for n in self.nodes.values() if n.is_stale(max_days)]

    def mark_access(self, node_key: str) -> None:
        if node_key in self.nodes:
            self.nodes[node_key].touch()
