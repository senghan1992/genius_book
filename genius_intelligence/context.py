"""
Knowledge Context Renderer
==========================
검색 쿼리를 받아 저장된 지식 노드를 마크다운 컨텍스트 블록으로 렌더링.

세션 시작 시 어시스턴트 컨텍스트로 주입 가능한 형태.
빈 결과면 빈 문자열(또는 한 줄) — 주입이 실패를 내지 않도록.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .core.manager import GeniusIntelligence


def render_knowledge_context(
    genius: "GeniusIntelligence",
    query: str = "",
    limit: int = 10,
) -> str:
    """검색 쿼리로 지식을 검색하여 마크다운 컨텍스트 블록으로 렌더링.

    Args:
        genius: GeniusIntelligence 인스턴스
        query: 검색 쿼리. 빈 문자열이면 최근 접근 지식 상위 N개 반환.
        limit: 반환할 최대 노드 수

    Returns:
        마크다운 문자열. 지식이 없으면 빈 문자열.
    """
    if query:
        nodes = genius.search_knowledge(query, limit=limit)
    else:
        # 빈 쿼리면 최근 접근 지식 (accessed_count 내림차순)
        all_nodes = list(genius.graph.nodes.values())
        all_nodes.sort(key=lambda n: n.accessed_count, reverse=True)
        nodes = all_nodes[:limit]

    if not nodes:
        return ""

    lines = [
        "<!-- Genius Intelligence: Knowledge Context -->",
        f"<!-- Query: {query or '(recent)'} | Nodes: {len(nodes)} -->",
        "",
    ]

    for i, node in enumerate(nodes, 1):
        lines.append(f"## {i}. {node.name or node.topic or 'Untitled'}")
        lines.append("")
        lines.append(f"**Domain:** `{node.domain}` | "
                     f"**Type:** `{node.knowledge_type.value}` | "
                     f"**Attempts:** {node.attempt_count} | "
                     f"**Success:** {node.success_count} | "
                     f"**Fail:** {node.fail_count}")
        lines.append("")

        if node.description:
            lines.append(f"> {node.description}")
            lines.append("")

        if node.solution:
            lines.append("**Solution:**")
            lines.append("```")
            lines.append(node.solution[:500])
            lines.append("```")
            lines.append("")

        if node.error_trace:
            lines.append("**Error Trace:**")
            lines.append("```")
            lines.append(node.error_trace[:300])
            lines.append("```")
            lines.append("")

        if node.raw_input:
            lines.append("<details><summary>Original Request</summary>")
            lines.append("")
            lines.append(f"```\n{node.raw_input[:300]}\n```")
            lines.append("</details>")
            lines.append("")

    lines.append("<!-- /Genius Intelligence -->")
    return "\n".join(lines)


def render_context_for_session_start(
    genius: "GeniusIntelligence",
    limit: int = 10,
) -> str:
    """세션 시작용 컨텍스트 — 최근 접근 + 반복 실패 지식 상위 N개.

    빈 결과면 빈 문자열.
    """
    all_nodes = list(genius.graph.nodes.values())

    # 반복 실패(fail_count > 0) 우선, 그 다음 accessed_count 내림차순
    all_nodes.sort(
        key=lambda n: (n.fail_count > 0, n.accessed_count),
        reverse=True,
    )
    nodes = all_nodes[:limit]

    if not nodes:
        return ""

    lines = [
        "<!-- Genius Intelligence: Session Context -->",
        f"<!-- Recent + Repeated-Failure Knowledge | Nodes: {len(nodes)} -->",
        "",
    ]

    for i, node in enumerate(nodes, 1):
        icon = "❌" if node.fail_count > 0 else "✅"
        lines.append(f"## {icon} {i}. {node.name or node.topic or 'Untitled'}")
        lines.append("")
        lines.append(f"**Domain:** `{node.domain}` | "
                     f"**Type:** `{node.knowledge_type.value}` | "
                     f"**Attempts:** {node.attempt_count} | "
                     f"**Fail:** {node.fail_count}")
        lines.append("")

        if node.description:
            lines.append(f"> {node.description}")
            lines.append("")

        if node.solution:
            lines.append("**Solution:**")
            lines.append(f"```\n{node.solution[:500]}\n```")
            lines.append("")

        if node.error_trace and node.fail_count > 0:
            lines.append("**Error Trace:**")
            lines.append(f"```\n{node.error_trace[:300]}\n```")
            lines.append("")

    lines.append("<!-- /Genius Intelligence -->")
    return "\n".join(lines)


def write_context_file(
    genius: "GeniusIntelligence",
    query: str = "",
    limit: int = 10,
) -> Optional[str]:
    """컨텍스트를 .genius_intelligence/context.md에 쓰기.

    Returns:
        파일 경로. 지식이 없어도 빈 파일을 쓰지 않고 None 반환.
    """
    if query:
        content = render_knowledge_context(genius, query, limit)
    else:
        content = render_context_for_session_start(genius, limit)

    if not content:
        return None

    from pathlib import Path
    context_path = Path(genius.config.genius_root) / "context.md"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(content, encoding="utf-8")
    return str(context_path)
