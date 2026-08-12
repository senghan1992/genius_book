"""
SQLite 데이터베이스 관리
=======================
knowledge_nodes, sessions, login_info, usage_stats 메타데이터 저장
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from ..types.knowledge import KnowledgeNode, KnowledgeGraph, KnowledgeType, KnowledgeStatus
from ..types.session import CodingSession, AttemptRecord
from ..types.config import GeniusConfig


class MemoryDB:
    """
    SQLite 기반 영속 메모리

    테이블 구조:
        - knowledge_nodes: 지식 노드 메타데이터
        - sessions: 코딩 세션 기록
        - attempt_records: 태스크 시도 기록
        - login_info: 로그인 정보 메타데이터
        - usage_stats: 지식 접근 통계
        - cleanup_log: 자동 정리 기록
    """

    _local = threading.local()

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        # Reset thread-local connection to force new connection
        if hasattr(MemoryDB._local, "conn") and MemoryDB._local.conn is not None:
            try:
                MemoryDB._local.conn.close()
            except Exception:
                pass
            MemoryDB._local.conn = None
        self._init_db()

    @classmethod
    def for_project(cls, project_root: str, config: GeniusConfig | None = None) -> "MemoryDB":
        """프로젝트용 DB 인스턴스 생성"""
        if config is None:
            config = GeniusConfig.load(project_root)

        db_dir = Path(project_root) / config.genius_dir_name
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "memory.sqlite.db"

        return cls(str(db_path))

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        """스레드 안전 컨넥션"""
        stale = False
        if hasattr(self._local, "conn") and self._local.conn is not None:
            # 연결된 DB 경로와 현재 경로가 다르면 재연결
            try:
                # check_same_thread=False로 열린 연결은 닫고 새로 열기
                try:
                    cursor = self._local.conn.execute("SELECT 1")
                    cursor.close()
                except (sqlite3.ProgrammingError, sqlite3.OperationalError):
                    stale = True
            except Exception:
                stale = True

            if stale:
                try:
                    self._local.conn.close()
                except Exception:
                    pass
                self._local.conn = None

        if not hasattr(self._local, "conn") or self._local.conn is None or stale:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                isolation_level="DEFERRED",
            )
            self._local.conn.row_factory = sqlite3.Row

        try:
            yield self._local.conn
            self._local.conn.commit()
        except Exception:
            if self._local.conn:
                self._local.conn.rollback()
            raise

    def _init_db(self) -> None:
        """테이블 초기화"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    domain TEXT NOT NULL DEFAULT '',
                    topic TEXT NOT NULL DEFAULT '',
                    depth INTEGER NOT NULL DEFAULT 0,
                    knowledge_type TEXT NOT NULL DEFAULT 'success',
                    status TEXT NOT NULL DEFAULT 'active',
                    description TEXT DEFAULT '',
                    raw_input TEXT DEFAULT '',
                    solution TEXT DEFAULT '',
                    error_trace TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    file_path TEXT DEFAULT '',
                    related_nodes TEXT DEFAULT '[]',
                    attempt_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    accessed_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    node_key TEXT UNIQUE NOT NULL,
                    is_etc INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_kn_domain ON knowledge_nodes(domain);
                CREATE INDEX IF NOT EXISTS idx_kn_topic ON knowledge_nodes(topic);
                CREATE INDEX IF NOT EXISTS idx_kn_status ON knowledge_nodes(status);
                CREATE INDEX IF NOT EXISTS idx_kn_last_accessed ON knowledge_nodes(last_accessed_at);
                CREATE INDEX IF NOT EXISTS idx_kn_node_key ON knowledge_nodes(node_key);

                CREATE TABLE IF NOT EXISTS coding_sessions (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    cli_tool TEXT DEFAULT '',
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    total_messages INTEGER DEFAULT 0,
                    total_errors INTEGER DEFAULT 0,
                    total_commands INTEGER DEFAULT 0,
                    knowledge_candidates_count INTEGER DEFAULT 0,
                    summary TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS attempt_records (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    task_description TEXT DEFAULT '',
                    attempts INTEGER DEFAULT 0,
                    successes INTEGER DEFAULT 0,
                    failures INTEGER DEFAULT 0,
                    final_status TEXT DEFAULT 'pending',
                    solution TEXT DEFAULT '',
                    failure_pattern TEXT DEFAULT '',
                    root_cause TEXT DEFAULT '',
                    error_traces TEXT DEFAULT '[]',
                    first_attempt_at TEXT,
                    last_attempt_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES coding_sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_ar_session ON attempt_records(session_id);

                CREATE TABLE IF NOT EXISTS login_info (
                    id TEXT PRIMARY KEY,
                    service_name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    field_count INTEGER DEFAULT 0,
                    fields_summary TEXT DEFAULT '',
                    file_path TEXT DEFAULT '',
                    authorized INTEGER DEFAULT 0,
                    requested_at TEXT NOT NULL,
                    stored_at TEXT,
                    last_used_at TEXT,
                    access_count INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_li_service ON login_info(service_name);

                CREATE TABLE IF NOT EXISTS usage_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT,
                    accessed_at TEXT NOT NULL,
                    access_type TEXT DEFAULT 'read',
                    session_id TEXT,
                    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id)
                );

                CREATE INDEX IF NOT EXISTS idx_us_node ON usage_stats(node_id);

                CREATE TABLE IF NOT EXISTS cleanup_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cleaned_at TEXT NOT NULL,
                    node_ids TEXT DEFAULT '[]',
                    count INTEGER DEFAULT 0,
                    reason TEXT DEFAULT 'stale'
                );

                CREATE TABLE IF NOT EXISTS session_events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    current_file TEXT DEFAULT '',
                    current_directory TEXT DEFAULT '',
                    event_metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (session_id) REFERENCES coding_sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_se_session ON session_events(session_id);

                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
            """)

            # 스키마 버전 체크
            cur = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cur.fetchone()
            current_version = row["version"] if row else 0
            target_version = 1

            if current_version < target_version:
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (target_version, datetime.now().isoformat())
                )

    # ── Knowledge Node CRUD ────────────────────────────────────────────

    def save_knowledge_node(self, node: KnowledgeNode) -> None:
        """지식 노드 저장/갱신

        node_key가 같으면 기존 row를 UPDATE (id, created_at 보존).
        INSERT OR REPLACE를 쓰면 새 id로 덮어써 usage_stats FK가 고아가 되므로,
        ON CONFLICT(node_key) DO UPDATE로 안전하게 갱신한다.
        """
        now = datetime.now().isoformat()
        node.updated_at = datetime.now()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO knowledge_nodes
                (id, name, domain, topic, depth, knowledge_type, status,
                 description, raw_input, solution, error_trace, content,
                 tags, file_path, related_nodes, attempt_count, success_count,
                 fail_count, accessed_count, created_at, updated_at,
                 last_accessed_at, node_key, is_etc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_key) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    knowledge_type=excluded.knowledge_type,
                    status=excluded.status,
                    raw_input=excluded.raw_input,
                    solution=excluded.solution,
                    error_trace=excluded.error_trace,
                    content=excluded.content,
                    tags=excluded.tags,
                    file_path=excluded.file_path,
                    related_nodes=excluded.related_nodes,
                    attempt_count=excluded.attempt_count,
                    success_count=excluded.success_count,
                    fail_count=excluded.fail_count,
                    accessed_count=excluded.accessed_count,
                    updated_at=excluded.updated_at,
                    last_accessed_at=excluded.last_accessed_at,
                    is_etc=excluded.is_etc
            """, (
                node.id,
                node.name,
                node.domain,
                node.topic,
                node.depth,
                node.knowledge_type.value,
                node.status.value,
                node.description,
                node.raw_input,
                node.solution,
                node.error_trace,
                node.content,
                json.dumps(node.tags),
                node.file_path,
                json.dumps(node.related_nodes),
                node.attempt_count,
                node.success_count,
                node.fail_count,
                node.accessed_count,
                node.created_at.isoformat(),
                now,
                node.last_accessed_at.isoformat(),
                node.node_key,
                1 if node.is_etc() else 0,
            ))

    def load_all_nodes(self) -> KnowledgeGraph:
        """모든 노드 로드 → KnowledgeGraph 반환"""
        graph = KnowledgeGraph()

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM knowledge_nodes WHERE status != 'deleted'"
            ).fetchall()

        for row in rows:
            node = self._row_to_node(row)
            graph.add_node(node)

        return graph

    def load_node(self, node_key: str) -> KnowledgeNode | None:
        """노드 키로 단일 노드 로드"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_nodes WHERE node_key = ? AND status != 'deleted'",
                (node_key,)
            ).fetchone()

        return self._row_to_node(row) if row else None

    def delete_node(self, node_id: str) -> None:
        """노드 삭제 (soft delete)"""
        with self._conn() as conn:
            conn.execute(
                "UPDATE knowledge_nodes SET status = 'deleted', updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), node_id)
            )

    def touch_node(self, node_key: str) -> None:
        """노드 접근 시간 업데이트"""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """UPDATE knowledge_nodes 
                   SET last_accessed_at = ?, accessed_count = accessed_count + 1
                   WHERE node_key = ?""",
                (now, node_key)
            )

            # 사용 통계 기록
            row = conn.execute(
                "SELECT id FROM knowledge_nodes WHERE node_key = ?", (node_key,)
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT INTO usage_stats (node_id, accessed_at, access_type) VALUES (?, ?, 'read')",
                    (row["id"], now)
                )

    def get_stale_nodes(self, max_days: int = 30) -> list[KnowledgeNode]:
        """오래된 노드 조회 (UTC ISO8601 기반 비교)

        last_accessed_at은 저장 시 UTC ISO8601로 쓰이므로,
        비교도 UTC ISO8601 문자열로 통일한다.
        """
        from datetime import timezone, timedelta
        now_utc = datetime.now(timezone.utc)
        threshold = now_utc - timedelta(days=max_days)
        threshold_str = threshold.isoformat()

        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM knowledge_nodes
                   WHERE status = 'active'
                   AND last_accessed_at < ?
                   ORDER BY last_accessed_at ASC""",
                (threshold_str,)
            ).fetchall()

        return [self._row_to_node(r) for r in rows]

    def bulk_save_nodes(self, nodes: list[KnowledgeNode]) -> None:
        """여러 노드 일괄 저장 — save_knowledge_node에 위임"""
        for node in nodes:
            self.save_knowledge_node(node)

    def _row_to_node(self, row: sqlite3.Row) -> KnowledgeNode:
        """DB Row → KnowledgeNode"""
        return KnowledgeNode(
            id=row["id"],
            name=row["name"],
            domain=row["domain"],
            topic=row["topic"],
            depth=row["depth"],
            knowledge_type=KnowledgeType(row["knowledge_type"]),
            status=KnowledgeStatus(row["status"]),
            description=row["description"],
            raw_input=row["raw_input"],
            solution=row["solution"],
            error_trace=row["error_trace"],
            content=row["content"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            file_path=row["file_path"],
            related_nodes=json.loads(row["related_nodes"]) if row["related_nodes"] else [],
            attempt_count=row["attempt_count"],
            success_count=row["success_count"],
            fail_count=row["fail_count"],
            accessed_count=row["accessed_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]),
        )

    # ── Session CRUD ────────────────────────────────────────────────────

    def save_session(self, session: CodingSession) -> None:
        """세션 저장"""
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO coding_sessions
                (id, project_path, cli_tool, started_at, ended_at,
                 total_messages, total_errors, total_commands,
                 knowledge_candidates_count, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.id,
                session.project_path,
                session.cli_tool,
                session.started_at.isoformat(),
                session.ended_at.isoformat() if session.ended_at else None,
                session.total_messages,
                session.total_errors,
                session.total_commands,
                len(session.knowledge_candidates),
                json.dumps(session.get_session_summary()),
            ))
    def save_session_events(self, session: "CodingSession") -> None:
        """세션 이벤트들을 DB에 영속화"""
        if not session.events:
            return
        with self._conn() as conn:
            for event in session.events:
                conn.execute("""
                    INSERT OR REPLACE INTO session_events
                    (id, session_id, event_type, timestamp, content,
                     current_file, current_directory, event_metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.id,
                    session.id,
                    event.event_type.value,
                    event.timestamp.isoformat(),
                    event.content[:500] if event.content else "",
                    event.current_file,
                    event.current_directory,
                    json.dumps(event.event_metadata, ensure_ascii=False)
                    if event.event_metadata else "{}",
                ))

    def save_attempt_records(self, session: "CodingSession") -> None:
        """세션의 attempt_records들을 DB에 영속화"""
        all_records = (
            list(session.active_tasks.values()) +
            session.completed_tasks +
            session.knowledge_candidates
        )
        # 중복 제거
        seen_ids = set()
        unique_records = []
        for record in all_records:
            if record.id not in seen_ids:
                seen_ids.add(record.id)
                unique_records.append(record)

        if not unique_records:
            return
        with self._conn() as conn:
            for record in unique_records:
                conn.execute("""
                    INSERT OR REPLACE INTO attempt_records
                    (id, session_id, task_description, attempts, successes,
                     failures, final_status, solution, failure_pattern,
                     root_cause, error_traces, first_attempt_at,
                     last_attempt_at, resolved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id,
                    session.id,
                    record.task_description[:500] if record.task_description else "",
                    record.attempts,
                    record.successes,
                    record.failures,
                    record.final_status,
                    record.solution[:1000] if record.solution else "",
                    record.failure_pattern,
                    record.root_cause,
                    json.dumps(record.error_traces, ensure_ascii=False),
                    record.first_attempt_at.isoformat() if record.first_attempt_at else None,
                    record.last_attempt_at.isoformat() if record.last_attempt_at else None,
                    record.resolved_at.isoformat() if record.resolved_at else None,
                ))

    def load_session_events(self, session_id: str) -> list[dict]:
        """세션 이벤트 조회"""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM session_events
                   WHERE session_id = ?
                   ORDER BY timestamp ASC""",
                (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def load_attempt_records(self, session_id: str) -> list[dict]:
        """세션의 attempt records 조회"""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM attempt_records
                   WHERE session_id = ?
                   ORDER BY last_attempt_at ASC""",
                (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def load_recent_sessions(self, limit: int = 10) -> list[dict]:
        """최근 세션 조회"""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM coding_sessions 
                   ORDER BY started_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Login Info CRUD ─────────────────────────────────────────────────

    def save_login_info(self, service: str, description: str,
                        fields: dict, authorized: bool,
                        file_path: str) -> None:
        """로그인 정보 메타데이터 저장"""
        import hashlib
        import base64

        # 필드 이름만 요약 (값은 저장 안 함)
        fields_summary = json.dumps(list(fields.keys()))
        field_count = len(fields)

        # 고유 ID 생성
        raw = f"{service}:{json.dumps(list(fields.keys()))}:{datetime.now().isoformat()}"
        info_id = base64.urlsafe_b64encode(
            hashlib.sha256(raw.encode()).digest()[:16]
        ).decode()

        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO login_info
                (id, service_name, description, field_count, fields_summary,
                 file_path, authorized, requested_at, stored_at, last_used_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                info_id,
                service,
                description,
                field_count,
                fields_summary,
                file_path,
                1 if authorized else 0,
                datetime.now().isoformat(),
                datetime.now().isoformat() if authorized else None,
                None,
                0,
            ))

    def get_login_info(self, service: str) -> list[dict]:
        """로그인 정보 조회"""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM login_info 
                   WHERE service_name = ? AND authorized = 1
                   ORDER BY stored_at DESC""",
                (service,)
            ).fetchall()
        return [dict(r) for r in rows]

    def touch_login_info(self, info_id: str) -> None:
        """로그인 정보 접근 시간 업데이트"""
        with self._conn() as conn:
            conn.execute(
                """UPDATE login_info 
                   SET last_used_at = ?, access_count = access_count + 1
                   WHERE id = ?""",
                (datetime.now().isoformat(), info_id)
            )

    # ── Cleanup ─────────────────────────────────────────────────────────

    def log_cleanup(self, node_ids: list[str], count: int, reason: str = "stale") -> None:
        """정리 로그 기록"""
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO cleanup_log (cleaned_at, node_ids, count, reason)
                   VALUES (?, ?, ?, ?)""",
                (datetime.now().isoformat(), json.dumps(node_ids), count, reason)
            )

    def get_stats(self) -> dict:
        """전체 통계 반환"""
        with self._conn() as conn:
            total_nodes = conn.execute(
                "SELECT COUNT(*) FROM knowledge_nodes WHERE status = 'active'"
            ).fetchone()[0]

            total_sessions = conn.execute(
                "SELECT COUNT(*) FROM coding_sessions"
            ).fetchone()[0]

            total_login_info = conn.execute(
                "SELECT COUNT(*) FROM login_info WHERE authorized = 1"
            ).fetchone()[0]

            domain_counts = {}
            rows = conn.execute(
                """SELECT domain, COUNT(*) as cnt 
                   FROM knowledge_nodes WHERE status = 'active'
                   GROUP BY domain"""
            ).fetchall()
            for r in rows:
                domain_counts[r["domain"]] = r["cnt"]

            return {
                "total_active_nodes": total_nodes,
                "total_sessions": total_sessions,
                "total_login_info": total_login_info,
                "domain_distribution": domain_counts,
            }

    def get_usage_count(self, access_type: str = "read") -> int:
        """usage_stats 기반 — 지식이 검색/주입된 횟수"""
        with self._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM usage_stats WHERE access_type = ?",
                (access_type,)
            ).fetchone()[0]
        return count


# ── 전역 DB 팩토리 ─────────────────────────────────────────────────────

_db_cache: dict[str, MemoryDB] = {}


def get_memory_db(project_root: str, config: GeniusConfig | None = None) -> MemoryDB:
    """프로젝트별 DB 인스턴스 (캐싱)"""
    key = str(Path(project_root).resolve())

    if key not in _db_cache:
        _db_cache[key] = MemoryDB.for_project(key, config)

    return _db_cache[key]
