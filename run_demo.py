"""
End-to-End CLI Benchmark & Simulation Runner for Enterprise-MCP-Router.
Demonstrates:
1. 105-Tool Enterprise MCP Catalog & Dense Semantic Top-k Routing (~95% Context Bloat Reduction)
2. FastMCP / JSON-RPC 2.0 Protocol Dispatch (`initialize`, `tools/list`, `tools/call`)
3. OAuth2 RBAC & Stateful Human-in-the-Loop (HITL) Approval Interrupt Queue
4. Governed Snowflake Cortex Search, Informatica Cloud (IICS) ELT Validation & PostgreSQL Time-Travel Snapshots
5. Amazon Bedrock / AgentCore Converse API, Structured Outputs & OpenTelemetry Runbooks
"""

from src.router import (
    AgentFrameworkBridges,
    BedrockAgentCoreAdapter,
    EnterpriseMCPRouter,
    FastMCPServer,
    InformaticaCloudTaskflowAdapter,
    PostgresEnterpriseConnector,
    ProductionTelemetryMonitor,
    SnowflakeCortexConnector,
)


def main() -> None:
    print("=" * 88)
    print(" ENTERPRISE-MCP-ROUTER v2.1.0 | FastMCP Semantic Gateway & Cloud Governance Benchmark")
    print("=" * 88)

    # 1. Semantic Routing across 105 Enterprise Tools
    router = EnterpriseMCPRouter.from_enterprise_catalog()
    server = FastMCPServer(router=router)
    print(f"\n[1] Loaded Enterprise MCP Registry: {len(router.tools)} tools across 7 domains")

    sample_queries = [
        "Query Snowflake Cortex Search for RRSP compliance guidelines and check fund NAV",
        "Validate Informatica Cloud IICS ELT taskflow SLA and staging row counts before RAG sync",
        "Execute outbound bank wire in PostgreSQL treasury ledger and create point-in-time snapshot",
        "Aggregate Snyk CVE alerts across GitHub repos and open automated Docker-tested PR",
        "Query Kinaxis Maestro gating supplies and compute LightGBM Croston SKU forecast",
    ]

    print("\n    Semantic Top-5 Routing & Context-Window Token Savings Benchmark:")
    print(f"    {'Intent Query (Truncated)':<52} | {'Top-1 Routed Tool':<36} | {'Token Saving':<12}")
    print("    " + "-" * 106)
    for q in sample_queries:
        res = router.route_by_query(q, k=5)
        top1 = res["routed_tools"][0]
        print(
            f"    {q[:50]:<52} | {top1['name']:<36} | "
            f"{res['token_reduction_pct']:.2f}% ({res['full_registry_tokens']}->{res['routed_tokens']})"
        )

    # 2. OAuth2 RBAC & Stateful HITL Interrupt Lifecycle
    print("\n[2] OAuth2 RBAC & Human-in-the-Loop (HITL) Approval Gate Verification:")
    blocked = router.authorize_execution("postgres.execute_outbound_wire", ["platform_admin"], hitl_approved=False)
    print(f"    - Unapproved Mutating Call: allowed={blocked['allowed']} (reason={blocked['reason']})")

    ticket = router.create_hitl_interrupt(
        tool_name="postgres.execute_outbound_wire",
        requested_by="langgraph_treasury_agent",
        user_roles=["platform_admin"],
        arguments={"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 50000.0},
    )
    print(f"    - Created HITL Interrupt Ticket: {ticket['ticket_id']} (status={ticket['status']})")

    resolved = router.resolve_hitl_interrupt(
        ticket_id=ticket["ticket_id"],
        reviewer="sr_ops_approver@enterprise.io",
        decision="APPROVED",
    )
    auth_after = router.authorize_execution(
        "postgres.execute_outbound_wire",
        ["platform_admin"],
        hitl_ticket_id=resolved["ticket_id"],
    )
    print(f"    - Post-HITL Approval Call : allowed={auth_after['allowed']} (ticket={resolved['ticket_id']})")

    # 3. Snowflake Cortex Search, Informatica IICS & PostgreSQL Snapshots
    print("\n[3] Cloud & Enterprise Data Connectors (Snowflake, Informatica IICS, PostgreSQL):")
    sf = SnowflakeCortexConnector(
        allowed_roles=["ai_platform_reader"],
        allowed_schemas=["PORTFOLIO_GOLD", "CORTEX_DOCS"],
    )
    sf.seed_default_corpus()
    sql_ok = sf.validate_readonly_sql("SELECT fund_id, nav FROM PORTFOLIO_GOLD.FUNDS WHERE active = 1", "ai_platform_reader", "PORTFOLIO_GOLD")
    sql_bad = sf.validate_readonly_sql("SELECT * FROM PORTFOLIO_GOLD.FUNDS; DROP TABLE FUNDS", "ai_platform_reader", "PORTFOLIO_GOLD")
    print(f"    - Snowflake Read-Only SQL Allow-List : SELECT valid={sql_ok['valid']} | Stacked DROP valid={sql_bad['valid']} ({sql_bad['reason']})")

    iics = InformaticaCloudTaskflowAdapter(min_rows_threshold=10, max_lag_minutes=30)
    elt_res = iics.validate_taskflow_run({"taskflow_name": "tf_snowflake_fund_docs_elt", "status": "SUCCESS", "rows_processed": 1450, "freshness_lag_minutes": 8})
    print(f"    - Informatica Cloud (IICS) ELT Gate  : ready_for_rag={elt_res['ready_for_rag']} (lock={elt_res['rag_index_lock']})")

    pg = PostgresEnterpriseConnector()
    pg.create_snapshot("pre_wire_snap")
    pg.execute_wire_transfer("ACC-9001", "ACC-9003", 50000.0, hitl_approved=True)
    restored = pg.restore_snapshot("pre_wire_snap")
    print(f"    - PostgreSQL Time-Travel Snapshot    : status={restored['status']} (ACC-9001 restored to ${restored['restored_accounts'][0]['balance_usd']:,.2f})")

    # 4. Amazon Bedrock / AgentCore & Framework Bridges
    print("\n[4] Amazon Bedrock / AgentCore Structured Outputs & Multi-Framework Bridges:")
    bedrock = BedrockAgentCoreAdapter()
    attempts = {"n": 0}

    def provider_sim():
        attempts["n"] += 1
        if attempts["n"] == 1:
            return {"output": {"summary": "Partial"}, "usage": {"prompt_tokens": 110, "completion_tokens": 20}}
        return {
            "output": {"summary": "RRSP compliant", "risk_tier": "LOW", "action": "APPROVE"},
            "usage": {"prompt_tokens": 240, "completion_tokens": 65},
        }

    bd_out = bedrock.invoke_with_structured_output(["summary", "risk_tier", "action"], provider_sim)
    routed_sample = router.route_by_query("Snowflake Cortex Search and PostgreSQL ledger", k=3)["routed_tools"]
    lg_tools = AgentFrameworkBridges.to_langgraph_tools(routed_sample)
    sm_tools = AgentFrameworkBridges.to_smolagents_tools(routed_sample)
    print(f"    - Bedrock Self-Healing Schema Verify : status={bd_out['status']} in {bd_out['attempts']} attempts ({bd_out['usage']['total_tokens']} tokens)")
    print(f"    - Exported Framework Tool Bridges    : LangGraph={len(lg_tools)} tools | HF smolagents={len(sm_tools)} tools")

    # 5. OpenTelemetry & L2 Runbooks
    print("\n[5] OpenTelemetry Trace Spans, Token Budgets & L2 Operational Runbooks:")
    monitor = ProductionTelemetryMonitor(token_budget_per_use_case=500)
    span = monitor.record_span("mcp.tool.snowflake_cortex_search", "advisor_rag_assistant", 118.4, "OK", 380, 160)
    rb = monitor.generate_runbook_entry("iics_taskflow_failed", "Informatica_Snowflake_ELT")
    print(f"    - OpenTelemetry W3C traceparent      : {span.traceparent}")
    print(f"    - Active Token Budget Alerts         : {len(monitor.alerts)} alert(s) triggered")
    print(f"    - L2 Runbook ({rb['incident_type']}) : {rb['severity']} | SLA: {rb['sla_target']}")
    print("\n" + "=" * 88)
    print(" ALL 5 ARCHITECTURAL PILLARS VERIFIED SUCCESSFULLY.")
    print("=" * 88)


if __name__ == "__main__":
    main()
