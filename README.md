# Enterprise-MCP-Router (`v2.3.0`)

**Zero-Trust Model Context Protocol (FastMCP / JSON-RPC 2.0 + SSE) Gateway, 120-Tool Hybrid BM25 + Dense Semantic Router, SQL AST Guard & Executive Light-Mode Control Plane**

Enterprise-MCP-Router solves tool-bloat, privilege escalation, SQL injection, and auditability failures when connecting LLM agents to enterprise data and execution systems:

1. **Zero-Trust Identity & Ticket-Bound Governance (Phase 0)**:
   - Client-supplied `user_roles` and `hitl_approved` bypass flags are stripped from API request schemas and ignored in JSON-RPC `tools/call`.
   - Caller roles are derived exclusively from verified **HS256 JWT Bearer tokens** (`Authorization: Bearer ...` / `POST /api/v1/auth/token`) or configured API keys (`X-API-Key`), with unauthenticated callers downgraded to read-only `["analyst", "ai_platform_reader"]`.
   - Every mutating tool execution requires a **single-use, TTL-expiring server HITL ticket** bound to the **canonical SHA-256 hash of `tool_name + arguments`** (`hitl_ticket_arguments_hash_mismatch` rejects any post-approval argument tampering).
   - Enforces **Separation of Duties** (`reviewer != requested_by`, HTTP `403`) and approver role validation via hierarchical RBAC.
2. **AST-Based SQL Guard (Phase 1)**:
   - Parses queries via **`sqlglot`** (Snowflake / PostgreSQL dialects) using a strict **single-`SELECT` AST allow-list**.
   - Blocks stacked statements, DML/DDL mutations, CTE data-modifying subqueries, `SELECT ... INTO`, locking clauses (`FOR UPDATE`, `FOR SHARE` via `exp.Lock`), and functions outside an explicit safe allow-list (blocking `SYSTEM$WHITELIST()`, `SYSTEM$CANCEL_ALL_QUERIES()`, `pg_sleep()`, `pg_read_file()`, `lo_import()`).
   - Correctly permits quoted SQL identifiers (e.g., `SELECT "update", "delete" FROM ...`) without brittle regex false positives.
   - Pairs app-level AST checks with `sqlite3.set_authorizer(READ_ONLY)` in the local SQLite sandbox.
3. **Role-Filtered Semantic Router & Honest Token Measurement (Phase 2 & 4)**:
   - Measures real serialized JSON Schema tokens across all **120 tools** (**33,453 serialized schema tokens** over `{"name","description","inputSchema"}`).
   - Filters candidate schemas by caller RBAC role before scoring (`analyst` callers never see `platform_admin` tools).
   - Supports **Okapi BM25 + Dense RRF** scoring with tuned blend weights `(0.25, 0.65, 0.10)`, automatic **`widen-k` fallback** on low-confidence/multi-domain queries, MCP **`tools/list` cursor pagination** (`cursor`, `page_size`, `nextCursor`, `domain_filter`), and a **tool-selection miss feedback loop** (`POST /api/v1/router/feedback`, `GET /api/v1/router/misses`).
4. **Tamper-Evident Audit Log, Rate Limiting & CI Hardening (Phase 3)**:
   - **SQLite WAL persistence** with **`BEFORE UPDATE` / `BEFORE DELETE` abort triggers** and **SHA-256 hash-chained `audit_events`** verifiable live via `GET /api/v1/governance/audit-verify`.
   - Per-principal **sliding-window rate limiter** (`429 rate_limit_exceeded`).
   - Non-root Docker image (`USER appuser`, UID `10001`) and GitHub Actions CI running `ruff`, `mypy`, `pip-audit`, `pytest --cov=src`, `run_demo.py`, and `docker build`.
5. **Executive Light-Mode Web Control Plane (`GET /`)**:
   - Clean, high-contrast Light Mode workspace with a top-header **JWT Session Persona Switcher**, live 160-query ablation charts, ticket-bound HITL approval workflow (including self-approval block vs peer approval), SQL AST Guard tester, Value Stream Management (VSM) Copilot, and OpenTelemetry monitor.

---

## Honest 160-Query Evaluation & Ablation Results

Evaluated using [`src/registry/eval_dataset.py`](src/registry/eval_dataset.py) across **160 labeled queries** (**120 single-domain** across 8 namespaces × 15 tools + **40 cross-domain** multi-tool queries) against the **120-tool / 33,453-token** registry:

| Scoring Configuration | Weights `(Dense, BM25, RRF)` | Recall@3 | Recall@5 | Recall@8 | Recall@10 | Recall@25 | Single@5 | Cross@5 | Mean Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `dense_only_hash64` | `(1.00, 0.00, 0.00)` | 0.6969 | 0.7500 | 0.8031 | 0.8531 | 0.9406 | 0.8000 | 0.6000 | 3.197 ms |
| `hybrid_default_55_35_10` | `(0.55, 0.35, 0.10)` | 0.8688 | 0.9125 | 0.9437 | 0.9500 | 0.9781 | 0.9417 | 0.8250 | 3.199 ms |
| `hybrid_widen_k5_fallback` *(27 widened)* | `(0.55, 0.35, 0.10)` | 0.8688 | 0.9156 | 0.9437 | 0.9500 | 0.9781 | 0.9417 | 0.8375 | 3.312 ms |
| `hybrid_lexical_heavy_30_60_10` | `(0.30, 0.60, 0.10)` | 0.9406 | 0.9656 | 0.9812 | 0.9875 | 1.0000 | 0.9750 | 0.9375 | 3.166 ms |
| **`hybrid_balanced_25_65_10` (Tuned Default)** | **`(0.25, 0.65, 0.10)`** | **0.9531** | **0.9844** | **0.9875** | **0.9875** | **1.0000** | **0.9917** | **0.9625** | **3.252 ms** |
| `bm25_only` | `(0.00, 1.00, 0.00)` | 0.9844 | 0.9938 | 0.9938 | 1.0000 | 1.0000 | 0.9917 | 1.0000 | 3.137 ms |

> **Engineering Note on Dense Embeddings & Schema Token Counting:**
> - **Dense Scorer:** Uses deterministic zero-dependency SHA-256 64-dim signed feature hashing. As the ablation proves, weighting noisy hash buckets at `0.55` hurt Recall@5 (`91.25%` vs `99.38%` BM25-only). Re-tuning to `(0.25, 0.65, 0.10)` lifted Hybrid Recall@5 to **`98.44%`**, with **~95.8%** prompt schema token savings (`~1,400` routed tokens vs `33,453` full-registry tokens at `k=5`). Production deployments with GPU/API budgets can swap the hash projector for a neural bi-encoder (e.g., `BAAI/bge-small-en-v1.5`).
> - **Token Counting:** Schema token counts serialize compact `{"name","description","inputSchema"}` JSON per tool and measure via `tiktoken` (`cl100k_base`) if installed or the regex BPE subword estimator (`_BPE_FALLBACK_RE`) offline.

---

## Live vs. Simulated Component Matrix

Every external boundary is explicitly labeled below so reviewers know what executes deterministically vs. what runs as an offline sandbox:

| Component | Status | Real Mechanics Implemented | Simulated / External Dependency Boundary |
| :--- | :--- | :--- | :--- |
| **MCP Protocol & Routing** | **Live In-Process** | FastAPI JSON-RPC 2.0 + SSE (`/mcp/jsonrpc`, `/mcp/messages`, `/mcp/sse`), `tools/list` cursor pagination, Okapi BM25 + dense RRF router, role filtering, miss feedback queue | Tool execution handlers beyond built-in SQLite/VSM/Snowflake/IICS return structured validated responses unless wired to live SaaS APIs |
| **RBAC, JWT & HITL Tickets** | **Live In-Process** | HMAC-SHA256 JWT (`create_jwt_token` / `verify_jwt_token`), role hierarchy, single-use TTL tickets bound to canonical `SHA-256(tool + args)`, SoD enforcement | Demo helper `POST /api/v1/auth/token` mints session JWTs (disable in prod via `MCP_DISABLE_DEMO_TOKEN_MINT=1` & external OIDC IdP) |
| **SQL AST Guard** | **Live In-Process** | `sqlglot` AST allow-list (Snowflake/Postgres dialects), `exp.Lock` + function allow-list blocking `SYSTEM$*`/`pg_*` | Requires read-only DB roles + `SET TRANSACTION READ ONLY` when pointed at live Snowflake/Postgres clusters |
| **Persistence & Audit Chain** | **Live SQLite WAL** | SQLite WAL `hitl_tickets`, `ledger_snapshots`, `telemetry_spans`, plus `BEFORE UPDATE`/`DELETE` abort triggers & SHA-256 hash-chained `audit_events` | Local SQLite relational store stands in for an institutional PostgreSQL cluster (`PostgresEnterpriseConnector` uses `sqlite3.set_authorizer`) |
| **Snowflake Cortex & IICS** | **Hybrid / Sandbox** | Real AST guard, circuit-breaker lock state, SLA threshold evaluation, and in-memory corpus search | Returns local compliance docs & simulated warehouse execution unless Snowflake/IICS credentials are configured |
| **Amazon Bedrock & OTel** | **Hybrid / Sandbox** | Schema verification retry loop, Converse tool config formatting, W3C `traceparent` spans & token alerts | Uses simulated flaky provider fallback unless live `boto3` Bedrock runtime + external OTLP collector are configured |

---

## Quickstart & Verification

```bash
# Install dependencies (including dev lint/security checks)
pip install -r requirements.txt

# Run the complete 37-test security, SQL AST adversarial, API & 160-query recall suite
pytest -v

# Run end-to-end CLI benchmark & 6-pillar smoke verification
python run_demo.py

# Launch FastAPI server + Executive Light Mode Control Plane at http://127.0.0.1:8000
uvicorn src.main:app --reload
```

### Demo Credentials (`X-API-Key` or UI JWT Switcher)
- `ak-analyst-demo` (`analyst` — read-only discovery & queries)
- `ak-engineer-demo` (`data_engineer`, `analyst`)
- `ak-admin-demo` (`platform_admin` — can request wires/rollbacks/snapshot restores)
- `ak-superadmin-demo` (`super_admin` — peer reviewer for HITL ticket resolution)
