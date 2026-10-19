"""
Enterprise Model Context Protocol (MCP) Server & Semantic Tool Router.
Provides top-k semantic tool filtering, RBAC enforcement, and Human-in-the-Loop (HITL)
approval gates for mutating enterprise operations across smolagents and LangGraph.
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class MCPToolSpec:
    name: str
    description: str
    is_mutating: bool
    required_role: str
    embedding: List[float]


class EnterpriseMCPRouter:
    """Routes agent intents to top-k MCP tools and enforces RBAC + HITL governance."""

    def __init__(self, tools: List[MCPToolSpec]):
        self.tools = {t.name: t for t in tools}

    def route_top_k_tools(self, query_embedding: List[float], k: int = 5) -> List[str]:
        """Filters large MCP tool registries down to top-k relevant tools via cosine dot product."""
        scored = []
        for name, spec in self.tools.items():
            score = sum(q * t for q, t in zip(query_embedding, spec.embedding))
            scored.append((score, name))
        scored.sort(reverse=True)
        return [name for _, name in scored[:k]]

    def authorize_execution(
        self,
        tool_name: str,
        user_roles: List[str],
        hitl_approved: bool = False,
    ) -> Dict[str, Any]:
        """Enforces deterministic RBAC and HITL confirmation before executing mutating MCP tools."""
        spec = self.tools.get(tool_name)
        if not spec:
            return {"allowed": False, "reason": "tool_not_found"}

        if spec.required_role not in user_roles:
            return {"allowed": False, "reason": "rbac_denied"}

        if spec.is_mutating and not hitl_approved:
            return {"allowed": False, "reason": "hitl_approval_required"}

        return {"allowed": True, "reason": "authorized"}
