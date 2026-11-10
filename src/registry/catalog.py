"""
Deterministic 105-Tool Enterprise Model Context Protocol (MCP) Catalog.
Spans 7 enterprise domains:
  1. snowflake      (Snowflake Cortex Search, Read-Only Warehouses, FinOps)
  2. informatica    (Informatica Cloud IICS Taskflows, Mappings, ELT SLAs)
  3. postgres       (PostgreSQL Transactional Ledger, Snapshots, Audit Logs)
  4. devops         (GitHub PRs, Snyk CVE Remediation, Jira Tickets, Argo CD)
  5. supply_chain   (Kinaxis Maestro / S&OP Exceptions, Demand.AI SKU Forecasts)
  6. crm_rest       (REST API Gateways, Twilio Outreach, KYC/AML Compliance)
  7. knowledge_graph(Neo4j Cypher Traversal, Qdrant Hybrid Vector Retrieval)
"""

import math
from typing import Any, Dict, List


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
}

DOMAIN_ORDER = [
    "snowflake",
    "informatica",
    "postgres",
    "devops",
    "supply_chain",
    "crm_rest",
    "knowledge_graph",
]


def _normalize(vec: List[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm < 1e-9:
        return [1.0 / math.sqrt(len(vec)) for _ in vec]
    return [round(v / norm, 6) for v in vec]


def compute_query_embedding(text: str) -> List[float]:
    """
    Computes a deterministic 16-dimensional normalized dense semantic embedding
    from query or tool description text across the 7 enterprise domains + action axes.
    """
    tokens = [
        t.strip(".,;:!?()[]{}\"'`").lower()
        for t in text.replace("_", " ").replace(".", " ").replace("-", " ").split()
    ]
    token_set = set(tokens)

    # First 7 dimensions correspond to the 7 enterprise domains
    vec: List[float] = []
    for dom in DOMAIN_ORDER:
        kw_list = DOMAIN_KEYWORDS[dom]
        hits = sum(1.5 if kw in token_set else (0.6 if any(kw in tok for tok in token_set) else 0.0) for kw in kw_list)
        vec.append(hits + 0.05)

    # Dimensions 7..15 capture operational semantics (read vs mutate, search, sql, alert, etc.)
    read_terms = {"read", "get", "list", "select", "search", "query", "fetch", "inspect", "validate", "check"}
    write_terms = {"execute", "update", "delete", "create", "trigger", "wire", "approve", "restore", "mutate", "write"}
    sql_terms = {"sql", "table", "schema", "select", "ledger", "warehouse", "postgres", "snowflake"}
    rag_terms = {"rag", "cortex", "vector", "graph", "qdrant", "neo4j", "chunk", "policy", "document"}
    ops_terms = {"sla", "alert", "runbook", "telemetry", "trace", "lag", "status", "health", "audit"}
    fin_terms = {"fund", "nav", "rrsp", "wire", "balance", "portfolio", "aum", "kyc", "aml", "risk"}
    eng_terms = {"cve", "snyk", "jira", "github", "pr", "docker", "k8s", "argo", "build"}
    scm_terms = {"sku", "forecast", "maestro", "demand", "inventory", "supplier", "order", "plant"}
    etl_terms = {"iics", "informatica", "taskflow", "elt", "etl", "staging", "mapping", "ingest"}

    for group in [read_terms, write_terms, sql_terms, rag_terms, ops_terms, fin_terms, eng_terms, scm_terms, etl_terms]:
        vec.append(float(len(token_set & group)) + 0.05)

    return _normalize(vec)


# 15 curated tools per domain * 7 domains = 105 Enterprise MCP Tools
_DOMAIN_TOOL_TEMPLATES: Dict[str, List[ tuple[str, str, bool, str] ]] = {
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
}


def get_enterprise_tool_catalog() -> List[Dict[str, Any]]:
    """
    Returns the complete 105-tool Enterprise MCP Catalog with embeddings,
    JSON Schema input contracts, RBAC roles, and token footprint estimates.
    """
    catalog: List[Dict[str, Any]] = []
    for domain in DOMAIN_ORDER:
        templates = _DOMAIN_TOOL_TEMPLATES[domain]
        for name, desc, is_mutating, role in templates:
            emb = compute_query_embedding(f"{name} {domain} {desc}")
            input_schema = {
                "type": "object",
                "properties": {
                    "query_or_id": {
                        "type": "string",
                        "description": f"Primary query, identifier, or payload for {name}",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum records or chunks to return",
                    },
                    "environment": {
                        "type": "string",
                        "enum": ["prod", "staging", "dev"],
                        "default": "prod",
                    },
                },
                "required": ["query_or_id"],
            }
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
