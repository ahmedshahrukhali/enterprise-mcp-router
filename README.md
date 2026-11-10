# Enterprise-MCP-Router

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP / JSON-RPC 2.0](https://img.shields.io/badge/Protocol-FastMCP%20%7C%20JSON--RPC%202.0-0ea5e9.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-2.1-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/tests-14%20passed-brightgreen.svg)]()

**A routing and governance gateway that sits between AI agents (Claude, GPT, open-weight models) and internal company databases, data pipelines, and APIs.**

---

## Overview

Connecting an AI agent to 5 tools in a local prototype is straightforward. Scaling that same agent to **100+ internal tools** across a company (Snowflake, Informatica, PostgreSQL, Jira, GitHub, ERP systems) usually breaks down in three places:

1. **Tool Schema Bloat in the Prompt:**
   Whenever an LLM uses tool-calling, the full JSON Schema definition of *every* available tool has to be injected into the prompt context on every turn. With 100+ tools across multiple connectors, you burn **~15,000+ input tokens per message** just listing tool definitions—and models start picking the wrong tool when descriptions overlap.
   * **What this repo does:** Before calling the model, the router runs a fast hybrid search (cosine similarity + keyword matching) over the 105 registered tools and passes **only the top-$k$ relevant tool schemas** for that turn.

2. **Unchecked Write Access to Production Systems:**
   Reading a report is safe; executing an outbound bank wire, running a `DROP TABLE` query, or triggering a production deployment without human sign-off is not.
   * **What this repo does:** Every tool call passes through a role check (**RBAC**). Read-only tools run immediately, SQL queries are inspected to block destructive commands (`DROP`, `DELETE`, `UPDATE`), and any tool marked as mutating pauses execution and creates a **Human-in-the-Loop (HITL) approval ticket** until a reviewer approves it.

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
   │                    ├─ No (Read-Only) ──▶ Executes tool immediately
   │                    └─ Yes (Mutating) ──▶ Pauses & queues a Human Approval Ticket
   ▼
3. Safe Connectors ──▶ Snowflake (SELECT-only guard & Cortex Search)
   │                   Informatica IICS (ELT freshness & row-count gate)
   │                   PostgreSQL (Parameterized queries & 1-click table snapshots)
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

# 3. Run the 14 automated unit & API tests
pytest -v
```

---

## What's Inside the Interactive Dashboard (`http://localhost:8000`)

* **Tab 1 — Semantic Tool Router:** Type any plain-English task (or click a preset) and watch how it scores the 105 tools across domains and trims the prompt schema footprint.
* **Tab 2 — RBAC & Human Approval Queue:** Test how read-only vs. mutating tools behave under different user roles (`analyst`, `data_engineer`, `platform_admin`), and approve or reject queued agent actions.
* **Tab 3 — Data Connectors (Snowflake, Informatica, Postgres):** Test the read-only SQL filter against `DROP TABLE` injection, check Informatica ELT pipeline SLAs, and test instant Postgres table snapshots/rollbacks.
* **Tab 4 — Bedrock & Framework Bridges:** Export routed tools directly into **Amazon Bedrock (`toolConfig`)**, **LangGraph (`ToolNode`)**, **Hugging Face `smolagents`**, or **CrewAI**, and test automatic retry when a model output misses a required JSON field.
* **Tab 5 — Telemetry & Runbooks:** Inspect W3C trace spans, per-use-case token budget alerts, and step-by-step L2 incident triage guides.

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

> **Design Note on Recall vs. Context Size:** Because aggressive filtering ($k=3$) can occasionally miss a secondary tool needed for a multi-system query, `top_k` is configurable per request (`1` to `25`) and supports optional `domain_filter` scoping or full catalog listing via the MCP `tools/list` endpoint.

---

## License
MIT License — Copyright (c) 2026 Ahmed S. Ali
