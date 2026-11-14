"""
Deterministic 120-Tool Enterprise Model Context Protocol (MCP) Catalog,
64-Dimensional Feature-Hashed Dense Embeddings, and Okapi BM25 Lexical Index.
Spans 8 enterprise domains:
  1. snowflake      (Snowflake Cortex Search, Read-Only Warehouses, FinOps)
  2. informatica    (Informatica Cloud IICS Taskflows, Mappings, ELT SLAs)
  3. postgres       (PostgreSQL Transactional Ledger, Snapshots, Audit Logs)
  4. devops         (GitHub PRs, Snyk CVE Remediation, Jira Tickets, Argo CD)
  5. supply_chain   (Kinaxis Maestro / S&OP Exceptions, Demand.AI SKU Forecasts)
  6. crm_rest       (REST API Gateways, Twilio Outreach, KYC/AML Compliance)
  7. knowledge_graph(Neo4j Cypher Traversal, Qdrant Hybrid Vector Retrieval)
  8. portfolio_vsm  (Value Stream Management, OKRs, Product Portfolios & Engineering Tickets)
"""

import hashlib
import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Tuple


DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "snowflake": [
        "snowflake", "cortex", "sql", "warehouse", "fund", "nav", "rrsp",
        "portfolio", "gold", "schema", "table", "query", "select", "aum",
    ],
    "informatica": [
        "informatica", "iics", "elt", "etl", "taskflow", "mapping", "staging",
        "freshness", "lag", "ingestion", "sync", "webhook", "pipeline", "batch",
    ],
    "postgres": [
        "postgres", "postgresql", "ledger", "account", "wire", "transfer",
        "snapshot", "restore", "transaction", "balance", "payment", "rds", "audit",
    ],
    "devops": [
        "github", "snyk", "dependabot", "cve", "vulnerability", "jira", "pull",
        "request", "docker", "kubernetes", "argo", "ci", "cd", "patch", "build",
    ],
    "supply_chain": [
        "supply", "chain", "maestro", "sku", "forecast", "inventory", "demand",
        "exception", "gating", "supplier", "plant", "order", "replenishment", "bom",
    ],
    "crm_rest": [
        "rest", "api", "crm", "customer", "kyc", "aml", "twilio", "sms",
        "voice", "notification", "webhook", "onboarding", "ticket", "profile",
    ],
    "knowledge_graph": [
        "neo4j", "qdrant", "graph", "vector", "cypher", "embedding", "rerank",
        "chunk", "document", "policy", "compliance", "multihop", "entity", "rag",
    ],
    "portfolio_vsm": [
        "vsm", "okr", "okrs", "objective", "milestone", "velocity",
        "bottleneck", "blocker", "concern", "epic", "initiative", "roadmap",
        "throughput", "reallocate", "capacity", "sprint", "flow", "efficiency",
        "stream",
    ],
}

DOMAIN_ORDER = [
    "snowflake",
    "informatica",
    "postgres",
    "devops",
    "supply_chain",
    "crm_rest",
    "knowledge_graph",
    "portfolio_vsm",
]

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize_text(text: str) -> List[str]:
    """Extracts normalized lowercase alphanumeric tokens for BM25 and hashing."""
    normalized = text.replace("_", " ").replace(".", " ").replace("-", " ").replace("/", " ")
    return [tok for tok in _TOKEN_RE.findall(normalized.lower()) if len(tok) > 1]


def _normalize(vec: List[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm < 1e-9:
        return [1.0 / math.sqrt(len(vec)) for _ in vec]
    return [round(v / norm, 6) for v in vec]


def compute_query_embedding(text: str) -> List[float]:
    """
    Computes a deterministic 64-dimensional L2-normalized dense semantic embedding:
      - Dims 0..7   : Enterprise domain affinity across the 8 domains
      - Dims 8..19  : 12 operational / semantic projection axes
      - Dims 20..63 : Signed SHA-256 feature hashing over unigrams, bigrams & 4-char subwords
    """
    tokens = tokenize_text(text)
    token_set = set(tokens)

    # First 8 dimensions correspond to the 8 enterprise domains
    vec: List[float] = []
    for dom in DOMAIN_ORDER:
        kw_list = DOMAIN_KEYWORDS[dom]
        hits = sum(
            1.6 if kw in token_set else (0.55 if len(kw) > 3 and any(kw in tok for tok in token_set) else 0.0)
            for kw in kw_list
        )
        vec.append(hits + 0.04)

    # Dimensions 8..19 capture operational & domain semantics
    semantic_groups = [
        {"read", "get", "list", "select", "search", "query", "fetch", "inspect", "validate", "check"},
        {"execute", "update", "delete", "create", "trigger", "wire", "approve", "restore", "mutate", "write", "reallocate"},
        {"sql", "table", "schema", "select", "ledger", "warehouse", "postgres", "snowflake"},
        {"rag", "cortex", "vector", "graph", "qdrant", "neo4j", "chunk", "policy", "document"},
        {"sla", "alert", "runbook", "telemetry", "trace", "lag", "status", "health", "audit"},
        {"fund", "nav", "rrsp", "wire", "balance", "portfolio", "aum", "kyc", "aml", "risk"},
        {"cve", "snyk", "jira", "github", "pr", "docker", "k8s", "argo", "build"},
        {"sku", "forecast", "maestro", "demand", "inventory", "supplier", "order", "plant"},
        {"iics", "informatica", "taskflow", "elt", "etl", "staging", "mapping", "ingest"},
        {"okr", "okrs", "vsm", "milestone", "capacity", "velocity", "bottleneck", "blocker", "concern", "epic", "sprint", "flow"},
        {"rbac", "oauth2", "security", "compliance", "pii", "phi", "hitl", "governance", "soc2"},
        {"aws", "bedrock", "claude", "sonnet", "azure", "gcp", "aks", "gke", "cloud"},
    ]
    for group in semantic_groups:
        vec.append(float(len(token_set & group)) * 1.1 + 0.04)

    # Dimensions 20..63: 44-dim signed SHA-256 feature hashing over unigrams, bigrams & char 4-grams
    hash_dims = 44
    hashed = [0.0] * hash_dims
    grams: List[Tuple[str, float]] = []
    for tok in tokens:
        grams.append((f"w:{tok}", 1.0))
        if len(tok) >= 4:
            for i in range(len(tok) - 3):
                grams.append((f"c:{tok[i:i+4]}", 0.35))
    for i in range(len(tokens) - 1):
        grams.append((f"b:{tokens[i]}_{tokens[i+1]}", 0.8))

    for gram, weight in grams:
        digest = hashlib.sha256(gram.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], "big") % hash_dims
        sign = 1.0 if (digest[2] & 1) == 0 else -1.0
        hashed[bucket] += sign * weight

    vec.extend(hashed)
    return _normalize(vec)


class OkapiBM25Index:
    """
    In-memory Okapi BM25 lexical retrieval index over registered MCP tool specifications.
    Computes corpus IDF weights and length-normalized TF scoring without external dependencies.
    """

    def __init__(self, documents: Iterable[Tuple[str, str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._doc_tf: Dict[str, Counter[str]] = {}
        self._doc_len: Dict[str, int] = {}
        self._df: Counter[str] = Counter()

        for doc_id, text in documents:
            tokens = tokenize_text(text)
            tf = Counter(tokens)
            self._doc_tf[doc_id] = tf
            self._doc_len[doc_id] = len(tokens)
            for term in tf.keys():
                self._df[term] += 1

        self.num_docs = len(self._doc_tf)
        total_len = sum(self._doc_len.values())
        self.avgdl = (total_len / self.num_docs) if self.num_docs > 0 else 1.0

    def idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        return math.log(1.0 + (self.num_docs - df + 0.5) / (df + 0.5))

    def score_raw(self, query: str, doc_id: str) -> float:
        tf_map = self._doc_tf.get(doc_id)
        if not tf_map:
            return 0.0
        dl = self._doc_len[doc_id]
        denom_norm = self.k1 * (1.0 - self.b + self.b * (dl / max(self.avgdl, 1e-9)))
        total = 0.0
        for term in set(tokenize_text(query)):
            tf = tf_map.get(term, 0)
            if tf == 0:
                continue
            idf_val = self.idf(term)
            total += idf_val * ((tf * (self.k1 + 1.0)) / (tf + denom_norm))
        return total

    def score(self, query: str, doc_id: str) -> float:
        """Returns normalized Okapi BM25 relevance score in [0.0, 1.0]."""
        q_terms = set(tokenize_text(query))
        if not q_terms:
            return 0.0
        raw = self.score_raw(query, doc_id)
        if raw <= 0.0:
            return 0.0
        # Theoretical per-query ceiling: sum over query terms present in corpus
        in_vocab_terms = [t for t in q_terms if self._df.get(t, 0) > 0]
        if not in_vocab_terms:
            return 0.0
        max_theoretical = sum(self.idf(t) * (self.k1 + 1.0) for t in in_vocab_terms)
        return round(min(1.0, raw / max(max_theoretical, 1e-9)), 4)


# 15 curated tools per domain * 8 domains = 120 Enterprise MCP Tools
_DOMAIN_TOOL_TEMPLATES: Dict[str, List[Tuple[str, str, bool, str]]] = {
    "snowflake": [
        ("snowflake.cortex_search_docs", "Search Snowflake Cortex Search vector index over compliance policies, RRSP rules, and fund prospectuses", False, "ai_platform_reader"),
        ("snowflake.execute_readonly_sql", "Execute governed read-only SELECT query on Snowflake PORTFOLIO_GOLD and CORTEX_DOCS schemas", False, "ai_platform_reader"),
        ("snowflake.get_fund_nav_history", "Retrieve historical Net Asset Value (NAV) and AUM series from Snowflake PORTFOLIO_GOLD.FUNDS", False, "analyst"),
        ("snowflake.inspect_table_schema", "Inspect Snowflake table column definitions, clustering keys, and row counts in allow-listed schemas", False, "ai_platform_reader"),
        ("snowflake.check_warehouse_load", "Monitor Snowflake virtual warehouse queue depth, credit burn rate, and auto-suspend telemetry", False, "data_engineer"),
        ("snowflake.list_cortex_services", "List active Snowflake Cortex Search services, embedding models, and indexing lag metrics", False, "ai_platform_reader"),
        ("snowflake.validate_rbac_grants", "Audit Snowflake role hierarchy and schema privilege grants for AI service principals", False, "compliance_officer"),
        ("snowflake.fetch_rrsp_contribution_limits", "Query Snowflake regulatory reference tables for Canadian RRSP/TFSA annual contribution rules", False, "analyst"),
        ("snowflake.query_institutional_holdings", "Retrieve aggregated institutional equity and fixed-income holdings from Snowflake Gold layer", False, "analyst"),
        ("snowflake.analyze_query_plan", "Explain Snowflake SQL execution plan and partition pruning efficiency without mutating data", False, "data_engineer"),
        ("snowflake.get_staging_freshness", "Verify last commit timestamp and stream offset on Snowflake Bronze/Silver staging tables", False, "data_engineer"),
        ("snowflake.export_compliance_extract", "Generate read-only regulatory audit extract from Snowflake history views", False, "compliance_officer"),
        ("snowflake.refresh_cortex_index", "Trigger incremental refresh on Snowflake Cortex Search document index (mutating operation)", True, "data_engineer"),
        ("snowflake.resume_virtual_warehouse", "Resume or resize Snowflake compute warehouse tier for burst AI batch workloads (mutating)", True, "platform_admin"),
        ("snowflake.quarantine_corrupt_stage", "Isolate malformed staging micro-partitions in Snowflake schema before downstream promotion", True, "data_engineer"),
    ],
    "informatica": [
        ("informatica.validate_taskflow_sla", "Validate Informatica Cloud (IICS) ELT taskflow completion status, row counts, and freshness lag before RAG sync", False, "data_engineer"),
        ("informatica.get_taskflow_run_logs", "Fetch detailed session logs and error codes for an Informatica Intelligent Cloud Services (IICS) taskflow", False, "data_engineer"),
        ("informatica.list_active_mappings", "List Informatica CloudCDI mappings feeding Snowflake Bronze and Silver enterprise tables", False, "data_engineer"),
        ("informatica.check_secure_agent_health", "Check IICS Secure Agent runtime group CPU, memory, and connector status", False, "data_engineer"),
        ("informatica.inspect_source_to_target_lineage", "Retrieve field-level ELT lineage from ERP/S3 sources through Informatica Cloud to Snowflake", False, "analyst"),
        ("informatica.verify_row_count_reconciliation", "Compare source extract row counts against Informatica target load counts for zero-loss verification", False, "data_engineer"),
        ("informatica.get_dead_letter_rejects", "Inspect rejected rows and schema drift errors from Informatica Cloud staging runs", False, "data_engineer"),
        ("informatica.audit_connection_credentials", "Verify rotation age and Secrets Manager bindings for Informatica Cloud connectors", False, "compliance_officer"),
        ("informatica.estimate_elt_window_eta", "Predict remaining ELT batch completion time from historical Informatica taskflow throughput", False, "analyst"),
        ("informatica.check_rag_gate_lock", "Check whether downstream RAG vector indexing is locked due to upstream Informatica SLA breach", False, "ai_platform_reader"),
        ("informatica.list_scheduled_jobs", "Retrieve cron schedules and dependency chains for enterprise Informatica Cloud jobs", False, "data_engineer"),
        ("informatica.retrigger_failed_taskflow", "Re-trigger a failed Informatica Cloud (IICS) ELT taskflow after transient connector recovery (mutating)", True, "data_engineer"),
        ("informatica.abort_stalled_mapping", "Force-terminate a hung Informatica Cloud mapping job exceeding SLA timeout (mutating)", True, "platform_admin"),
        ("informatica.promote_staging_to_gold", "Execute Informatica post-load stored procedure promoting validated Silver tables to Gold (mutating)", True, "data_engineer"),
        ("informatica.update_watermark_offset", "Reset CDC high-watermark timestamp for Informatica incremental extraction (mutating)", True, "platform_admin"),
    ],
    "postgres": [
        ("postgres.read_accounting_ledger", "Query PostgreSQL enterprise accounting ledger for account balances, risk tiers, and transaction history", False, "analyst"),
        ("postgres.get_customer_portfolio_summary", "Fetch consolidated client portfolio positions and cash balances from PostgreSQL relational store", False, "analyst"),
        ("postgres.list_recent_audit_events", "Retrieve immutable compliance audit trail logs from PostgreSQL security schema", False, "compliance_officer"),
        ("postgres.check_connection_pool_stats", "Monitor PostgreSQL PgBouncer active connections, idle transactions, and lock wait queues", False, "data_engineer"),
        ("postgres.verify_foreign_key_integrity", "Run read-only referential integrity diagnostics across PostgreSQL order and settlement tables", False, "data_engineer"),
        ("postgres.list_database_snapshots", "List available point-in-time PostgreSQL state snapshots for test/reproduction environments", False, "data_engineer"),
        ("postgres.explain_query_cost", "Run EXPLAIN on parameterized PostgreSQL SELECT query to verify index scan usage", False, "data_engineer"),
        ("postgres.get_pending_settlements", "Fetch T+1 pending wire and equity settlement records from PostgreSQL treasury tables", False, "analyst"),
        ("postgres.search_transaction_anomalies", "Scan PostgreSQL ledger for high-velocity or out-of-band transaction amounts", False, "compliance_officer"),
        ("postgres.get_table_bloat_metrics", "Check PostgreSQL dead tuple ratios and autovacuum lag on high-churn tables", False, "data_engineer"),
        ("postgres.create_state_snapshot", "Create an instant point-in-time state snapshot of PostgreSQL tables before agent mutation", True, "data_engineer"),
        ("postgres.restore_state_snapshot", "Restore PostgreSQL tables to a verified point-in-time snapshot for deterministic rollback", True, "platform_admin"),
        ("postgres.execute_outbound_wire", "Execute an outbound institutional bank wire transfer in PostgreSQL treasury ledger (mutating, requires HITL)", True, "platform_admin"),
        ("postgres.update_account_risk_tier", "Update client credit/risk tier classification in PostgreSQL master table (mutating)", True, "compliance_officer"),
        ("postgres.purge_expired_sessions", "Delete expired agent session checkpoints from PostgreSQL state store (mutating)", True, "platform_admin"),
    ],
    "devops": [
        ("devops.list_snyk_cve_alerts", "Aggregate open Snyk and Dependabot CVE vulnerability findings across microservice repositories", False, "data_engineer"),
        ("devops.get_github_pr_diff", "Fetch unified diff and CI check status for a GitHub pull request", False, "data_engineer"),
        ("devops.inspect_docker_sandbox_logs", "Read pytest execution logs and stack traces from isolated Docker test containers", False, "data_engineer"),
        ("devops.check_dependency_eol_status", "Audit repository dependencies against End-of-Life (EOL) security schedules", False, "compliance_officer"),
        ("devops.get_argocd_sync_status", "Check Argo CD application sync health across Azure AKS and Google GKE clusters", False, "data_engineer"),
        ("devops.query_kashops_cluster_costs", "Retrieve Kubernetes namespace and tenant cloud cost breakdown from Datadog / KashOps API", False, "analyst"),
        ("devops.search_jira_engineering_tickets", "Search Jira issues by CVE ID, service name, or sprint backlog status", False, "analyst"),
        ("devops.validate_json_schema_contract", "Validate microservice JSON Schema data contract compatibility prior to merge", False, "data_engineer"),
        ("devops.get_github_actions_workflow_runs", "List recent GitHub Actions CI/CD pipeline runs, durations, and pass rates", False, "data_engineer"),
        ("devops.inspect_helm_chart_values", "Read Kubernetes resource quotas, HPA limits, and probe configs from Helm values", False, "data_engineer"),
        ("devops.create_jira_remediation_ticket", "Auto-create a tracked Jira engineering ticket for a verified CVE vulnerability (mutating)", True, "data_engineer"),
        ("devops.open_automated_security_pr", "Open a GitHub pull request with Docker-verified dependency upgrade patches (mutating)", True, "data_engineer"),
        ("devops.trigger_argocd_rollout", "Trigger Argo CD production sync or canary promotion on Kubernetes cluster (mutating, requires HITL)", True, "platform_admin"),
        ("devops.rollback_kubernetes_deployment", "Rollback a degraded Kubernetes deployment to previous stable replica set (mutating)", True, "platform_admin"),
        ("devops.rotate_service_principal_secret", "Rotate expired CI/CD service principal credentials in cloud secret vault (mutating)", True, "platform_admin"),
    ],
    "supply_chain": [
        ("supply_chain.query_maestro_gating_supplies", "Query Kinaxis Maestro / RapidResponse for gating supply shortages and late component deliveries", False, "analyst"),
        ("supply_chain.get_sku_demand_forecast", "Retrieve LightGBM/XGBoost + Croston/SBA demand forecast and WMAPE metrics for enterprise SKUs", False, "analyst"),
        ("supply_chain.classify_sku_adi_cv2_regime", "Classify SKU demand pattern into smooth, intermittent, erratic, or lumpy using ADI and CV2 cutoffs", False, "analyst"),
        ("supply_chain.compute_shap_forecast_drivers", "Generate SHAP TreeExplainer feature attribution summary for SKU promotional and macro drivers", False, "analyst"),
        ("supply_chain.simulate_what_if_scenario", "Run read-only S&OP what-if inventory buffer and supplier lead-time simulation in Maestro", False, "analyst"),
        ("supply_chain.inspect_bom_dependency_tree", "Traverse multi-tier Bill of Materials (BOM) component dependencies for manufacturing plants", False, "analyst"),
        ("supply_chain.check_plant_capacity_constraints", "Evaluate factory line utilization and bottleneck constraints across global shipping plants", False, "analyst"),
        ("supply_chain.translate_nl_to_mql_preview", "Compile natural language supply chain question into intermediate SQL and Maestro MQL with back-translation", False, "analyst"),
        ("supply_chain.get_macroeconomic_indicators", "Fetch PMI, industrial production MoM, and building permit signals for demand sensing", False, "analyst"),
        ("supply_chain.monitor_evidently_feature_drift", "Check Evidently AI covariate shift and Population Stability Index (PSI) on incoming SKU feeds", False, "data_engineer"),
        ("supply_chain.update_odoo_reorder_rules", "Write dynamic min/max safety stock replenishment rules into ERP orderpoint table (mutating)", True, "data_engineer"),
        ("supply_chain.commit_maestro_worksheet_override", "Commit planner forecast override directly into live Kinaxis Maestro production worksheet (mutating)", True, "platform_admin"),
        ("supply_chain.expedite_purchase_order", "Issue automated supplier expedite request for critical gating semiconductor components (mutating)", True, "platform_admin"),
        ("supply_chain.reallocate_plant_inventory", "Execute cross-plant inventory transfer order to resolve regional stockout (mutating)", True, "platform_admin"),
        ("supply_chain.trigger_optuna_cluster_retuning", "Launch distributed Azure Databricks Optuna hyperparameter tuning job across entropy clusters (mutating)", True, "data_engineer"),
    ],
    "crm_rest": [
        ("crm_rest.get_client_kyc_profile", "Fetch client KYC/AML verification status and regulatory jurisdiction from enterprise CRM REST API", False, "analyst"),
        ("crm_rest.check_pii_guardrail_status", "Verify GLiNER and Microsoft Presidio PII/PHI redaction vault status (PHIPA, Law 25, HIPAA)", False, "compliance_officer"),
        ("crm_rest.lookup_advisor_book_of_business", "Retrieve financial advisor assigned households and SLA response metrics via REST service", False, "analyst"),
        ("crm_rest.get_twilio_outreach_delivery_status", "Check Twilio SMS and voice appointment reminder delivery receipts and call logs", False, "analyst"),
        ("crm_rest.verify_ceba_cerb_relief_eligibility", "Run read-only adjudication rule check against historical federal credit relief criteria", False, "analyst"),
        ("crm_rest.inspect_rest_circuit_breaker", "Check downstream REST API gateway circuit breaker state, error rate, and p95 latency", False, "data_engineer"),
        ("crm_rest.validate_iso8583_card_message", "Parse and validate ISO 8583 payment switch authorization message fields", False, "data_engineer"),
        ("crm_rest.search_support_ticket_taxonomy", "Classify and search customer support tickets using multi-tier intent taxonomy", False, "analyst"),
        ("crm_rest.get_calendar_booking_slots", "Query available advisor/clinic consultation slots from scheduling REST API", False, "analyst"),
        ("crm_rest.audit_oauth2_obo_token_claims", "Inspect Microsoft Entra ID On-Behalf-Of (OBO) JWT scopes and tenant claims", False, "compliance_officer"),
        ("crm_rest.dispatch_twilio_sms_notification", "Send automated Twilio SMS appointment confirmation to verified client phone (mutating)", True, "analyst"),
        ("crm_rest.book_client_appointment_slot", "Reserve calendar appointment slot and emit confirmation webhook via n8n/REST (mutating)", True, "analyst"),
        ("crm_rest.block_compromised_payment_card", "Issue immediate card block command to payment switch middleware (mutating, requires HITL)", True, "platform_admin"),
        ("crm_rest.escalate_aml_suspicious_activity", "File formal AML compliance escalation dossier to regulatory review queue (mutating)", True, "compliance_officer"),
        ("crm_rest.revoke_external_api_webhook", "Disable compromised third-party webhook subscription on REST gateway (mutating)", True, "platform_admin"),
    ],
    "knowledge_graph": [
        ("knowledge_graph.qdrant_hybrid_vector_search", "Perform BGE-M3 dense + sparse vector retrieval in Qdrant with Cross-Encoder reranking", False, "ai_platform_reader"),
        ("knowledge_graph.neo4j_cypher_hop_traversal", "Execute read-only multi-hop Cypher entity-relationship traversal in Neo4j knowledge graph", False, "ai_platform_reader"),
        ("knowledge_graph.evaluate_retrieval_metrics", "Compute Recall@k, Mean Reciprocal Rank (MRR), and nDCG@k on golden RAG evaluation set", False, "data_engineer"),
        ("knowledge_graph.colpali_visual_patch_search", "Retrieve multi-column financial tables and engineering schematics via ColPali MaxSim patch scoring", False, "ai_platform_reader"),
        ("knowledge_graph.extract_docling_structured_table", "Extract typed Pydantic tables from complex PDFs using Qwen2.5-VL and Docling", False, "ai_platform_reader"),
        ("knowledge_graph.get_entity_neighborhood_subgraph", "Fetch 2-hop ego subgraph around a target regulation, part number, or fund entity in Neo4j", False, "analyst"),
        ("knowledge_graph.compare_hop1_vs_hop2_lift", "Measure multi-hop query reformulation accuracy lift over single-stage dense RAG", False, "data_engineer"),
        ("knowledge_graph.inspect_qdrant_collection_info", "Check Qdrant vector collection segment count, HNSW index parameters, and RAM footprint", False, "data_engineer"),
        ("knowledge_graph.trace_document_citation_provenance", "Verify exact page, section, and chunk provenance for LLM generated claims", False, "compliance_officer"),
        ("knowledge_graph.detect_contradictory_policy_chunks", "Identify conflicting version clauses across enterprise policy documents in vector store", False, "compliance_officer"),
        ("knowledge_graph.upsert_neo4j_entity_nodes", "Upsert extracted domain entities and topological relations into Neo4j graph (mutating)", True, "data_engineer"),
        ("knowledge_graph.reindex_qdrant_collection", "Rebuild Qdrant HNSW vector index with updated BGE-M3 embeddings (mutating)", True, "data_engineer"),
        ("knowledge_graph.prune_deprecated_doc_chunks", "Delete superseded regulatory document chunks from Qdrant and Neo4j stores (mutating)", True, "platform_admin"),
        ("knowledge_graph.merge_duplicate_graph_entities", "Execute entity resolution merge across duplicate nodes in Neo4j knowledge graph (mutating)", True, "data_engineer"),
        ("knowledge_graph.snapshot_vector_collection", "Create point-in-time Qdrant collection snapshot prior to bulk ingestion (mutating)", True, "data_engineer"),
    ],
    "portfolio_vsm": [
        ("portfolio_vsm.detect_management_concerns", "Analyze connected OKRs, product portfolios, and blocked engineering tickets to identify management concerns and suggest corrective actions", False, "analyst"),
        ("portfolio_vsm.query_okr_alignment", "Query Objectives and Key Results (OKRs) progress, confidence scores, and strategic alignment across product portfolios", False, "analyst"),
        ("portfolio_vsm.get_portfolio_health_summary", "Retrieve product portfolio budget utilization, R&D capacity allocation, flow efficiency, and cycle time metrics", False, "analyst"),
        ("portfolio_vsm.list_blocked_engineering_tickets", "List blocked or high-aging Jira and GitHub engineering work tickets delaying portfolio milestones", False, "analyst"),
        ("portfolio_vsm.compute_flow_efficiency_metrics", "Compute Value Stream Management (VSM) flow time, flow velocity, flow load, and wait-state bottlenecks", False, "analyst"),
        ("portfolio_vsm.analyze_sprint_velocity_bottlenecks", "Correlate engineering ticket cycle times and PR review latency against team sprint capacity", False, "data_engineer"),
        ("portfolio_vsm.check_epic_dependency_risks", "Traverse cross-team epic and engineering work ticket dependencies to flag critical-path slippage", False, "analyst"),
        ("portfolio_vsm.forecast_milestone_completion", "Run Monte Carlo throughput simulation over historical engineering ticket velocity to forecast release dates", False, "analyst"),
        ("portfolio_vsm.compare_planned_vs_actual_capacity", "Compare planned FTE investment by strategic theme against actual engineering ticket effort logged", False, "analyst"),
        ("portfolio_vsm.generate_executive_steering_brief", "Synthesize weekly portfolio risk, at-risk OKRs, and recommended management actions for product leadership", False, "analyst"),
        ("portfolio_vsm.reallocate_portfolio_capacity", "Reallocate engineering squad capacity across product portfolios to mitigate critical OKR slippage (mutating, requires HITL)", True, "platform_admin"),
        ("portfolio_vsm.escalate_blocked_work_ticket", "Trigger cross-team blocker escalation and priority promotion on stalled engineering work tickets (mutating)", True, "data_engineer"),
        ("portfolio_vsm.update_okr_confidence_status", "Update quarterly OKR confidence rating and attach mitigation action plan in portfolio ledger (mutating)", True, "analyst"),
        ("portfolio_vsm.rebalance_sprint_backlog_scope", "Defer non-critical backlog tickets to next sprint to protect committed portfolio milestone SLA (mutating)", True, "data_engineer"),
        ("portfolio_vsm.approve_milestone_scope_change", "Approve formal product portfolio baseline budget or milestone target date adjustment (mutating, requires HITL)", True, "platform_admin"),
    ],
}


def _build_tool_input_schema(name: str, domain: str) -> Dict[str, Any]:
    """Builds realistic, domain-specific JSON Schema Draft-07 contracts per MCP tool."""
    env_prop = {
        "type": "string",
        "enum": ["prod", "staging", "dev"],
        "default": "prod",
    }
    if name == "postgres.execute_outbound_wire":
        return {
            "type": "object",
            "properties": {
                "from_account": {"type": "string", "minLength": 3, "description": "Source institutional account ID"},
                "to_account": {"type": "string", "minLength": 3, "description": "Destination institutional account ID"},
                "amount_usd": {"type": "number", "minimum": 0.01, "description": "Wire amount in USD"},
                "environment": env_prop,
            },
            "required": ["from_account", "to_account", "amount_usd"],
        }
    if name in ("snowflake.execute_readonly_sql", "snowflake.analyze_query_plan"):
        return {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "minLength": 6, "description": "Read-only SELECT SQL query"},
                "role": {"type": "string", "default": "ai_platform_reader"},
                "schema_name": {"type": "string", "default": "PORTFOLIO_GOLD"},
                "environment": env_prop,
            },
            "required": ["sql"],
        }
    if domain == "portfolio_vsm":
        if name == "portfolio_vsm.reallocate_portfolio_capacity":
            return {
                "type": "object",
                "properties": {
                    "portfolio_id": {"type": "string", "minLength": 3, "description": "Target portfolio ID (e.g. PF-101)"},
                    "delta_fte": {"type": "number", "minimum": -20.0, "maximum": 20.0},
                    "justification": {"type": "string", "minLength": 5},
                    "environment": env_prop,
                },
                "required": ["portfolio_id", "delta_fte"],
            }
        if name == "portfolio_vsm.escalate_blocked_work_ticket":
            return {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "minLength": 3, "description": "Engineering ticket ID (e.g. ENG-401)"},
                    "escalation_tier": {"type": "string", "enum": ["L2", "VP_ENG", "EXEC"], "default": "VP_ENG"},
                    "environment": env_prop,
                },
                "required": ["ticket_id"],
            }
        return {
            "type": "object",
            "properties": {
                "portfolio_id": {"type": "string", "description": "Optional portfolio ID filter (e.g. PF-101)"},
                "okr_id": {"type": "string", "description": "Optional OKR ID filter (e.g. OKR-201)"},
                "query": {"type": "string", "description": f"Natural language question for {name}"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 10},
                "environment": env_prop,
            },
            "required": [],
        }

    return {
        "type": "object",
        "properties": {
            "query_or_id": {
                "type": "string",
                "minLength": 1,
                "description": f"Primary query, identifier, or payload for {name}",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "default": 10,
                "description": "Maximum records or chunks to return",
            },
            "environment": env_prop,
        },
        "required": ["query_or_id"],
    }


def get_enterprise_tool_catalog() -> List[Dict[str, Any]]:
    """
    Returns the complete 120-tool Enterprise MCP Catalog with 64-dim embeddings,
    JSON Schema input contracts, RBAC roles, and token footprint estimates.
    """
    catalog: List[Dict[str, Any]] = []
    for domain in DOMAIN_ORDER:
        templates = _DOMAIN_TOOL_TEMPLATES[domain]
        for name, desc, is_mutating, role in templates:
            emb = compute_query_embedding(f"{name} {domain} {desc}")
            input_schema = _build_tool_input_schema(name, domain)
            # Realistic token count for full MCP tool definition (name + description + JSON schema properties)
            schema_tokens = 128 + len(desc.split()) * 2
            catalog.append(
                {
                    "name": name,
                    "domain": domain,
                    "description": desc,
                    "is_mutating": is_mutating,
                    "required_role": role,
                    "embedding": emb,
                    "input_schema": input_schema,
                    "schema_tokens": schema_tokens,
                }
            )
    return catalog


BUILD_ENTERPRISE_CATALOG = get_enterprise_tool_catalog
