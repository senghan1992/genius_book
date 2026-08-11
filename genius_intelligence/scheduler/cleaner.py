"""
AutoCleaner
===========
미사용 지식 자동 정리 스케줄러

- 특정 기간 동안 접근되지 않은 지식 노드 삭제
- 주기적 실행 (기본: 24시간마다)
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.manager import GeniusIntelligence

logger = logging.getLogger("genius_intelligence")


class AutoCleaner:
    """
    자동 정리 스케줄러

    일정 기간 동안 사용되지 않은 지식 노드를
    자동으로 삭제합니다.
    """

    def __init__(self, genius: "GeniusIntelligence"):
        self.genius = genius
        self.config = genius.config
        self._timer: threading.Timer | None = None
        self._running = False
        self._last_cleanup: datetime | None = None

    def start(self) -> None:
        """정리 스케줄러 시작"""
        if not self.config.auto_cleanup_enabled:
            logger.info("[AutoCleaner] Disabled in config")
            return

        if self._running:
            return

        self._running = True
        interval = self.config.cleanup_interval_hours * 3600
        self._schedule_next(interval)
        logger.info(f"[AutoCleaner] Started (interval: {self.config.cleanup_interval_hours}h)")

    def stop(self) -> None:
        """정리 스케줄러 중지"""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        logger.info("[AutoCleaner] Stopped")

    def _schedule_next(self, interval: float) -> None:
        """다음 정리 예약"""
        self._timer = threading.Timer(interval, self._run_cleanup)
        self._timer.daemon = True
        self._timer.start()

    def _run_cleanup(self) -> None:
        """정리 실행"""
        if not self._running:
            return

        try:
            self.cleanup()
        except Exception as e:
            logger.error(f"[AutoCleaner] Cleanup failed: {e}")
        finally:
            if self._running:
                interval = self.config.cleanup_interval_hours * 3600
                self._schedule_next(interval)

    def maybe_cleanup(self) -> None:
        """
        정리 필요 여부 확인 후 실행

        마지막 정리 후 interval이 지났으면 실행
        """
        if not self.config.auto_cleanup_enabled:
            return

        if self._last_cleanup is None:
            self.cleanup()
            return

        elapsed = (datetime.now() - self._last_cleanup).total_seconds()
        threshold = self.config.cleanup_interval_hours * 3600

        if elapsed >= threshold:
            self.cleanup()

    def cleanup(self, max_days: int | None = None) -> dict:
        """
        미사용 지식 정리 실행

        Returns:
            정리 결과 요약
        """
        if max_days is None:
            max_days = self.config.stale_days

        # 오래된 노드 조회
        stale_nodes = self.genius.db.get_stale_nodes(max_days)

        if not stale_nodes:
            self._last_cleanup = datetime.now()
            logger.info("[AutoCleaner] No stale nodes found")
            return {"deleted": 0, "reason": "no_stale_nodes"}

        # 파일 삭제
        deleted_ids = []
        for node in stale_nodes:
            try:
                self.genius.store.delete_node_file(node)
                self.genius.db.delete_node(node.id)
                deleted_ids.append(node.id)
                logger.info(f"[AutoCleaner] Deleted: {node.node_key}")
            except Exception as e:
                logger.error(f"[AutoCleaner] Failed to delete {node.id}: {e}")

        # 정리 로그 기록
        self.genius.db.log_cleanup(
            node_ids=deleted_ids,
            count=len(deleted_ids),
            reason="stale",
        )

        self._last_cleanup = datetime.now()
        result = {
            "deleted": len(deleted_ids),
            "node_ids": deleted_ids,
            "reason": "stale",
            "max_days": max_days,
        }

        logger.info(f"[AutoCleaner] Cleanup done: {len(deleted_ids)} nodes deleted")
        return result

    def get_cleanup_stats(self) -> dict:
        """정리 통계 반환"""
        stale = self.genius.db.get_stale_nodes(self.config.stale_days)
        return {
            "scheduled": self._running,
            "interval_hours": self.config.cleanup_interval_hours,
            "stale_nodes_count": len(stale),
            "stale_max_days": self.config.stale_days,
            "last_cleanup": (
                self._last_cleanup.isoformat()
                if self._last_cleanup else None
            ),
        }