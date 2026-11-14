"""
Web Control Plane UI loader for Enterprise-MCP-Router.
Loads the static Executive Light Mode single-page UI from `src/static/index.html`.
"""

from pathlib import Path

_STATIC_HTML_PATH = Path(__file__).resolve().parent / "static" / "index.html"
DASHBOARD_HTML: str = _STATIC_HTML_PATH.read_text(encoding="utf-8")
