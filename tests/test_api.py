"""
FastAPI REST & JSON-RPC 2.0 Integration Tests for Enterprise-MCP-Router.
"""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_dashboard_and_health_endpoints():
    resp_html = client.get("/")
    assert resp_html.status_code == 200
    assert "Enterprise-MCP-Router" in resp_html.text

    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    body = resp_health.json()
    assert body["status"] == "healthy"
    assert body["total_registered_tools"] == 105


def test_mcp_jsonrpc_protocol_endpoint():
    resp = client.post(
        "/mcp/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/list",
            "params": {"query": "Informatica Cloud IICS ELT taskflow SLA", "top_k": 3},
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["result"]["tools"]) == 3
    assert payload["result"]["tools"][0]["domain"] == "informatica"


def test_semantic_router_and_governance_endpoints():
    route_resp = client.post(
        "/api/v1/router/search",
        json={"query": "Execute outbound wire in PostgreSQL ledger", "top_k": 5},
    )
    assert route_resp.status_code == 200
    r_data = route_resp.json()
    assert r_data["total_registered_tools"] == 105
    assert r_data["token_reduction_pct"] > 90.0

    # Create and resolve HITL interrupt ticket via API
    create_resp = client.post(
        "/api/v1/governance/hitl/create",
        json={
            "tool_name": "postgres.execute_outbound_wire",
            "requested_by": "test_suite_agent",
            "user_roles": ["platform_admin"],
            "arguments": {"amount_usd": 10000},
        },
    )
    assert create_resp.status_code == 200
    ticket_id = create_resp.json()["ticket_id"]

    resolve_resp = client.post(
        "/api/v1/governance/hitl/resolve",
        json={
            "ticket_id": ticket_id,
            "reviewer": "ops_lead@enterprise.io",
            "decision": "APPROVED",
        },
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "APPROVED"

    auth_resp = client.post(
        "/api/v1/governance/authorize",
        json={
            "tool_name": "postgres.execute_outbound_wire",
            "user_roles": ["platform_admin"],
            "hitl_ticket_id": ticket_id,
        },
    )
    assert auth_resp.status_code == 200
    assert auth_resp.json()["allowed"] is True


def test_connectors_adapters_and_telemetry_endpoints():
    sf_resp = client.post(
        "/api/v1/connectors/snowflake/validate-sql",
        json={
            "sql": "SELECT fund_id, nav FROM PORTFOLIO_GOLD.FUNDS",
            "role": "ai_platform_reader",
            "schema_name": "PORTFOLIO_GOLD",
        },
    )
    assert sf_resp.status_code == 200
    assert sf_resp.json()["valid"] is True

    cortex_resp = client.post(
        "/api/v1/connectors/snowflake/cortex-search",
        json={"query": "RRSP contribution compliance rules", "role": "ai_platform_reader", "top_k": 2},
    )
    assert cortex_resp.status_code == 200
    assert cortex_resp.json()["status"] == "ok"

    iics_resp = client.post(
        "/api/v1/connectors/informatica/validate",
        json={
            "taskflow_name": "tf_snowflake_fund_docs_elt",
            "status": "SUCCESS",
            "rows_processed": 1200,
            "freshness_lag_minutes": 6,
        },
    )
    assert iics_resp.status_code == 200
    assert iics_resp.json()["ready_for_rag"] is True

    pg_resp = client.post(
        "/api/v1/connectors/postgres/query",
        json={"sql": "SELECT * FROM accounts WHERE risk_tier = 'LOW'", "role": "analyst"},
    )
    assert pg_resp.status_code == 200
    assert pg_resp.json()["row_count"] >= 1

    bd_resp = client.post(
        "/api/v1/adapters/bedrock/invoke",
        json={
            "prompt": "Verify RRSP compliance",
            "required_keys": ["summary", "risk_tier", "recommended_action"],
            "simulate_flaky_first_attempt": True,
        },
    )
    assert bd_resp.status_code == 200
    assert bd_resp.json()["status"] == "success"
    assert bd_resp.json()["attempts"] == 2

    bridge_resp = client.get("/api/v1/adapters/bridges/langgraph")
    assert bridge_resp.status_code == 200
    assert bridge_resp.json()["framework"] == "langgraph"

    tel_resp = client.get("/api/v1/telemetry/summary")
    assert tel_resp.status_code == 200
    assert tel_resp.json()["total_spans"] >= 2

    rb_resp = client.post(
        "/api/v1/telemetry/runbook",
        json={"incident_type": "snowflake_query_timeout", "component": "Snowflake_Cortex"},
    )
    assert rb_resp.status_code == 200
    assert "Cortex Search" in rb_resp.json()["triage_steps"]
