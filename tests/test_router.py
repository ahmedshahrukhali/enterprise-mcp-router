from src.router import (
    AgentFrameworkBridges,
    BedrockAgentCoreAdapter,
    EnterpriseMCPRouter,
    EnterpriseRESTConnector,
    FastMCPServer,
    InformaticaCloudTaskflowAdapter,
    MCPToolSpec,
    PostgresEnterpriseConnector,
    ProductionTelemetryMonitor,
    SnowflakeCortexConnector,
)


def test_mcp_routing_and_governance():
    tools = [
        MCPToolSpec("read_ledger", "Read SQL accounting ledger", False, "analyst", [0.9, 0.1]),
        MCPToolSpec("execute_wire", "Execute outbound bank wire", True, "admin", [0.1, 0.9]),
    ]
    router = EnterpriseMCPRouter(tools)

    top = router.route_top_k_tools([0.85, 0.15], k=1)
    assert top == ["read_ledger"]

    # Mutating tool requires HITL approval
    res_pending = router.authorize_execution("execute_wire", ["admin"], hitl_approved=False)
    assert res_pending["allowed"] is False
    assert res_pending["reason"] == "hitl_approval_required"

    res_ok = router.authorize_execution("execute_wire", ["admin"], hitl_approved=True)
    assert res_ok["allowed"] is True


def test_enterprise_105_tool_catalog_and_token_reduction():
    router = EnterpriseMCPRouter.from_enterprise_catalog()
    assert len(router.tools) == 105

    res = router.route_by_query(
        "Query Snowflake Cortex Search for Fidelity RRSP compliance rules and fund NAV",
        k=5,
    )
    assert res["total_registered_tools"] == 105
    assert len(res["routed_tools"]) == 5
    assert res["token_reduction_pct"] > 90.0
    assert res["routed_tools"][0]["domain"] == "snowflake"


def test_stateful_hitl_interrupt_lifecycle():
    router = EnterpriseMCPRouter.from_enterprise_catalog()
    ticket = router.create_hitl_interrupt(
        tool_name="postgres.execute_outbound_wire",
        requested_by="agent_01",
        user_roles=["platform_admin"],
        arguments={"amount_usd": 50000},
    )
    assert ticket["status"] == "PENDING_APPROVAL"

    # Before resolution, ticket does not grant approval
    denied = router.authorize_execution(
        "postgres.execute_outbound_wire",
        ["platform_admin"],
        hitl_ticket_id=ticket["ticket_id"],
    )
    assert denied["allowed"] is False

    # Approve ticket
    resolved = router.resolve_hitl_interrupt(
        ticket_id=ticket["ticket_id"],
        reviewer="approver@enterprise.io",
        decision="APPROVED",
    )
    assert resolved["status"] == "APPROVED"

    allowed = router.authorize_execution(
        "postgres.execute_outbound_wire",
        ["platform_admin"],
        hitl_ticket_id=ticket["ticket_id"],
    )
    assert allowed["allowed"] is True


def test_fastmcp_jsonrpc_server_and_decorator():
    server = FastMCPServer()

    @server.tool(
        name="custom.verify_margin",
        description="Verify institutional margin requirement",
        is_mutating=False,
        required_role="analyst",
    )
    def verify_margin(account_id: str) -> dict:
        return {"account_id": account_id, "margin_ok": True}

    init_resp = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp["result"]["serverInfo"]["name"] == "enterprise-mcp-router"

    list_resp = server.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {"query": "Snowflake Cortex Search compliance", "top_k": 4},
        }
    )
    assert len(list_resp["result"]["tools"]) == 4
    assert list_resp["result"]["semantic_routing_metrics"]["token_reduction_pct"] > 90.0

    call_resp = server.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "custom.verify_margin",
                "user_roles": ["analyst"],
                "arguments": {"account_id": "ACC-9001"},
            },
        }
    )
    assert call_resp["result"]["isError"] is False
    assert call_resp["result"]["content"][0]["json"]["margin_ok"] is True


def test_snowflake_cortex_readonly_and_retrieval():
    sf = SnowflakeCortexConnector(
        allowed_roles=["ai_platform_reader"],
        allowed_schemas=["PORTFOLIO_GOLD", "CORTEX_DOCS"],
    )
    sf.index_chunks(
        [
            {"doc_id": "POL-101", "text": "Fidelity RRSP contribution rules and compliance guidelines"},
            {"doc_id": "POL-202", "text": "Equity portfolio rebalancing schedule and settlement SLA"},
        ]
    )

    valid_q = sf.validate_readonly_sql(
        "SELECT fund_id, nav FROM PORTFOLIO_GOLD.FUNDS WHERE active = 1",
        role="ai_platform_reader",
        schema="PORTFOLIO_GOLD",
    )
    assert valid_q["valid"] is True

    blocked_ddl = sf.validate_readonly_sql(
        "SELECT * FROM PORTFOLIO_GOLD.FUNDS; DROP TABLE FUNDS",
        role="ai_platform_reader",
        schema="PORTFOLIO_GOLD",
    )
    assert blocked_ddl["valid"] is False
    assert blocked_ddl["reason"] == "mutating_sql_keyword_blocked"

    rag_res = sf.retrieve_cortex_rag(
        "RRSP contribution compliance guidelines", role="ai_platform_reader", top_k=1
    )
    assert rag_res["status"] == "ok"
    assert rag_res["results"][0]["doc_id"] == "POL-101"


def test_informatica_cloud_taskflow_validation():
    iics = InformaticaCloudTaskflowAdapter(min_rows_threshold=10, max_lag_minutes=30)

    ok_run = iics.validate_taskflow_run(
        {
            "taskflow_name": "tf_snowflake_fund_docs_elt",
            "status": "SUCCESS",
            "rows_processed": 450,
            "freshness_lag_minutes": 12,
        }
    )
    assert ok_run["ready_for_rag"] is True

    failed_run = iics.validate_taskflow_run(
        {
            "taskflow_name": "tf_snowflake_fund_docs_elt",
            "status": "FAILED",
            "rows_processed": 0,
            "freshness_lag_minutes": 5,
        }
    )
    assert failed_run["ready_for_rag"] is False
    assert failed_run["alert_severity"] == "CRITICAL"


def test_postgres_snapshot_and_restore():
    pg = PostgresEnterpriseConnector()
    snap = pg.create_snapshot("before_wire")
    assert snap["status"] == "snapshot_created"

    wire = pg.execute_wire_transfer("ACC-9001", "ACC-9002", 100000.0, hitl_approved=True)
    assert wire["status"] == "committed"
    assert wire["from_account"]["balance_usd"] == 1350000.0

    restored = pg.restore_snapshot("before_wire")
    assert restored["status"] == "snapshot_restored"
    assert restored["restored_accounts"][0]["balance_usd"] == 1450000.0


def test_rest_circuit_breaker_and_framework_bridges():
    rest = EnterpriseRESTConnector(failure_threshold=2)

    def failing_call():
        raise RuntimeError("503 Service Unavailable")

    r1 = rest.call_endpoint("kyc_service", "/v1/verify", provider_fn=failing_call)
    assert r1["circuit_state"] == "CLOSED"
    r2 = rest.call_endpoint("kyc_service", "/v1/verify", provider_fn=failing_call)
    assert r2["circuit_state"] == "OPEN"
    r3 = rest.call_endpoint("kyc_service", "/v1/verify")
    assert r3["status"] == "circuit_open"

    router = EnterpriseMCPRouter.from_enterprise_catalog()
    sample = router.route_by_query("Snowflake Cortex Search", k=2)["routed_tools"]
    assert len(AgentFrameworkBridges.to_langgraph_tools(sample)) == 2
    assert len(AgentFrameworkBridges.to_smolagents_tools(sample)) == 2
    assert len(AgentFrameworkBridges.to_crewai_tools(sample)) == 2


def test_bedrock_agentcore_structured_output_and_retries():
    adapter = BedrockAgentCoreAdapter(max_retries=2)
    call_count = {"n": 0}

    def flaky_bedrock_provider():
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First attempt missing required structured output key
            return {"output": {"summary": "Incomplete"}, "usage": {"prompt_tokens": 50, "completion_tokens": 10}}
        return {
            "output": {"summary": "Validated portfolio compliance", "risk_tier": "LOW"},
            "usage": {"prompt_tokens": 120, "completion_tokens": 45},
        }

    res = adapter.invoke_with_structured_output(
        required_keys=["summary", "risk_tier"],
        provider_fn=flaky_bedrock_provider,
    )
    assert res["status"] == "success"
    assert res["attempts"] == 2
    assert res["usage"]["total_tokens"] == 165


def test_production_telemetry_token_alerts_and_runbook():
    monitor = ProductionTelemetryMonitor(token_budget_per_use_case=500)
    span = monitor.record_span(
        span_name="bedrock.converse.tool_call",
        use_case="advisor_rag_assistant",
        latency_ms=340.5,
        status="OK",
        prompt_tokens=400,
        completion_tokens=180,
    )
    assert span.traceparent.startswith("00-")
    assert monitor.token_usage_by_use_case["advisor_rag_assistant"] == 580
    assert any(a["type"] == "TOKEN_BUDGET_EXCEEDED" for a in monitor.alerts)

    runbook = monitor.generate_runbook_entry("iics_taskflow_failed", "Informatica_Snowflake_ELT")
    assert "Informatica Cloud (IICS)" in runbook["triage_steps"]
