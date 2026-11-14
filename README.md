# Enterprise-MCP-Router (`v2.3.0`)

**Fail-Closed Model Context Protocol (FastMCP / JSON-RPC 2.0 + SSE) Gateway, 120-Tool Hybrid BM25 + `BAAI/bge-small-en-v1.5` Router, AST SQL Guard & Executive Light-Mode Control Plane**

Enterprise-MCP-Router addresses tool-bloat, privilege escalation, SQL injection, and auditability gaps when connecting LLM agents to relational stores, warehouses, and execution APIs:

1. **Fail-Closed Identity & Group-Separated HITL Governance**:
   - Server lifespan startup raises `RuntimeError` unless `ROUTER_JWT_SECRET`, `ROUTER_JWT_PUBLIC_KEY_PEM`, or `ROUTER_JWKS_JSON` is configured, or `ROUTER_DEV_MODE=1` is explicitly enabled.
   - All `/api/v1/*` and `/mcp/jsonrpc` endpoints fail closed (`401`) for unauthenticated callers unless `ROUTER_DEV_MODE=1`.
   - Demo API keys (`ak-*-demo`) and `POST /api/v1/auth/token` are disabled by default; even in dev mode, `/api/v1/auth/token` is capped to the `platform_operators` group and cannot mint `super_admin` or `hitl_approvers`.
   - Verifies both **RS256** (OIDC / JWKS `kid` lookup) and **HS256** JWTs, enforcing `exp`, `sub`, `iss`, and `aud` claims.
   - Mutating tool calls require a single-use, TTL-expiring ticket bound to the **canonical SHA-256 hash of `tool_name + arguments`** (`hitl_ticket_arguments_hash_mismatch` blocks post-approval argument mutation).
   - Approvers must be distinct (`reviewer != requested_by`), hold an approver role, and belong to the dedicated **`hitl_approvers` group** (`reviewer_missing_approver_group` -> HTTP `403`), preventing dual-account operator self-approval (`mallory` + `sock_puppet`).

2. **AST-Based SQL & Table Allow-List Guard**:
   - Parses SQL via **`sqlglot`** (Snowflake / PostgreSQL / SQLite dialects) using a single-`SELECT` / `UNION` AST shape allow-list.
   - Walks every `exp.Table` AST node (covering `FROM`, `JOIN`, `UNION`/`UNION ALL`, subqueries, and CTE bodies) to enforce schema and table allow-lists (`PORTFOLIO_GOLD.FUNDS`, `ACCOUNTS`, etc.), enforce the `schema` parameter directly against AST tables, reject unexpected catalogs or unqualified Snowflake tables, and block CTE table shadowing (`WITH FUNDS AS (...)` -> `cte_table_shadowing_blocked`).
   - Rejects `SELECT INTO`, locking clauses (`exp.Lock`), and unsafe functions outside an allow-list (`SYSTEM$*`, `pg_sleep`, `pg_read_file`, `lo_import`), while preserving safe quoted column identifiers (`SELECT "update" FROM ...`) and pairing local execution with `sqlite3.set_authorizer(READ_ONLY)`.

3. **Role-Filtered Semantic Router (`BAAI/bge-small-en-v1.5` + Okapi BM25)**:
   - Measures serialized JSON Schema tokens across all **120 tools** (**33,453 tokens** over `{"name","description","inputSchema"}`).
   - Filters candidates by caller RBAC role before scoring (`analyst` callers never see `platform_admin` tools).
   - Supports `hybrid_bge_bm25`, `bge_small_only` (384-dim `BAAI/bge-small-en-v1.5`), `bm25_only`, `hybrid` (64-dim hash + BM25), `dense_only` (hash64), automatic **`widen-k` fallback**, MCP `tools/list` cursor pagination, and a routing miss feedback queue.

4. **Default SQLite WAL Persistence & Hash-Chained Audit Log**:
   - Defaults to **SQLite WAL persistence** (`SQLiteStateStore` unless `ROUTER_STORAGE_BACKEND=memory` is set), hydrating pending/resolved HITL tickets and recent audit history across router restarts.
   - `audit_events` enforces `BEFORE UPDATE` / `BEFORE DELETE` abort triggers and SHA-256 hash chaining (`prev_hash -> entry_hash`), verifiable via `GET /api/v1/governance/audit-verify`.
   - Non-root Docker image (`USER appuser`, UID `10001`) and GitHub Actions CI running `ruff`, `mypy`, `pip-audit`, `pytest --cov=src`, `run_demo.py`, and `docker build`.

5. **Executive Light-Mode Control Plane (`GET /`)**:
   - Served from [`src/static/index.html`](src/static/index.html) via [`src/dashboard_html.py`](src/dashboard_html.py), featuring an Operator Session Switcher, 200-query held-out benchmark charts, ticket-bound HITL workflow, AST table allow-list SQL tester, VSM advisor, and OpenTelemetry monitor.

---

## Evaluation & Held-Out Benchmark Results (200 Queries)

Evaluated using [`src/registry/eval_dataset.py`](src/registry/eval_dataset.py) across **200 labeled queries** (**96 Train** + **104 Held-Out Test**, where Held-Out comprises **64 standard held-out queries** and **40 newly authored paraphrased/adversarial zero-overlap queries**) over the **120-tool / 33,453-token** registry:

### Held-Out Test Split (`104` Unseen Queries: `64` Standard + `40` Paraphrased Zero-Overlap)

| Configuration | Recall@3 | Recall@5 | Recall@8 | Recall@10 | Recall@25 | Single@5 | Cross@5 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `dense_only_hash64` | 0.4231 | 0.4952 | 0.5240 | 0.6106 | 0.7837 | 0.5000 | 0.4792 |
| `hybrid_hash64_default_55_35_10` | 0.6490 | 0.7067 | 0.7452 | 0.7500 | 0.8269 | 0.7250 | 0.6458 |
| `hybrid_hash64_tuned_25_65_10` | 0.7404 | 0.7644 | 0.7740 | 0.7981 | 0.8606 | 0.7625 | 0.7708 |
| `bm25_only` | 0.7885 | 0.8269 | 0.8365 | 0.8365 | 0.8750 | 0.8250 | 0.8333 |
| `bge_small_only` *(384-dim)* | **0.8798** | 0.8990 | **0.9231** | **0.9375** | **0.9856** | 0.9250 | 0.8125 |
| `hybrid_bge_bm25_45_45_10` | 0.8317 | 0.8798 | **0.9231** | **0.9375** | 0.9808 | 0.8875 | 0.8542 |
| `hybrid_bge_widen_k5_fallback` *(22 widened)* | 0.8317 | **0.9279** | **0.9231** | **0.9375** | 0.9808 | **0.9375** | **0.8958** |

### Train vs. Held-Out Standard vs. Paraphrased Adversarial Breakdown (Recall@5)

| Configuration | Train (`96`) | Held-Out Std (`64`) | Held-Out Paraphrased (`40`) | Combined Held-Out (`104`) |
| :--- | :---: | :---: | :---: | :---: |
| `dense_only_hash64` | 0.7865 | 0.6953 | 0.1750 | 0.4952 |
| `hybrid_hash64_tuned_25_65_10` | 0.9792 | 0.9922 | 0.4000 | 0.7644 |
| `bm25_only` | 0.9896 | **1.0000** | 0.5500 | 0.8269 |
| `bge_small_only` *(384-dim)* | 0.9896 | 0.9766 | **0.7750** | 0.8990 |
| `hybrid_bge_bm25_45_45_10` | **0.9948** | **1.0000** | 0.6875 | 0.8798 |
| `hybrid_bge_widen_k5_fallback` | **0.9948** | **1.0000** | **0.8125** | **0.9279** |

> **Honest Conclusion on Embeddings vs. BM25:**
> - **The 64-dim signed feature-hashing baseline (`hash64`) adds nothing over Okapi BM25.** On vocabulary-matched queries (`Held-Out Std 64`), `bm25_only` reaches **1.0000** Recall@5, whereas adding `hash64` drops Recall@5 (`0.9922` / `0.9141`) and collapses to **0.1750** on paraphrased queries.
> - **A real pretrained dense bi-encoder (`BAAI/bge-small-en-v1.5`, 384-dim) provides real lift on paraphrased zero-overlap intents:** on the 40 paraphrased/adversarial queries, `bge_small_only` reaches **0.7750** Recall@5 (+22.5 points above `bm25_only`'s **0.5500**), and `hybrid_bge_bm25` + `auto_widen` reaches **0.8125** Recall@5 on paraphrased queries (**0.9279** overall across all 104 held-out queries) while cutting routed schema tokens by ~95% at `k=5`.
> - For deterministic, fast offline/CI runs without downloading model weights, precomputed normalized 384-dim embeddings for the catalog and evaluation suite live in [`src/registry/bge_cache.json`](src/registry/bge_cache.json), with live `BAAI/bge-small-en-v1.5` inference for unseen runtime queries when `transformers` + `torch` are installed.

---

## Live vs. Simulated Component Matrix

| Component | Mode | What Actually Executes | Simulated / External Boundary |
| :--- | :--- | :--- | :--- |
| **MCP Protocol & Routing** | `live_in_process` | FastAPI JSON-RPC 2.0 + SSE (`/mcp/jsonrpc`, `/mcp/messages`, `/mcp/sse`), `tools/list` cursor pagination, BGE-small/BM25 RRF router, role filtering, miss feedback queue | Tool execution calls outside SQLite/VSM return contextual domain telemetry labeled `"execution_mode": "sandbox_simulation"` unless wired to external SaaS APIs |
| **RBAC, OIDC/JWT & HITL** | `live_in_process` | Fail-closed auth & startup guard, `RS256` (JWKS) & `HS256` JWT verification (`iss`/`aud`), single-use TTL tickets bound to `SHA-256(tool + args)`, SoD + `hitl_approvers` group check | Local `/api/v1/auth/token` & `ak-*-demo` keys exist strictly for `ROUTER_DEV_MODE=1` demos and are disabled by default |
| **SQL AST & Table Guard** | `live_in_process` | `sqlglot` AST statement check + `exp.Table` schema/table positive allow-listing + CTE shadowing block + `sqlite3.set_authorizer(READ_ONLY)` | When connected to live Snowflake/PostgreSQL clusters, pair with read-only DB roles and `SET TRANSACTION READ ONLY` |
| **Persistence & Audit Chain** | `live_sqlite` | Default SQLite WAL store (`enterprise_router.db`), `BEFORE UPDATE`/`DELETE` abort triggers, SHA-256 hash-chained `audit_events`, startup ticket hydration | Set `ROUTER_STORAGE_BACKEND=memory` for ephemeral runs |
| **VSM & Ledger Queries** | `live_sqlite` | Real relational SQLite tables (`product_portfolios`, `objectives_okrs`, `engineering_tickets`, `accounts`, `audit_log`) with rollback snapshots (`execution_mode: "live_sqlite"`) | Pre-seeded local SQLite relational tables simulate external Planview / PostgreSQL hosts |
| **Snowflake, IICS, Bedrock & OTel** | `sandbox_simulation` | SQL AST validation, Cortex keyword retrieval, IICS SLA gate, Bedrock retry validation loop, W3C `traceparent` spans | Uses local fixtures/simulated provider fallback unless live Snowflake, IICS, AWS Bedrock, or OTLP collector endpoints are configured |

---

## Quickstart & Verification

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pytest suite (tests/conftest.py isolates ROUTER_DEV_MODE=1 + temp SQLite DB;
# dedicated fail-closed tests explicitly unset ROUTER_DEV_MODE to verify startup refusal & 401/403)
pytest -v

# Run CLI benchmark & governance smoke verification (uses ROUTER_DEV_MODE=1)
python run_demo.py

# Start locally in dev mode with interactive Control Plane at http://127.0.0.1:8000
ROUTER_DEV_MODE=1 uvicorn src.main:app --reload

# Start fail-closed (requires external RS256 JWKS or HS256 secret; refuses startup without credentials)
ROUTER_JWKS_JSON='{"keys":[...]}' ROUTER_JWT_ISSUER="https://idp.example.com" ROUTER_JWT_AUDIENCE="mcp-gateway" uvicorn src.main:app
```

### Dev-Only Credentials (`ROUTER_DEV_MODE=1` only; disabled by default)
- `ak-analyst-demo` (`analyst`, group `platform_operators`)
- `ak-engineer-demo` (`data_engineer`, `analyst`, group `platform_operators`)
- `ak-admin-demo` (`platform_admin`, group `platform_operators`)
- `ak-superadmin-demo` (`super_admin`, `compliance_officer`, group `hitl_approvers` — peer approver)
