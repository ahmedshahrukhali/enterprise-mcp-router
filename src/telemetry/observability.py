"""
Production Observability, OpenTelemetry Trace Collector, Token Budget Alerts,
and Standardized L2 Operational Support Runbook Generator.
"""

import math
import uuid
from dataclasses import asdict, dataclass
from typing import Any, ClassVar


@dataclass
class TraceSpan:
    trace_id: str
    span_name: str
    use_case: str
    latency_ms: float
    status: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error_message: str | None = None
    traceparent: str = ""

    def __post_init__(self) -> None:
        if not self.traceparent:
            raw_trace = self.trace_id.replace("-", "")[:32].ljust(32, "0")
            raw_span = uuid.uuid4().hex[:16]
            self.traceparent = f"00-{raw_trace}-{raw_span}-01"


class ProductionTelemetryMonitor:
    """
    Production observability and telemetry collector for Agentic AI workloads.
    Tracks OpenTelemetry trace spans, token usage per use case, runtime errors,
    latency percentiles (p50, p95, p99), and generates operational support
    runbook entries for L2 incident triage.
    """

    RUNBOOK_CATALOG: ClassVar[dict[str, dict[str, str]]] = {
        "iics_taskflow_failed": {
            "severity": "SEV-2 (Data Pipeline SLA Breach)",
            "sla_target": "15 minutes",
            "triage_steps": (
                "1. Inspect Informatica Cloud (IICS) taskflow session logs and Secure Agent health. "
                "2. Verify source ERP/document connector credentials in AWS Secrets Manager. "
                "3. Confirm downstream RAG sync lock is active; re-trigger failed IICS mapping task and verify Snowflake staging table row count."
            ),
        },
        "snowflake_query_timeout": {
            "severity": "SEV-2 (Retrieval Degradation)",
            "sla_target": "10 minutes",
            "triage_steps": (
                "1. Check Snowflake virtual warehouse queue depth and auto-suspend settings in PORTFOLIO_GOLD. "
                "2. Verify Cortex Search index refresh status and RBAC role grants (ai_platform_reader). "
                "3. Fail over retrieval tool to cached snapshot if warehouse recovery exceeds 5 minutes."
            ),
        },
        "bedrock_throttling_or_schema_error": {
            "severity": "SEV-2 (Model Invocation / Schema Contract)",
            "sla_target": "10 minutes",
            "triage_steps": (
                "1. Check CloudWatch metrics for Amazon Bedrock ModelInvocationThrottledException and token usage spikes. "
                "2. Validate Pydantic JSON-schema prompt constraints and fallback to secondary cross-region inference profile (us-west-2)."
            ),
        },
        "hitl_approval_timeout": {
            "severity": "SEV-3 (Governance Gate Pending)",
            "sla_target": "30 minutes",
            "triage_steps": (
                "1. Inspect pending HITL ticket ID in Enterprise-MCP-Router governance queue. "
                "2. Verify Slack/PagerDuty webhook notification delivery to designated platform_admin reviewer. "
                "3. Auto-expire mutating tool execution token and roll back staged transaction if unapproved after TTL."
            ),
        },
        "postgres_connection_pool_exhausted": {
            "severity": "SEV-1 (Transactional Store Saturation)",
            "sla_target": "5 minutes",
            "triage_steps": (
                "1. Inspect PgBouncer active/waiting client connections and terminate idle-in-transaction agent sessions. "
                "2. Verify read-only queries are routed to read replicas. "
                "3. Restore point-in-time table snapshot if partial mutation occurred prior to timeout."
            ),
        },
        "rbac_privilege_escalation_attempt": {
            "severity": "SEV-1 (Security & Access-Control Alert)",
            "sla_target": "Immediate (Automated Block)",
            "triage_steps": (
                "1. Isolate offending session OAuth2 JWT subject and traceparent ID in SIEM/Datadog logs. "
                "2. Confirm deterministic RBAC gate blocked execution of mutating or unauthorized SQL/MCP tool. "
                "3. Rotate temporary On-Behalf-Of (OBO) credentials and notify Security Operations."
            ),
        },
    }

    def __init__(
        self,
        token_budget_per_use_case: int = 10_000,
        max_spans: int = 2000,
        max_alerts: int = 500,
    ):
        self.token_budget_per_use_case = token_budget_per_use_case
        self.max_spans = max_spans
        self.max_alerts = max_alerts
        self.spans: list[TraceSpan] = []
        self.token_usage_by_use_case: dict[str, int] = {}
        self.alerts: list[dict[str, Any]] = []

    def record_span(
        self,
        span_name: str,
        use_case: str,
        latency_ms: float,
        status: str = "OK",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error_message: str | None = None,
    ) -> TraceSpan:
        """Records an execution trace span, aggregates token usage, and triggers alerts."""
        total_tokens = prompt_tokens + completion_tokens
        span = TraceSpan(
            trace_id=str(uuid.uuid4()),
            span_name=span_name,
            use_case=use_case,
            latency_ms=round(float(latency_ms), 2),
            status=status,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            error_message=error_message,
        )
        self.spans.append(span)
        if len(self.spans) > self.max_spans:
            self.spans = self.spans[-self.max_spans:]

        self.token_usage_by_use_case[use_case] = (
            self.token_usage_by_use_case.get(use_case, 0) + total_tokens
        )

        if status != "OK" or error_message:
            self.alerts.append(
                {
                    "type": "RUNTIME_FAILURE",
                    "use_case": use_case,
                    "span_name": span_name,
                    "traceparent": span.traceparent,
                    "detail": error_message or "non_ok_span_status",
                }
            )

        if self.token_usage_by_use_case[use_case] > self.token_budget_per_use_case:
            self.alerts.append(
                {
                    "type": "TOKEN_BUDGET_EXCEEDED",
                    "use_case": use_case,
                    "total_tokens": self.token_usage_by_use_case[use_case],
                    "budget": self.token_budget_per_use_case,
                }
            )

        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]

        return span

    def get_summary_metrics(self) -> dict[str, Any]:
        latencies = sorted(s.latency_ms for s in self.spans)
        n = len(latencies)
        if n == 0:
            p50 = p95 = p99 = 0.0
        else:
            p50 = latencies[min(math.floor(0.50 * (n - 1)), n - 1)]
            p95 = latencies[min(math.floor(0.95 * (n - 1)), n - 1)]
            p99 = latencies[min(math.floor(0.99 * (n - 1)), n - 1)]

        total_tokens = sum(self.token_usage_by_use_case.values())
        error_spans = sum(1 for s in self.spans if s.status != "OK" or s.error_message)

        return {
            "total_spans": n,
            "error_spans": error_spans,
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
            "total_tokens_consumed": total_tokens,
            "token_budget_per_use_case": self.token_budget_per_use_case,
            "token_usage_by_use_case": dict(self.token_usage_by_use_case),
            "active_alerts": list(self.alerts),
            "recent_spans": [asdict(s) for s in self.spans[-12:]],
        }

    def generate_runbook_entry(self, incident_type: str, component: str) -> dict[str, str]:
        """Generates a standardized L2 operational runbook procedure for incident triage."""
        entry = self.RUNBOOK_CATALOG.get(incident_type)
        if entry:
            return {
                "incident_type": incident_type,
                "component": component,
                "severity": entry["severity"],
                "sla_target": entry["sla_target"],
                "triage_steps": entry["triage_steps"],
            }
        return {
            "incident_type": incident_type,
            "component": component,
            "severity": "SEV-3 (General Operational Alert)",
            "sla_target": "30 minutes",
            "triage_steps": (
                "1. Inspect structured application logs and OpenTelemetry trace ID. "
                "2. Validate upstream data/API health and escalate to Platform Ops if unresolved."
            ),
        }
