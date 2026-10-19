# Enterprise MCP (Model Context Protocol) Gateway & Semantic Tool Router

Standardized **Model Context Protocol (`FastMCP`)** server and governance router connecting **`smolagents`** and **`LangGraph`** workflows to enterprise databases and APIs.

## Core Capabilities
- **Semantic Tool Routing:** Uses lightweight dense embeddings to dynamically filter 100+ registered MCP tools down to the top-$k$ per turn, slashing context-window token bloat and tool-selection hallucinations.
- **Deterministic RBAC & HITL Governance:** Enforces role-based access control (OAuth2 scopes) and Human-in-the-Loop (HITL) approval interrupts prior to executing mutating database or API calls.
