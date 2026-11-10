# Enterprise-MCP-Router: FastMCP Semantic Tool Gateway, Cloud Data Connectors & Agentic AI Governance

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP / JSON-RPC 2.0](https://img.shields.io/badge/Protocol-FastMCP%20%7C%20JSON--RPC%202.0-0ea5e9.svg)]()
[![AWS Bedrock AgentCore](https://img.shields.io/badge/AWS-Bedrock%20%7C%20AgentCore-ff9900.svg)]()
[![Snowflake Cortex](https://img.shields.io/badge/Snowflake-Cortex%20Search%20%7C%20RBAC-29b5e8.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-2.1-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/tests-14%20passed-brightgreen.svg)]()

A production-grade **Model Context Protocol (`FastMCP` / JSON-RPC 2.0)** gateway, **105-tool semantic router**, and **cloud data connector harness** engineered to move enterprise **Agentic AI** workloads (**LangGraph**, **Hugging Face `smolagents`**, **CrewAI**, and **Amazon Bedrock / AgentCore**) from prototype into controlled production across **Snowflake**, **Informatica Cloud (IICS)**, **PostgreSQL**, and **REST microservices**.

Includes an **interactive web control plane** (Tailwind CSS + Chart.js), a **JSON-RPC 2.0 MCP protocol server**, an automated **CLI benchmark runner (`run_demo.py`)**, and a **FastAPI REST server**.

---

## 🚀 Key Technical Pillars & Capabilities

1. **Standardized FastMCP Server & 105-Tool Semantic Router (`EnterpriseMCPRouter` & `FastMCPServer`):**
   - Full JSON-RPC 2.0 MCP protocol handler (`initialize`, `tools/list`, `tools/call`, `resources/list`) and `@mcp.tool()` decorator registration.
   - Pre-loaded with a **105-tool Enterprise MCP Catalog** across 7 enterprise namespaces (`snowflake.*`, `informatica.*`, `postgres.*`, `devops.*`, `supply_chain.*`, `crm_rest.*`, `knowledge_graph.*`).
   - Hybrid **dense cosine similarity + lexical BM25 boosting** filters 105 registered tool schemas (`16,382 tokens`) down to top-$k$ per turn (`~780 tokens` at $k=5$), cutting prompt context-window bloat by **95.24%** in **<2ms**.

2. **Deterministic OAuth2 RBAC & Stateful Human-in-the-Loop (HITL) Interrupt Queue:**
   - Enforces granular role-based access control (`analyst`, `ai_platform_reader`, `data_engineer`, `compliance_officer`, `platform_admin`) before tool invocation.
   - Intercepts mutating tool executions (`is_mutating=True`, e.g., outbound treasury wires, production Argo CD rollouts, Maestro worksheet overrides) and issues a stateful **HITL Interrupt Ticket** (`PENDING_APPROVAL` $\rightarrow$ `APPROVED` / `REJECTED`) with full audit trail logging.

3. **Governed Enterprise Data & Cloud Connectors (`src/connectors/`):**
   - **Snowflake Cortex Search & Read-Only SQL AST Guard (`SnowflakeCortexConnector`):** Strips obfuscated SQL comments, blocks multi-statement semicolon injection, enforces `SELECT`/`WITH`-only execution against allow-listed schemas (`PORTFOLIO_GOLD`, `CORTEX_DOCS`), blocks mutating DDL/DML (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `COPY`), and runs governed Cortex Search retrieval.
   - **Informatica Cloud (IICS) ELT Taskflow Validator (`InformaticaCloudTaskflowAdapter`):** Validates upstream IICS ELT webhook payloads, row-count thresholds, and Snowflake staging table freshness SLAs prior to RAG vector sync—automatically locking downstream RAG indexing on pipeline failure.
   - **PostgreSQL Transactional Ledger & Time-Travel Snapshots (`PostgresEnterpriseConnector`):** Parameterized relational queries, HITL-gated institutional wire execution, and instant point-in-time state snapshot/restore for deterministic rollback.
   - **Resilient REST Service Gateway (`EnterpriseRESTConnector`):** Circuit-breaker state machine (`CLOSED` $\rightarrow$ `OPEN` $\rightarrow$ `HALF_OPEN`) protecting downstream enterprise APIs.

4. **Amazon Bedrock / AgentCore Structured Outputs & Multi-Framework Bridges (`src/adapters/`):**
   - **Bedrock Converse API & Self-Healing Schema Verification (`BedrockAgentCoreAdapter`):** Compiles routed MCP tools into AWS Bedrock Converse `toolConfig` payloads and enforces required structured-output schema keys with automated self-healing retry prompts and token accounting.
   - **Native Agent Framework Exporters (`AgentFrameworkBridges`):** Converts routed MCP tools directly into **LangGraph** `ToolNode` definitions, **Hugging Face `smolagents`** `CodeAgent` Python signatures, and **CrewAI** `StructuredTool` specs.

5. **OpenTelemetry Tracing, Per-Use-Case Token Budgets & L2 Support Runbooks (`src/telemetry/`):**
   - Emits W3C `traceparent` spans (`00-<trace_id>-<span_id>-01`), computes p50/p95/p99 latency percentiles, enforces per-use-case token budget alerts (`TOKEN_BUDGET_EXCEEDED`), and generates standardized **L2 Operational Support Runbooks** across 6 enterprise incident classes.

---

## 📐 System Architecture & Mathematical Grounding

```
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │  Agent Runtimes: LangGraph | HF smolagents | CrewAI | Amazon Bedrock AgentCore   │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │ JSON-RPC 2.0 (tools/list, tools/call)
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │               Enterprise-MCP-Router (FastMCP Gateway Control Plane)              │
 │                                                                                  │
 │  ┌──────────────────────────────────┐    ┌────────────────────────────────────┐  │
 │  │ 1. Dense Semantic Tool Router    │    │ 2. OAuth2 RBAC & HITL Gate         │  │
 │  │ • 105 Enterprise Tools (16.4k t) │───▶│ • Role Scope Verification          │  │
 │  │ • Top-k Hybrid Filter (~780 t)   │    │ • Stateful HITL Interrupt Queue    │  │
 │  │ • 95.2% Context Token Reduction  │    │   (PENDING -> APPROVED / REJECTED) │  │
 │  └──────────────────────────────────┘    └─────────────────┬──────────────────┘  │
 └────────────────────────────────────────────────────────────┼─────────────────────┘
                                                              │ Authorized Call
        ┌─────────────────────────┬───────────────────────────┼────────────────────┐
        ▼                         ▼                           ▼                    ▼
 ┌──────────────┐        ┌─────────────────┐         ┌────────────────┐   ┌────────────────┐
 │  Snowflake   │        │ Informatica IICS│         │   PostgreSQL   │   │ OpenTelemetry  │
 │ Cortex + SQL │        │  ELT SLA Gate   │         │ Ledger & Snaps │   │ & L2 Runbooks  │
 │ Allow-Lister │        │ (RAG Sync Lock) │         │ (Time-Travel)  │   │ (Token Budget) │
 └──────────────┘        └─────────────────┘         └────────────────┘   └────────────────┘
```

### 1. Hybrid Dense + Lexical Semantic Routing Score
To prevent context-window degradation and tool-selection hallucination when scaling past 100+ enterprise tools, each tool $t_i \in \mathcal{T}$ is embedded into a unit-normalized vector $\mathbf{e}_i \in \mathbb{R}^d$. Given an agent turn query $q$ with normalized embedding $\mathbf{e}_q$ and query token set $W_q$, the router scores each tool via:

$$S(q, t_i) = \alpha \left( \frac{\mathbf{e}_q \cdot \mathbf{e}_i}{\|\mathbf{e}_q\|_2 \|\mathbf{e}_i\|_2} \right) + \min\left(\gamma_{\max}, \; \beta \sum_{w \in W_q} \mathbb{I}[w \in \text{desc}(t_i)]\right)$$

### 2. Context-Window Token Savings Ratio
Let $\tau(t_i)$ denote the JSON Schema token footprint of tool $t_i$. Filtering the full registry $\mathcal{T}$ ($|\mathcal{T}| = 105$) down to the top-$k$ subset $\mathcal{T}_k$ yields a per-turn prompt token reduction of:

$$\text{Token Reduction (\%)} = \left( 1 - \frac{\sum_{t \in \mathcal{T}_k} \tau(t)}{\sum_{t \in \mathcal{T}} \tau(t)} \right) \times 100\%$$

---

## 📊 Empirical Benchmarks (105-Tool Enterprise Registry)

| Top-$k$ Routed Tools | Full Registry Tokens (105 Tools) | Routed Schema Tokens | Context Token Reduction | Router Latency (p95) | Top-1 Domain Recall@k |
|---|---|---|---|---|---|
| **$k = 3$ Tools** | 16,382 tokens | **472 tokens** | **97.12%** | 1.62 ms | 99.1% |
| **$k = 5$ Tools (Default)** | 16,382 tokens | **780 tokens** | **95.24%** | 1.85 ms | 100.0% |
| **$k = 8$ Tools** | 16,382 tokens | **1,246 tokens** | **92.39%** | 2.04 ms | 100.0% |
| **$k = 10$ Tools** | 16,382 tokens | **1,558 tokens** | **90.49%** | 2.18 ms | 100.0% |

---

## 📁 Repository Structure

```
enterprise-mcp-router/
├── .github/
│   └── workflows/
│       └── ci.yml                      # GitHub Actions CI across Python 3.10, 3.11, 3.12
├── src/
│   ├── __init__.py
│   ├── main.py                         # FastAPI server, REST API & JSON-RPC 2.0 endpoints
│   ├── models.py                       # Pydantic v2 request/response data contracts
│   ├── router.py                       # EnterpriseMCPRouter, FastMCPServer & HITL state machine
│   ├── dashboard_html.py               # Interactive Web Control Plane UI (Tailwind + Chart.js)
│   ├── registry/
│   │   ├── __init__.py
│   │   └── catalog.py                  # 105-tool Enterprise MCP Catalog across 7 domains
│   ├── connectors/
│   │   ├── __init__.py
│   │   └── data_connectors.py          # Snowflake Cortex, Informatica IICS, PostgreSQL, REST
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── agent_adapters.py           # Amazon Bedrock AgentCore & LangGraph/smolagents/CrewAI
│   └── telemetry/
│       ├── __init__.py
│       └── observability.py            # OpenTelemetry spans, token budgets & L2 runbooks
├── tests/
│   ├── test_router.py                  # Core routing, RBAC/HITL, connectors & adapter unit tests
│   └── test_api.py                     # FastAPI REST & JSON-RPC 2.0 integration tests
├── run_demo.py                         # End-to-end CLI benchmark & simulation runner
├── Dockerfile                          # Production container image definition
├── requirements.txt                    # Runtime & test dependencies
├── pyproject.toml                      # PEP 517/518 package configuration
├── pytest.ini                          # Pytest runner configuration
├── LICENSE                             # MIT License
└── README.md                           # Project documentation
```

---

## 🛠️ Quickstart & Reproduction

### 1. Install Dependencies
```bash
git clone https://github.com/ahmedshahrukhali/enterprise-mcp-router.git
cd enterprise-mcp-router
pip install -r requirements.txt
```

### 2. Launch the Interactive Web Control Plane
Start the FastAPI server and open `http://localhost:8000` in your browser:
```bash
uvicorn src.main:app --reload --port 8000
```

### 3. Run the End-to-End CLI Benchmark Suite
```bash
python run_demo.py
```

### 4. Run the Automated Test Suite
```bash
pytest -v
```

---

## 🌐 REST & JSON-RPC 2.0 API Reference

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the interactive 5-tab Enterprise MCP Control Plane dashboard |
| `GET` | `/health` | Returns service health, 105-tool count, pending HITL tickets, and RAG lock status |
| `POST` | `/mcp/jsonrpc` | Standardized MCP JSON-RPC 2.0 endpoint (`initialize`, `tools/list`, `tools/call`, `resources/list`) |
| `POST` | `/api/v1/router/search` | Routes natural language intent to top-$k$ MCP tools and computes token reduction |
| `POST` | `/api/v1/governance/authorize` | Evaluates deterministic OAuth2 RBAC and HITL approval gates |
| `GET` | `/api/v1/governance/hitl` | Lists pending and resolved Human-in-the-Loop (HITL) interrupt tickets |
| `POST` | `/api/v1/governance/hitl/create` | Creates a stateful HITL approval ticket for a mutating MCP tool |
| `POST` | `/api/v1/governance/hitl/resolve` | Approves or rejects a pending HITL interrupt ticket |
| `POST` | `/api/v1/connectors/snowflake/validate-sql` | Validates Snowflake SQL against RBAC, schema allow-list, and DDL/DML blocklist |
| `POST` | `/api/v1/connectors/snowflake/cortex-search` | Runs governed Snowflake Cortex Search retrieval over compliance docs |
| `POST` | `/api/v1/connectors/informatica/validate` | Validates Informatica Cloud (IICS) ELT taskflow SLA and row counts prior to RAG sync |
| `POST` | `/api/v1/connectors/postgres/query` | Executes parameterized read-only SQL against the PostgreSQL institutional ledger |
| `POST` | `/api/v1/connectors/postgres/snapshot/create` | Creates a point-in-time state snapshot of the PostgreSQL ledger |
| `POST` | `/api/v1/connectors/postgres/snapshot/restore` | Restores PostgreSQL tables to a verified point-in-time snapshot |
| `POST` | `/api/v1/adapters/bedrock/invoke` | Invokes Amazon Bedrock / AgentCore with structured output verification & self-healing retry |
| `GET` | `/api/v1/adapters/bridges/{framework}` | Exports routed MCP tools into `langgraph`, `smolagents`, or `crewai` tool schemas |
| `GET` | `/api/v1/telemetry/summary` | Returns OpenTelemetry latency percentiles (p50/p95/p99), spans, and token budget alerts |
| `POST` | `/api/v1/telemetry/runbook` | Generates standardized L2 operational support runbooks for incident triage |

---

## 📄 License
MIT License. Copyright (c) 2026 Ahmed S. Ali.
