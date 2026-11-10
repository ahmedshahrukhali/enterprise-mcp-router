# Enterprise-MCP-Router

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP / JSON-RPC 2.0](https://img.shields.io/badge/Protocol-FastMCP%20%7C%20JSON--RPC%202.0-0ea5e9.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-2.1-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/tests-21%20passed-brightgreen.svg)]()

**A routing and governance gateway that sits between AI agents (Claude, GPT, open-weight models) and internal company databases, data pipelines, and APIs.**

---

## Overview

Connecting an AI agent to 5 tools in a local prototype is straightforward. Scaling that same agent to **100+ internal tools** across a company (Snowflake, Informatica, PostgreSQL, Jira, GitHub, ERP systems) usually breaks down in three places:

1. **Tool Schema Bloat in the Prompt:**
   Whenever an LLM uses tool-calling, the full JSON Schema definition of *every* available tool has to be injected into the prompt context on every turn. With 100+ tools across multiple connectors, you burn **~15,000+ input tokens per message** just listing tool definitions—and models start picking the wrong tool when descriptions overlap.
   * **What this repo does:** Before calling the model, the router runs a fast hybrid search over the 105 registered tools and passes **only the top-$k$ relevant tool schemas** for that turn.

2. **Unchecked Write Access to Production Systems:**
   Reading a report is safe; executing an outbound bank wire, running a `DROP TABLE` query, or triggering a production deployment without human sign-off is not.
   * **What this repo does:** Every tool call passes through a role check (**RBAC**). Read-only tools run immediately, SQL queries are parsed using an **AST Safe SQL Guard (`sqlglot`)** to block destructive commands (`DROP`, `DELETE`, `UPDATE`, `SELECT ... INTO`), and any tool marked as mutating pauses execution and queues a **Human-in-the-Loop (HITL) approval ticket** with separation-of-duties enforcement and single-use replay prevention.

3. **Querying Stale or Broken Data Pipelines:**
   If an upstream ETL/ELT job (like Informatica Cloud $\rightarrow$ Snowflake) fails overnight, an AI agent won't know—it will confidently answer questions using stale or empty staging tables.
   * **What this repo does:** It validates upstream pipeline status, row counts, and freshness SLAs before unlocking downstream RAG retrieval, and logs OpenTelemetry trace spans, per-use-case token budgets, and L2 troubleshooting runbooks.

---

## How It Works

```
User / Agent Question
   │  "Check Fidelity RRSP rules in Snowflake and get fund NAV"
   ▼
1. Semantic Router ──▶ Scores 105 registered tools across 7 connectors (<2ms)
   │                    and passes only the top-k tool schemas to the LLM prompt
   ▼
2. Permission Gate ──▶ Checks caller RBAC role. Does the tool modify data?
   │                    ├─ No (Read-Only) ──▶ Validates SQL AST & executes tool immediately
   │                    └─ Yes (Mutating) ──▶ Pauses & queues a Human Approval Ticket (TTL + anti-replay)
   ▼
3. Safe Connectors ──▶ Snowflake (AST SELECT-only guard & Cortex Search)
   │                   Informatica IICS (ELT freshness & row-count gate)
   │                   PostgreSQL (AST-governed ledger & 1-click table snapshots)
   ▼
4. Trace & Alerts  ──▶ Logs W3C traceparent spans, token budgets, and L2 runbooks
```

---

## Quickstart

```bash
git clone https://github.com/ahmedshahrukhali/enterprise-mcp-router.git
cd enterprise-mcp-router
pip install -r requirements.txt

# 1. Launch the interactive web control plane at http://localhost:8000 (OpenAPI docs at /docs)
uvicorn src.main:app --reload --port 8000

# 2. Run the terminal benchmark & simulation runner
python run_demo.py

# 3. Run the 21 automated unit, security, and recall benchmark tests
pytest -v
```

---

## Architecture & Security Defenses

### 1. AST-Based Read-Only SQL Guard (`src/connectors/sql_guard.py`)
Rather than relying on brittle regex pattern-matching, queries are parsed into Abstract Syntax Trees using `sqlglot` across both **Snowflake** and **PostgreSQL** dialects:
* **Allowed:** Pure `SELECT` and `UNION` statements, including Common Table Expressions (`WITH ... SELECT ...`), comments (`--` and `/* ... */`), and semicolons safely contained inside string literals (`WHERE memo = 'run 1; run 2'`).
* **Blocked:** DDL/DML mutations (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`), subclause bypasses (`SELECT ... INTO new_table`), stacked multi-statements (`SELECT 1; DROP TABLE foo`), and unauthorized schema access.

### 2. Human-in-the-Loop (HITL) Governance & Separation of Duties
* **Separation of Duties:** Requesters are strictly prohibited from approving their own tickets (`self_approval_prohibited`).
* **Approver Authorization:** Only reviewers holding `platform_admin` or `super_admin` roles can approve or reject interrupt tickets.
* **TTL Expiration:** Tickets carry an expiration timestamp (default: 30 minutes). Expired tickets transition to `EXPIRED` and cannot be approved or executed.
* **Single-Use Replay Prevention:** Once a ticket is consumed to authorize tool execution, its status transitions to `CONSUMED`. Replaying the same ticket ID is rejected.
* **No Direct Bypass:** Mutating MCP tools cannot be executed via public API endpoints by setting boolean flags (`hitl_approved=True`); authorization requires a valid, unconsumed ticket ID.

### 3. Persistent & Bounded Storage (`src/storage.py`)
* **SQLite Persistence (`SQLiteStateStore`):** Full ACID persistence with WAL journaling for tickets, audit events, ledger snapshots, and telemetry spans across worker reloads.
* **Bounded In-Memory Queues (`InMemoryStateStore`):** Thread-safe ring buffers using bounded `deque`s for audit trails and trace spans to guarantee zero memory leaks under high throughput.

---

## Production Implementations vs. Simulated Components

To enable zero-setup local demonstration without requiring paid cloud infrastructure, some connectors simulate cloud backends:

| Component | Status | Description |
|---|---|---|
| **Semantic Router & Catalog** | **Production-Ready** | 105-tool catalog, dense cosine + keyword router, prompt token profiler |
| **FastMCP Server & JSON-RPC** | **Production-Ready** | FastMCP `@mcp.tool()` registration, JSON-RPC 2.0 dispatch, RBAC validation |
| **AST Safe SQL Guard** | **Production-Ready** | Full AST parser via `sqlglot` for Snowflake and PostgreSQL |
| **HITL Governance Engine** | **Production-Ready** | Stateful approval queue, TTL expiry, anti-replay, separation-of-duties |
| **State Storage (SQLite)** | **Production-Ready** | Thread-safe SQLite ACID persistence and bounded in-memory queues |
| **Snowflake Cortex Search** | *Simulated Mock* | Demonstrates hybrid keyword/vector search over in-memory compliance chunks |
| **Informatica IICS Taskflow** | *Simulated Mock* | Demonstrates webhook validation, freshness lag checks, and RAG sync locks |
| **PostgreSQL Ledger** | *Simulated Mock* | Demonstrates in-memory transactional ledger with instant rollback snapshots |
| **Bedrock Converse Adapter** | *Simulated Mock* | Demonstrates self-healing retry loop when LLM output misses required JSON keys |

---

## Understanding the Token Savings & Routing Tradeoff

In standard LLM tool-calling, every tool in your registry adds roughly **140–160 tokens** of JSON Schema metadata (`name`, `description`, parameter types, enums) to the system prompt on every turn. Across 105 tools in 7 domains, sending the full catalog costs **15,878 tokens per turn** before the user even says hello.

By filtering the catalog down to the **top-$k$ tools** matching the user's intent, we avoid sending irrelevant connector schemas (for example, omitting DevOps and CRM tool schemas when the user asks a Snowflake finance question):

| Routed Subset ($k$) | Full Catalog Schema Tokens | Routed Schema Tokens | Prompt Schema Reduction | Router Latency | Recommended Use Case |
|---|---|---|---|---|---|
| **Top-3 Tools** | 15,878 tokens | **472 tokens** | **97.0%** | 1.6 ms | Single-domain lookups (e.g., pure SQL or doc search) |
| **Top-5 Tools (Default)** | 15,878 tokens | **758 tokens** | **95.2%** | 1.8 ms | Standard single- or two-step agent turns |
| **Top-8 Tools** | 15,878 tokens | **1,218 tokens** | **92.3%** | 2.0 ms | Cross-connector workflows (e.g., Informatica + Snowflake) |
| **Top-10 Tools** | 15,878 tokens | **1,520 tokens** | **90.4%** | 2.1 ms | Broad multi-hop investigation across 3+ systems |

> **Design Note on Recall vs. Context Size:** Because aggressive filtering ($k=3$) can occasionally miss a secondary tool needed for a multi-system query, `top_k` is configurable per request (`1` to `25`) and supports optional `domain_filter` scoping or full catalog listing via the MCP `tools/list` endpoint. Automated benchmark tests (`tests/test_router_recall.py`) verify 100% Top-1 and Top-3 recall on standard domain intents.

---

## License
MIT License — Copyright (c) 2026 Ahmed S. Ali
