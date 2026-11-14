# Security Policy

## Security Architecture & Threat Model

Enterprise-MCP-Router acts as a governed gateway between AI agent callers and relational, warehouse, or API tool backends (Snowflake, Informatica Cloud, PostgreSQL/SQLite, DevOps, ERP/VSM).

```
                      ┌───────────────────────────────────────┐
                      │    AI Agent / Orchestrator / Caller   │
                      └──────────────────┬────────────────────┘
                                         │ Fail-Closed Identity (OIDC/JWKS RS256 or HS256 / API Key)
                                         ▼
                      ┌───────────────────────────────────────┐
                      │    FastMCP & REST API Gateway         │
                      │  - Fail-Closed 401 by Default         │
                      │  - Semantic Top-k Role-Filtered Route │
                      └──────────────────┬────────────────────┘
                                         │
                         Is tool mutating?
                        /                 \
                 [No: Read-Only]      [Yes: Mutating]
                       │                     │
                       ▼                     ▼
          ┌────────────────────────┐  ┌────────────────────────┐
          │  AST Safe SQL Guard    │  │  HITL Governance Gate  │
          │  (sqlglot inspection)  │  │  - Separate Approver   │
          │  - SELECT / UNION only │  │    Group (hitl_approvers)
          │  - exp.Table & Schema  │  │  - reviewer != requester
          │    Positive Allow-List │  │  - Canonical Args SHA256
          │  - CTE Shadowing Block │  │  - Single-Use + TTL      │
          └────────────┬───────────┘  └───────────┬────────────┘
                       │                          │
                       ▼                          ▼
          ┌───────────────────────────────────────────────────┐
          │   Backends (Snowflake / Postgres / Local SQLite)  │
          └───────────────────────────────────────────────────┘
```

### 1. Fail-Closed Identity & OIDC/JWT Verification
- **Startup Credential Guard:** Server lifespan startup refuses to boot (`RuntimeError`) unless a JWT HMAC secret (`ROUTER_JWT_SECRET`) or asymmetric verification key (`ROUTER_JWT_PUBLIC_KEY_PEM` / `ROUTER_JWKS_JSON`) is configured, or `ROUTER_DEV_MODE=1` is explicitly enabled.
- **No Unauthenticated Access by Default:** All `/api/v1/*` and `/mcp/jsonrpc` endpoints fail closed (`401`) without valid credentials unless `ROUTER_DEV_MODE=1` is active for local testing.
- **Disabled Demo Keys & Token Minting:** Demo API keys (`ak-*-demo`) and `POST /api/v1/auth/token` are disabled by default (`401`/`403`). Even in dev mode, `/api/v1/auth/token` is capped to the `platform_operators` group and cannot mint `super_admin` or `hitl_approvers`.
- **Asymmetric & Symmetric JWT Verification:** Supports `RS256` (via `ROUTER_JWKS_JSON` key lookup by `kid` or `ROUTER_JWT_PUBLIC_KEY_PEM`) and `HS256`, strictly validating `exp`, `sub`, `iss`, and `aud` claims.

### 2. Human-in-the-Loop (HITL) Governance & Dual-Account Defense
- **Dedicated Approver Group:** Ticket approval requires BOTH an authorized reviewer role (`platform_admin` or `super_admin`) AND membership in the dedicated `hitl_approvers` group (`reviewer_missing_approver_group` -> HTTP `403`). This prevents two operator accounts in `platform_operators` from approving each other's requests.
- **Separation of Duties:** `reviewer != requested_by`.
- **Canonical Argument Hash Binding:** Each ticket binds `SHA-256(tool_name + canonical_arguments)`. Argument mutation after approval fails with `hitl_ticket_arguments_hash_mismatch`.
- **TTL Expiration & Single-Use Consumption:** Approved tickets expire by epoch timestamp (`EXPIRED`) and transition to `CONSUMED` upon first execution (`hitl_ticket_already_consumed`).

### 3. AST-Based Read-Only SQL & Table Allow-List Guard
- Uses `sqlglot` (Snowflake and PostgreSQL dialects) to permit only single `exp.Select` / `exp.Union` root statements.
- Walks every `exp.Table` AST node across `FROM`, `JOIN`, `UNION`/`UNION ALL`, subqueries, and CTE bodies:
  - Enforces positive schema and qualified table allow-lists (`PORTFOLIO_GOLD.FUNDS`, etc.) and validates the declared `schema` parameter directly against AST table nodes.
  - Blocks CTE table shadowing (e.g., `WITH FUNDS AS (...)`) via `cte_table_shadowing_blocked`.
  - Rejects `SELECT INTO`, locking clauses (`exp.Lock`), unsafe SQL functions outside the safe allow-list (`SYSTEM$*`, `pg_sleep`, `pg_read_file`, `lo_import`), and multi-statement stacked payloads.
- Preserves safe quoted column identifiers (e.g., `SELECT "update" FROM ...`) without regex false positives, and pairs local execution with `sqlite3.set_authorizer(READ_ONLY)`.

### 4. Default Durable Storage & Tamper-Evident Audit Chain
- Defaults to SQLite WAL (`SQLiteStateStore`) with `BEFORE UPDATE` / `BEFORE DELETE` abort triggers on `audit_events` and SHA-256 hash chaining (`prev_hash -> entry_hash`), hydrating tickets and audit history across router restarts.
- Use `ROUTER_STORAGE_BACKEND=memory` only when ephemeral in-memory testing is desired.

---

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please send an advisory or email to `ahmedshahrukhali@gmail.com` with:
- Summary of the vulnerability
- Reproduction steps or proof-of-concept payload
- Potential impact

We will review and acknowledge vulnerabilities within 48 hours and coordinate a fix.
