"""
UI helpers
==========
시각적 출력, 업데이트 체크 등 CLI 사용성을 위한 유틸리티.

rich 라이브러리가 있으면 컬러/스타일 출력, 없으면 plain text fallback.
업데이트 체크는 1일 캐시 + 2초 timeout으로 빠른 실패.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


__all__ = [
    "banner",
    "check_for_update",
    "HAS_RICH",
    "status_error",
    "status_info",
    "status_success",
    "status_warn",
]


# ── 캐시 / PyPI ──────────────────────────────────────────────────────

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "genius_intelligence"
CACHE_FILE = CACHE_DIR / "update_check.json"
PYPI_URL = "https://pypi.org/pypi/genius-intelligence/json"
CHECK_TTL = 86400  # 1 day
PYPI_TIMEOUT = 2  # seconds


def _stderr_console():
    """stderr로 출력하는 rich console (없으면 None)"""
    if HAS_RICH:
        return Console(stderr=True, force_terminal=None)
    return None


def _read_cache() -> Optional[dict]:
    """캐시에서 최근 체크 결과 읽기. TTL 초과 시 None"""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if time.time() - data.get("ts", 0) > CHECK_TTL:
            return None
        return data
    except Exception:
        return None


def _write_cache(latest_version: str, has_update: bool) -> None:
    """캐시 저장 (실패해도 무시)"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps({"ts": time.time(), "latest": latest_version, "update": has_update}),
            encoding="utf-8",
        )
    except Exception:
        pass


def check_for_update(current_version: str, force: bool = False) -> Optional[str]:
    """PyPI에서 최신 버전 확인.

    Returns:
        최신 버전 (현재보다 높으면), 아니면 None.

    캐시 TTL 1일, 네트워크 timeout 2초. 실패는 조용히 무시.
    """
    if not force:
        cached = _read_cache()
        if cached is not None and not cached.get("update"):
            return None
        if cached is not None:
            return cached.get("latest") if cached.get("update") else None

    try:
        req = urllib.request.Request(PYPI_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=PYPI_TIMEOUT) as resp:
            data = json.loads(resp.read())
            latest = data["info"]["version"]
    except Exception:
        return None

    has_update = _is_newer(latest, current_version)
    _write_cache(latest, has_update)
    return latest if has_update else None


def _is_newer(latest: str, current: str) -> bool:
    """버전 비교. packaging 없으면 문자열 비교"""
    try:
        from packaging.version import Version

        return Version(latest) > Version(current)
    except Exception:
        return latest != current


# ── 출력 헬퍼 ────────────────────────────────────────────────────────


def banner() -> None:
    """인터랙티브 첫 실행 시 표시하는 배너."""
    if HAS_RICH:
        console = _stderr_console()
        if console:
            console.print(
                Panel(
                    Text("GENIUS INTELLIGENCE", style="bold cyan")
                    + Text("\n")
                    + Text("Project-aware knowledge for AI coding assistants", style="dim"),
                    border_style="cyan",
                    padding=(0, 2),
                )
            )
            return
    # fallback
    print(
        "\n  ╭──────────────────────────────────────────╮\n"
        "  │  🧠  G E N I U S   I N T E L L I G E N C E │\n"
        "  │  Project-aware knowledge for AI assistants │\n"
        "  ╰──────────────────────────────────────────╯\n",
        file=sys.stderr,
    )


def _prefix(icon: str, msg: str, style: str) -> None:
    """공통 prefix 출력 로직"""
    if HAS_RICH:
        console = _stderr_console()
        if console:
            console.print(f"  {icon}  {msg}", style=style)
            return
    print(f"  [{icon}] {msg}", file=sys.stderr)


def status_info(msg: str) -> None:
    _prefix("ℹ", msg, "cyan")


def status_success(msg: str) -> None:
    _prefix("✓", msg, "bold green")


def status_warn(msg: str) -> None:
    _prefix("⚠", msg, "yellow")


def status_error(msg: str) -> None:
    _prefix("✗", msg, "bold red")


def print_update_notice(latest: str, current: str) -> None:
    """업데이트 가능 알림 한 줄 (stderr)."""
    msg = (
        f"💡 genius-intelligence {latest} available "
        f"(current: {current}). Run 'genius update' to upgrade."
    )
    if HAS_RICH:
        console = _stderr_console()
        if console:
            console.print(f"\n  {msg}", style="bold yellow")
            return
    print(f"\n  {msg}", file=sys.stderr)


def print_install_banner() -> None:
    """설치 직후 첫 실행 시 표시하는 더 친절한 환영 배너."""
    if HAS_RICH:
        console = _stderr_console()
        if console:
            console.print(
                Panel(
                    Text("🎉 genius-intelligence installed successfully!\n\n", style="bold green")
                    + Text("다음 단계:\n", style="bold")
                    + Text("  1. 프로젝트 디렉토리로 이동\n")
                    + Text("  2. ", style="dim")
                    + Text("genius init", style="bold cyan")
                    + Text(" 실행 — .genius_intelligence/ 초기화\n", style="dim")
                    + Text("  3. ", style="dim")
                    + Text("genius wrap <cli>", style="bold cyan")
                    + Text(" 실행 — 코딩 어시스턴트를 지능적으로 감싸기", style="dim"),
                    border_style="green",
                    padding=(1, 2),
                )
            )
            return
    print(
        "\n  🎉 genius-intelligence installed successfully!\n\n"
        "  다음 단계:\n"
        "    1. 프로젝트 디렉토리로 이동\n"
        "    2. genius init 실행 — .genius_intelligence/ 초기화\n"
        "    3. genius wrap <cli> 실행 — 코딩 어시스턴트를 지능적으로 감싸기\n",
        file=sys.stderr,
    )


def show_install_progress(description: str):
    """pip install 등의 진행 상황을 표시하는 컨텍스트 매니저.

    Usage:
        with show_install_progress("Installing genius-intelligence"):
            subprocess.run(...)
    """
    if HAS_RICH:
        console = _stderr_console()
        if console:
            return Progress(
                SpinnerColumn(style="cyan"),
                TextColumn(f"[bold cyan]{description}[/bold cyan]"),
                BarColumn(bar_style="cyan"),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
                transient=True,
            )
    # fallback: plain context manager
    class _NullProgress:
        def __enter__(self):
            status_info(description)
            return self

        def __exit__(self, *args):
            return False

    return _NullProgress()
