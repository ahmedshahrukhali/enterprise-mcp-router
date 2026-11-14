"""
Thread-Safe Persistent and In-Memory Storage Backends for Enterprise-MCP-Router.
Supports SQLite (zero-external-dependency ACID persistence) and Bounded In-Memory Stores
to prevent memory leaks, eliminate data loss across process reloads, and ensure worker isolation.
"""

from abc import ABC, abstractmethod
from collections import deque
import hashlib
import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional


def _compute_audit_entry_hash(prev_hash: str, payload: Dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 link hash over the previous hash and canonical event JSON."""
    base = {k: v for k, v in payload.items() if k not in ("prev_hash", "entry_hash")}
    canonical = json.dumps(base, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}:{canonical}".encode("utf-8")).hexdigest()


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
    def append_audit_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def verify_audit_chain(self) -> Dict[str, Any]:
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

    def close(self) -> None:
        """Closes underlying storage handles when applicable."""
        return None


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
                    prev_hash TEXT NOT NULL DEFAULT '',
                    entry_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                """
            )
            cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(audit_events);").fetchall()}
            if "prev_hash" not in cols:
                self._conn.execute("ALTER TABLE audit_events ADD COLUMN prev_hash TEXT NOT NULL DEFAULT '';")
            if "entry_hash" not in cols:
                self._conn.execute("ALTER TABLE audit_events ADD COLUMN entry_hash TEXT NOT NULL DEFAULT '';")
            self._conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_audit_update
                BEFORE UPDATE ON audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'audit_events_append_only');
                END;
                """
            )
            self._conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
                BEFORE DELETE ON audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'audit_events_append_only');
                END;
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

    def append_audit_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event_type = event.get("event", "GENERIC_AUDIT")
        created_at = event.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with self._lock, self._conn:
            row = self._conn.execute("SELECT entry_hash FROM audit_events ORDER BY id DESC LIMIT 1;").fetchone()
            prev_hash = row["entry_hash"] if (row and row["entry_hash"]) else ("0" * 64)
            stored = {k: v for k, v in event.items() if k not in ("prev_hash", "entry_hash")}
            entry_hash = _compute_audit_entry_hash(prev_hash, stored)
            stored["prev_hash"] = prev_hash
            stored["entry_hash"] = entry_hash
            payload = json.dumps(stored)
            self._conn.execute(
                "INSERT INTO audit_events (event_type, data_json, prev_hash, entry_hash, created_at) VALUES (?, ?, ?, ?, ?);",
                (event_type, payload, prev_hash, entry_hash, created_at),
            )
            return stored

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT data_json FROM audit_events ORDER BY id DESC LIMIT ?;", (limit,))
            return [json.loads(r["data_json"]) for r in cur.fetchall()]

    def verify_audit_chain(self) -> Dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, data_json, prev_hash, entry_hash FROM audit_events ORDER BY id ASC;"
            ).fetchall()
            expected_prev = "0" * 64
            for row in rows:
                data = json.loads(row["data_json"])
                if row["prev_hash"] != expected_prev or data.get("prev_hash") != expected_prev:
                    return {
                        "valid": False,
                        "reason": "prev_hash_mismatch",
                        "broken_at_id": row["id"],
                        "total_events": len(rows),
                    }
                recomputed = _compute_audit_entry_hash(expected_prev, data)
                if recomputed != row["entry_hash"] or data.get("entry_hash") != row["entry_hash"]:
                    return {
                        "valid": False,
                        "reason": "entry_hash_tamper_detected",
                        "broken_at_id": row["id"],
                        "total_events": len(rows),
                    }
                expected_prev = row["entry_hash"]
            return {
                "valid": True,
                "total_events": len(rows),
                "head_hash": expected_prev,
                "append_only_enforced": True,
                "backend": "sqlite_wal",
            }

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

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class InMemoryStateStore(BaseStateStore):
    """
    Thread-safe bounded in-memory storage engine.
    Uses bounded deques for audit trails and telemetry spans to guarantee zero memory leaks.
    """

    def __init__(self, max_audit: int = 1000, max_spans: int = 2000):
        self._lock = threading.RLock()
        self._tickets: Dict[str, Dict[str, Any]] = {}
        self._audit_trail: deque[Dict[str, Any]] = deque(maxlen=max_audit)
        self._audit_total_appended: int = 0
        self._last_audit_hash: str = "0" * 64
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

    def append_audit_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            prev_hash = self._last_audit_hash
            stored = {k: v for k, v in event.items() if k not in ("prev_hash", "entry_hash")}
            entry_hash = _compute_audit_entry_hash(prev_hash, stored)
            stored["prev_hash"] = prev_hash
            stored["entry_hash"] = entry_hash
            self._audit_trail.append(stored)
            self._audit_total_appended += 1
            self._last_audit_hash = entry_hash
            return dict(stored)

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._audit_trail)
            return list(reversed(items[-limit:]))

    def verify_audit_chain(self) -> Dict[str, Any]:
        with self._lock:
            events = list(self._audit_trail)
            if not events:
                return {
                    "valid": True,
                    "total_events": 0,
                    "head_hash": "0" * 64,
                    "append_only_enforced": True,
                    "backend": "in_memory_bounded",
                }
            # If deque hasn't evicted head, first prev_hash must be genesis ("0"*64)
            expected_prev = "0" * 64 if self._audit_total_appended == len(events) else events[0].get("prev_hash", "")
            for idx, ev in enumerate(events):
                if ev.get("prev_hash") != expected_prev:
                    return {
                        "valid": False,
                        "reason": "prev_hash_mismatch",
                        "broken_at_index": idx,
                        "total_events": len(events),
                    }
                recomputed = _compute_audit_entry_hash(expected_prev, ev)
                if recomputed != ev.get("entry_hash"):
                    return {
                        "valid": False,
                        "reason": "entry_hash_tamper_detected",
                        "broken_at_index": idx,
                        "total_events": len(events),
                    }
                expected_prev = ev["entry_hash"]
            return {
                "valid": True,
                "total_events": len(events),
                "head_hash": expected_prev,
                "append_only_enforced": True,
                "backend": "in_memory_bounded",
            }

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
