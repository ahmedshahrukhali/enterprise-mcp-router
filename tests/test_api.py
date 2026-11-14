"""
FastAPI REST, JSON-RPC 2.0 & SSE Integration Tests for Enterprise-MCP-Router.
"""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_dashboard_and_health_endpoints():
    resp_html = client.get("/")
    assert resp_html.status_code == 200
    assert "Enterprise-MCP-Router" in resp_html.text
    assert "Value Stream" in resp_html.text

    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    body = resp_health.json()
    assert body["status"] == "healthy"
    assert body["total_registered_tools"] == 120
    assert "portfolio_vsm" in body["domains"]


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


def test_mcp_sse_transport_endpoint():
    resp = client.get("/mcp/sse")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "event: endpoint" in resp.text
    assert "/mcp/messages" in resp.text


def test_semantic_router_and_governance_endpoints():
    admin_headers = {"X-API-Key": "ak-admin-demo"}
    reviewer_headers = {"X-API-Key": "ak-superadmin-demo"}

    route_resp = client.post(
        "/api/v1/router/search",
        headers=admin_headers,
        json={"query": "Execute outbound wire in PostgreSQL ledger", "top_k": 5},
    )
    assert route_resp.status_code == 200
    r_data = route_resp.json()
    assert r_data["total_registered_tools"] == 120
    assert r_data["token_reduction_pct"] > 90.0
    assert r_data["full_registry_tokens"] > 25000
    assert "bm25_score" in r_data["routed_tools"][0]

    # Validate JSON Schema contract check endpoint
    bad_schema_resp = client.post(
        "/api/v1/governance/validate-schema",
        json={"tool_name": "postgres.execute_outbound_wire", "arguments": {"amount_usd": -5}},
    )
    assert bad_schema_resp.status_code == 200
    assert bad_schema_resp.json()["valid"] is False

    wire_args = {"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 10000}

    # Create and resolve HITL interrupt ticket via authenticated principals
    create_resp = client.post(
        "/api/v1/governance/hitl/create",
        headers=admin_headers,
        json={
            "tool_name": "postgres.execute_outbound_wire",
            "arguments": wire_args,
            "justification": "API integration test wire transfer",
        },
    )
    assert create_resp.status_code == 200
    ticket_payload = create_resp.json()
    ticket_id = ticket_payload["ticket_id"]
    assert "arguments_hash" in ticket_payload

    resolve_resp = client.post(
        "/api/v1/governance/hitl/resolve",
        headers=reviewer_headers,
        json={
            "ticket_id": ticket_id,
            "decision": "APPROVED",
        },
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "APPROVED"

    auth_resp = client.post(
        "/api/v1/governance/authorize",
        headers=admin_headers,
        json={
            "tool_name": "postgres.execute_outbound_wire",
            "hitl_ticket_id": ticket_id,
            "arguments": wire_args,
        },
    )
    assert auth_resp.status_code == 200
    assert auth_resp.json()["allowed"] is True


def test_vsm_overview_query_and_concern_analysis_endpoints():
    ov_resp = client.get("/api/v1/vsm/overview")
    assert ov_resp.status_code == 200
    ov_data = ov_resp.json()
    assert ov_data["summary"]["total_portfolios"] == 4
    assert ov_data["summary"]["blocked_tickets_count"] == 3

    sql_resp = client.post(
        "/api/v1/vsm/query",
        json={
            "sql": (
                "SELECT p.portfolio_id, COUNT(t.ticket_id) AS blocked_count "
                "FROM product_portfolios p "
                "JOIN engineering_tickets t ON p.portfolio_id = t.portfolio_id "
                "WHERE t.status = 'BLOCKED' GROUP BY p.portfolio_id"
            ),
            "role": "analyst",
        },
    )
    assert sql_resp.status_code == 200
    assert sql_resp.json()["status"] == "ok"
    assert sql_resp.json()["row_count"] >= 2

    concern_resp = client.post(
        "/api/v1/vsm/analyze-concerns",
        json={"query": "Identify blocked engineering tickets impacting OKRs", "portfolio_id": "PF-101"},
    )
    assert concern_resp.status_code == 200
    c_data = concern_resp.json()
    assert c_data["status"] == "ok"
    assert c_data["concerns_count"] >= 2
    assert c_data["bedrock_validation"]["status"] == "success"


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
        json={"sql": "SELECT * FROM accounts WHERE risk_tier = ?", "params": ["LOW"], "role": "analyst"},
    )
    assert pg_resp.status_code == 200
    assert pg_resp.json()["row_count"] == 2

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


def test_mcp_messages_endpoint_and_builtin_vsm_tools_call():
    resp = client.post(
        "/mcp/messages",
        json={
            "jsonrpc": "2.0",
            "id": 77,
            "method": "tools/call",
            "params": {
                "name": "portfolio_vsm.detect_management_concerns",
                "user_roles": ["analyst"],
                "arguments": {"portfolio_id": "PF-101"},
            },
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["result"]["isError"] is False
    tool_out = payload["result"]["content"][0]["json"]
    assert tool_out["status"] == "ok"
    assert tool_out["concerns_count"] >= 2


def test_rbac_denial_and_jsonrpc_32001():
    resp = client.post(
        "/mcp/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": 88,
            "method": "tools/call",
            "params": {
                "name": "postgres.execute_outbound_wire",
                "user_roles": ["analyst"],
                "hitl_approved": True,
                "arguments": {"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 500.0},
            },
        },
    )
    assert resp.status_code == 200
    err = resp.json()["error"]
    assert err["code"] == -32001
    assert err["data"]["reason"] == "rbac_denied"


def test_jwt_session_role_filtering_and_mcp_pagination():
    # Issue real HS256 JWT tokens for analyst and platform_admin
    tok_analyst = client.post(
        "/api/v1/auth/token",
        json={"username": "junior_analyst@enterprise.io", "role": "analyst"},
    )
    assert tok_analyst.status_code == 200
    analyst_jwt = tok_analyst.json()["access_token"]

    tok_admin = client.post(
        "/api/v1/auth/token",
        json={"username": "ops_admin@enterprise.io", "role": "platform_admin"},
    )
    assert tok_admin.status_code == 200
    admin_jwt = tok_admin.json()["access_token"]

    # Analyst searches for wire/admin action -> must NEVER see platform_admin tools
    analyst_search = client.post(
        "/api/v1/router/search",
        headers={"Authorization": f"Bearer {analyst_jwt}"},
        json={"query": "Execute outbound wire in PostgreSQL ledger", "top_k": 10},
    )
    assert analyst_search.status_code == 200
    a_data = analyst_search.json()
    assert all(t["required_role"] in ("analyst", "ai_platform_reader") for t in a_data["routed_tools"])
    assert "postgres.execute_outbound_wire" not in [t["name"] for t in a_data["routed_tools"]]

    # Admin JWT sees full accessible set including execute_outbound_wire
    admin_search = client.post(
        "/api/v1/router/search",
        headers={"Authorization": f"Bearer {admin_jwt}"},
        json={"query": "Execute outbound wire in PostgreSQL ledger", "top_k": 5},
    )
    assert admin_search.status_code == 200
    assert any(t["name"] == "postgres.execute_outbound_wire" for t in admin_search.json()["routed_tools"])

    # Test tools/list pagination & domain_filter over /mcp/jsonrpc
    page1 = client.post(
        "/mcp/jsonrpc",
        headers={"Authorization": f"Bearer {admin_jwt}"},
        json={
            "jsonrpc": "2.0",
            "id": 91,
            "method": "tools/list",
            "params": {"domain_filter": "snowflake", "cursor": 0, "page_size": 5},
        },
    ).json()
    assert len(page1["result"]["tools"]) == 5
    assert page1["result"]["nextCursor"] == "5"
    assert all(t["domain"] == "snowflake" for t in page1["result"]["tools"])


def test_routing_feedback_misses_and_audit_chain_endpoints():
    fb = client.post(
        "/api/v1/router/feedback",
        json={
            "query": "Escalate AML transaction alert",
            "routed_tools": ["snowflake.cortex_search_docs"],
            "selected_tool": "crm_rest.escalate_aml_suspicious_activity",
        },
    )
    assert fb.status_code == 200
    assert fb.json()["hit"] is False
    assert fb.json()["miss_queue_size"] >= 1

    misses = client.get("/api/v1/router/misses")
    assert misses.status_code == 200
    assert any(
        m["selected_tool"] == "crm_rest.escalate_aml_suspicious_activity"
        for m in misses.json()["misses"]
    )

    audit = client.get("/api/v1/governance/audit-verify")
    assert audit.status_code == 200
    assert audit.json()["valid"] is True
    assert audit.json()["checked_events"] >= 1

