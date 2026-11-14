"""
Pytest session configuration for Enterprise-MCP-Router.

Runs BEFORE test module collection so `src.main` imports in test modules use:
- Explicit dev mode (`ROUTER_DEV_MODE=1`) for functional API & playground tests
  (individual fail-closed security tests unset `ROUTER_DEV_MODE` explicitly).
- An isolated temporary SQLite WAL database path (`ROUTER_SQLITE_PATH`) so the
  workspace root stays clean across test runs while exercising real persistence.
"""

import atexit
import os
from pathlib import Path
import tempfile

_TEST_DB_DIR = tempfile.TemporaryDirectory(prefix="mcp_router_pytest_")
_TEST_DB_PATH = str(Path(_TEST_DB_DIR.name) / "pytest_router.db")

os.environ.setdefault("ROUTER_DEV_MODE", "1")
os.environ.setdefault("ROUTER_SQLITE_PATH", _TEST_DB_PATH)


def _cleanup_test_db_dir() -> None:
    try:
        from src.storage import get_default_storage, reset_default_storage

        store = get_default_storage()
        close_fn = getattr(store, "close", None)
        if callable(close_fn):
            close_fn()
        reset_default_storage(None)
    except Exception:
        pass
    try:
        _TEST_DB_DIR.cleanup()
    except Exception:
        pass


atexit.register(_cleanup_test_db_dir)
