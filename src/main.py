"""
FastAPI REST & JSON-RPC 2.0 / SSE Server for Enterprise-MCP-Router.
Exposes:
- Interactive Web Control Plane Dashboard (`GET /`)
- Standardized Model Context Protocol JSON-RPC 2.0 & SSE endpoints (`POST /mcp/jsonrpc`, `GET /mcp/sse`, `POST /mcp/messages`)
- Hybrid Okapi BM25 + 64-Dim Dense Semantic Tool Router (`POST /api/v1/router/search`)
- OAuth2 RBAC, JSON Schema Contract Validator & Stateful HITL Queue (`/api/v1/governance/*`)
- Value Stream Management (OKRs, Product Portfolios, Engineering Tickets & Concern Advisor) (`/api/v1/vsm/*`)
- Governed Snowflake Cortex Search, Informatica Cloud (IICS) & Relational SQLite/PostgreSQL Connectors (`/api/v1/connectors/*`)
- Amazon Bedrock / AgentCore Converse API & Multi-Framework Bridges (`/api/v1/adapters/*`)
- OpenTelemetry Tracing, Token Budgets & L2 Operational Runbooks (`/api/v1/telemetry/*`)
"""

from contextlib import asynccontextmanager
import json
import os
import time
from typing import Any, Dict, Iterator, Optional
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from src.dashboard_html import DASHBOARD_HTML
from src.security import (
    AuthenticatedPrincipal,
    create_jwt_token,
    enforce_rate_limit,
    is_dev_mode,
    is_role_authorized,
    validate_security_config,
)
from src.storage import SQLiteStateStore
from src.models import (
    AuthorizationRequest,
    AuthTokenRequest,
    BedrockStructuredInvokeRequest,
    HITLCreateRequest,
    HITLResolutionRequest,
    IICSTaskflowWebhookPayload,
    MCPJsonRpcRequest,
    PostgresQueryRequest,
    PostgresSnapshotRequest,
    RoutingFeedbackRequest,
    RunbookLookupRequest,
    SchemaValidationRequest,
    SemanticRouteRequest,
    SnowflakeCortexQueryRequest,
    SnowflakeSQLValidationRequest,
    TelemetrySpanRequest,
    VSMConcernRequest,
    VSMSqlQueryRequest,
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
    ValueStreamManagementConnector,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Refuses server startup unless JWT/OIDC credentials or explicit dev mode are configured."""
    validate_security_config()
    yield


app = FastAPI(
    title="Enterprise-MCP-Router",
    description=(
        "FastMCP / JSON-RPC 2.0 + SSE Server, 120-Tool Semantic & BM25 Router, "
        "RBAC/JSON Schema/HITL Governance Gate, Value Stream Management, "
        "Cloud Data Connectors (Snowflake Cortex, Informatica IICS, SQLite/PostgreSQL), and Bedrock Observability."
    ),
    version="2.2.0",
    lifespan=lifespan,
)

# Singleton service instances initialized with realistic enterprise state
mcp_router = EnterpriseMCPRouter.from_enterprise_catalog()
snowflake_connector = SnowflakeCortexConnector(
    allowed_roles=["ai_platform_reader", "analyst", "data_engineer"],
    allowed_schemas=["PORTFOLIO_GOLD", "CORTEX_DOCS"],
)
snowflake_connector.seed_default_corpus()

informatica_adapter = InformaticaCloudTaskflowAdapter(min_rows_threshold=10, max_lag_minutes=30)
postgres_connector = PostgresEnterpriseConnector()
vsm_connector = ValueStreamManagementConnector()
fastmcp_server = FastMCPServer(
    version="2.2.0",
    router=mcp_router,
    connectors={
        "snowflake": snowflake_connector,
        "informatica": informatica_adapter,
        "postgres": postgres_connector,
        "vsm": vsm_connector,
    },
)
bedrock_adapter = BedrockAgentCoreAdapter(
    model_id="anthropic.claude-sonnet-4-20250514",
    max_retries=2,
)
telemetry_monitor = ProductionTelemetryMonitor(token_budget_per_use_case=5_000)

# Seed initial telemetry spans & sample HITL ticket for live dashboard demonstration
telemetry_monitor.record_span(
    span_name="mcp.router.route_by_query",
    use_case="advisor_rag_assistant",
    latency_ms=0.92,
    status="OK",
    prompt_tokens=180,
    completion_tokens=45,
)
telemetry_monitor.record_span(
    span_name="mcp.vsm.analyze_management_concerns",
    use_case="vsm_portfolio_copilot",
    latency_ms=42.6,
    status="OK",
    prompt_tokens=410,
    completion_tokens=215,
)
if not mcp_router.hitl_tickets:
    mcp_router.create_hitl_interrupt(
        tool_name="postgres.execute_outbound_wire",
        requested_by="treasury_rebalance_agent",
        user_roles=["platform_admin"],
        arguments={"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 50000.0},
        justification="Scheduled institutional liquidity sweep exceeding $25k auto-approval threshold.",
        requester_groups=["platform_operators"],
    )


@app.get("/", response_class=HTMLResponse)
def serve_dashboard() -> HTMLResponse:
    """Serves the interactive Enterprise MCP Control Plane dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Returns service health, registered tool count, storage backend, and governance status."""
    storage_backend = "sqlite_wal" if isinstance(mcp_router.storage, SQLiteStateStore) else "in_memory_bounded"
    return {
        "status": "healthy",
        "version": "2.2.0",
        "service": "enterprise-mcp-router",
        "protocol": "FastMCP / JSON-RPC 2.0 + SSE",
        "dev_mode": is_dev_mode(),
        "storage_backend": storage_backend,
        "total_registered_tools": len(mcp_router.tools),
        "domains": sorted({t.domain for t in mcp_router.tools.values()}),
        "pending_hitl_tickets": sum(
            1 for t in mcp_router.hitl_tickets.values() if t["status"] == "PENDING_APPROVAL"
        ),
        "rag_sync_locked": informatica_adapter.rag_sync_locked,
    }


@app.post("/mcp/jsonrpc")
def mcp_jsonrpc_endpoint(
    req: MCPJsonRpcRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Standard Model Context Protocol (MCP) JSON-RPC 2.0 endpoint."""
    return fastmcp_server.handle_jsonrpc(req.model_dump(), principal=principal)


@app.post("/mcp/messages")
def mcp_messages_endpoint(
    req: MCPJsonRpcRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """MCP HTTP+SSE message dispatch endpoint."""
    return fastmcp_server.handle_jsonrpc(req.model_dump(), principal=principal)


@app.get("/mcp/sse")
def mcp_sse_endpoint() -> StreamingResponse:
    """MCP Server-Sent Events (SSE) endpoint advertising message transport and capabilities."""
    def _event_stream() -> Iterator[str]:
        yield "event: endpoint\ndata: /mcp/messages\n\n"
        capabilities_payload = json.dumps(
            {
                "serverInfo": {"name": fastmcp_server.name, "version": fastmcp_server.version},
                "totalTools": len(mcp_router.tools),
                "domains": sorted({t.domain for t in mcp_router.tools.values()}),
            }
        )
        yield f"event: capabilities\ndata: {capabilities_payload}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@app.post("/api/v1/auth/token")
def issue_session_jwt(
    req: AuthTokenRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """
    Mints a short-lived HS256 JWT bearer token strictly in dev mode (ROUTER_DEV_MODE=1).
    Disabled by default and capped to the platform_operators group (cannot mint super_admin or hitl_approvers).
    """
    if not is_dev_mode() or os.getenv("MCP_DISABLE_DEMO_TOKEN_MINT", "0") == "1":
        raise HTTPException(status_code=403, detail="token_minting_disabled_unless_dev_mode")
    token = create_jwt_token(
        username=req.username,
        roles=[req.role],
        groups=["platform_operators"],
        expires_in_seconds=3600,
    )
    return {
        "access_token": token,
        "token_type": "Bearer",
        "username": req.username,
        "roles": [req.role],
        "groups": ["platform_operators"],
        "expires_in": 3600,
    }


@app.post("/api/v1/router/search")
def semantic_route_tools(
    req: SemanticRouteRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Routes natural language intent to top-k role-authorized MCP tools via tuned BM25 + dense RRF scoring."""
    res = mcp_router.route_by_query(
        query=req.query,
        k=req.top_k,
        domain_filter=req.domain_filter,
        caller_roles=principal.roles,
        scoring_mode=req.scoring_mode,
        auto_widen=req.auto_widen,
    )
    telemetry_monitor.record_span(
        span_name="mcp.router.semantic_search",
        use_case="mcp_tool_discovery",
        latency_ms=res["routing_latency_ms"],
        status="OK",
        prompt_tokens=max(1, res["routed_tokens"] // 4),
        completion_tokens=32,
    )
    return res


@app.post("/api/v1/router/feedback")
def record_routing_feedback(
    req: RoutingFeedbackRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Records whether an LLM actually selected one of the routed top-k tools, queuing misses for eval."""
    return mcp_router.record_tool_selection_feedback(
        query=req.query,
        routed_tools=req.routed_tools,
        selected_tool=req.selected_tool,
    )


@app.get("/api/v1/router/misses")
def get_routing_misses(
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Returns captured routing misses queued for the continuous evaluation dataset."""
    return {
        "stats": dict(mcp_router.routing_feedback_stats),
        "misses": list(reversed(mcp_router.routing_misses_eval_queue)),
    }


@app.post("/api/v1/governance/authorize")
def authorize_tool_call(
    req: AuthorizationRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """
    Evaluates deterministic JWT/API-key RBAC and server-side HITL ticket + argument-hash approval gates.
    Client-supplied user_roles and hitl_approved are not accepted.
    """
    return mcp_router.authorize_execution(
        tool_name=req.tool_name,
        user_roles=principal.roles,
        hitl_approved=False,
        hitl_ticket_id=req.hitl_ticket_id,
        require_ticket=True,
        arguments=req.arguments,
    )


@app.post("/api/v1/governance/validate-schema")
def validate_tool_schema(
    req: SchemaValidationRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Validates tool arguments against the tool's registered JSON Schema Draft-07 contract."""
    return mcp_router.validate_tool_arguments(
        tool_name=req.tool_name,
        arguments=req.arguments,
    )


@app.get("/api/v1/governance/hitl")
def list_hitl_tickets(
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Lists all Human-in-the-Loop (HITL) approval interrupt tickets from durable storage."""
    tickets = mcp_router.storage.list_tickets()
    return {"total": len(tickets), "tickets": tickets}


@app.get("/api/v1/governance/audit-verify")
def verify_audit_hash_chain(
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Verifies SHA-256 hash-chain tamper integrity across persisted append-only audit events."""
    chain = mcp_router.storage.verify_audit_chain()
    return {
        **chain,
        "checked_events": chain.get("total_events", 0),
        "recent_events": mcp_router.storage.get_audit_trail(limit=15),
    }


@app.post("/api/v1/governance/hitl/create")
def create_hitl_ticket(
    req: HITLCreateRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Any:
    """Creates a new Human-in-the-Loop (HITL) approval interrupt ticket bound to verified principal & arg hash."""
    if not principal.is_authenticated:
        raise HTTPException(status_code=401, detail="authentication_required_to_create_hitl_ticket")

    spec = mcp_router.tools.get(req.tool_name)
    if spec and not is_role_authorized(spec.required_role, principal.roles):
        return JSONResponse(
            status_code=403,
            content={
                "status": "error",
                "reason": "rbac_denied",
                "required_role": spec.required_role,
                "caller_roles": principal.roles,
            },
        )

    return mcp_router.create_hitl_interrupt(
        tool_name=req.tool_name,
        requested_by=principal.username,
        user_roles=principal.roles,
        arguments=req.arguments,
        justification=req.justification,
        ttl_seconds=req.ttl_seconds,
        requester_groups=principal.groups,
    )


@app.post("/api/v1/governance/hitl/resolve")
def resolve_hitl_ticket(
    req: HITLResolutionRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Any:
    """Approves or rejects a pending Human-in-the-Loop (HITL) interrupt ticket via verified reviewer identity."""
    if not principal.is_authenticated:
        raise HTTPException(status_code=401, detail="authentication_required_to_resolve_hitl_ticket")

    result = mcp_router.resolve_hitl_interrupt(
        ticket_id=req.ticket_id,
        reviewer=principal.username,
        decision=req.decision,
        notes=req.notes,
        reviewer_roles=principal.roles,
        reviewer_groups=principal.groups,
    )
    if result.get("status") == "error":
        reason = result.get("reason", "")
        if "prohibited" in reason or "not_authorized" in reason or "missing_approver_group" in reason:
            return JSONResponse(status_code=403, content=result)
        if "not_found" in reason:
            return JSONResponse(status_code=404, content=result)
        if "expired" in reason:
            return JSONResponse(status_code=410, content=result)
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/v1/vsm/overview")
def get_vsm_overview(
    portfolio_id: Optional[str] = None,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Returns connected product portfolios, OKRs, and engineering work tickets."""
    return vsm_connector.get_overview(portfolio_id=portfolio_id)


@app.post("/api/v1/vsm/query")
def query_vsm_relational(
    req: VSMSqlQueryRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Executes read-only relational SQL queries across product portfolios, OKRs, and tickets."""
    return vsm_connector.query_vsm_sql(sql=req.sql, role=req.role, params=req.params)


@app.post("/api/v1/vsm/analyze-concerns")
def analyze_vsm_concerns(
    req: VSMConcernRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Detects management concerns across OKRs, portfolios & tickets and recommends governed MCP actions."""
    t0 = time.perf_counter()
    res = vsm_connector.analyze_management_concerns(
        query=req.query,
        portfolio_id=req.portfolio_id,
        router=mcp_router,
        bedrock_adapter=bedrock_adapter,
    )
    elapsed_ms = round(max(0.01, (time.perf_counter() - t0) * 1000.0), 2)
    usage = (res.get("bedrock_validation") or {}).get("usage", {})
    telemetry_monitor.record_span(
        span_name="mcp.vsm.analyze_management_concerns",
        use_case="vsm_portfolio_copilot",
        latency_ms=elapsed_ms,
        status="OK",
        prompt_tokens=int(usage.get("prompt_tokens", 320)),
        completion_tokens=int(usage.get("completion_tokens", 180)),
    )
    return res


@app.post("/api/v1/connectors/snowflake/validate-sql")
def validate_snowflake_sql(
    req: SnowflakeSQLValidationRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Validates read-only Snowflake SQL against RBAC, schema/table allow-lists, and AST checks."""
    return snowflake_connector.validate_readonly_sql(
        sql=req.sql,
        role=req.role,
        schema=req.schema_name,
    )


@app.post("/api/v1/connectors/snowflake/cortex-search")
def query_snowflake_cortex(
    req: SnowflakeCortexQueryRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Executes governed Snowflake Cortex Search retrieval over enterprise compliance docs."""
    return snowflake_connector.retrieve_cortex_rag(
        query=req.query,
        role=req.role,
        top_k=req.top_k,
    )


@app.post("/api/v1/connectors/informatica/validate")
def validate_informatica_taskflow(
    req: IICSTaskflowWebhookPayload,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Validates Informatica Cloud (IICS) ELT taskflow SLA and row counts prior to RAG indexing."""
    return informatica_adapter.validate_taskflow_run(req.model_dump())


@app.post("/api/v1/connectors/postgres/query")
def query_postgres_ledger(
    req: PostgresQueryRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Executes read-only parameterized SQL query against the relational ledger."""
    return postgres_connector.query_ledger(sql=req.sql, role=req.role, params=req.params)


@app.post("/api/v1/connectors/postgres/snapshot/create")
def create_postgres_snapshot(
    req: PostgresSnapshotRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Creates a point-in-time state snapshot of the relational ledger."""
    return postgres_connector.create_snapshot(req.snapshot_name)


@app.post("/api/v1/connectors/postgres/snapshot/restore")
def restore_postgres_snapshot(
    req: PostgresSnapshotRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Restores the relational ledger to a verified point-in-time snapshot."""
    if not principal.is_authenticated or not is_role_authorized("platform_admin", principal.roles):
        raise HTTPException(status_code=403, detail="platform_admin_role_required_for_snapshot_restore")
    return postgres_connector.restore_snapshot(req.snapshot_name, actor=principal.username)


@app.get("/api/v1/router/benchmark")
def get_router_benchmark(
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Returns cached train & held-out Recall@k and ablation measurements over serialized schemas."""
    cached = getattr(app.state, "benchmark_cache", None)
    if cached is None:
        from src.registry.eval_dataset import run_full_routing_benchmark

        cached = run_full_routing_benchmark(mcp_router)
        app.state.benchmark_cache = cached
    return cached


@app.post("/api/v1/adapters/bedrock/invoke")
def invoke_bedrock_structured(
    req: BedrockStructuredInvokeRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
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
    result = bedrock_adapter.invoke_converse_live_or_sim(
        prompt=req.prompt,
        required_keys=req.required_keys,
        tools=routed,
        fallback_fn=simulated_bedrock_provider,
    )
    result["bedrock_converse_tool_config"] = bedrock_adapter.format_converse_tool_config(routed)
    return result


@app.get("/api/v1/adapters/bridges/{framework}")
def get_framework_bridge(
    framework: str,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Exports top routed MCP tools into LangGraph, smolagents, or CrewAI schemas."""
    sample_tools = mcp_router.route_by_query(
        "Value Stream OKR management concerns, Snowflake Cortex Search, and PostgreSQL ledger", k=4
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
def get_telemetry_summary(
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Returns aggregated OpenTelemetry trace metrics, latency percentiles, and token budgets."""
    return telemetry_monitor.get_summary_metrics()


@app.post("/api/v1/telemetry/span")
def record_telemetry_span(
    req: TelemetrySpanRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
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
def lookup_operational_runbook(
    req: RunbookLookupRequest,
    principal: AuthenticatedPrincipal = Depends(enforce_rate_limit),
) -> Dict[str, str]:
    """Generates an operational runbook procedure for incident triage."""
    return telemetry_monitor.generate_runbook_entry(
        incident_type=req.incident_type,
        component=req.component,
    )
