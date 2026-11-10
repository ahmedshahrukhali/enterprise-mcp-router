# Security Policy

## Security Architecture & Threat Model

Enterprise-MCP-Router is designed as a secure gateway between AI agent reasoning engines (LLMs) and institutional systems of record (Snowflake, Informatica Cloud, PostgreSQL, DevOps, ERPs).

```
                      ┌───────────────────────────────────────┐
                      │    AI Agent / Orchestrator / Caller   │
                      └──────────────────┬────────────────────┘
                                         │ Authentication (API Key / Bearer)
                                         ▼
                      ┌───────────────────────────────────────┐
                      │    FastMCP & REST API Gateway         │
                      │  - Identity & Role Derivation         │
                      │  - Semantic Top-k Context Filter      │
                      └──────────────────┬────────────────────┘
                                         │
                         Is tool mutating?
                        /                 \
                 [No: Read-Only]      [Yes: Mutating]
                       │                     │
                       ▼                     ▼
          ┌────────────────────────┐  ┌────────────────────────┐
          │  AST Safe SQL Guard    │  │  HITL Governance Gate  │
          │  (sqlglot inspection)  │  │  - Separation of Duties│
          │  - SELECT / CTEs only  │  │  - Ticket Expiry (TTL) │
          │  - Stacked SQL blocked │  │  - Single-Use Replay   │
          │  - SELECT INTO blocked │  │    Prevention          │
          └────────────┬───────────┘  └───────────┬────────────┘
                       │                          │
                       ▼                          ▼
          ┌───────────────────────────────────────────────────┐
          │     Institutional Systems (Snowflake / Postgres)  │
          └───────────────────────────────────────────────────┘
```

### 1. AST-Based Read-Only SQL Guard
- Uses `sqlglot` to parse and inspect abstract syntax trees (AST) across Snowflake and PostgreSQL dialects.
- Strictly permits `exp.Select` and `exp.Union` root statements (including CTEs).
- Detects and blocks `SELECT ... INTO` table-creation clauses.
- Blocks multi-statement stacked query injection (`SELECT 1; DROP TABLE ...`), while safely parsing semicolons embedded within string literals.
- Prevents false-positive blocks on column names or filter values (e.g., columns named `created_at` or filters like `WHERE method = 'GET'`).

### 2. Role-Based Access Control (RBAC) & Identity
- API callers authenticate via standard `X-API-Key` or `Authorization: Bearer <key>` headers.
- User roles are resolved cryptographically and mapped server-side, preventing unauthenticated privilege escalation.
- Super-admin and platform-admin roles are required to execute mutating operations, resolve approval tickets, or perform state snapshot restorations.

### 3. Human-in-the-Loop (HITL) Governance
- **Separation of Duties:** The reviewer who approves or rejects an interrupt ticket cannot be the same principal who requested the ticket (`reviewer != requested_by`).
- **Ticket Expiration (TTL):** Every interrupt ticket carries a time-to-live (`expires_at_epoch`, default 30 minutes). Expired tickets transition to `EXPIRED` and cannot be approved or used.
- **Single-Use Replay Prevention:** Once an approved ticket is consumed to authorize tool execution, its state immediately transitions to `CONSUMED`. Replaying the same ticket ID is rejected.
- **No Direct Mutation Bypass:** Mutating MCP tools cannot be executed via the public API with arbitrary boolean flags (`hitl_approved=True`); execution requires a valid, unconsumed, non-expired ticket ID.

### 4. Storage & Persistence
- State storage supports SQLite ACID persistence (`SQLiteStateStore`) and bounded in-memory queues (`InMemoryStateStore`).
- In-memory audit trails and OpenTelemetry trace spans use bounded deques to prevent memory exhaustion in high-throughput environments.

---

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please send an advisory or email to `ahmedshahrukhali@gmail.com` with:
- Summary of the vulnerability
- Reproduction steps or proof-of-concept payload
- Potential impact

We will review and acknowledge vulnerabilities within 48 hours and coordinate a fix.
