from src.router import (
    AgentFrameworkBridges,
    BedrockAgentCoreAdapter,
    EnterpriseMCPRouter,
    EnterpriseRESTConnector,
    FastMCPServer,
    InformaticaCloudTaskflowAdapter,
    JSONSchemaContractValidator,
    MCPToolSpec,
    PostgresEnterpriseConnector,
    ProductionTelemetryMonitor,
    SnowflakeCortexConnector,
    ValueStreamManagementConnector,
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


def test_enterprise_120_tool_catalog_and_token_reduction():
    router = EnterpriseMCPRouter.from_enterprise_catalog()
    assert len(router.tools) == 120

    res = router.route_by_query(
        "Query Snowflake Cortex Search for Fidelity RRSP compliance rules and fund NAV",
        k=5,
    )
    assert res["total_registered_tools"] == 120
    assert len(res["routed_tools"]) == 5
    assert res["token_reduction_pct"] > 90.0
    assert res["routed_tools"][0]["domain"] == "snowflake"


def test_hybrid_bm25_and_dense_scores_without_synthetic_latency():
    router = EnterpriseMCPRouter.from_enterprise_catalog()
    res = router.route_by_query(
        "Identify management concerns across at-risk OKRs, product portfolios, and blocked engineering tickets",
        k=5,
    )
    top_tool = res["routed_tools"][0]
    assert top_tool["domain"] == "portfolio_vsm"
    assert "dense_score" in top_tool and "bm25_score" in top_tool
    assert 0.0 <= top_tool["dense_score"] <= 1.0
    assert 0.0 <= top_tool["bm25_score"] <= 1.0
    assert top_tool["bm25_score"] > 0.0
    assert res["routing_latency_ms"] >= 0.01


def test_json_schema_contract_validation_and_jsonrpc_32602():
    router = EnterpriseMCPRouter.from_enterprise_catalog()
    valid_wire = router.validate_tool_arguments(
        "postgres.execute_outbound_wire",
        {"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 5000.0, "environment": "prod"},
    )
    assert valid_wire["valid"] is True

    invalid_wire = router.validate_tool_arguments(
        "postgres.execute_outbound_wire",
        {"from_account": "ACC-9001", "amount_usd": -10, "environment": "invalid_env"},
    )
    assert invalid_wire["valid"] is False
    assert any("missing_required_field:to_account" in e for e in invalid_wire["errors"])
    assert any("minimum_violation:amount_usd" in e for e in invalid_wire["errors"])
    assert any("enum_violation:environment" in e for e in invalid_wire["errors"])

    server = FastMCPServer(router=router)
    err_resp = server.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": "postgres.execute_outbound_wire",
                "user_roles": ["platform_admin"],
                "hitl_approved": True,
                "arguments": {"from_account": "ACC-9001"},
            },
        }
    )
    assert err_resp["error"]["code"] == -32602


def test_stateful_hitl_interrupt_lifecycle():
    router = EnterpriseMCPRouter.from_enterprise_catalog()
    ticket = router.create_hitl_interrupt(
        tool_name="postgres.execute_outbound_wire",
        requested_by="agent_01",
        user_roles=["platform_admin"],
        arguments={"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 50000},
    )
    assert ticket["status"] == "PENDING_APPROVAL"

    # Before resolution, ticket does not grant approval
    denied = router.authorize_execution(
        "postgres.execute_outbound_wire",
        ["platform_admin"],
        hitl_ticket_id=ticket["ticket_id"],
    )
    assert denied["allowed"] is False

    # Approve ticket via authorized reviewer in dedicated hitl_approvers group
    resolved = router.resolve_hitl_interrupt(
        ticket_id=ticket["ticket_id"],
        reviewer="approver@enterprise.io",
        decision="APPROVED",
        reviewer_roles=["super_admin"],
        reviewer_groups=["hitl_approvers"],
    )
    assert resolved["status"] == "APPROVED"

    allowed = router.authorize_execution(
        "postgres.execute_outbound_wire",
        ["platform_admin"],
        hitl_ticket_id=ticket["ticket_id"],
        arguments={"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 50000},
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


def test_mcp_ping_resources_read_and_prompts_endpoints():
    vsm = ValueStreamManagementConnector()
    server = FastMCPServer(connectors={"vsm": vsm})

    ping_resp = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 10, "method": "ping"})
    assert ping_resp["result"]["status"] == "pong"

    res_list = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 11, "method": "resources/list"})
    uris = [r["uri"] for r in res_list["result"]["resources"]]
    assert "vsm://planview_portfolios/okrs_and_tickets" in uris

    res_read = server.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "resources/read",
            "params": {"uri": "vsm://planview_portfolios/okrs_and_tickets"},
        }
    )
    assert "PF-101" in res_read["result"]["contents"][0]["text"]

    prompts_list = server.handle_jsonrpc({"jsonrpc": "2.0", "id": 13, "method": "prompts/list"})
    assert any(p["name"] == "vsm_management_concern_briefing" for p in prompts_list["result"]["prompts"])

    prompt_get = server.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "prompts/get",
            "params": {"name": "vsm_management_concern_briefing", "arguments": {"portfolio_id": "PF-101"}},
        }
    )
    assert "PF-101" in prompt_get["result"]["messages"][0]["content"]["text"]


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

    # Keywords inside single-quoted string literals should not falsely trigger DDL/DML block
    literal_q = sf.validate_readonly_sql(
        "SELECT fund_id, name FROM PORTFOLIO_GOLD.FUNDS WHERE name = 'UPDATE OR DROP; TEST'",
        role="ai_platform_reader",
        schema="PORTFOLIO_GOLD",
    )
    assert literal_q["valid"] is True

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


def test_postgres_snapshot_and_real_relational_queries():
    pg = PostgresEnterpriseConnector()
    snap = pg.create_snapshot("before_wire")
    assert snap["status"] == "snapshot_created"

    # Real relational GROUP BY & parameterized WHERE queries
    agg = pg.query_ledger(
        "SELECT risk_tier, COUNT(*) AS cnt, SUM(balance_usd) AS total_usd FROM accounts GROUP BY risk_tier ORDER BY total_usd DESC"
    )
    assert agg["status"] == "ok"
    assert agg["engine"] == "sqlite3_relational"
    assert agg["row_count"] == 3
    assert agg["rows"][0]["risk_tier"] == "LOW"

    param_q = pg.query_ledger(
        "SELECT account_id, balance_usd FROM accounts WHERE risk_tier = ?",
        params=["HIGH"],
    )
    assert param_q["row_count"] == 1
    assert param_q["rows"][0]["account_id"] == "ACC-9004"

    # Authorizer must block write SQL through read-only endpoint
    denied_write = pg.query_ledger("DELETE FROM accounts")
    assert denied_write["status"] == "error"

    wire = pg.execute_wire_transfer("ACC-9001", "ACC-9002", 100000.0, hitl_approved=True)
    assert wire["status"] == "committed"
    assert wire["from_account"]["balance_usd"] == 1350000.0

    restored = pg.restore_snapshot("before_wire")
    assert restored["status"] == "snapshot_restored"
    assert restored["restored_accounts"][0]["balance_usd"] == 1450000.0


def test_vsm_connector_okr_portfolio_ticket_concern_analysis():
    vsm = ValueStreamManagementConnector()
    router = EnterpriseMCPRouter.from_enterprise_catalog()
    bedrock = BedrockAgentCoreAdapter()

    overview = vsm.get_overview()
    assert overview["summary"]["total_portfolios"] == 4
    assert overview["summary"]["blocked_tickets_count"] == 3

    analysis = vsm.analyze_management_concerns(
        query="Identify management concerns across OKRs, portfolios, and blocked tickets",
        router=router,
        bedrock_adapter=bedrock,
    )
    assert analysis["status"] == "ok"
    assert analysis["risk_tier"] == "CRITICAL"
    assert analysis["concerns_count"] >= 3
    blocked_ids = {t for c in analysis["concerns"] for t in c["blocking_tickets"]}
    assert {"ENG-401", "ENG-402", "ENG-403"}.issubset(blocked_ids)
    assert analysis["bedrock_validation"]["status"] == "success"
    assert len(analysis["recommended_actions"]) == analysis["concerns_count"]


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
    assert res["cumulative_usage"]["total_tokens"] == 225


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


def test_json_schema_validator_types_bounds_and_patterns():
    schema = {
        "type": "object",
        "properties": {
            "count": {"type": "integer", "minimum": 1, "maximum": 10},
            "code": {"type": "string", "minLength": 4, "pattern": "^PF-[0-9]+$"},
        },
        "required": ["count", "code"],
    }
    assert JSONSchemaContractValidator.validate(schema, {"count": 3, "code": "PF-101"})["valid"] is True
    # Booleans must not pass as integers in Python
    bad_bool = JSONSchemaContractValidator.validate(schema, {"count": True, "code": "PF-101"})
    assert bad_bool["valid"] is False
    bad_bounds = JSONSchemaContractValidator.validate(schema, {"count": 15, "code": "BAD"})
    assert bad_bounds["valid"] is False
    assert any("maximum_violation:count" in e for e in bad_bounds["errors"])
    assert any("min_length_violation:code" in e for e in bad_bounds["errors"])
    assert any("pattern_violation:code" in e for e in bad_bounds["errors"])


def test_snowflake_cte_write_block_and_iics_stale_rag_lock():
    sf = SnowflakeCortexConnector(allowed_roles=["ai_platform_reader"], allowed_schemas=["PORTFOLIO_GOLD"])
    cte_delete = sf.validate_readonly_sql(
        "WITH target AS (SELECT fund_id FROM PORTFOLIO_GOLD.FUNDS) DELETE FROM PORTFOLIO_GOLD.FUNDS",
        role="ai_platform_reader",
        schema="PORTFOLIO_GOLD",
    )
    assert cte_delete["valid"] is False
    assert cte_delete["reason"] == "mutating_sql_keyword_blocked"

    iics = InformaticaCloudTaskflowAdapter(min_rows_threshold=10, max_lag_minutes=30)
    stale_run = iics.validate_taskflow_run(
        {"taskflow_name": "tf_snowflake_fund_docs_elt", "status": "SUCCESS", "rows_processed": 500, "freshness_lag_minutes": 45}
    )
    assert stale_run["ready_for_rag"] is False
    assert stale_run["reason"] == "snowflake_staging_stale"
    assert iics.rag_sync_locked is True

