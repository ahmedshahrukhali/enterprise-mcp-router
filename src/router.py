"""
Enterprise Model Context Protocol (MCP) Server, Hybrid Semantic + BM25 Tool Router & Cloud Data Connectors.
Provides:
- FastMCP-compatible decorator registration (@mcp.tool) and JSON-RPC 2.0 protocol dispatch
- 64-dim Feature-Hashed Dense + Okapi BM25 + RRF top-k tool routing across 120+ registered enterprise tools
- OAuth2 / RBAC governance, JSON Schema Draft-07 input/output contract validation & stateful HITL approval queue
- Re-exports of SnowflakeCortexConnector, InformaticaCloudTaskflowAdapter, PostgresEnterpriseConnector,
  ValueStreamManagementConnector, EnterpriseRESTConnector, BedrockAgentCoreAdapter, AgentFrameworkBridges,
  and ProductionTelemetryMonitor.
"""

import inspect
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.adapters.agent_adapters import AgentFrameworkBridges, BedrockAgentCoreAdapter
from src.connectors.data_connectors import (
    EnterpriseRESTConnector,
    InformaticaCloudTaskflowAdapter,
    PostgresEnterpriseConnector,
    SnowflakeCortexConnector,
    ValueStreamManagementConnector,
)
from src.registry.bge_embeddings import (
    DEFAULT_BGE_PROVIDER,
    cosine_similarity as bge_cosine_similarity,
)
from src.registry.catalog import (
    OkapiBM25Index,
    compute_query_embedding,
    get_enterprise_tool_catalog,
)
from src.security import AuthenticatedPrincipal, HITLGovernanceRules, is_role_authorized
from src.storage import BaseStateStore, get_default_storage
from src.telemetry.observability import ProductionTelemetryMonitor, TraceSpan


@dataclass
class MCPToolSpec:
    name: str
    description: str
    is_mutating: bool
    required_role: str
    embedding: List[float]
    domain: str = "enterprise"
    input_schema: Dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {"query_or_id": {"type": "string"}},
            "required": ["query_or_id"],
        }
    )
    schema_tokens: int = 148


class JSONSchemaContractValidator:
    """
    Deterministic JSON Schema Draft-07 contract validator for MCP tool arguments
    and structured agent outputs.
    """

    @staticmethod
    def _matches_type(value: Any, expected_type: str) -> bool:
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "object":
            return isinstance(value, dict)
        return True

    @classmethod
    def validate(cls, schema: Dict[str, Any], payload: Any) -> Dict[str, Any]:
        """Validates `payload` against a JSON Schema object contract."""
        errors: List[str] = []
        expected_root = schema.get("type", "object")
        if expected_root == "object" and not isinstance(payload, dict):
            return {"valid": False, "errors": [f"expected object payload, got {type(payload).__name__}"]}

        if not isinstance(payload, dict):
            return {"valid": True, "errors": []}

        for req_key in schema.get("required", []):
            if req_key not in payload or payload[req_key] is None:
                errors.append(f"missing_required_field:{req_key}")

        properties = schema.get("properties", {})
        for key, value in payload.items():
            prop_schema = properties.get(key)
            if not prop_schema:
                continue

            expected_type = prop_schema.get("type")
            if expected_type and not cls._matches_type(value, expected_type):
                errors.append(f"invalid_type:{key}:expected_{expected_type}_got_{type(value).__name__}")
                continue

            if "enum" in prop_schema and value not in prop_schema["enum"]:
                errors.append(f"enum_violation:{key}:value_{value}_not_in_{prop_schema['enum']}")

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if "minimum" in prop_schema and value < prop_schema["minimum"]:
                    errors.append(f"minimum_violation:{key}:{value}<{prop_schema['minimum']}")
                if "maximum" in prop_schema and value > prop_schema["maximum"]:
                    errors.append(f"maximum_violation:{key}:{value}>{prop_schema['maximum']}")

            if isinstance(value, str):
                if "minLength" in prop_schema and len(value) < prop_schema["minLength"]:
                    errors.append(f"min_length_violation:{key}:len={len(value)}<{prop_schema['minLength']}")
                if "pattern" in prop_schema and not re.search(prop_schema["pattern"], value):
                    errors.append(f"pattern_violation:{key}")

        return {"valid": len(errors) == 0, "errors": errors}


class EnterpriseMCPRouter:
    """
    Routes agent intents to top-k MCP tools via hybrid 64-dim dense + Okapi BM25 + RRF scoring
    and enforces deterministic OAuth2 RBAC, JSON Schema validation & HITL governance.
    """

    def __init__(
        self,
        tools: Optional[List[MCPToolSpec]] = None,
        storage: Optional[BaseStateStore] = None,
    ):
        if tools is None:
            tools = self._load_default_catalog_specs()
        self.tools: Dict[str, MCPToolSpec] = {t.name: t for t in tools}
        self.storage: BaseStateStore = storage or get_default_storage()
        # Hydrate persisted HITL tickets and recent audit events across restarts
        self.hitl_tickets: Dict[str, Dict[str, Any]] = {
            t["ticket_id"]: t for t in self.storage.list_tickets()
        }
        self.audit_trail: List[Dict[str, Any]] = list(reversed(self.storage.get_audit_trail(limit=500)))
        self.routing_feedback_stats: Dict[str, int] = {"total_feedback": 0, "hits": 0, "misses": 0}
        self.routing_misses_eval_queue: List[Dict[str, Any]] = []
        self._bm25_index = self._build_bm25_index()

    def _build_bm25_index(self) -> OkapiBM25Index:
        docs = [
            (spec.name, f"{spec.name} {spec.domain} {spec.description}")
            for spec in self.tools.values()
        ]
        return OkapiBM25Index(docs)

    def rebuild_index(self) -> None:
        """Rebuilds the Okapi BM25 lexical index after dynamic tool registration."""
        self._bm25_index = self._build_bm25_index()

    @classmethod
    def from_enterprise_catalog(
        cls,
        storage: Optional[BaseStateStore] = None,
    ) -> "EnterpriseMCPRouter":
        """Instantiates router pre-loaded with the 120-tool Enterprise MCP Catalog."""
        return cls(tools=cls._load_default_catalog_specs(), storage=storage)

    @staticmethod
    def _load_default_catalog_specs() -> List[MCPToolSpec]:
        raw = get_enterprise_tool_catalog()
        return [
            MCPToolSpec(
                name=item["name"],
                description=item["description"],
                is_mutating=item["is_mutating"],
                required_role=item["required_role"],
                embedding=item["embedding"],
                domain=item["domain"],
                input_schema=item["input_schema"],
                schema_tokens=item["schema_tokens"],
            )
            for item in raw
        ]

    def route_top_k_tools(self, query_embedding: List[float], k: int = 5) -> List[str]:
        """Filters large MCP tool registries down to top-k relevant tools via cosine dot product."""
        scored = []
        for name, spec in self.tools.items():
            score = sum(q * t for q, t in zip(query_embedding, spec.embedding))
            scored.append((score, name))
        scored.sort(reverse=True)
        return [name for _, name in scored[:k]]

    def route_by_query(
        self,
        query: str,
        k: int = 5,
        domain_filter: Optional[str] = None,
        caller_roles: Optional[List[str]] = None,
        scoring_mode: str = "hybrid",
        weights: Optional[Tuple[float, float, float]] = None,
        auto_widen: bool = False,
    ) -> Dict[str, Any]:
        """
        Routes a natural language agent intent across the full 120+ tool registry,
        supporting 64-dim hashed embeddings, Okapi BM25, real 384-dim BAAI/bge-small-en-v1.5
        dense vectors, and Reciprocal Rank Fusion (RRF), filtered by caller RBAC roles
        with optional automatic widen-k fallback when top-5 confidence is ambiguous.
        """
        t0 = time.perf_counter()
        use_bge = scoring_mode in ("bge_small_only", "hybrid_bge_bm25")
        q_emb = compute_query_embedding(query)
        q_bge = DEFAULT_BGE_PROVIDER.embed_query(query) if use_bge else None

        active_weights = weights
        if active_weights is None:
            active_weights = (0.45, 0.45, 0.10) if scoring_mode == "hybrid_bge_bm25" else (0.25, 0.65, 0.10)

        candidates: List[MCPToolSpec] = [
            spec
            for spec in self.tools.values()
            if (not domain_filter or spec.domain == domain_filter)
            and (caller_roles is None or is_role_authorized(spec.required_role, caller_roles))
        ]

        dense_scores: Dict[str, float] = {}
        bm25_scores: Dict[str, float] = {}
        for spec in candidates:
            if use_bge and q_bge is not None:
                t_bge = DEFAULT_BGE_PROVIDER.embed_tool(spec.name, spec.domain, spec.description)
                dense_scores[spec.name] = (
                    bge_cosine_similarity(q_bge, t_bge)
                    if t_bge is not None
                    else max(0.0, sum(q * t for q, t in zip(q_emb, spec.embedding)))
                )
            else:
                dense_scores[spec.name] = max(0.0, sum(q * t for q, t in zip(q_emb, spec.embedding)))
            bm25_scores[spec.name] = self._bm25_index.score(query, spec.name)

        dense_order = sorted(candidates, key=lambda s: dense_scores[s.name], reverse=True)
        bm25_order = sorted(candidates, key=lambda s: bm25_scores[s.name], reverse=True)
        dense_ranks = {spec.name: idx + 1 for idx, spec in enumerate(dense_order)}
        bm25_ranks = {spec.name: idx + 1 for idx, spec in enumerate(bm25_order)}
        max_rrf = 2.0 / 61.0
        w_d, w_b, w_r = active_weights

        scored_items: List[Tuple[float, float, float, MCPToolSpec]] = []
        for spec in candidates:
            d_score = dense_scores[spec.name]
            b_score = bm25_scores[spec.name]
            if scoring_mode in ("dense_only", "bge_small_only"):
                raw_score = d_score
            elif scoring_mode == "bm25_only":
                raw_score = b_score
            else:
                rrf_raw = (1.0 / (60.0 + dense_ranks[spec.name])) + (1.0 / (60.0 + bm25_ranks[spec.name]))
                rrf_norm = rrf_raw / max_rrf
                raw_score = w_d * d_score + w_b * b_score + w_r * rrf_norm
            combined_score = round(min(0.998, raw_score), 4)
            scored_items.append((combined_score, round(d_score, 4), round(b_score, 4), spec))

        scored_items.sort(key=lambda x: (x[0], not x[3].is_mutating), reverse=True)

        effective_k = k
        widened_k = False
        if auto_widen and k <= 5 and scored_items:
            top1 = scored_items[0][0]
            top3_slice = scored_items[: min(3, len(scored_items))]
            top3_domains = {s.domain for _, _, _, s in top3_slice}
            margin = top1 - top3_slice[-1][0]
            if top1 < 0.38 or (len(top3_domains) >= 2 and margin <= 0.06):
                effective_k = min(len(scored_items), max(k * 2, 8))
                widened_k = effective_k > k

        top_specs = scored_items[:effective_k]

        full_tokens = sum(s.schema_tokens for s in self.tools.values())
        routed_tokens = sum(s.schema_tokens for _, _, _, s in top_specs)
        reduction_pct = (
            round((1.0 - (routed_tokens / max(full_tokens, 1))) * 100.0, 2)
            if full_tokens > 0
            else 0.0
        )
        elapsed_ms = round(max(0.01, (time.perf_counter() - t0) * 1000.0), 3)

        return {
            "query": query,
            "top_k": k,
            "effective_k": effective_k,
            "widened_k": widened_k,
            "scoring_mode": scoring_mode,
            "caller_roles_applied": caller_roles,
            "total_registered_tools": len(self.tools),
            "total_accessible_tools": len(candidates),
            "full_registry_tokens": full_tokens,
            "routed_tokens": routed_tokens,
            "token_reduction_pct": reduction_pct,
            "routing_latency_ms": elapsed_ms,
            "routed_tools": [
                {
                    "name": spec.name,
                    "domain": spec.domain,
                    "description": spec.description,
                    "is_mutating": spec.is_mutating,
                    "required_role": spec.required_role,
                    "similarity_score": score,
                    "dense_score": d_score,
                    "bm25_score": b_score,
                    "schema_tokens": spec.schema_tokens,
                    "input_schema": spec.input_schema,
                }
                for score, d_score, b_score, spec in top_specs
            ],
        }

    def record_tool_selection_feedback(
        self,
        query: str,
        routed_tools: List[str],
        selected_tool: str,
    ) -> Dict[str, Any]:
        """Logs whether the model's chosen tool appeared in routed top-k and captures misses for eval."""
        hit = selected_tool in routed_tools
        self.routing_feedback_stats["total_feedback"] += 1
        if hit:
            self.routing_feedback_stats["hits"] += 1
        else:
            self.routing_feedback_stats["misses"] += 1
            spec = self.tools.get(selected_tool)
            miss_record = {
                "query": query,
                "selected_tool": selected_tool,
                "expected_domain": spec.domain if spec else "unknown",
                "routed_tools": list(routed_tools),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self.routing_misses_eval_queue.append(miss_record)
            self.storage.append_audit_event({"event": "ROUTING_MISS_CAPTURED", **miss_record})

        return {
            "hit": hit,
            "selected_tool": selected_tool,
            "stats": dict(self.routing_feedback_stats),
            "miss_queue_size": len(self.routing_misses_eval_queue),
        }

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validates invocation arguments against the registered tool's JSON Schema contract."""
        spec = self.tools.get(tool_name)
        if not spec:
            return {"valid": False, "tool_name": tool_name, "errors": ["tool_not_found"]}
        check = JSONSchemaContractValidator.validate(spec.input_schema, arguments)
        return {
            "valid": check["valid"],
            "tool_name": tool_name,
            "errors": check["errors"],
            "schema": spec.input_schema,
        }

    def create_hitl_interrupt(
        self,
        tool_name: str,
        requested_by: str,
        user_roles: List[str],
        arguments: Optional[Dict[str, Any]] = None,
        justification: str = "Agent requested execution of mutating enterprise tool.",
        ttl_seconds: int = 1800,
        requester_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Creates a stateful Human-in-the-Loop (HITL) approval interrupt ticket with TTL expiration."""
        spec = self.tools.get(tool_name)
        ticket_id = f"HITL-{uuid.uuid4().hex[:8].upper()}"
        now = time.time()
        expires_at_epoch = now + ttl_seconds
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(expires_at_epoch))
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

        normalized_args = arguments or {}
        arguments_hash = HITLGovernanceRules.compute_arguments_hash(tool_name, normalized_args)

        ticket = {
            "ticket_id": ticket_id,
            "tool_name": tool_name,
            "domain": spec.domain if spec else "unknown",
            "required_role": spec.required_role if spec else "platform_admin",
            "is_mutating": spec.is_mutating if spec else True,
            "requested_by": requested_by,
            "user_roles": user_roles,
            "requester_groups": list(requester_groups or []),
            "arguments": normalized_args,
            "arguments_hash": arguments_hash,
            "justification": justification,
            "status": "PENDING_APPROVAL",
            "reviewer": None,
            "notes": None,
            "created_at": created_at,
            "expires_at": expires_at,
            "expires_at_epoch": expires_at_epoch,
        }
        self.hitl_tickets[ticket_id] = ticket
        self.storage.save_ticket(ticket)
        audit_event = {
            "event": "HITL_INTERRUPT_CREATED",
            "ticket_id": ticket_id,
            "tool_name": tool_name,
            "requested_by": requested_by,
            "arguments_hash": arguments_hash,
            "expires_at": expires_at,
        }
        self.audit_trail.append(audit_event)
        self.storage.append_audit_event(audit_event)
        return ticket

    def resolve_hitl_interrupt(
        self,
        ticket_id: str,
        reviewer: str,
        decision: str,
        notes: str = "",
        reviewer_roles: Optional[List[str]] = None,
        reviewer_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Approves or rejects a pending HITL interrupt ticket with separation-of-duties enforcement."""
        ticket = self.hitl_tickets.get(ticket_id)
        if not ticket:
            ticket = self.storage.get_ticket(ticket_id)
            if ticket:
                self.hitl_tickets[ticket_id] = ticket
        if not ticket:
            return {"status": "error", "reason": "hitl_ticket_not_found", "ticket_id": ticket_id}

        normalized_decision = decision.upper()
        if normalized_decision not in ("APPROVED", "REJECTED"):
            return {"status": "error", "reason": "invalid_hitl_decision", "ticket_id": ticket_id}

        # Enforce HITL governance rules (no self-approval, no expired tickets, valid roles & approver group)
        ok, rule_err = HITLGovernanceRules.validate_resolution(
            ticket=ticket,
            reviewer=reviewer,
            reviewer_roles=reviewer_roles,
            reviewer_groups=reviewer_groups,
        )
        if not ok:
            if rule_err == "hitl_ticket_expired":
                ticket["status"] = "EXPIRED"
                self.storage.save_ticket(ticket)
            return {"status": "error", "reason": rule_err, "ticket_id": ticket_id}

        ticket["status"] = normalized_decision
        ticket["reviewer"] = reviewer
        ticket["notes"] = notes
        ticket["resolved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.storage.save_ticket(ticket)

        audit_event = {
            "event": f"HITL_{normalized_decision}",
            "ticket_id": ticket_id,
            "tool_name": ticket["tool_name"],
            "reviewer": reviewer,
        }
        self.audit_trail.append(audit_event)
        self.storage.append_audit_event(audit_event)
        return ticket

    def authorize_execution(
        self,
        tool_name: str,
        user_roles: List[str],
        hitl_approved: bool = False,
        hitl_ticket_id: Optional[str] = None,
        require_ticket: bool = False,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Enforces deterministic RBAC hierarchy and hash-bound HITL approval before tool execution."""
        spec = self.tools.get(tool_name)
        if not spec:
            return {"allowed": False, "reason": "tool_not_found", "tool_name": tool_name}

        if not is_role_authorized(spec.required_role, user_roles):
            audit_event = {
                "event": "RBAC_DENIED",
                "tool_name": tool_name,
                "required_role": spec.required_role,
                "user_roles": user_roles,
            }
            self.audit_trail.append(audit_event)
            self.storage.append_audit_event(audit_event)
            return {
                "allowed": False,
                "reason": "rbac_denied",
                "tool_name": tool_name,
                "required_role": spec.required_role,
                "user_roles": user_roles,
            }

        # Check HITL ticket approval if provided
        if hitl_ticket_id:
            ticket = self.hitl_tickets.get(hitl_ticket_id)
            if not ticket:
                ticket = self.storage.get_ticket(hitl_ticket_id)
                if ticket:
                    self.hitl_tickets[hitl_ticket_id] = ticket

            if not ticket:
                return {
                    "allowed": False,
                    "reason": "hitl_ticket_not_found",
                    "tool_name": tool_name,
                    "ticket_id": hitl_ticket_id,
                }

            ok, rule_err = HITLGovernanceRules.validate_consumption(
                ticket=ticket,
                tool_name=tool_name,
                arguments=arguments,
            )
            if not ok:
                return {
                    "allowed": False,
                    "reason": rule_err,
                    "tool_name": tool_name,
                    "ticket_id": hitl_ticket_id,
                }

            # Mark ticket as CONSUMED (single-use replay prevention)
            ticket["status"] = "CONSUMED"
            ticket["consumed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.storage.save_ticket(ticket)
            hitl_approved = True

        if spec.is_mutating:
            if require_ticket and not hitl_ticket_id:
                return {
                    "allowed": False,
                    "reason": "hitl_ticket_required",
                    "tool_name": tool_name,
                    "required_role": spec.required_role,
                    "is_mutating": True,
                }
            if not hitl_approved:
                return {
                    "allowed": False,
                    "reason": "hitl_approval_required",
                    "tool_name": tool_name,
                    "required_role": spec.required_role,
                    "is_mutating": True,
                }

        audit_event = {
            "event": "EXECUTION_AUTHORIZED",
            "tool_name": tool_name,
            "user_roles": user_roles,
            "hitl_approved": hitl_approved,
        }
        self.audit_trail.append(audit_event)
        self.storage.append_audit_event(audit_event)
        return {
            "allowed": True,
            "reason": "authorized",
            "tool_name": tool_name,
            "domain": spec.domain,
            "required_role": spec.required_role,
            "is_mutating": spec.is_mutating,
        }


class FastMCPServer:
    """
    Standardized FastMCP & JSON-RPC 2.0 Protocol Server wrapping EnterpriseMCPRouter
    and governed enterprise connectors.
    Supports `@mcp.tool()` registration and MCP methods:
      - `initialize`, `ping`
      - `tools/list` (with semantic `query` filtering)
      - `tools/call` (with JSON Schema contract validation, RBAC & HITL enforcement)
      - `resources/list`, `resources/read`
      - `prompts/list`, `prompts/get`
    """

    _PY_TYPE_TO_JSON = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array",
    }

    _PROMPTS_CATALOG: Dict[str, Dict[str, Any]] = {
        "vsm_management_concern_briefing": {
            "name": "vsm_management_concern_briefing",
            "description": "Analyze connected OKRs, product portfolios, and blocked engineering tickets to surface management concerns and corrective actions.",
            "arguments": [{"name": "portfolio_id", "description": "Optional target portfolio ID", "required": False}],
            "template": "Review product portfolio {portfolio_id} OKR drift, blocked Jira/GitHub tickets, and flow efficiency bottlenecks. Recommend HITL-governed actions.",
        },
        "snowflake_compliance_audit": {
            "name": "snowflake_compliance_audit",
            "description": "Audit Snowflake Cortex Search compliance rules and verify read-only SQL RBAC grants.",
            "arguments": [{"name": "schema_name", "description": "Target Snowflake schema", "required": True}],
            "template": "Inspect Snowflake schema {schema_name} via read-only SELECT queries and validate RRSP/AML compliance guidelines.",
        },
        "devops_cve_remediation_plan": {
            "name": "devops_cve_remediation_plan",
            "description": "Triage Snyk/Dependabot CVE findings and stage Docker-verified pull requests.",
            "arguments": [{"name": "repo_name", "description": "Microservice repository slug", "required": True}],
            "template": "Aggregate critical CVEs for {repo_name}, verify pytest suite in isolated Docker sandbox, and open a tracked Jira ticket.",
        },
    }

    def __init__(
        self,
        name: str = "enterprise-mcp-router",
        version: str = "2.2.0",
        router: Optional[EnterpriseMCPRouter] = None,
        connectors: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.version = version
        self.router = router or EnterpriseMCPRouter.from_enterprise_catalog()
        self.custom_handlers: Dict[str, Callable[..., Any]] = {}
        self.connectors = connectors or {}

    @classmethod
    def _infer_schema_from_fn(cls, fn: Callable[..., Any]) -> Dict[str, Any]:
        sig = inspect.signature(fn)
        properties: Dict[str, Dict[str, Any]] = {}
        required: List[str] = []
        for param_name, param in sig.parameters.items():
            json_type = cls._PY_TYPE_TO_JSON.get(param.annotation, "string")
            properties[param_name] = {"type": json_type}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
        return {"type": "object", "properties": properties, "required": required}

    def tool(
        self,
        name: Optional[str] = None,
        description: str = "",
        is_mutating: bool = False,
        required_role: str = "analyst",
        domain: str = "custom",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """FastMCP-compatible `@mcp.tool()` decorator for registering Python functions as MCP tools."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or fn.__name__
            tool_desc = description or (fn.__doc__ or f"MCP tool {tool_name}").strip()
            spec = MCPToolSpec(
                name=tool_name,
                description=tool_desc,
                is_mutating=is_mutating,
                required_role=required_role,
                embedding=compute_query_embedding(f"{tool_name} {domain} {tool_desc}"),
                domain=domain,
                input_schema=self._infer_schema_from_fn(fn),
            )
            self.router.tools[tool_name] = spec
            self.router.rebuild_index()
            self.custom_handlers[tool_name] = fn
            return fn

        return decorator

    def _dispatch_builtin_connector(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        vsm = self.connectors.get("vsm")
        sf = self.connectors.get("snowflake")
        pg = self.connectors.get("postgres")
        iics = self.connectors.get("informatica")

        if tool_name == "portfolio_vsm.detect_management_concerns" and vsm is not None:
            res = vsm.analyze_management_concerns(
                query=arguments.get("query", "Identify management concerns and recommend actions"),
                portfolio_id=arguments.get("portfolio_id"),
                router=self.router,
            )
            return {**res, "execution_mode": "live_sqlite"}
        if tool_name == "portfolio_vsm.get_portfolio_health_summary" and vsm is not None:
            res = vsm.get_overview(portfolio_id=arguments.get("portfolio_id"))
            return {**res, "execution_mode": "live_sqlite"}
        if tool_name == "snowflake.execute_readonly_sql" and sf is not None:
            res = sf.validate_readonly_sql(
                sql=arguments.get("sql", "SELECT fund_id, nav FROM PORTFOLIO_GOLD.FUNDS LIMIT 10"),
                role=arguments.get("role", "ai_platform_reader"),
                schema=arguments.get("schema_name", "PORTFOLIO_GOLD"),
            )
            return {**res, "execution_mode": "sandbox_simulation"}
        if tool_name == "snowflake.cortex_search_docs" and sf is not None:
            res = sf.retrieve_cortex_rag(
                query=arguments.get("query_or_id", "RRSP compliance"),
                role=arguments.get("role", "ai_platform_reader"),
                top_k=int(arguments.get("limit", 3)),
            )
            return {**res, "execution_mode": "sandbox_simulation"}
        if tool_name == "postgres.read_accounting_ledger" and pg is not None:
            res = pg.query_ledger(
                sql="SELECT account_id, portfolio_name, balance_usd, risk_tier FROM accounts ORDER BY balance_usd DESC",
                role="analyst",
            )
            return {**res, "execution_mode": "live_sqlite"}
        if tool_name == "informatica.validate_taskflow_sla" and iics is not None:
            res = iics.validate_taskflow_run(
                {
                    "taskflow_name": arguments.get("query_or_id", "tf_snowflake_fund_docs_elt"),
                    "status": "SUCCESS",
                    "rows_processed": 1450,
                    "freshness_lag_minutes": 8,
                }
            )
            return {**res, "execution_mode": "sandbox_simulation"}

        domain = tool_name.split(".", 1)[0] if "." in tool_name else "enterprise"
        if domain == "devops":
            return {
                "tool": tool_name,
                "domain": domain,
                "status": "executed",
                "execution_mode": "sandbox_simulation",
                "sandbox_telemetry": {
                    "repository": arguments.get("query_or_id", "enterprise-mcp-router"),
                    "critical_cves_open": 1,
                    "argocd_sync_state": "Synced",
                    "ci_workflow_status": "passing",
                },
                "arguments_received": arguments,
            }
        if domain == "supply_chain":
            return {
                "tool": tool_name,
                "domain": domain,
                "status": "executed",
                "execution_mode": "sandbox_simulation",
                "sandbox_telemetry": {
                    "target_sku_or_site": arguments.get("query_or_id", "SKU-4402"),
                    "gating_components": ["COMP-TX-900", "SUB-PWR-14"],
                    "projected_fill_rate_pct": 94.2,
                },
                "arguments_received": arguments,
            }
        if domain == "crm_rest":
            return {
                "tool": tool_name,
                "domain": domain,
                "status": "executed",
                "execution_mode": "sandbox_simulation",
                "sandbox_telemetry": {
                    "client_ref": arguments.get("query_or_id", "CLI-MASKED-7812"),
                    "pii_redaction_active": True,
                    "rest_circuit_breaker": "CLOSED",
                },
                "arguments_received": arguments,
            }
        if domain == "knowledge_graph":
            return {
                "tool": tool_name,
                "domain": domain,
                "status": "executed",
                "execution_mode": "sandbox_simulation",
                "sandbox_telemetry": {
                    "collection": "enterprise_policies_v2",
                    "vector_dimension": 384,
                    "graph_hop_depth": 2,
                    "mrr_estimate": 0.91,
                },
                "arguments_received": arguments,
            }
        return None

    def handle_jsonrpc(
        self,
        request_payload: Dict[str, Any],
        principal: Optional[AuthenticatedPrincipal] = None,
    ) -> Dict[str, Any]:
        """Processes a standard JSON-RPC 2.0 Model Context Protocol request with verified identity."""
        req_id = request_payload.get("id", 1)
        method = request_payload.get("method", "")
        params = request_payload.get("params") or {}
        verified_roles = list(principal.roles) if principal is not None else ["analyst", "ai_platform_reader"]

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"status": "pong"}}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "serverInfo": {"name": self.name, "version": self.version},
                    "capabilities": {
                        "tools": {"listChanged": True, "semanticRouting": True, "bm25Hybrid": True},
                        "resources": {"subscribe": True, "read": True},
                        "prompts": {"listChanged": False},
                        "governance": {"rbac": True, "hitlInterrupts": True, "jsonSchemaValidation": True},
                    },
                },
            }

        if method == "tools/list":
            query = params.get("query")
            domain_filter = params.get("domain_filter")
            top_k = int(params.get("top_k", 10))
            filter_by_role = bool(params.get("filter_by_role", principal is not None and principal.is_authenticated))
            caller_roles = verified_roles if filter_by_role else None

            if query:
                routed = self.router.route_by_query(
                    query,
                    k=top_k,
                    domain_filter=domain_filter,
                    caller_roles=caller_roles,
                    auto_widen=bool(params.get("auto_widen", False)),
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": routed["routed_tools"],
                        "semantic_routing_metrics": {
                            "total_registered_tools": routed["total_registered_tools"],
                            "total_accessible_tools": routed["total_accessible_tools"],
                            "full_registry_tokens": routed["full_registry_tokens"],
                            "routed_tokens": routed["routed_tokens"],
                            "token_reduction_pct": routed["token_reduction_pct"],
                            "widened_k": routed["widened_k"],
                            "effective_k": routed["effective_k"],
                        },
                    },
                }

            cursor_raw = params.get("cursor")
            offset = int(cursor_raw) if cursor_raw is not None else 0
            page_size = int(params.get("page_size", params.get("top_k", 20)))

            filtered_specs = [
                s
                for s in self.router.tools.values()
                if (not domain_filter or s.domain == domain_filter)
                and (caller_roles is None or is_role_authorized(s.required_role, caller_roles))
            ]
            page_specs = filtered_specs[offset : offset + page_size]
            next_cursor = str(offset + page_size) if (offset + page_size) < len(filtered_specs) else None

            all_tools = [
                {
                    "name": s.name,
                    "domain": s.domain,
                    "description": s.description,
                    "is_mutating": s.is_mutating,
                    "required_role": s.required_role,
                    "inputSchema": s.input_schema,
                }
                for s in page_specs
            ]
            res_payload: Dict[str, Any] = {
                "tools": all_tools,
                "total_registered_tools": len(self.router.tools),
                "total_filtered_tools": len(filtered_specs),
            }
            if next_cursor is not None:
                res_payload["nextCursor"] = next_cursor
            return {"jsonrpc": "2.0", "id": req_id, "result": res_payload}

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments") or {}
            hitl_ticket_id = params.get("hitl_ticket_id")

            # 1. Deterministic JSON Schema input contract validation
            schema_check = self.router.validate_tool_arguments(tool_name, arguments)
            if not schema_check["valid"] and "tool_not_found" not in schema_check["errors"]:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid params: JSON Schema contract violation",
                        "data": schema_check,
                    },
                }

            # 2. Deterministic OAuth2/JWT RBAC & Ticket/Hash-Bound HITL gate
            # Client-supplied user_roles and hitl_approved are ignored unconditionally.
            auth = self.router.authorize_execution(
                tool_name=tool_name,
                user_roles=verified_roles,
                hitl_approved=False,
                hitl_ticket_id=hitl_ticket_id,
                require_ticket=True,
                arguments=arguments,
            )
            if not auth["allowed"]:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32001 if auth["reason"] == "rbac_denied" else -32002,
                        "message": f"Governance Gate Blocked Execution: {auth['reason']}",
                        "data": auth,
                    },
                }

            if tool_name in self.custom_handlers:
                out = self.custom_handlers[tool_name](**arguments)
            else:
                builtin_out = self._dispatch_builtin_connector(tool_name, arguments)
                if builtin_out is not None:
                    out = builtin_out
                else:
                    spec = self.router.tools.get(tool_name)
                    out = {
                        "tool": tool_name,
                        "domain": spec.domain if spec else "unknown",
                        "status": "executed",
                        "execution_mode": "sandbox_simulation",
                        "schema_validated": True,
                        "governance": auth,
                        "arguments_received": arguments,
                    }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "json", "json": out}],
                    "isError": False,
                },
            }

        if method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": [
                        {
                            "uri": "snowflake://PORTFOLIO_GOLD/CORTEX_DOCS",
                            "name": "Snowflake Cortex Search Compliance Corpus",
                            "mimeType": "application/json",
                        },
                        {
                            "uri": "postgres://enterprise_ledger/accounts",
                            "name": "PostgreSQL Institutional Treasury Ledger",
                            "mimeType": "application/json",
                        },
                        {
                            "uri": "informatica://iics/tf_snowflake_fund_docs_elt",
                            "name": "Informatica Cloud (IICS) ELT Taskflow Telemetry",
                            "mimeType": "application/json",
                        },
                        {
                            "uri": "vsm://planview_portfolios/okrs_and_tickets",
                            "name": "Value Stream Management (OKRs, Portfolios & Engineering Tickets)",
                            "mimeType": "application/json",
                        },
                    ]
                },
            }

        if method == "resources/read":
            uri = params.get("uri", "")
            resource_map: Dict[str, Any] = {
                "snowflake://PORTFOLIO_GOLD/CORTEX_DOCS": {
                    "allowed_roles": ["ai_platform_reader", "analyst", "data_engineer"],
                    "schemas": ["PORTFOLIO_GOLD", "CORTEX_DOCS"],
                },
                "postgres://enterprise_ledger/accounts": (
                    self.connectors["postgres"]._accounts if "postgres" in self.connectors else {"table": "accounts", "engine": "sqlite3_relational"}
                ),
                "informatica://iics/tf_snowflake_fund_docs_elt": {
                    "taskflow": "tf_snowflake_fund_docs_elt",
                    "max_lag_minutes": 30,
                    "min_rows_threshold": 10,
                },
                "vsm://planview_portfolios/okrs_and_tickets": (
                    self.connectors["vsm"].get_overview() if "vsm" in self.connectors else {"portfolios": 4, "okrs": 5, "tickets": 6}
                ),
            }
            if uri not in resource_map:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Unknown resource URI: {uri}"},
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(resource_map[uri]),
                        }
                    ]
                },
            }

        if method == "prompts/list":
            prompts = [
                {
                    "name": p["name"],
                    "description": p["description"],
                    "arguments": p["arguments"],
                }
                for p in self._PROMPTS_CATALOG.values()
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": prompts}}

        if method == "prompts/get":
            prompt_name = params.get("name", "")
            prompt_args = params.get("arguments") or {}
            spec = self._PROMPTS_CATALOG.get(prompt_name)
            if not spec:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Prompt not found: {prompt_name}"},
                }
            rendered = spec["template"].format(
                portfolio_id=prompt_args.get("portfolio_id", "ALL"),
                schema_name=prompt_args.get("schema_name", "PORTFOLIO_GOLD"),
                repo_name=prompt_args.get("repo_name", "enterprise-mcp-router"),
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "description": spec["description"],
                    "messages": [{"role": "user", "content": {"type": "text", "text": rendered}}],
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


__all__ = [
    "AgentFrameworkBridges",
    "BedrockAgentCoreAdapter",
    "EnterpriseMCPRouter",
    "EnterpriseRESTConnector",
    "FastMCPServer",
    "InformaticaCloudTaskflowAdapter",
    "JSONSchemaContractValidator",
    "MCPToolSpec",
    "PostgresEnterpriseConnector",
    "ProductionTelemetryMonitor",
    "SnowflakeCortexConnector",
    "TraceSpan",
    "ValueStreamManagementConnector",
]
