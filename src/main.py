"""
FastAPI REST & JSON-RPC 2.0 Server for Enterprise-MCP-Router.
Exposes:
- Interactive Web Control Plane Dashboard (`GET /`)
- Standardized Model Context Protocol JSON-RPC 2.0 endpoint (`POST /mcp/jsonrpc`)
- Semantic Tool Routing & Context Bloat Profiler (`POST /api/v1/router/search`)
- OAuth2 RBAC & Stateful HITL Approval Interrupt Queue (`/api/v1/governance/*`)
- Governed Snowflake Cortex Search, Informatica Cloud (IICS) & PostgreSQL Connectors (`/api/v1/connectors/*`)
- Amazon Bedrock / AgentCore Converse API & Multi-Framework Bridges (`/api/v1/adapters/*`)
- OpenTelemetry Tracing, Token Budgets & L2 Operational Runbooks (`/api/v1/telemetry/*`)
"""

from typing import Any, Dict
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from src.dashboard_html import DASHBOARD_HTML
from src.security import AuthenticatedPrincipal, get_current_principal
from src.models import (
    AuthorizationRequest,
    BedrockStructuredInvokeRequest,
    HITLCreateRequest,
    HITLResolutionRequest,
    IICSTaskflowWebhookPayload,
    MCPJsonRpcRequest,
    PostgresQueryRequest,
    PostgresSnapshotRequest,
    RunbookLookupRequest,
    SemanticRouteRequest,
    SnowflakeCortexQueryRequest,
    SnowflakeSQLValidationRequest,
    TelemetrySpanRequest,
)
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

app = FastAPI(
    title="Enterprise-MCP-Router",
    description=(
        "Enterprise Model Context Protocol (FastMCP / JSON-RPC 2.0) Server, 105-Tool Semantic Router, "
        "RBAC/HITL Governance Gate, Cloud Data Connectors (Snowflake Cortex, Informatica IICS, PostgreSQL), "
        "and Amazon Bedrock / AgentCore Observability."
    ),
    version="2.1.0",
)

# Singleton service instances initialized with realistic enterprise state
mcp_router = EnterpriseMCPRouter.from_enterprise_catalog()
fastmcp_server = FastMCPServer(router=mcp_router)

snowflake_connector = SnowflakeCortexConnector(
    allowed_roles=["ai_platform_reader", "analyst", "data_engineer"],
    allowed_schemas=["PORTFOLIO_GOLD", "CORTEX_DOCS"],
)
snowflake_connector.seed_default_corpus()

informatica_adapter = InformaticaCloudTaskflowAdapter(min_rows_threshold=10, max_lag_minutes=30)
postgres_connector = PostgresEnterpriseConnector()
bedrock_adapter = BedrockAgentCoreAdapter(
    model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    max_retries=2,
)
telemetry_monitor = ProductionTelemetryMonitor(token_budget_per_use_case=5_000)

# Seed initial telemetry spans & sample HITL ticket for live dashboard demonstration
telemetry_monitor.record_span(
    span_name="mcp.router.route_by_query",
    use_case="advisor_rag_assistant",
    latency_ms=1.85,
    status="OK",
    prompt_tokens=180,
    completion_tokens=45,
)
telemetry_monitor.record_span(
    span_name="mcp.tool.snowflake_cortex_search",
    use_case="advisor_rag_assistant",
    latency_ms=138.4,
    status="OK",
    prompt_tokens=620,
    completion_tokens=210,
)
mcp_router.create_hitl_interrupt(
    tool_name="postgres.execute_outbound_wire",
    requested_by="treasury_rebalance_agent",
    user_roles=["platform_admin"],
    arguments={"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 50000.0},
    justification="Scheduled institutional liquidity sweep exceeding $25k auto-approval threshold.",
)


@app.get("/", response_class=HTMLResponse)
def serve_dashboard() -> HTMLResponse:
    """Serves the interactive Enterprise MCP Control Plane dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Returns service health, registered tool count, and active governance status."""
    return {
        "status": "healthy",
        "service": "enterprise-mcp-router",
        "protocol": "FastMCP / JSON-RPC 2.0",
        "total_registered_tools": len(mcp_router.tools),
        "domains": sorted({t.domain for t in mcp_router.tools.values()}),
        "pending_hitl_tickets": sum(
            1 for t in mcp_router.hitl_tickets.values() if t["status"] == "PENDING_APPROVAL"
        ),
        "rag_sync_locked": informatica_adapter.rag_sync_locked,
    }


@app.post("/mcp/jsonrpc")
def mcp_jsonrpc_endpoint(req: MCPJsonRpcRequest) -> Dict[str, Any]:
    """Standard Model Context Protocol (MCP) JSON-RPC 2.0 endpoint."""
    return fastmcp_server.handle_jsonrpc(req.model_dump())


@app.post("/api/v1/router/search")
def semantic_route_tools(req: SemanticRouteRequest) -> Dict[str, Any]:
    """Routes natural language intent to top-k MCP tools and reports token reduction."""
    res = mcp_router.route_by_query(
        query=req.query,
        k=req.top_k,
        domain_filter=req.domain_filter,
    )
    telemetry_monitor.record_span(
        span_name="mcp.router.semantic_search",
        use_case="mcp_tool_discovery",
        latency_ms=res["routing_latency_ms"],
        status="OK",
        prompt_tokens=res["routed_tokens"] // 4,
        completion_tokens=32,
    )
    return res


@app.post("/api/v1/governance/authorize")
def authorize_tool_call(
    req: AuthorizationRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Evaluates deterministic RBAC and HITL approval gates for a tool invocation."""
    user_roles = principal.roles if principal.is_authenticated else (req.user_roles or principal.roles)
    return mcp_router.authorize_execution(
        tool_name=req.tool_name,
        user_roles=user_roles,
        hitl_approved=False,  # External callers must supply an approved ticket_id for mutations
        hitl_ticket_id=req.hitl_ticket_id,
        require_ticket=True,
    )


@app.get("/api/v1/governance/hitl")
def list_hitl_tickets() -> Dict[str, Any]:
    """Lists all Human-in-the-Loop (HITL) approval interrupt tickets."""
    tickets = list(mcp_router.hitl_tickets.values())
    return {"total": len(tickets), "tickets": list(reversed(tickets))}


@app.post("/api/v1/governance/hitl/create")
def create_hitl_ticket(
    req: HITLCreateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Creates a new Human-in-the-Loop (HITL) approval interrupt ticket."""
    requested_by = principal.username if principal.is_authenticated else req.requested_by
    user_roles = principal.roles if principal.is_authenticated else req.user_roles
    return mcp_router.create_hitl_interrupt(
        tool_name=req.tool_name,
        requested_by=requested_by,
        user_roles=user_roles,
        arguments=req.arguments,
        justification=req.justification,
    )


@app.post("/api/v1/governance/hitl/resolve")
def resolve_hitl_ticket(
    req: HITLResolutionRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Approves or rejects a pending Human-in-the-Loop (HITL) interrupt ticket."""
    reviewer = principal.username if principal.is_authenticated else req.reviewer
    reviewer_roles = principal.roles if principal.is_authenticated else ["platform_admin"]

    result = mcp_router.resolve_hitl_interrupt(
        ticket_id=req.ticket_id,
        reviewer=reviewer,
        decision=req.decision,
        notes=req.notes,
        reviewer_roles=reviewer_roles,
    )
    if result.get("status") == "error":
        reason = result.get("reason", "")
        if "prohibited" in reason or "not_authorized" in reason:
            return JSONResponse(status_code=403, content=result)
        elif "not_found" in reason:
            return JSONResponse(status_code=404, content=result)
        elif "expired" in reason:
            return JSONResponse(status_code=410, content=result)
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/api/v1/connectors/snowflake/validate-sql")
def validate_snowflake_sql(req: SnowflakeSQLValidationRequest) -> Dict[str, Any]:
    """Validates read-only Snowflake SQL against RBAC, schema allow-list, and DDL/DML blocklist."""
    return snowflake_connector.validate_readonly_sql(
        sql=req.sql,
        role=req.role,
        schema=req.schema_name,
    )


@app.post("/api/v1/connectors/snowflake/cortex-search")
def query_snowflake_cortex(req: SnowflakeCortexQueryRequest) -> Dict[str, Any]:
    """Executes governed Snowflake Cortex Search retrieval over enterprise compliance docs."""
    return snowflake_connector.retrieve_cortex_rag(
        query=req.query,
        role=req.role,
        top_k=req.top_k,
    )


@app.post("/api/v1/connectors/informatica/validate")
def validate_informatica_taskflow(req: IICSTaskflowWebhookPayload) -> Dict[str, Any]:
    """Validates Informatica Cloud (IICS) ELT taskflow SLA and row counts prior to RAG indexing."""
    return informatica_adapter.validate_taskflow_run(req.model_dump())


@app.post("/api/v1/connectors/postgres/query")
def query_postgres_ledger(req: PostgresQueryRequest) -> Dict[str, Any]:
    """Executes read-only SQL query against the PostgreSQL institutional ledger."""
    return postgres_connector.query_ledger(sql=req.sql, role=req.role)


@app.post("/api/v1/connectors/postgres/snapshot/create")
def create_postgres_snapshot(req: PostgresSnapshotRequest) -> Dict[str, Any]:
    """Creates a point-in-time state snapshot of the PostgreSQL ledger."""
    return postgres_connector.create_snapshot(req.snapshot_name)


@app.post("/api/v1/connectors/postgres/snapshot/restore")
def restore_postgres_snapshot(
    req: PostgresSnapshotRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Restores the PostgreSQL ledger to a verified point-in-time snapshot."""
    if not (principal.has_role("platform_admin") or "platform_admin" in principal.roles):
        raise HTTPException(status_code=403, detail="platform_admin_role_required_for_snapshot_restore")
    actor = principal.username if principal.is_authenticated else "platform_admin"
    return postgres_connector.restore_snapshot(req.snapshot_name, actor=actor)


@app.post("/api/v1/adapters/bedrock/invoke")
def invoke_bedrock_structured(req: BedrockStructuredInvokeRequest) -> Dict[str, Any]:
    """Invokes Amazon Bedrock / AgentCore with deterministic structured output verification and retry."""
    state = {"calls": 0}

    def simulated_bedrock_provider() -> Dict[str, Any]:
        state["calls"] += 1
        if req.simulate_flaky_first_attempt and state["calls"] == 1:
            return {
                "output": {"summary": "Initial compliance pass (missing risk_tier and action)"},
                "usage": {"prompt_tokens": 190, "completion_tokens": 35},
            }
        return {
            "output": {
                "summary": "Verified Fund POL-101 compliance against RRSP & T+1 settlement rules.",
                "risk_tier": "LOW",
                "recommended_action": "PROCEED_WITH_REBALANCE",
                "confidence_score": 0.985,
            },
            "usage": {"prompt_tokens": 310, "completion_tokens": 95},
        }

    routed = mcp_router.route_by_query(req.prompt, k=3)["routed_tools"]
    result = bedrock_adapter.invoke_with_structured_output(
        required_keys=req.required_keys,
        provider_fn=simulated_bedrock_provider,
    )
    result["bedrock_converse_tool_config"] = bedrock_adapter.format_converse_tool_config(routed)
    return result


@app.get("/api/v1/adapters/bridges/{framework}")
def get_framework_bridge(framework: str) -> Dict[str, Any]:
    """Exports top routed MCP tools into LangGraph, smolagents, or CrewAI schemas."""
    sample_tools = mcp_router.route_by_query(
        "Snowflake Cortex Search, Informatica ELT, and PostgreSQL ledger", k=4
    )["routed_tools"]
    fw = framework.lower()
    if fw == "langgraph":
        exported = AgentFrameworkBridges.to_langgraph_tools(sample_tools)
    elif fw == "smolagents":
        exported = AgentFrameworkBridges.to_smolagents_tools(sample_tools)
    elif fw == "crewai":
        exported = AgentFrameworkBridges.to_crewai_tools(sample_tools)
    else:
        return {"status": "error", "reason": f"unsupported_framework:{framework}"}

    return {"status": "ok", "framework": fw, "exported_count": len(exported), "tools": exported}


@app.get("/api/v1/telemetry/summary")
def get_telemetry_summary() -> Dict[str, Any]:
    """Returns aggregated OpenTelemetry trace metrics, latency percentiles, and token budgets."""
    return telemetry_monitor.get_summary_metrics()


@app.post("/api/v1/telemetry/span")
def record_telemetry_span(req: TelemetrySpanRequest) -> Dict[str, Any]:
    """Records an OpenTelemetry execution span and evaluates token budget thresholds."""
    span = telemetry_monitor.record_span(
        span_name=req.span_name,
        use_case=req.use_case,
        latency_ms=req.latency_ms,
        status=req.status,
        prompt_tokens=req.prompt_tokens,
        completion_tokens=req.completion_tokens,
        error_message=req.error_message,
    )
    return {"status": "recorded", "trace_id": span.trace_id, "traceparent": span.traceparent}


@app.post("/api/v1/telemetry/runbook")
def lookup_operational_runbook(req: RunbookLookupRequest) -> Dict[str, str]:
    """Generates a standardized L2 operational runbook procedure for incident triage."""
    return telemetry_monitor.generate_runbook_entry(
        incident_type=req.incident_type,
        component=req.component,
    )
