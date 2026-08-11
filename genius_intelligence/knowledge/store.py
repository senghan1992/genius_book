"""
Knowledge Store
===============
지식 그래프를 파일 시스템 디렉토리/파일 트리로 변환 저장

.genius_intelligence/
├── knowledge_graph/
│   ├── _index.md
│   ├── api/
│   │   ├── _index.md
│   │   ├── jwt-auth.md
│   │   └── jwt-auth.meta.json
│   ├── database/
│   │   └── ...
│   └── etc/
│       ├── _index.md
│       └── failed-task.md
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..types.knowledge import KnowledgeNode, KnowledgeDomain, KnowledgeGraph, KnowledgeType, KnowledgeStatus
from ..types.config import GeniusConfig

if TYPE_CHECKING:
    from ..memory.db import MemoryDB


def slugify(text: str, max_length: int = 60) -> str:
    """텍스트를 파일명/폴더명에 안전한 슬러그로 변환"""
    if not text:
        return "untitled"
    # Unicode → ASCII 변환
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode()
    # 소문자, 공백 → 하이픈
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:max_length]


class KnowledgeStore:
    """
    지식 저장소: 메모리 ↔ 파일 시스템 동기화
    """

    def __init__(self, genius_root: str, config: GeniusConfig):
        self.genius_root = Path(genius_root)
        self.config = config
        self.knowledge_graph_dir = self.genius_root / "knowledge_graph"
        self.login_info_dir = self.genius_root / "login_information"
        self._ensure_structure()

    def _ensure_structure(self) -> None:
        """필요한 디렉토리 구조 생성"""
        dirs = [
            self.knowledge_graph_dir,
            self.knowledge_graph_dir / "etc",
            self.login_info_dir,
            self.genius_root / ".config",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def save_node(self, node: KnowledgeNode, db: "MemoryDB | None" = None) -> str:
        """KnowledgeNode를 파일로 저장"""
        file_path, meta_path = self._resolve_paths(node)
        node.file_path = str(file_path.relative_to(self.genius_root))
        file_path.parent.mkdir(parents=True, exist_ok=True)

        content = node.to_markdown()
        file_path.write_text(content, encoding="utf-8")

        meta = self._node_to_meta(node)
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        self._update_domain_index(node.domain)
        self._update_root_index()

        if db:
            db.save_knowledge_node(node)

        return str(file_path)

    def save_nodes_bulk(self, nodes: list[KnowledgeNode],
                        db: "MemoryDB | None" = None) -> list[str]:
        """여러 노드 일괄 저장"""
        saved_paths = []
        for node in nodes:
            path = self.save_node(node, db)
            saved_paths.append(path)
        return saved_paths

    def load_node_from_disk(self, node_key: str) -> KnowledgeNode | None:
        """디스크에서 노드 로드"""
        domain, topic = self._parse_node_key(node_key)
        if not topic:
            path = self.knowledge_graph_dir / domain / self.config.index_file_name
        elif domain == "etc":
            path = self.knowledge_graph_dir / "etc" / f"{slugify(topic)}.md"
        else:
            path = self.knowledge_graph_dir / domain / f"{slugify(topic)}.md"

        if not path.exists():
            return None

        content = path.read_text(encoding="utf-8")
        meta_path = path.with_suffix(".meta.json")

        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            meta = {}

        node = self._meta_to_node(meta)
        node.content = content
        node.file_path = str(path.relative_to(self.genius_root))
        return node

    def delete_node_file(self, node: KnowledgeNode) -> None:
        """노드의 파일 삭제"""
        if not node.file_path:
            return
        path = self.genius_root / node.file_path
        if path.exists():
            path.unlink()
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            meta_path.unlink()
        self._update_domain_index(node.domain)
        self._update_root_index()

    def _update_root_index(self) -> None:
        """전체 인덱스 갱신"""
        index_path = self.knowledge_graph_dir / "_index.md"
        domains = {}
        for d in self.knowledge_graph_dir.iterdir():
            if d.is_dir() and not d.name.startswith("_"):
                domains[d.name] = d

        lines = [
            "# Genius Intelligence - Knowledge Graph",
            "",
            f"**생성일:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 도메인",
            "",
        ]

        for domain_name in sorted(domains.keys()):
            icon = "📂" if domain_name == "etc" else "📁"
            lines.append(f"### {icon} [{domain_name}]({domain_name}/_index.md)")
            lines.append("")

        index_path.write_text("\n".join(lines), encoding="utf-8")

    def _update_domain_index(self, domain: str) -> None:
        """도메인 인덱스 갱신"""
        domain_dir = self.knowledge_graph_dir / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        index_path = domain_dir / self.config.index_file_name

        nodes_info = []
        for md_file in domain_dir.glob("*.md"):
            if md_file.name == self.config.index_file_name:
                continue
            meta_path = md_file.with_suffix(".meta.json")
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    nodes_info.append({
                        "file": md_file,
                        "type": meta.get("knowledge_type", "success"),
                        "desc": meta.get("description", "")[:80],
                        "attempts": meta.get("attempt_count", 0),
                        "successes": meta.get("success_count", 0),
                        "failures": meta.get("fail_count", 0),
                    })
                except json.JSONDecodeError:
                    nodes_info.append({"file": md_file, "type": "success",
                                        "desc": "", "attempts": 0, "successes": 0, "failures": 0})

        type_icons = {"success": "✅", "failure": "❌", "login_info": "🔑",
                      "pattern": "🔄", "workaround": "⚠️", "best_practice": "⭐"}

        lines = [
            f"# {domain.title()} - Knowledge",
            "",
            f"**도메인:** `{domain}` | **지식 수:** {len(nodes_info)}",
            "",
            "| 주제 | 유형 | 시도 | 성공 | 실패 | 설명 |",
            "|-----|------|------|------|------|------|",
        ]

        for info in sorted(nodes_info, key=lambda x: x["file"].stem):
            icon = type_icons.get(info["type"], "📄")
            rel = info["file"].relative_to(self.knowledge_graph_dir)
            lines.append(
                f"| [{icon} {info['file'].stem}]({rel}) "
                f"| `{info['type']}` "
                f"| {info['attempts']} | {info['successes']} | {info['failures']} "
                f"| {info['desc']} |"
            )

        index_path.write_text("\n".join(lines), encoding="utf-8")

    def _resolve_paths(self, node: KnowledgeNode) -> tuple[Path, Path]:
        """노드 → (md_path, meta_path)"""
        domain = node.domain or "root"
        if node.depth == 0:
            md_path = self.knowledge_graph_dir / "_root.md"
        elif node.depth == 1:
            md_path = self.knowledge_graph_dir / domain / self.config.index_file_name
        else:
            topic_slug = slugify(node.topic or node.name or node.id)
            if domain == "etc":
                md_path = self.knowledge_graph_dir / "etc" / f"{topic_slug}.md"
            else:
                md_path = self.knowledge_graph_dir / domain / f"{topic_slug}.md"
        return md_path, md_path.with_suffix(".meta.json")

    def _parse_node_key(self, node_key: str) -> tuple[str, str]:
        """node_key → (domain, topic)"""
        parts = node_key.split("/", 1)
        return (parts[0], parts[1]) if len(parts) > 1 else (parts[0], "")

    def _node_to_meta(self, node: KnowledgeNode) -> dict:
        return {
            "id": node.id,
            "name": node.name,
            "domain": node.domain,
            "topic": node.topic,
            "depth": node.depth,
            "knowledge_type": node.knowledge_type.value,
            "status": node.status.value,
            "description": node.description,
            "raw_input": node.raw_input[:500] if node.raw_input else "",
            "solution": node.solution[:1000] if node.solution else "",
            "error_trace": node.error_trace[:500] if node.error_trace else "",
            "tags": node.tags,
            "file_path": node.file_path,
            "related_nodes": node.related_nodes,
            "attempt_count": node.attempt_count,
            "success_count": node.success_count,
            "fail_count": node.fail_count,
            "accessed_count": node.accessed_count,
            "created_at": node.created_at.isoformat(),
            "updated_at": node.updated_at.isoformat(),
            "last_accessed_at": node.last_accessed_at.isoformat(),
        }

    def _meta_to_node(self, meta: dict) -> KnowledgeNode:
        return KnowledgeNode(
            id=meta.get("id", ""),
            name=meta.get("name", ""),
            domain=meta.get("domain", ""),
            topic=meta.get("topic", ""),
            depth=meta.get("depth", 0),
            knowledge_type=KnowledgeType(meta.get("knowledge_type", "success")),
            status=KnowledgeStatus(meta.get("status", "active")),
            description=meta.get("description", ""),
            raw_input=meta.get("raw_input", ""),
            solution=meta.get("solution", ""),
            error_trace=meta.get("error_trace", ""),
            content="",
            tags=meta.get("tags", []),
            file_path=meta.get("file_path", ""),
            related_nodes=meta.get("related_nodes", []),
            attempt_count=meta.get("attempt_count", 0),
            success_count=meta.get("success_count", 0),
            fail_count=meta.get("fail_count", 0),
            accessed_count=meta.get("accessed_count", 0),
            created_at=datetime.fromisoformat(meta.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(meta.get("updated_at", datetime.now().isoformat())),
            last_accessed_at=datetime.fromisoformat(meta.get("last_accessed_at", datetime.now().isoformat())),
        )

    def save_login_info(self, service: str, fields: dict,
                        description: str = "") -> tuple[str, bool]:
        """로그인 정보 저장"""
        file_path = self.login_info_dir / "user_information.md"
        existing: dict = {}
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            current = None
            for line in content.split("\n"):
                if line.startswith("## "):
                    current = line[3:].strip()
                    existing[current] = {"description": "", "fields": []}

        if service not in existing:
            existing[service] = {"description": description, "fields": []}
        for fname, fvalue in fields.items():
            existing[service]["fields"].append({
                "name": fname,
                "preview": f"{fvalue[:2]}***{fvalue[-2:]}",
            })

        lines = [
            "# Login Information",
            "",
            "*This file stores approved login information. Values are masked.*",
            "",
        ]
        for svc, data in existing.items():
            lines.append(f"## {svc}")
            if data["description"]:
                lines.append(f"*{data['description']}*")
            lines.append("")
            for field in data["fields"]:
                lines.append(f"- **{field['name']}**: `{field['preview']}`")
            lines.append("")

        file_path.write_text("\n".join(lines), encoding="utf-8")
        return str(file_path), True

    def list_all_nodes(self) -> list[dict]:
        """모든 저장된 노드 정보 반환"""
        nodes = []
        for domain_dir in self.knowledge_graph_dir.iterdir():
            if not domain_dir.is_dir() or domain_dir.name.startswith("_"):
                continue
            for md_file in domain_dir.glob("*.md"):
                if md_file.name == self.config.index_file_name:
                    continue
                meta_path = md_file.with_suffix(".meta.json")
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        nodes.append(meta)
                    except json.JSONDecodeError:
                        nodes.append({"file_path": str(md_file.relative_to(self.genius_root)),
                                      "domain": domain_dir.name, "topic": md_file.stem})
        return nodes

    def get_tree_structure(self) -> dict:
        """트리 구조 반환"""
        tree = {"name": self.genius_root.name, "type": "dir", "children": []}
        for item in sorted(self.genius_root.iterdir()):
            if item.name.startswith(".") and item.name not in [".genius_intelligence"]:
                continue
            if item.is_dir():
                children = []
                if item.name == "knowledge_graph":
                    for domain in sorted(item.iterdir()):
                        if domain.name.startswith("_"):
                            continue
                        domain_children = [
                            f.name for f in sorted(domain.iterdir())
                            if f.is_file() and f.name != self.config.index_file_name
                        ]
                        children.append({"name": domain.name, "type": "dir",
                                          "children": [{"name": c, "type": "file"} for c in domain_children]})
                elif item.name == "login_information":
                    children = [{"name": f.name, "type": "file"} for f in item.iterdir() if f.is_file()]
                tree["children"].append({"name": item.name, "type": "dir", "children": children})
            elif item.name == "memory.sqlite.db":
                tree["children"].append({"name": item.name, "type": "db"})
        return tree


def create_knowledge_store(project_root: str,
                            config: GeniusConfig | None = None) -> KnowledgeStore:
    """KnowledgeStore 팩토리"""
    if config is None:
        config = GeniusConfig.load(project_root)
    genius_root = str(Path(project_root) / config.genius_dir_name)
    return KnowledgeStore(genius_root, config)