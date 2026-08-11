"""
설정 타입 정의
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG = {
    "genius_dir_name": ".genius_intelligence",
    "max_depth": 2,
    "auto_knowledge_threshold": 3,         # 이 횟수 이상 시도 시 지식화
    "stale_days": 30,                       # 미사용 시 삭제 기준일
    "auto_cleanup_enabled": True,
    "cleanup_interval_hours": 24,
    "log_level": "INFO",
    "enable_login_tracking": True,
    "ask_before_login_save": True,
    "supported_cli_tools": [
        "claude", "claude-code",
        "omp", "opencode", "codex", 
        "aider", "cursor", "copilot",
    ],
    "auto_domain_detection": True,
    "custom_domains": [],
    "context_window_size": 10,             # 최근 N개 이벤트만 유지
    "knowledge_format": "markdown",
    "index_file_name": "_index.md",
}


@dataclass
class GeniusConfig:
    """라이브러리 전체 설정"""
    genius_dir_name: str = ".genius_intelligence"
    max_depth: int = 2
    auto_knowledge_threshold: int = 3
    stale_days: int = 30
    auto_cleanup_enabled: bool = True
    cleanup_interval_hours: int = 24
    log_level: str = "INFO"
    enable_login_tracking: bool = True
    ask_before_login_save: bool = True
    supported_cli_tools: list[str] = field(
        default_factory=lambda: DEFAULT_CONFIG["supported_cli_tools"].copy()
    )
    auto_domain_detection: bool = True
    custom_domains: list[str] = field(default_factory=list)
    context_window_size: int = 10
    knowledge_format: str = "markdown"
    index_file_name: str = "_index.md"

    # 런타임 상태
    project_root: str = ""
    genius_root: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "GeniusConfig":
        """딕셔너리에서 로드"""
        known = {k: v for k, v in data.items() if k in DEFAULT_CONFIG}
        return cls(**known)

    @classmethod
    def load(cls, project_root: str) -> "GeniusConfig":
        """프로젝트에서 설정 로드"""
        config = cls()
        config.project_root = str(Path(project_root).resolve())
        config.genius_root = str(Path(project_root) / config.genius_dir_name)

        config_path = Path(config.genius_root) / ".config" / "config.json"

        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f)
                    config = cls.from_dict(data)
                    config.project_root = str(Path(project_root).resolve())
                    config.genius_root = str(Path(project_root) / config.genius_dir_name)
            except (json.JSONDecodeError, TypeError):
                pass  # 기본값 사용

        return config

    def save(self) -> None:
        """설정을 .genius_intelligence/.config/config.json에 저장"""
        if not self.genius_root:
            return

        config_path = Path(self.genius_root) / ".config" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "genius_dir_name": self.genius_dir_name,
            "max_depth": self.max_depth,
            "auto_knowledge_threshold": self.auto_knowledge_threshold,
            "stale_days": self.stale_days,
            "auto_cleanup_enabled": self.auto_cleanup_enabled,
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "log_level": self.log_level,
            "enable_login_tracking": self.enable_login_tracking,
            "ask_before_login_save": self.ask_before_login_save,
            "supported_cli_tools": self.supported_cli_tools,
            "auto_domain_detection": self.auto_domain_detection,
            "custom_domains": self.custom_domains,
            "context_window_size": self.context_window_size,
            "knowledge_format": self.knowledge_format,
            "index_file_name": self.index_file_name,
            "_saved_at": datetime.now().isoformat(),
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "genius_dir_name": self.genius_dir_name,
            "max_depth": self.max_depth,
            "auto_knowledge_threshold": self.auto_knowledge_threshold,
            "stale_days": self.stale_days,
            "auto_cleanup_enabled": self.auto_cleanup_enabled,
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "log_level": self.log_level,
            "enable_login_tracking": self.enable_login_tracking,
            "ask_before_login_save": self.ask_before_login_save,
            "supported_cli_tools": self.supported_cli_tools,
            "auto_domain_detection": self.auto_domain_detection,
            "custom_domains": self.custom_domains,
            "context_window_size": self.context_window_size,
            "knowledge_format": self.knowledge_format,
            "index_file_name": self.index_file_name,
        }
