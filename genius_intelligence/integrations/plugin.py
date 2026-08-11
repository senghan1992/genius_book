"""
Plugin Registry
===============
"""
from __future__ import annotations
import logging
from typing import Any, Callable

logger = logging.getLogger("genius_intelligence")


class PluginRegistry:
    def __init__(self):
        self._pre_handlers: list[Callable] = []
        self._post_handlers: list[Callable] = []
        self._knowledgeize_hooks: list[Callable] = []
        self._cleanup_hooks: list[Callable] = []

    def register_pre_handler(self, handler: Callable) -> None:
        self._pre_handlers.append(handler)

    def register_post_handler(self, handler: Callable) -> None:
        self._post_handlers.append(handler)

    def register_knowledgeize_hook(self, handler: Callable) -> None:
        self._knowledgeize_hooks.append(handler)

    def register_cleanup_hook(self, handler: Callable) -> None:
        self._cleanup_hooks.append(handler)

    def run_pre_handlers(self, event_data: dict) -> None:
        for handler in self._pre_handlers:
            try:
                handler(event_data)
            except Exception as e:
                logger.error(f"Pre-handler error: {e}")

    def run_post_handlers(self, event_data: dict) -> None:
        for handler in self._post_handlers:
            try:
                handler(event_data)
            except Exception as e:
                logger.error(f"Post-handler error: {e}")

    def run_knowledgeize_hooks(self, node: Any) -> None:
        for hook in self._knowledgeize_hooks:
            try:
                hook(node)
            except Exception as e:
                logger.error(f"Knowledgeize hook error: {e}")

    def run_cleanup_hooks(self, result: dict) -> None:
        for hook in self._cleanup_hooks:
            try:
                hook(result)
            except Exception as e:
                logger.error(f"Cleanup hook error: {e}")


_global_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    return _global_registry
