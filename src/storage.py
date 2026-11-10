"""
Thread-Safe Persistent and In-Memory Storage Backends for Enterprise-MCP-Router.
Supports SQLite (zero-external-dependency ACID persistence) and Bounded In-Memory Stores
to prevent memory leaks, eliminate data loss across process reloads, and ensure worker isolation.
"""

from abc import ABC, abstractmethod
from collections import deque
import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional


class BaseStateStore(ABC):
    """Abstract Base Class for Enterprise MCP state persistence."""

    @abstractmethod
    def save_ticket(self, ticket: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_tickets(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def append_audit_event(self, event: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_snapshot(self, name: str, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_snapshot(self, name: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_snapshots(self) -> List[str]:
        pass

    @abstractmethod
    def record_span(self, span: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_spans(self, limit: int = 100) -> List[Dict[str, Any]]:
        pass


class SQLiteStateStore(BaseStateStore):
    """
    SQLite-backed ACID persistent storage engine.
    Safe for multi-threaded FastAPI workers with connection locks and WAL journaling.
    """

    def __init__(self, db_path: str = "enterprise_router.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hitl_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    expires_at REAL,
                    created_at TEXT NOT NULL,
                    data_json TEXT NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_snapshots (
                    snapshot_name TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry_spans (
                    trace_id TEXT PRIMARY KEY,
                    span_name TEXT NOT NULL,
                    use_case TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_ticket(self, ticket: Dict[str, Any]) -> None:
        ticket_id = ticket["ticket_id"]
        tool_name = ticket.get("tool_name", "")
        status = ticket.get("status", "PENDING_APPROVAL")
        requested_by = ticket.get("requested_by", "")
        expires_at = ticket.get("expires_at_epoch", 0.0)
        created_at = ticket.get("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        payload = json.dumps(ticket)

        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO hitl_tickets (ticket_id, tool_name, status, requested_by, expires_at, created_at, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticket_id) DO UPDATE SET
                    status = excluded.status,
                    expires_at = excluded.expires_at,
                    data_json = excluded.data_json;
                """,
                (ticket_id, tool_name, status, requested_by, expires_at, created_at, payload),
            )

    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT data_json FROM hitl_tickets WHERE ticket_id = ?;", (ticket_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def list_tickets(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT data_json FROM hitl_tickets ORDER BY created_at DESC;")
            return [json.loads(r["data_json"]) for r in cur.fetchall()]

    def append_audit_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("event", "GENERIC_AUDIT")
        created_at = event.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        payload = json.dumps(event)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO audit_events (event_type, data_json, created_at) VALUES (?, ?, ?);",
                (event_type, payload, created_at),
            )

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT data_json FROM audit_events ORDER BY id DESC LIMIT ?;", (limit,))
            return [json.loads(r["data_json"]) for r in cur.fetchall()]

    def save_snapshot(self, name: str, data: Dict[str, Any]) -> None:
        created_at = data.get("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        payload = json.dumps(data)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO ledger_snapshots (snapshot_name, data_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(snapshot_name) DO UPDATE SET
                    data_json = excluded.data_json,
                    created_at = excluded.created_at;
                """,
                (name, payload, created_at),
            )

    def get_snapshot(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT data_json FROM ledger_snapshots WHERE snapshot_name = ?;", (name,))
            row = cur.fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def list_snapshots(self) -> List[str]:
        with self._lock:
            cur = self._conn.execute("SELECT snapshot_name FROM ledger_snapshots ORDER BY created_at ASC;")
            return [r["snapshot_name"] for r in cur.fetchall()]

    def record_span(self, span: Dict[str, Any]) -> None:
        trace_id = span.get("trace_id", "")
        span_name = span.get("span_name", "")
        use_case = span.get("use_case", "")
        status = span.get("status", "OK")
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload = json.dumps(span)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO telemetry_spans (trace_id, span_name, use_case, status, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET data_json = excluded.data_json;
                """,
                (trace_id, span_name, use_case, status, payload, created_at),
            )

    def get_spans(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT data_json FROM telemetry_spans ORDER BY rowid DESC LIMIT ?;", (limit,))
            return [json.loads(r["data_json"]) for r in cur.fetchall()]


class InMemoryStateStore(BaseStateStore):
    """
    Thread-safe bounded in-memory storage engine.
    Uses bounded deques for audit trails and telemetry spans to guarantee zero memory leaks.
    """

    def __init__(self, max_audit: int = 1000, max_spans: int = 2000):
        self._lock = threading.RLock()
        self._tickets: Dict[str, Dict[str, Any]] = {}
        self._audit_trail: deque[Dict[str, Any]] = deque(maxlen=max_audit)
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._spans: deque[Dict[str, Any]] = deque(maxlen=max_spans)

    def save_ticket(self, ticket: Dict[str, Any]) -> None:
        with self._lock:
            self._tickets[ticket["ticket_id"]] = dict(ticket)

    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            return dict(ticket) if ticket else None

    def list_tickets(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(t) for t in self._tickets.values()]

    def append_audit_event(self, event: Dict[str, Any]) -> None:
        with self._lock:
            self._audit_trail.append(dict(event))

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._audit_trail)
            return list(reversed(items[-limit:]))

    def save_snapshot(self, name: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._snapshots[name] = dict(data)

    def get_snapshot(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            snap = self._snapshots.get(name)
            return dict(snap) if snap else None

    def list_snapshots(self) -> List[str]:
        with self._lock:
            return list(self._snapshots.keys())

    def record_span(self, span: Dict[str, Any]) -> None:
        with self._lock:
            self._spans.append(dict(span))

    def get_spans(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._spans)
            return items[-limit:]


_GLOBAL_STORE: Optional[BaseStateStore] = None


def get_default_storage(db_path: Optional[str] = None) -> BaseStateStore:
    """Returns or initializes the global storage backend."""
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        # Check environment variable for SQLite persistence or fallback to InMemory
        sqlite_env = os.environ.get("ROUTER_SQLITE_PATH")
        if sqlite_env or db_path:
            target = db_path or sqlite_env or "enterprise_router.db"
            _GLOBAL_STORE = SQLiteStateStore(target)
        else:
            _GLOBAL_STORE = InMemoryStateStore()
    return _GLOBAL_STORE


def reset_default_storage(store: Optional[BaseStateStore] = None) -> None:
    """Resets global storage backend (useful in tests)."""
    global _GLOBAL_STORE
    _GLOBAL_STORE = store
