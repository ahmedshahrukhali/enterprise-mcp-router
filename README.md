# Enterprise-MCP-Router

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP / JSON-RPC 2.0 + SSE](https://img.shields.io/badge/Protocol-FastMCP%20%7C%20JSON--RPC%202.0%20%2B%20SSE-0ea5e9.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-2.2-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/tests-31%20passed-brightgreen.svg)]()

**A routing and governance gateway that sits between AI agents (Claude Sonnet on Amazon Bedrock, GPT, open-weight models) and internal company databases, value stream management systems, data pipelines, and APIs.**

---

## Overview

Connecting an AI agent to 5 tools in a local prototype is straightforward. Scaling that same agent to **120+ internal tools** across a company (Product Portfolios & OKRs, Jira/GitHub engineering tickets, Snowflake, Informatica, PostgreSQL, ERP systems) usually breaks down in three places:

1. **Tool Schema Bloat in the Prompt:**
   Whenever an LLM uses tool-calling, the full JSON Schema definition of *every* available tool has to be injected into the prompt context on every turn. With 120+ tools across 8 enterprise domains, you burn **~18,000+ input tokens per message** just listing tool definitions—and models start picking the wrong tool when descriptions overlap.
   * **What this repo does:** Before calling the model, the router runs a **hybrid Okapi BM25 + 64-dim feature-hashed dense embedding search with Reciprocal Rank Fusion (RRF)** over the 120 registered tools and passes **only the top-$k$ relevant tool schemas** for that turn.

2. **Unchecked Write Access & Malformed Tool Arguments:**
   Reading a report is safe; executing an outbound bank wire, reallocating portfolio FTE capacity, running a `DROP TABLE` or `SELECT ... INTO` query, or passing invalid arguments without human sign-off is not.
   * **What this repo does:** Every tool call passes through deterministic **JSON Schema Draft-07 contract validation** (`-32602` on mismatch), API key / RBAC role verification (`src/security.py`), **AST-based Read-Only SQL guarding via `sqlglot`** (`src/connectors/sql_guard.py`) plus `sqlite3.set_authorizer` protection, and **HITL approval queues** with separation-of-duties (no self-approval), TTL expiration, single-use replay prevention, and **SQLite ACID persistence** (`src/storage.py`). See [SECURITY.md](SECURITY.md).

3. **Disconnected Management Data & Stale Pipelines:**
   Engineering and product teams track OKRs, portfolios, and engineering tickets across siloed tools, while upstream ELT jobs (Informatica Cloud $\rightarrow$ Snowflake) can fail overnight.
   * **What this repo does:** The **Value Stream Management (VSM) Connector** joins connected `product_portfolios`, `objectives_okrs`, and `engineering_tickets` in a relational SQLite3 store, uses **Claude Sonnet (`BedrockAgentCoreAdapter`)** to identify management concerns (OKR drift, blocked critical-path tickets, capacity overload) and recommend HITL-governed MCP actions, and validates upstream IICS ELT SLAs alongside W3C `traceparent` OpenTelemetry spans and L2 runbooks.

---

## How It Works

```
User / Agent Question
   │  "Identify management concerns across at-risk OKRs, portfolios, and blocked tickets"
   ▼
1. Hybrid Router       ──▶ Okapi BM25 + 64-dim Dense + RRF scores 120 tools across 8 domains
   │                       and passes only the top-k tool schemas to the LLM prompt
   ▼
2. Contract & RBAC Gate──▶ Validates JSON Schema (-32602), API Key/RBAC, & HITL separation-of-duties
   │                       ├─ Read-Only & Authorized ──▶ Executes SQL AST check & runs tool
   │                       └─ Mutating ──▶ Pauses & persists HITL Ticket (TTL + single-use lock)
   ▼
3. Safe Connectors     ──▶ Value Stream Management (SQLite3 JOINs across Portfolios, OKRs, Tickets)
   │                       PostgreSQL / SQLite3 Ledger (sqlglot AST guard, authorizer & snapshots)
   │                       Snowflake (sqlglot AST SELECT-only guard & Cortex Search)
   │                       Informatica IICS (ELT freshness & row-count gate)
   ▼
4. Trace & Alerts      ──▶ Logs W3C traceparent spans, token budgets, and L2 runbooks
```

---

## Quickstart

```bash
git clone https://github.com/ahmedshahrukhali/enterprise-mcp-router.git
cd enterprise-mcp-router
pip install -r requirements.txt

# 1. Launch the interactive 6-tab web control plane at http://localhost:8000 (OpenAPI docs at /docs)
uvicorn src.main:app --reload --port 8000

# 2. Run the terminal benchmark & simulation runner
python run_demo.py

# 3. Run the automated unit & API test suite
pytest -v
```

---

## What's Inside the Interactive Dashboard (`http://localhost:8000`)

* **Tab 1 — Semantic Tool Router (`120 -> Top-k`):** Type any plain-English task (or click a preset) and inspect the hybrid **BM25 + 64-dim Dense + Fused** scores and prompt schema token reduction.
* **Tab 2 — Value Stream & OKR Copilot (VSM):** Inspect connected Product Portfolios, OKRs, and blocked Engineering Work Tickets, trigger **Identify Management Concerns & Suggest Actions (Claude Sonnet)**, run relational `JOIN` SQL queries, and queue recommended actions directly into the HITL gate.
* **Tab 3 — RBAC, Schema Contract & Human Approval Queue:** Validate JSON Schema contracts, test role permissions (`analyst`, `ai_platform_reader`, `data_engineer`, `platform_admin`), and approve or reject queued agent actions.
* **Tab 4 — Data Connectors (Snowflake, Informatica, SQLite3/Postgres):** Test the literal-safe read-only SQL filter against `DROP TABLE` injection, check Informatica ELT pipeline SLAs, run relational `GROUP BY` ledger queries, and test transactional snapshots/rollbacks.
* **Tab 5 — Bedrock Claude Sonnet & Framework Bridges:** Export routed tools directly into **Amazon Bedrock (`toolConfig`)**, **LangGraph (`ToolNode`)**, **Hugging Face `smolagents`**, or **CrewAI**, and test automatic retry when a model output misses a required JSON field.
* **Tab 6 — Telemetry & Runbooks:** Inspect W3C `traceparent` spans, per-use-case token budget alerts, and step-by-step L2 incident triage guides.

---

## Understanding the Token Savings & Routing Tradeoff

Across **120 tools in 8 domains** (`snowflake`, `informatica`, `postgres`, `devops`, `supply_chain`, `crm_rest`, `knowledge_graph`, `portfolio_vsm`), sending the full catalog costs **~18,000+ tokens per turn** before the user even asks a question. Filtering down to top-$k$ tools via Okapi BM25 + 64-dim dense hybrid RRF typically reduces prompt schema overhead by **90%–97%** (`top_k` configurable from `1` to `25`, plus `domain_filter` or full MCP `tools/list` inspection).

---

## License
MIT License — Copyright (c) 2026 Ahmed S. Ali
