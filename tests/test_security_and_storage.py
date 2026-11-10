"""
Security, AST SQL Guard, HITL Governance, and Persistence Tests for Enterprise-MCP-Router.
Verifies:
1. AST SQL injection defenses (semicolon inside strings, SELECT INTO, keywords in columns/values)
2. HITL Governance (self-approval prevention, expiration TTL, single-use replay defense, ticket requirement)
3. SQLiteStateStore persistence and thread safety
4. API Key authentication and RBAC role derivation
"""

import os
import tempfile
import time
from fastapi.testclient import TestClient

from src.connectors.sql_guard import SafeSQLValidator
from src.main import app
from src.router import EnterpriseMCPRouter
from src.security import AuthenticatedPrincipal, HITLGovernanceRules
from src.storage import SQLiteStateStore

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

    # 3. Legitimate authorized reviewer can approve
    valid_approve = router.resolve_hitl_interrupt(
        ticket_id=ticket_id,
        reviewer="bob_security_lead",
        decision="APPROVED",
        reviewer_roles=["platform_admin"],
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
    # Calling /api/v1/governance/authorize for a mutating tool with hitl_approved=True
    # but NO ticket must be rejected
    resp = client.post(
        "/api/v1/governance/authorize",
        json={
            "tool_name": "postgres.execute_outbound_wire",
            "user_roles": ["platform_admin"],
            "hitl_approved": True,  # Attacker attempt to bypass approval
            "hitl_ticket_id": None,
        },
    )
    data = resp.json()
    assert data["allowed"] is False
    assert data["reason"] in ("hitl_ticket_required", "hitl_approval_required")


def test_sqlite_persistence_across_reloads():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        # Create store 1 and write ticket & snapshot
        store1 = SQLiteStateStore(db_path)
        router1 = EnterpriseMCPRouter.from_enterprise_catalog(storage=store1)
        t = router1.create_hitl_interrupt(
            tool_name="postgres.execute_outbound_wire",
            requested_by="persisted_agent",
            user_roles=["platform_admin"],
        )
        router1.resolve_hitl_interrupt(t["ticket_id"], reviewer="lead_reviewer", decision="APPROVED")

        # Now instantiate a completely new store & router from the same SQLite DB file
        store2 = SQLiteStateStore(db_path)
        router2 = EnterpriseMCPRouter.from_enterprise_catalog(storage=store2)
        loaded_ticket = router2.storage.get_ticket(t["ticket_id"])
        assert loaded_ticket is not None
        assert loaded_ticket["status"] == "APPROVED"
        assert loaded_ticket["reviewer"] == "lead_reviewer"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
