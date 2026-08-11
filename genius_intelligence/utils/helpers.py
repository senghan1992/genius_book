"""
Helpers
=======
유용한 유틸리티 함수들
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    로깅 설정

    CLI 관례상 로그/진단 메시지는 반드시 stderr로 보냅니다.
    stdout은 `genius shell-init` 같이 실제 셸에서 eval/source 될 수 있는
    "순수한 출력"을 위해 깨끗하게 비워둬야 합니다. (stdout에 로그가 섞이면
    `eval "$(genius shell-init)"` 같은 셸 통합이 문법 오류를 일으킵니다.)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    return logging.getLogger("genius_intelligence")


def find_project_root(start: str | None = None) -> str | None:
    """프로젝트 루트 탐색"""
    if start is None:
        start = os.getcwd()

    current = Path(start).resolve()
    markers = [
        ".git", "package.json", "pyproject.toml", "requirements.txt",
        "Cargo.toml", "go.mod", "pom.xml", "Makefile",
        ".claude", ".cursor", ".vscode",
    ]

    while True:
        for marker in markers:
            if (current / marker).exists():
                return str(current)
        parent = current.parent
        if parent == current:
            break
        current = parent

    return str(Path(start).resolve())


def is_genius_project(path: str) -> bool:
    """지정 경로가 Genius Intelligence 프로젝트인지 확인"""
    genius_dir = Path(path) / ".genius_intelligence"
    return genius_dir.exists() and (genius_dir / "memory.sqlite.db").exists()


def format_tree(tree: dict, prefix: str = "", is_last: bool = True) -> str:
    """트리 구조를 문자열로 포맷팅"""
    lines = []
    connector = "└── " if is_last else "├── "

    name = tree.get("name", "")
    ntype = tree.get("type", "dir")

    if ntype == "db":
        name = f"🗄️ {name}"
    elif ntype == "file":
        name = f"📄 {name}"
    else:
        name = f"📁 {name}"

    lines.append(f"{prefix}{connector}{name}")

    children = tree.get("children", [])
    new_prefix = prefix + ("    " if is_last else "│   ")

    for i, child in enumerate(children):
        is_child_last = (i == len(children) - 1)
        lines.append(format_tree(child, prefix=new_prefix, is_last=is_child_last))

    return "\n".join(lines)


def pretty_print_stats(stats: dict) -> None:
    """통계를 예쁘게 출력"""
    print("\n" + "=" * 50)
    print("  📊 Genius Intelligence Statistics")
    print("=" * 50)

    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"\n  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        elif isinstance(value, list):
            print(f"  {key}: {len(value)} items")
        elif value is None:
            print(f"  {key}: -")
        else:
            print(f"  {key}: {value}")

    print("=" * 50 + "\n")


def truncate(text: str, max_length: int = 100) -> str:
    """텍스트 자르기"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def extract_code_blocks(text: str) -> list[str]:
    """마크다운에서 코드 블록 추출"""
    import re
    pattern = r"```(?:\w+)?\n(.*?)```"
    return re.findall(pattern, text, re.DOTALL)