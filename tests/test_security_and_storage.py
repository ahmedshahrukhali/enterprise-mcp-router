"""
Security, AST SQL Guard, HITL Governance, and Persistence Tests for Enterprise-MCP-Router.
Verifies:
1. AST SQL injection defenses (semicolon inside strings, SELECT INTO, keywords in columns/values)
2. HITL Governance (self-approval prevention, expiration TTL, single-use replay defense, ticket requirement)
3. SQLiteStateStore persistence and thread safety
4. API Key authentication and RBAC role derivation
"""

import json
import os
import sqlite3
import tempfile
import time
import pytest
from fastapi.testclient import TestClient

from src.connectors.data_connectors import (
    PostgresEnterpriseConnector,
    SnowflakeCortexConnector,
    ValueStreamManagementConnector,
)
from src.connectors.sql_guard import SafeSQLValidator
from src.main import app, mcp_router
from src.router import EnterpriseMCPRouter
from src.security import (
    DEFAULT_RATE_LIMITER,
    create_jwt_token,
    create_rs256_jwt_token,
    generate_rsa_keypair_and_jwks,
    validate_security_config,
    verify_jwt_token,
)
from src.storage import SQLiteStateStore, get_default_storage, reset_default_storage

client = TestClient(app)


def test_sql_guard_ast_hardened_defenses():
    # 1. Column and string containing 'GET' / 'CREATE' should NOT be falsely blocked
    valid_query = "SELECT created_at, nav FROM PORTFOLIO_GOLD.FUNDS WHERE call_type = 'GET'"
    res = SafeSQLValidator.validate_readonly_sql(
        sql=valid_query,
        dialect="snowflake",
        allowed_roles={"ai_platform_reader"},
        allowed_schemas={"PORTFOLIO_GOLD"},
        role="ai_platform_reader",
        schema="PORTFOLIO_GOLD",
    )
    assert res["valid"] is True
    assert "GET" in res["normalized_sql"]

    # 2. Semicolon inside string literal should be allowed as a single statement
    semicolon_str_query = "SELECT fund_id FROM PORTFOLIO_GOLD.FUNDS WHERE memo = 'benchmark; run 2'"
    res_str = SafeSQLValidator.validate_readonly_sql(
        sql=semicolon_str_query,
        dialect="snowflake",
        allowed_roles={"ai_platform_reader"},
        allowed_schemas={"PORTFOLIO_GOLD"},
        role="ai_platform_reader",
        schema="PORTFOLIO_GOLD",
    )
    assert res_str["valid"] is True

    # 3. Stacked multi-statement execution MUST be blocked
    stacked = "SELECT * FROM PORTFOLIO_GOLD.FUNDS; DROP TABLE FUNDS"
    res_stacked = SafeSQLValidator.validate_readonly_sql(
        sql=stacked,
        dialect="snowflake",
        allowed_roles={"ai_platform_reader"},
        allowed_schemas={"PORTFOLIO_GOLD"},
        role="ai_platform_reader",
        schema="PORTFOLIO_GOLD",
    )
    assert res_stacked["valid"] is False
    assert res_stacked["reason"] == "mutating_sql_keyword_blocked"

    # 4. SELECT INTO bypass in PostgreSQL dialect MUST be blocked
    select_into = "SELECT * INTO new_table FROM accounts"
    res_into = SafeSQLValidator.validate_readonly_sql(
        sql=select_into,
        dialect="postgres",
        allowed_roles={"analyst"},
        role="analyst",
    )
    assert res_into["valid"] is False
    assert res_into["reason"] == "mutating_sql_keyword_blocked"

    # 5. Comment-obfuscated attack should be analyzed and blocked
    comment_attack = "/* safe comment */ DROP TABLE PORTFOLIO_GOLD.FUNDS"
    res_comment = SafeSQLValidator.validate_readonly_sql(
        sql=comment_attack,
        dialect="snowflake",
        allowed_roles={"ai_platform_reader"},
        allowed_schemas={"PORTFOLIO_GOLD"},
        role="ai_platform_reader",
        schema="PORTFOLIO_GOLD",
    )
    assert res_comment["valid"] is False
    assert res_comment["reason"] == "mutating_sql_keyword_blocked"


def test_hitl_self_approval_and_role_enforcement():
    router = EnterpriseMCPRouter.from_enterprise_catalog()

    # Create ticket requested by 'alice_agent'
    ticket = router.create_hitl_interrupt(
        tool_name="postgres.execute_outbound_wire",
        requested_by="alice_agent",
        user_roles=["platform_admin"],
        arguments={"amount_usd": 75000},
    )
    ticket_id = ticket["ticket_id"]

    # 1. Requester cannot approve their own ticket (Separation of Duties)
    self_approve = router.resolve_hitl_interrupt(
        ticket_id=ticket_id,
        reviewer="alice_agent",
        decision="APPROVED",
    )
    assert self_approve["status"] == "error"
    assert self_approve["reason"] == "self_approval_prohibited"

    # 2. Reviewer lacking platform_admin or super_admin cannot approve
    unauthorized_approve = router.resolve_hitl_interrupt(
        ticket_id=ticket_id,
        reviewer="charlie_analyst",
        decision="APPROVED",
        reviewer_roles=["analyst"],
    )
    assert unauthorized_approve["status"] == "error"
    assert unauthorized_approve["reason"] == "reviewer_not_authorized"

    # 3. Same-group operator without hitl_approvers group is blocked (defeats sock-puppet)
    missing_group = router.resolve_hitl_interrupt(
        ticket_id=ticket_id,
        reviewer="sock_puppet_admin",
        decision="APPROVED",
        reviewer_roles=["super_admin", "platform_admin"],
        reviewer_groups=["platform_operators"],
    )
    assert missing_group["status"] == "error"
    assert missing_group["reason"] == "reviewer_missing_approver_group"

    # 4. Legitimate authorized reviewer in dedicated hitl_approvers group can approve
    valid_approve = router.resolve_hitl_interrupt(
        ticket_id=ticket_id,
        reviewer="bob_security_lead",
        decision="APPROVED",
        reviewer_roles=["platform_admin"],
        reviewer_groups=["hitl_approvers"],
    )
    assert valid_approve["status"] == "APPROVED"


def test_hitl_ticket_expiration_and_replay_prevention():
    router = EnterpriseMCPRouter.from_enterprise_catalog()

    # 1. Test expiration with short TTL
    ticket_exp = router.create_hitl_interrupt(
        tool_name="postgres.execute_outbound_wire",
        requested_by="timely_agent",
        user_roles=["platform_admin"],
        ttl_seconds=-10,  # Already expired
    )
    resolve_exp = router.resolve_hitl_interrupt(
        ticket_id=ticket_exp["ticket_id"],
        reviewer="ops_manager",
        decision="APPROVED",
    )
    assert resolve_exp["status"] == "error"
    assert resolve_exp["reason"] == "hitl_ticket_expired"

    # 2. Test Single-Use (Replay Prevention)
    ticket_live = router.create_hitl_interrupt(
        tool_name="postgres.execute_outbound_wire",
        requested_by="agent_x",
        user_roles=["platform_admin"],
        ttl_seconds=1800,
    )
    router.resolve_hitl_interrupt(
        ticket_id=ticket_live["ticket_id"],
        reviewer="approver_y",
        decision="APPROVED",
        reviewer_roles=["platform_admin"],
        reviewer_groups=["hitl_approvers"],
    )

    # First authorization consumes the ticket
    auth_first = router.authorize_execution(
        tool_name="postgres.execute_outbound_wire",
        user_roles=["platform_admin"],
        hitl_ticket_id=ticket_live["ticket_id"],
    )
    assert auth_first["allowed"] is True

    # Second authorization with the same ticket is blocked (replay defense)
    auth_replay = router.authorize_execution(
        tool_name="postgres.execute_outbound_wire",
        user_roles=["platform_admin"],
        hitl_ticket_id=ticket_live["ticket_id"],
    )
    assert auth_replay["allowed"] is False
    assert auth_replay["reason"] == "hitl_ticket_already_consumed"


def test_api_cannot_bypass_hitl_without_ticket():
    # 1. Unauthenticated caller supplying client user_roles + hitl_approved is downgraded to anonymous_readonly -> rbac_denied
    anon_resp = client.post(
        "/api/v1/governance/authorize",
        json={
            "tool_name": "postgres.execute_outbound_wire",
            "user_roles": ["platform_admin"],
            "hitl_approved": True,
            "hitl_ticket_id": None,
        },
    )
    anon_data = anon_resp.json()
    assert anon_data["allowed"] is False
    assert anon_data["reason"] == "rbac_denied"

    # 2. Authenticated platform_admin attempting hitl_approved=True without server ticket -> hitl_ticket_required
    admin_resp = client.post(
        "/api/v1/governance/authorize",
        headers={"X-API-Key": "ak-admin-demo"},
        json={
            "tool_name": "postgres.execute_outbound_wire",
            "hitl_approved": True,
            "hitl_ticket_id": None,
        },
    )
    admin_data = admin_resp.json()
    assert admin_data["allowed"] is False
    assert admin_data["reason"] == "hitl_ticket_required"


def test_sqlite_persistence_across_reloads():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    store1 = None
    store2 = None
    try:
        # Create store 1 and write ticket & snapshot
        store1 = SQLiteStateStore(db_path)
        router1 = EnterpriseMCPRouter.from_enterprise_catalog(storage=store1)
        t = router1.create_hitl_interrupt(
            tool_name="postgres.execute_outbound_wire",
            requested_by="persisted_agent",
            user_roles=["platform_admin"],
            requester_groups=["platform_operators"],
        )
        router1.resolve_hitl_interrupt(
            t["ticket_id"],
            reviewer="lead_reviewer",
            decision="APPROVED",
            reviewer_roles=["platform_admin"],
            reviewer_groups=["hitl_approvers"],
        )
        assert store1.verify_audit_chain()["valid"] is True
        store1.close()
        store1 = None

        # Now instantiate a completely new store & router from the same SQLite DB file
        store2 = SQLiteStateStore(db_path)
        router2 = EnterpriseMCPRouter.from_enterprise_catalog(storage=store2)
        loaded_ticket = router2.storage.get_ticket(t["ticket_id"])
        assert loaded_ticket is not None
        assert loaded_ticket["status"] == "APPROVED"
        assert loaded_ticket["reviewer"] == "lead_reviewer"
        assert router2.hitl_tickets[t["ticket_id"]]["status"] == "APPROVED"
        assert len(router2.audit_trail) >= 2
        assert store2.verify_audit_chain()["valid"] is True

        # Verify SQLite append-only triggers reject UPDATE and DELETE on audit_events
        try:
            store2._conn.execute("UPDATE audit_events SET data_json = '{}' WHERE id = 1")
            raise AssertionError("Expected sqlite3.DatabaseError on audit UPDATE")
        except sqlite3.DatabaseError as exc:
            assert "append_only" in str(exc).lower()

        try:
            store2._conn.execute("DELETE FROM audit_events WHERE id = 1")
            raise AssertionError("Expected sqlite3.DatabaseError on audit DELETE")
        except sqlite3.DatabaseError as exc:
            assert "append_only" in str(exc).lower()
    finally:
        if store1 is not None:
            store1.close()
        if store2 is not None:
            store2.close()
        for suffix in ("", "-wal", "-shm"):
            candidate = f"{db_path}{suffix}"
            if os.path.exists(candidate):
                try:
                    os.remove(candidate)
                except PermissionError:
                    pass


def test_phase0_bypass_regression_suite(monkeypatch):
    # 1. Mint HS256 JWT tokens for requester and peer reviewer
    requester_jwt = create_jwt_token(
        "wire_agent_01",
        ["platform_admin"],
        expires_in_seconds=600,
        groups=["platform_operators"],
    )
    reviewer_jwt = create_jwt_token(
        "sr_ops_approver",
        ["super_admin"],
        expires_in_seconds=600,
        groups=["hitl_approvers"],
    )
    expired_jwt = create_jwt_token(
        "wire_agent_01",
        ["platform_admin"],
        expires_in_seconds=-10,
        groups=["platform_operators"],
    )

    claims = verify_jwt_token(requester_jwt)
    assert claims["sub"] == "wire_agent_01"

    try:
        verify_jwt_token(expired_jwt)
        raise AssertionError("Expired JWT must be rejected")
    except ValueError as exc:
        assert "expired" in str(exc)

    tampered_jwt = requester_jwt[:-4] + "ZZZZ"
    try:
        verify_jwt_token(tampered_jwt)
        raise AssertionError("Tampered JWT signature must be rejected")
    except ValueError:
        pass

    # Unauthenticated tools/call claiming hitl_approved=True + user_roles=["platform_admin"] is blocked (-32001)
    unauth_rpc = client.post(
        "/mcp/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": 501,
            "method": "tools/call",
            "params": {
                "name": "postgres.execute_outbound_wire",
                "user_roles": ["platform_admin"],
                "hitl_approved": True,
                "arguments": {"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 100.0},
            },
        },
    ).json()
    assert unauth_rpc["error"]["code"] == -32001
    assert unauth_rpc["error"]["data"]["reason"] == "rbac_denied"

    # Authenticated platform_admin tools/call claiming hitl_approved=True WITHOUT a ticket is blocked (-32002)
    noticket_rpc = client.post(
        "/mcp/jsonrpc",
        headers={"Authorization": f"Bearer {requester_jwt}"},
        json={
            "jsonrpc": "2.0",
            "id": 502,
            "method": "tools/call",
            "params": {
                "name": "postgres.execute_outbound_wire",
                "hitl_approved": True,
                "arguments": {"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 100.0},
            },
        },
    ).json()
    assert noticket_rpc["error"]["code"] == -32002
    assert noticket_rpc["error"]["data"]["reason"] == "hitl_ticket_required"

    # Create canonical-argument bound ticket as wire_agent_01
    approved_args = {"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 100.0}
    create_resp = client.post(
        "/api/v1/governance/hitl/create",
        headers={"Authorization": f"Bearer {requester_jwt}"},
        json={"tool_name": "postgres.execute_outbound_wire", "arguments": approved_args},
    )
    assert create_resp.status_code == 200
    ticket_id = create_resp.json()["ticket_id"]

    # Self-approval attempt via HTTP must be rejected with 403
    self_approve = client.post(
        "/api/v1/governance/hitl/resolve",
        headers={"Authorization": f"Bearer {requester_jwt}"},
        json={"ticket_id": ticket_id, "decision": "APPROVED"},
    )
    assert self_approve.status_code == 403

    # Peer super_admin approves ticket
    peer_approve = client.post(
        "/api/v1/governance/hitl/resolve",
        headers={"Authorization": f"Bearer {reviewer_jwt}"},
        json={"ticket_id": ticket_id, "decision": "APPROVED"},
    )
    assert peer_approve.status_code == 200

    # Argument-tampered execution (amount_usd=999999.0 instead of 100.0) MUST be blocked by SHA-256 hash mismatch!
    tampered_args = {"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 999999.0}
    tampered_call = client.post(
        "/mcp/jsonrpc",
        headers={"Authorization": f"Bearer {requester_jwt}"},
        json={
            "jsonrpc": "2.0",
            "id": 503,
            "method": "tools/call",
            "params": {
                "name": "postgres.execute_outbound_wire",
                "hitl_ticket_id": ticket_id,
                "arguments": tampered_args,
            },
        },
    ).json()
    assert tampered_call["error"]["code"] == -32002
    assert tampered_call["error"]["data"]["reason"] == "hitl_ticket_arguments_hash_mismatch"

    # Untampered execution with exact approved arguments succeeds once, and replay is blocked
    valid_call = client.post(
        "/mcp/jsonrpc",
        headers={"Authorization": f"Bearer {requester_jwt}"},
        json={
            "jsonrpc": "2.0",
            "id": 504,
            "method": "tools/call",
            "params": {
                "name": "postgres.execute_outbound_wire",
                "hitl_ticket_id": ticket_id,
                "arguments": approved_args,
            },
        },
    ).json()
    assert valid_call["result"]["isError"] is False

    replay_call = client.post(
        "/mcp/jsonrpc",
        headers={"Authorization": f"Bearer {requester_jwt}"},
        json={
            "jsonrpc": "2.0",
            "id": 505,
            "method": "tools/call",
            "params": {
                "name": "postgres.execute_outbound_wire",
                "hitl_ticket_id": ticket_id,
                "arguments": approved_args,
            },
        },
    ).json()
    assert replay_call["error"]["code"] == -32002
    assert replay_call["error"]["data"]["reason"] == "hitl_ticket_already_consumed"

    # Rate limiter HTTP 429 enforcement check (reset afterward so other tests stay clean)
    try:
        DEFAULT_RATE_LIMITER.reset()
        monkeypatch.setenv("ROUTER_RATE_LIMIT_RPM", "2")
        rl_hdr = {
            "Authorization": (
                f"Bearer {create_jwt_token('rate_probe', ['analyst'], expires_in_seconds=60, groups=['platform_operators'])}"
            )
        }
        assert client.post("/api/v1/router/search", headers=rl_hdr, json={"query": "NAV"}).status_code == 200
        assert client.post("/api/v1/router/search", headers=rl_hdr, json={"query": "NAV"}).status_code == 200
        blocked_429 = client.post("/api/v1/router/search", headers=rl_hdr, json={"query": "NAV"})
        assert blocked_429.status_code == 429
    finally:
        DEFAULT_RATE_LIMITER.reset()


def test_sql_guard_adversarial_payload_suite():
    """Tests 34 real SQL payloads (26 attacks + 8 safe read-only / quoted-keyword queries)."""
    adversarial_attacks = [
        ("SYSTEM$WHITELIST()", "SELECT SYSTEM$WHITELIST() FROM PORTFOLIO_GOLD.FUNDS"),
        ("SYSTEM$CANCEL_ALL_QUERIES()", "SELECT SYSTEM$CANCEL_ALL_QUERIES()"),
        ("SYSTEM$TYPEOF()", "SELECT SYSTEM$TYPEOF(1) FROM PORTFOLIO_GOLD.FUNDS"),
        ("pg_sleep(10)", "SELECT pg_sleep(10) FROM PORTFOLIO_GOLD.FUNDS"),
        ("pg_read_file()", "SELECT pg_read_file('/etc/passwd') FROM PORTFOLIO_GOLD.FUNDS"),
        ("lo_import()", "SELECT lo_import('/etc/passwd') FROM PORTFOLIO_GOLD.FUNDS"),
        ("pg_terminate_backend()", "SELECT pg_terminate_backend(1) FROM PORTFOLIO_GOLD.FUNDS"),
        ("FOR UPDATE lock", "SELECT * FROM PORTFOLIO_GOLD.FUNDS FOR UPDATE"),
        ("FOR SHARE lock", "SELECT * FROM PORTFOLIO_GOLD.FUNDS FOR SHARE"),
        ("SELECT INTO table", "SELECT * INTO evil_copy FROM PORTFOLIO_GOLD.FUNDS"),
        ("CREATE TABLE", "CREATE TABLE evil_tbl (id INT)"),
        ("DROP TABLE", "DROP TABLE PORTFOLIO_GOLD.FUNDS"),
        ("DELETE FROM", "DELETE FROM PORTFOLIO_GOLD.FUNDS WHERE 1=1"),
        ("UPDATE SET", "UPDATE PORTFOLIO_GOLD.FUNDS SET nav = 0"),
        ("INSERT INTO", "INSERT INTO PORTFOLIO_GOLD.FUNDS VALUES ('X', 1, 1)"),
        ("TRUNCATE TABLE", "TRUNCATE TABLE PORTFOLIO_GOLD.FUNDS"),
        ("ALTER TABLE", "ALTER TABLE PORTFOLIO_GOLD.FUNDS ADD COLUMN x INT"),
        ("GRANT ALL", "GRANT ALL ON PORTFOLIO_GOLD.FUNDS TO PUBLIC"),
        ("REVOKE SELECT", "REVOKE SELECT ON PORTFOLIO_GOLD.FUNDS FROM analyst"),
        ("MERGE INTO", "MERGE INTO PORTFOLIO_GOLD.FUNDS USING src ON 1=1 WHEN MATCHED THEN DELETE"),
        ("COPY TO file", "COPY PORTFOLIO_GOLD.FUNDS TO '/tmp/out.csv'"),
        ("CTE DELETE", "WITH d AS (DELETE FROM PORTFOLIO_GOLD.FUNDS RETURNING *) SELECT * FROM d"),
        ("Stacked DELETE", "SELECT 1; DELETE FROM PORTFOLIO_GOLD.FUNDS"),
        ("Comment-obfuscated INSERT", "/* benign */ INSERT INTO PORTFOLIO_GOLD.FUNDS VALUES (1)"),
        ("Stacked DROP", "SELECT fund_id FROM PORTFOLIO_GOLD.FUNDS; DROP TABLE PORTFOLIO_GOLD.FUNDS"),
        ("CALL procedure", "CALL system_admin_proc('arg')"),
    ]
    for label, sql in adversarial_attacks:
        res = SafeSQLValidator.validate_readonly_sql(
            sql=sql,
            dialect="snowflake",
            allowed_roles={"platform_admin"},
            allowed_schemas={"PORTFOLIO_GOLD"},
            role="platform_admin",
            schema="PORTFOLIO_GOLD",
        )
        assert res["valid"] is False, f"Attack payload was NOT blocked ({label}): {res}"

    safe_queries = [
        ("Quoted keyword identifiers", 'SELECT "update", "delete", "select", fund_id FROM PORTFOLIO_GOLD.FUNDS LIMIT 10'),
        ("Allow-listed aggregates", "SELECT COUNT(*), SUM(nav), AVG(aum_cad), MIN(nav), MAX(nav) FROM PORTFOLIO_GOLD.FUNDS"),
        ("Allow-listed scalar fns", "SELECT COALESCE(fund_id, 'NONE'), ROUND(nav, 2), CAST(active AS VARCHAR) FROM PORTFOLIO_GOLD.FUNDS"),
        ("String transforms", "SELECT fund_id, UPPER(TRIM(name)), LOWER(category) FROM PORTFOLIO_GOLD.FUNDS ORDER BY nav DESC LIMIT 5"),
        ("SUBSTR & ABS", "SELECT fund_id, SUBSTR(name, 1, 8), ABS(nav) FROM PORTFOLIO_GOLD.FUNDS WHERE fund_id IN ('POL-101', 'POL-102')"),
        ("Read-only CTE", "WITH top_funds AS (SELECT fund_id, nav FROM PORTFOLIO_GOLD.FUNDS WHERE nav > 10) SELECT * FROM top_funds"),
        ("CASE expression", "SELECT CASE WHEN nav > 50 THEN 'HIGH' ELSE 'LOW' END AS tier FROM PORTFOLIO_GOLD.FUNDS"),
        ("String literal semicolons", "SELECT DISTINCT fund_id FROM PORTFOLIO_GOLD.FUNDS WHERE note = 'DROP TABLE test; update=true'"),
    ]
    for label, sql in safe_queries:
        res = SafeSQLValidator.validate_readonly_sql(
            sql=sql,
            dialect="snowflake",
            allowed_roles={"platform_admin"},
            allowed_schemas={"PORTFOLIO_GOLD"},
            role="platform_admin",
            schema="PORTFOLIO_GOLD",
        )
        assert res["valid"] is True, f"Safe SQL was falsely blocked ({label}): {res}"


def test_identity_fail_closed_startup_and_disabled_demo_keys(monkeypatch):
    monkeypatch.delenv("ROUTER_DEV_MODE", raising=False)
    monkeypatch.delenv("ROUTER_JWT_SECRET", raising=False)
    monkeypatch.delenv("ROUTER_JWT_PUBLIC_KEY_PEM", raising=False)
    monkeypatch.delenv("ROUTER_JWKS_JSON", raising=False)

    with pytest.raises(RuntimeError):
        validate_security_config()

    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass

    monkeypatch.setenv("ROUTER_JWT_SECRET", "prod-test-secret-key-at-least-32-bytes-long")
    with TestClient(app) as client:
        assert client.post("/api/v1/router/search", json={"query": "snowflake"}).status_code == 401
        assert client.get("/api/v1/governance/audit-verify").status_code == 401
        assert (
            client.post(
                "/mcp/jsonrpc",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/router/search",
                headers={"X-API-Key": "ak-superadmin-demo"},
                json={"query": "snowflake"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/router/search",
                headers={"X-API-Key": "ak-admin-demo"},
                json={"query": "snowflake"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/auth/token",
                json={"username": "mallory", "role": "platform_admin"},
            ).status_code
            == 401
        )
        valid_token = create_jwt_token(
            "alice_ops",
            ["platform_admin"],
            expires_in_seconds=300,
            groups=["platform_operators"],
        )
        assert (
            client.post(
                "/api/v1/auth/token",
                headers={"Authorization": f"Bearer {valid_token}"},
                json={"username": "mallory", "role": "platform_admin"},
            ).status_code
            == 403
        )


def test_rs256_jwks_and_issuer_audience_validation(monkeypatch):
    bundle = generate_rsa_keypair_and_jwks(kid="idp-test-1")
    issuer = "https://idp.enterprise.example"
    audience = "enterprise-mcp-router"

    good_jwt = create_rs256_jwt_token(
        username="oidc_approver",
        roles=["super_admin"],
        private_pem=bundle["private_pem"],
        expires_in_seconds=300,
        groups=["hitl_approvers"],
        kid="idp-test-1",
        issuer=issuer,
        audience=audience,
    )
    claims = verify_jwt_token(
        good_jwt,
        jwks=bundle["jwks"],
        expected_issuer=issuer,
        expected_audience=audience,
    )
    assert claims["sub"] == "oidc_approver"
    assert "hitl_approvers" in claims["groups"]

    with pytest.raises(ValueError):
        verify_jwt_token(
            good_jwt,
            jwks=bundle["jwks"],
            expected_issuer="https://wrong-idp.example",
            expected_audience=audience,
        )

    with pytest.raises(ValueError):
        verify_jwt_token(
            good_jwt,
            jwks=bundle["jwks"],
            expected_issuer=issuer,
            expected_audience="wrong-audience",
        )

    monkeypatch.delenv("ROUTER_DEV_MODE", raising=False)
    monkeypatch.delenv("ROUTER_JWT_SECRET", raising=False)
    monkeypatch.delenv("ROUTER_JWT_PUBLIC_KEY_PEM", raising=False)
    monkeypatch.setenv("ROUTER_JWKS_JSON", json.dumps(bundle["jwks"]))
    monkeypatch.setenv("ROUTER_JWT_ISSUER", issuer)
    monkeypatch.setenv("ROUTER_JWT_AUDIENCE", audience)

    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/governance/audit-verify",
            headers={"Authorization": f"Bearer {good_jwt}"},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


def test_sock_puppet_dual_account_self_approval_defeated():
    mallory_jwt = create_jwt_token(
        "mallory",
        ["super_admin"],
        expires_in_seconds=600,
        groups=["platform_operators"],
    )
    sock_puppet_jwt = create_jwt_token(
        "sock_puppet",
        ["super_admin"],
        expires_in_seconds=600,
        groups=["platform_operators"],
    )
    real_approver_jwt = create_jwt_token(
        "sec_director",
        ["super_admin"],
        expires_in_seconds=600,
        groups=["hitl_approvers"],
    )

    with TestClient(app) as client:
        mint_super = client.post(
            "/api/v1/auth/token",
            json={"username": "attacker", "role": "super_admin"},
        )
        assert mint_super.status_code == 422

        create_resp = client.post(
            "/api/v1/governance/hitl/create",
            headers={"Authorization": f"Bearer {mallory_jwt}"},
            json={
                "tool_name": "postgres.execute_outbound_wire",
                "arguments": {
                    "from_account": "ACC-9001",
                    "to_account": "ACC-9003",
                    "amount_usd": 5000.0,
                },
                "justification": "sock puppet separation-of-duties verification",
            },
        )
        assert create_resp.status_code == 200
        create_data = create_resp.json()
        assert create_data["status"] == "PENDING_APPROVAL"
        ticket_id = create_data["ticket_id"]

        puppet_resolve = client.post(
            "/api/v1/governance/hitl/resolve",
            headers={"Authorization": f"Bearer {sock_puppet_jwt}"},
            json={
                "ticket_id": ticket_id,
                "decision": "APPROVED",
                "notes": "sock puppet self-approval attempt",
            },
        )
        assert puppet_resolve.status_code == 403
        assert "hitl_approvers" in puppet_resolve.text or "reviewer_missing_approver_group" in puppet_resolve.text

        real_resolve = client.post(
            "/api/v1/governance/hitl/resolve",
            headers={"Authorization": f"Bearer {real_approver_jwt}"},
            json={
                "ticket_id": ticket_id,
                "decision": "APPROVED",
                "notes": "independent peer approval",
            },
        )
        assert real_resolve.status_code == 200
        assert real_resolve.json()["status"] == "APPROVED"


def test_sql_guard_table_allowlist_union_subquery_cte_shadowing():
    sf = SnowflakeCortexConnector(
        allowed_roles=["platform_admin"],
        allowed_schemas=["PORTFOLIO_GOLD", "CORTEX_DOCS"],
    )
    pg = PostgresEnterpriseConnector()
    vsm = ValueStreamManagementConnector()

    blocked_snowflake = [
        ("other_schema", "SELECT * FROM other_schema.payroll", "PORTFOLIO_GOLD"),
        (
            "union_secrets",
            "SELECT * FROM PORTFOLIO_GOLD.FUNDS UNION ALL SELECT * FROM secrets.pii",
            "PORTFOLIO_GOLD",
        ),
        (
            "subquery_restricted",
            "SELECT * FROM PORTFOLIO_GOLD.FUNDS WHERE id IN (SELECT user_id FROM restricted.secret)",
            "PORTFOLIO_GOLD",
        ),
        (
            "schema_param_mismatch",
            "SELECT * FROM CORTEX_DOCS.COMPLIANCE_CHUNKS",
            "PORTFOLIO_GOLD",
        ),
        ("unqualified_table", "SELECT * FROM FUNDS", "PORTFOLIO_GOLD"),
        ("quoted_forbidden", 'SELECT * FROM "secrets"."pii"', "PORTFOLIO_GOLD"),
        (
            "cte_shadowing",
            "WITH FUNDS AS (SELECT * FROM secrets.pii) SELECT * FROM FUNDS",
            "PORTFOLIO_GOLD",
        ),
    ]
    for label, sql, schema in blocked_snowflake:
        res = sf.validate_readonly_sql(sql=sql, role="platform_admin", schema=schema)
        assert res["valid"] is False, f"Snowflake query should block ({label}): {res}"

    safe_sf = sf.validate_readonly_sql(
        sql='SELECT * FROM "PORTFOLIO_GOLD"."FUNDS" LIMIT 5',
        role="platform_admin",
        schema="PORTFOLIO_GOLD",
    )
    assert safe_sf["valid"] is True, f"Valid quoted Snowflake table blocked: {safe_sf}"

    for bad_pg in [
        "SELECT * FROM other_schema.payroll",
        "SELECT * FROM accounts UNION ALL SELECT * FROM secrets.pii",
        "SELECT * FROM sqlite_master",
        "WITH accounts AS (SELECT 1) SELECT * FROM accounts",
    ]:
        pg_res = pg.query_ledger(bad_pg)
        assert pg_res["status"] == "error", f"Postgres query should block ({bad_pg}): {pg_res}"

    ok_pg = pg.query_ledger("SELECT account_id, portfolio_name FROM accounts LIMIT 2")
    assert ok_pg["status"] == "ok", f"Safe Postgres query failed: {ok_pg}"

    for bad_vsm in [
        "SELECT * FROM secrets.pii",
        "SELECT * FROM engineering_tickets UNION ALL SELECT * FROM restricted.secret",
        "SELECT * FROM sqlite_master",
        "WITH engineering_tickets AS (SELECT 1) SELECT * FROM engineering_tickets",
    ]:
        vsm_res = vsm.query_vsm_sql(bad_vsm)
        assert vsm_res["status"] == "error", f"VSM query should block ({bad_vsm}): {vsm_res}"

    ok_vsm = vsm.query_vsm_sql("SELECT ticket_id, team FROM engineering_tickets LIMIT 2")
    assert ok_vsm["status"] == "ok", f"Safe VSM query failed: {ok_vsm}"


def test_default_sqlite_wal_storage_and_restart_hydration(tmp_path, monkeypatch):
    monkeypatch.delenv("ROUTER_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("ROUTER_SQLITE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    original_storage = mcp_router.storage
    created_store = None
    try:
        reset_default_storage(None)
        created_store = get_default_storage()
        assert isinstance(created_store, SQLiteStateStore)
        expected_db = tmp_path / "enterprise_router.db"
        assert expected_db.exists()
        assert created_store.verify_audit_chain()["backend"] == "sqlite_wal"

        router_a = EnterpriseMCPRouter.from_enterprise_catalog(storage=created_store)
        ticket = router_a.create_hitl_interrupt(
            tool_name="postgres.execute_outbound_wire",
            requested_by="restart_agent",
            user_roles=["platform_admin"],
            requester_groups=["platform_operators"],
        )
        router_a.resolve_hitl_interrupt(
            ticket["ticket_id"],
            reviewer="restart_approver",
            decision="APPROVED",
            reviewer_roles=["platform_admin"],
            reviewer_groups=["hitl_approvers"],
        )
        created_store.close()
        created_store = None

        reloaded_store = SQLiteStateStore(str(expected_db))
        try:
            router_b = EnterpriseMCPRouter.from_enterprise_catalog(storage=reloaded_store)
            assert ticket["ticket_id"] in router_b.hitl_tickets
            assert router_b.hitl_tickets[ticket["ticket_id"]]["status"] == "APPROVED"
            assert len(router_b.audit_trail) >= 2
            assert reloaded_store.verify_audit_chain()["valid"] is True
        finally:
            reloaded_store.close()
    finally:
        if created_store is not None:
            created_store.close()
        reset_default_storage(original_storage)
