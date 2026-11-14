"""
Labeled 160-Query Evaluation Benchmark & Ablation Harness for Enterprise-MCP-Router.

Addresses Phase 2 ("Make the numbers honest"):
- 120 single-domain evaluation queries (15 per domain across all 8 enterprise namespaces)
- 40 cross-domain multi-tool queries (spanning 2-3 domains per intent)
- Computes Recall@k for k in (3, 5, 8, 10, 25), split by single-domain vs cross-domain
- Runs ablations across:
  * dense_only (weights=(1.0, 0.0, 0.0))
  * bm25_only (weights=(0.0, 1.0, 0.0))
  * hybrid default (weights=(0.55, 0.35, 0.10))
  * hybrid tuned weights (e.g., (0.40, 0.45, 0.15) and (0.65, 0.25, 0.10))
  * widen-k fallback comparison at k=5 (`auto_widen=True`)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Sequence, Tuple

if TYPE_CHECKING:
    from src.router import EnterpriseMCPRouter


@dataclass(frozen=True)
class EvalQueryCase:
    """Single labeled query case for semantic routing evaluation."""

    query_id: str
    category: str  # "single_domain" or "cross_domain"
    domains: Tuple[str, ...]
    query: str
    expected_tools: Tuple[str, ...]


# ---------------------------------------------------------------------------
# 120 Single-Domain Queries (15 per domain x 8 enterprise namespaces)
# ---------------------------------------------------------------------------

SINGLE_DOMAIN_EVAL_CASES: List[EvalQueryCase] = [
    # --- 1. snowflake (15) ---
    EvalQueryCase("sf-01", "single_domain", ("snowflake",), "Search RRSP compliance guidelines and mutual fund documents in Cortex RAG", ("snowflake.cortex_search_docs",)),
    EvalQueryCase("sf-02", "single_domain", ("snowflake",), "Run a guarded read-only SELECT SQL query against PORTFOLIO_GOLD warehouse tables", ("snowflake.execute_readonly_sql",)),
    EvalQueryCase("sf-03", "single_domain", ("snowflake",), "Fetch historical net asset value time series for institutional fund POL-101", ("snowflake.get_fund_nav_history",)),
    EvalQueryCase("sf-04", "single_domain", ("snowflake",), "Inspect column types and table DDL metadata in the gold warehouse schema", ("snowflake.inspect_table_schema",)),
    EvalQueryCase("sf-05", "single_domain", ("snowflake",), "Check virtual warehouse queue depth and compute credit consumption load", ("snowflake.check_warehouse_load",)),
    EvalQueryCase("sf-06", "single_domain", ("snowflake",), "List active Cortex Search indexes and vector sync configurations", ("snowflake.list_cortex_services",)),
    EvalQueryCase("sf-07", "single_domain", ("snowflake",), "Validate Snowflake role privileges and least-privilege RBAC table grants", ("snowflake.validate_rbac_grants",)),
    EvalQueryCase("sf-08", "single_domain", ("snowflake",), "Look up CRA yearly RRSP contribution ceiling and tax deduction thresholds", ("snowflake.fetch_rrsp_contribution_limits",)),
    EvalQueryCase("sf-09", "single_domain", ("snowflake",), "Query institutional asset allocation positions and equity sector weights", ("snowflake.query_institutional_holdings",)),
    EvalQueryCase("sf-10", "single_domain", ("snowflake",), "Profile Snowflake query execution plan for full table scan bottlenecks", ("snowflake.analyze_query_plan",)),
    EvalQueryCase("sf-11", "single_domain", ("snowflake",), "Check staging table landing freshness timestamp and ELT lag watermark", ("snowflake.get_staging_freshness",)),
    EvalQueryCase("sf-12", "single_domain", ("snowflake",), "Export regulatory SEC or OSC compliance audit extract from curated tables", ("snowflake.export_compliance_extract",)),
    EvalQueryCase("sf-13", "single_domain", ("snowflake",), "Trigger incremental rebuild of Cortex vector search document index", ("snowflake.refresh_cortex_index",)),
    EvalQueryCase("sf-14", "single_domain", ("snowflake",), "Resume suspended Snowflake compute warehouse cluster to serve queries", ("snowflake.resume_virtual_warehouse",)),
    EvalQueryCase("sf-15", "single_domain", ("snowflake",), "Quarantine malformed staging batch files to isolate corrupt ELT payloads", ("snowflake.quarantine_corrupt_stage",)),

    # --- 2. informatica (15) ---
    EvalQueryCase("infa-01", "single_domain", ("informatica",), "Verify Informatica IICS taskflow SLA lag and minimum row count gate", ("informatica.validate_taskflow_sla",)),
    EvalQueryCase("infa-02", "single_domain", ("informatica",), "Download IICS mapping task execution stdout and stderr session logs", ("informatica.get_taskflow_run_logs",)),
    EvalQueryCase("infa-03", "single_domain", ("informatica",), "List all running and recently completed Informatica CDI mapping tasks", ("informatica.list_active_mappings",)),
    EvalQueryCase("infa-04", "single_domain", ("informatica",), "Monitor on-prem IICS Secure Agent JVM heap memory and runtime health", ("informatica.check_secure_agent_health",)),
    EvalQueryCase("infa-05", "single_domain", ("informatica",), "Trace end-to-end column data lineage from ERP source to analytics target", ("informatica.inspect_source_to_target_lineage",)),
    EvalQueryCase("infa-06", "single_domain", ("informatica",), "Reconcile source extract record totals against destination warehouse rows", ("informatica.verify_row_count_reconciliation",)),
    EvalQueryCase("infa-07", "single_domain", ("informatica",), "Inspect Informatica dead-letter error table for rejected schema rows", ("informatica.get_dead_letter_rejects",)),
    EvalQueryCase("infa-08", "single_domain", ("informatica",), "Audit IICS connection service credentials and key rotation expiry age", ("informatica.audit_connection_credentials",)),
    EvalQueryCase("infa-09", "single_domain", ("informatica",), "Estimate completion time ETA for the nightly batch ingestion pipeline window", ("informatica.estimate_elt_window_eta",)),
    EvalQueryCase("infa-10", "single_domain", ("informatica",), "Check whether the Informatica pre-RAG ingestion circuit-breaker lock is open", ("informatica.check_rag_gate_lock",)),
    EvalQueryCase("infa-11", "single_domain", ("informatica",), "List recurring CRON and event-triggered IICS ingestion schedules", ("informatica.list_scheduled_jobs",)),
    EvalQueryCase("infa-12", "single_domain", ("informatica",), "Restart a failed Informatica cloud taskflow from last recovery checkpoint", ("informatica.retrigger_failed_taskflow",)),
    EvalQueryCase("infa-13", "single_domain", ("informatica",), "Force terminate a hung Informatica mapping job stuck in loop", ("informatica.abort_stalled_mapping",)),
    EvalQueryCase("infa-14", "single_domain", ("informatica",), "Promote validated staging dataset into production gold layer tables", ("informatica.promote_staging_to_gold",)),
    EvalQueryCase("infa-15", "single_domain", ("informatica",), "Adjust CDC replication high-watermark timestamp offset for backfill", ("informatica.update_watermark_offset",)),

    # --- 3. postgres (15) ---
    EvalQueryCase("pg-01", "single_domain", ("postgres",), "Query PostgreSQL accounting ledger balances and risk tier classifications", ("postgres.read_accounting_ledger",)),
    EvalQueryCase("pg-02", "single_domain", ("postgres",), "Retrieve customer wealth account valuation and aggregated portfolio holdings", ("postgres.get_customer_portfolio_summary",)),
    EvalQueryCase("pg-03", "single_domain", ("postgres",), "List recent immutable security audit log entries from PostgreSQL store", ("postgres.list_recent_audit_events",)),
    EvalQueryCase("pg-04", "single_domain", ("postgres",), "Inspect PgBouncer database connection pool saturation and active locks", ("postgres.check_connection_pool_stats",)),
    EvalQueryCase("pg-05", "single_domain", ("postgres",), "Validate foreign key referential constraints across financial ledger tables", ("postgres.verify_foreign_key_integrity",)),
    EvalQueryCase("pg-06", "single_domain", ("postgres",), "List available point-in-time PostgreSQL database rollback snapshots", ("postgres.list_database_snapshots",)),
    EvalQueryCase("pg-07", "single_domain", ("postgres",), "Run PostgreSQL EXPLAIN cost analyzer to diagnose sequential index scans", ("postgres.explain_query_cost",)),
    EvalQueryCase("pg-08", "single_domain", ("postgres",), "Fetch unsettled T+1 equity clearing settlements pending cash finality", ("postgres.get_pending_settlements",)),
    EvalQueryCase("pg-09", "single_domain", ("postgres",), "Search anomalous high-velocity wire transfers for AML behavioral flags", ("postgres.search_transaction_anomalies",)),
    EvalQueryCase("pg-10", "single_domain", ("postgres",), "Measure dead tuple bloat and autovacuum lag on PostgreSQL tables", ("postgres.get_table_bloat_metrics",)),
    EvalQueryCase("pg-11", "single_domain", ("postgres",), "Capture pre-mutation state snapshot of relational financial accounts", ("postgres.create_state_snapshot",)),
    EvalQueryCase("pg-12", "single_domain", ("postgres",), "Roll back PostgreSQL database state to an approved prior snapshot", ("postgres.restore_state_snapshot",)),
    EvalQueryCase("pg-13", "single_domain", ("postgres",), "Transfer institutional treasury funds via outbound wire between accounts", ("postgres.execute_outbound_wire",)),
    EvalQueryCase("pg-14", "single_domain", ("postgres",), "Modify customer suitability risk tier rating after compliance review", ("postgres.update_account_risk_tier",)),
    EvalQueryCase("pg-15", "single_domain", ("postgres",), "Clean up expired authentication tokens and stale session rows", ("postgres.purge_expired_sessions",)),

    # --- 4. devops (15) ---
    EvalQueryCase("dev-01", "single_domain", ("devops",), "List critical Snyk CVE dependency vulnerability alerts across repositories", ("devops.list_snyk_cve_alerts",)),
    EvalQueryCase("dev-02", "single_domain", ("devops",), "Fetch GitHub pull request code diff and review annotations", ("devops.get_github_pr_diff",)),
    EvalQueryCase("dev-03", "single_domain", ("devops",), "Tail isolated Docker container sandbox stderr and build execution logs", ("devops.inspect_docker_sandbox_logs",)),
    EvalQueryCase("dev-04", "single_domain", ("devops",), "Check end-of-life support deprecation dates for Python and Node runtimes", ("devops.check_dependency_eol_status",)),
    EvalQueryCase("dev-05", "single_domain", ("devops",), "Inspect ArgoCD Kubernetes GitOps application sync drift status", ("devops.get_argocd_sync_status",)),
    EvalQueryCase("dev-06", "single_domain", ("devops",), "Analyze Kubecost Kubernetes namespace spend and idle GPU cluster cost", ("devops.query_kashops_cluster_costs",)),
    EvalQueryCase("dev-07", "single_domain", ("devops",), "Search Jira software engineering backlog for sprint bug and CVE tickets", ("devops.search_jira_engineering_tickets",)),
    EvalQueryCase("dev-08", "single_domain", ("devops",), "Validate JSON Schema contract compatibility for microservice API payloads", ("devops.validate_json_schema_contract",)),
    EvalQueryCase("dev-09", "single_domain", ("devops",), "Check GitHub Actions CI pipeline workflow run exit status and timing", ("devops.get_github_actions_workflow_runs",)),
    EvalQueryCase("dev-10", "single_domain", ("devops",), "Inspect Kubernetes Helm chart deployment values and replica limits", ("devops.inspect_helm_chart_values",)),
    EvalQueryCase("dev-11", "single_domain", ("devops",), "Create a tracked Jira security remediation issue with SLA priority", ("devops.create_jira_remediation_ticket",)),
    EvalQueryCase("dev-12", "single_domain", ("devops",), "Open an automated GitHub PR patching vulnerable requirements versions", ("devops.open_automated_security_pr",)),
    EvalQueryCase("dev-13", "single_domain", ("devops",), "Sync and deploy production Kubernetes release rollout via ArgoCD", ("devops.trigger_argocd_rollout",)),
    EvalQueryCase("dev-14", "single_domain", ("devops",), "Roll back broken Kubernetes deployment revision to last healthy pod set", ("devops.rollback_kubernetes_deployment",)),
    EvalQueryCase("dev-15", "single_domain", ("devops",), "Rotate Azure or AWS service principal client secret and refresh vault", ("devops.rotate_service_principal_secret",)),

    # --- 5. supply_chain (15) ---
    EvalQueryCase("sc-01", "single_domain", ("supply_chain",), "Query Kinaxis Maestro gating components causing BOM stockout delays", ("supply_chain.query_maestro_gating_supplies",)),
    EvalQueryCase("sc-02", "single_domain", ("supply_chain",), "Retrieve SKU weekly demand forecast time series with P10/P90 bounds", ("supply_chain.get_sku_demand_forecast",)),
    EvalQueryCase("sc-03", "single_domain", ("supply_chain",), "Classify SKU intermittency regime using Syntetos-Boylan ADI and CV2", ("supply_chain.classify_sku_adi_cv2_regime",)),
    EvalQueryCase("sc-04", "single_domain", ("supply_chain",), "Compute LightGBM SHAP feature importance attributions driving demand", ("supply_chain.compute_shap_forecast_drivers",)),
    EvalQueryCase("sc-05", "single_domain", ("supply_chain",), "Run supply chain digital twin what-if disruption simulation for tariff shock", ("supply_chain.simulate_what_if_scenario",)),
    EvalQueryCase("sc-06", "single_domain", ("supply_chain",), "Explode multi-tier Bill of Materials parent-child assembly dependency tree", ("supply_chain.inspect_bom_dependency_tree",)),
    EvalQueryCase("sc-07", "single_domain", ("supply_chain",), "Check factory plant bottleneck machine utilization and shift capacity", ("supply_chain.check_plant_capacity_constraints",)),
    EvalQueryCase("sc-08", "single_domain", ("supply_chain",), "Translate natural language planning question into structured Maestro MQL", ("supply_chain.translate_nl_to_mql_preview",)),
    EvalQueryCase("sc-09", "single_domain", ("supply_chain",), "Fetch Bank of Canada FX rates, CPI inflation, and freight macro indexes", ("supply_chain.get_macroeconomic_indicators",)),
    EvalQueryCase("sc-10", "single_domain", ("supply_chain",), "Monitor Evidently ML covariate and prediction drift on demand features", ("supply_chain.monitor_evidently_feature_drift",)),
    EvalQueryCase("sc-11", "single_domain", ("supply_chain",), "Update ERP Odoo safety stock minimums and automated reorder point rules", ("supply_chain.update_odoo_reorder_rules",)),
    EvalQueryCase("sc-12", "single_domain", ("supply_chain",), "Commit manual planner override adjustment to Kinaxis Maestro worksheet", ("supply_chain.commit_maestro_worksheet_override",)),
    EvalQueryCase("sc-13", "single_domain", ("supply_chain",), "Expedite open supplier purchase order with air freight priority escalation", ("supply_chain.expedite_purchase_order",)),
    EvalQueryCase("sc-14", "single_domain", ("supply_chain",), "Transfer constrained raw inventory allocation between distribution plants", ("supply_chain.reallocate_plant_inventory",)),
    EvalQueryCase("sc-15", "single_domain", ("supply_chain",), "Launch Optuna hyperparameter retuning job for clustered SKU forecasting", ("supply_chain.trigger_optuna_cluster_retuning",)),

    # --- 6. crm_rest (15) ---
    EvalQueryCase("crm-01", "single_domain", ("crm_rest",), "Fetch masked customer KYC onboarding identity verification profile", ("crm_rest.get_client_kyc_profile",)),
    EvalQueryCase("crm-02", "single_domain", ("crm_rest",), "Verify PII redaction guardrail status blocking SIN numbers in payloads", ("crm_rest.check_pii_guardrail_status",)),
    EvalQueryCase("crm-03", "single_domain", ("crm_rest",), "Lookup financial advisor CRM book of business AUM and client tiers", ("crm_rest.lookup_advisor_book_of_business",)),
    EvalQueryCase("crm-04", "single_domain", ("crm_rest",), "Check Twilio SMS client outreach delivery webhook confirmation status", ("crm_rest.get_twilio_outreach_delivery_status",)),
    EvalQueryCase("crm-05", "single_domain", ("crm_rest",), "Evaluate small business CEBA loan repayment and government relief rules", ("crm_rest.verify_ceba_cerb_relief_eligibility",)),
    EvalQueryCase("crm-06", "single_domain", ("crm_rest",), "Inspect REST API retry exponential backoff and circuit breaker trip counts", ("crm_rest.inspect_rest_circuit_breaker",)),
    EvalQueryCase("crm-07", "single_domain", ("crm_rest",), "Parse and validate ISO-8583 banking card authorization bitmap fields", ("crm_rest.validate_iso8583_card_message",)),
    EvalQueryCase("crm-08", "single_domain", ("crm_rest",), "Categorize incoming client service desk complaints by topic taxonomy", ("crm_rest.search_support_ticket_taxonomy",)),
    EvalQueryCase("crm-09", "single_domain", ("crm_rest",), "Query advisor calendar availability windows for client portfolio review", ("crm_rest.get_calendar_booking_slots",)),
    EvalQueryCase("crm-10", "single_domain", ("crm_rest",), "Inspect Microsoft Entra OAuth2 On-Behalf-Of federated token scope claims", ("crm_rest.audit_oauth2_obo_token_claims",)),
    EvalQueryCase("crm-11", "single_domain", ("crm_rest",), "Send compliant client notification SMS message through Twilio gateway", ("crm_rest.dispatch_twilio_sms_notification",)),
    EvalQueryCase("crm-12", "single_domain", ("crm_rest",), "Book confirmed financial planning meeting slot on client and advisor calendar", ("crm_rest.book_client_appointment_slot",)),
    EvalQueryCase("crm-13", "single_domain", ("crm_rest",), "Immediately freeze and block compromised credit card upon fraud signal", ("crm_rest.block_compromised_payment_card",)),
    EvalQueryCase("crm-14", "single_domain", ("crm_rest",), "File FINTRAC anti-money-laundering suspicious transaction escalation case", ("crm_rest.escalate_aml_suspicious_activity",)),
    EvalQueryCase("crm-15", "single_domain", ("crm_rest",), "Revoke third-party webhook subscription API key after partner offboarding", ("crm_rest.revoke_external_api_webhook",)),

    # --- 7. knowledge_graph (15) ---
    EvalQueryCase("kg-01", "single_domain", ("knowledge_graph",), "Run hybrid dense and sparse vector similarity search in Qdrant index", ("knowledge_graph.qdrant_hybrid_vector_search",)),
    EvalQueryCase("kg-02", "single_domain", ("knowledge_graph",), "Execute multi-hop Cypher graph traversal in Neo4j entity knowledge graph", ("knowledge_graph.neo4j_cypher_hop_traversal",)),
    EvalQueryCase("kg-03", "single_domain", ("knowledge_graph",), "Compute MRR, nDCG@10, and Recall@k retrieval quality evaluation metrics", ("knowledge_graph.evaluate_retrieval_metrics",)),
    EvalQueryCase("kg-04", "single_domain", ("knowledge_graph",), "Perform ColPali multimodal visual document page patch embedding search", ("knowledge_graph.colpali_visual_patch_search",)),
    EvalQueryCase("kg-05", "single_domain", ("knowledge_graph",), "Parse financial PDF tables into structured JSON using Docling extractor", ("knowledge_graph.extract_docling_structured_table",)),
    EvalQueryCase("kg-06", "single_domain", ("knowledge_graph",), "Retrieve 1-hop neighborhood subgraph of connected policies and funds", ("knowledge_graph.get_entity_neighborhood_subgraph",)),
    EvalQueryCase("kg-07", "single_domain", ("knowledge_graph",), "Benchmark 1-hop vs 2-hop graph retrieval recall lift on Q&A ground truth", ("knowledge_graph.compare_hop1_vs_hop2_lift",)),
    EvalQueryCase("kg-08", "single_domain", ("knowledge_graph",), "Inspect Qdrant vector collection segment count, HNSW parameters, and RAM", ("knowledge_graph.inspect_qdrant_collection_info",)),
    EvalQueryCase("kg-09", "single_domain", ("knowledge_graph",), "Verify strict page and chunk citation lineage for grounded RAG answers", ("knowledge_graph.trace_document_citation_provenance",)),
    EvalQueryCase("kg-10", "single_domain", ("knowledge_graph",), "Detect conflicting compliance policy clauses across indexed document versions", ("knowledge_graph.detect_contradictory_policy_chunks",)),
    EvalQueryCase("kg-11", "single_domain", ("knowledge_graph",), "Upsert extracted ontology nodes and relationship edges into Neo4j graph", ("knowledge_graph.upsert_neo4j_entity_nodes",)),
    EvalQueryCase("kg-12", "single_domain", ("knowledge_graph",), "Reindex Qdrant embeddings after upgrading sentence encoder dimensions", ("knowledge_graph.reindex_qdrant_collection",)),
    EvalQueryCase("kg-13", "single_domain", ("knowledge_graph",), "Delete obsolete superseded document chunks from active vector store", ("knowledge_graph.prune_deprecated_doc_chunks",)),
    EvalQueryCase("kg-14", "single_domain", ("knowledge_graph",), "Resolve and merge duplicate corporate entity aliases inside Neo4j", ("knowledge_graph.merge_duplicate_graph_entities",)),
    EvalQueryCase("kg-15", "single_domain", ("knowledge_graph",), "Create portable Qdrant collection snapshot archive before reindexing", ("knowledge_graph.snapshot_vector_collection",)),

    # --- 8. portfolio_vsm (15) ---
    EvalQueryCase("vsm-01", "single_domain", ("portfolio_vsm",), "Detect executive management concerns across at-risk OKRs and blocked work", ("portfolio_vsm.detect_management_concerns",)),
    EvalQueryCase("vsm-02", "single_domain", ("portfolio_vsm",), "Query Value Stream OKR key results progress and confidence ratings", ("portfolio_vsm.query_okr_alignment",)),
    EvalQueryCase("vsm-03", "single_domain", ("portfolio_vsm",), "Get portfolio budget health, SLA attainment, and delivery RAG summary", ("portfolio_vsm.get_portfolio_health_summary",)),
    EvalQueryCase("vsm-04", "single_domain", ("portfolio_vsm",), "List severely blocked engineering tickets stalling critical OKR milestones", ("portfolio_vsm.list_blocked_engineering_tickets",)),
    EvalQueryCase("vsm-05", "single_domain", ("portfolio_vsm",), "Calculate value stream cycle time, lead time, and flow efficiency ratio", ("portfolio_vsm.compute_flow_efficiency_metrics",)),
    EvalQueryCase("vsm-06", "single_domain", ("portfolio_vsm",), "Analyze sprint velocity trends and WIP queue bottleneck stages", ("portfolio_vsm.analyze_sprint_velocity_bottlenecks",)),
    EvalQueryCase("vsm-07", "single_domain", ("portfolio_vsm",), "Identify cross-team epic dependency chains putting launch dates at risk", ("portfolio_vsm.check_epic_dependency_risks",)),
    EvalQueryCase("vsm-08", "single_domain", ("portfolio_vsm",), "Forecast Monte Carlo milestone delivery date probability curve", ("portfolio_vsm.forecast_milestone_completion",)),
    EvalQueryCase("vsm-09", "single_domain", ("portfolio_vsm",), "Compare planned FTE headcount allocation against actual sprint burn", ("portfolio_vsm.compare_planned_vs_actual_capacity",)),
    EvalQueryCase("vsm-10", "single_domain", ("portfolio_vsm",), "Synthesize board-ready Value Stream quarterly steering committee brief", ("portfolio_vsm.generate_executive_steering_brief",)),
    EvalQueryCase("vsm-11", "single_domain", ("portfolio_vsm",), "Reallocate engineering FTE capacity between strategic product portfolios", ("portfolio_vsm.reallocate_portfolio_capacity",)),
    EvalQueryCase("vsm-12", "single_domain", ("portfolio_vsm",), "Escalate blocked production work item to engineering incident owners", ("portfolio_vsm.escalate_blocked_work_ticket",)),
    EvalQueryCase("vsm-13", "single_domain", ("portfolio_vsm",), "Update OKR objective confidence status score after quarterly check-in", ("portfolio_vsm.update_okr_confidence_status",)),
    EvalQueryCase("vsm-14", "single_domain", ("portfolio_vsm",), "De-scope low-priority sprint stories to protect critical path milestone", ("portfolio_vsm.rebalance_sprint_backlog_scope",)),
    EvalQueryCase("vsm-15", "single_domain", ("portfolio_vsm",), "Approve executive product milestone scope change with HITL sign-off", ("portfolio_vsm.approve_milestone_scope_change",)),
]


# ---------------------------------------------------------------------------
# 40 Cross-Domain Evaluation Queries (spanning 2+ domains / expected tools)
# ---------------------------------------------------------------------------

CROSS_DOMAIN_EVAL_CASES: List[EvalQueryCase] = [
    EvalQueryCase(
        "xd-01", "cross_domain", ("informatica", "snowflake"),
        "Validate Informatica taskflow SLA row counts and refresh Snowflake Cortex vector search index",
        ("informatica.validate_taskflow_sla", "snowflake.refresh_cortex_index"),
    ),
    EvalQueryCase(
        "xd-02", "cross_domain", ("snowflake", "postgres"),
        "Fetch institutional fund NAV history in Snowflake and query PostgreSQL accounting ledger balances",
        ("snowflake.get_fund_nav_history", "postgres.read_accounting_ledger"),
    ),
    EvalQueryCase(
        "xd-03", "cross_domain", ("postgres", "crm_rest"),
        "Search PostgreSQL transaction wire anomalies and escalate suspicious AML activity in CRM",
        ("postgres.search_transaction_anomalies", "crm_rest.escalate_aml_suspicious_activity"),
    ),
    EvalQueryCase(
        "xd-04", "cross_domain", ("devops", "postgres"),
        "List Snyk CVE vulnerability alerts and create a PostgreSQL state snapshot before patching",
        ("devops.list_snyk_cve_alerts", "postgres.create_state_snapshot"),
    ),
    EvalQueryCase(
        "xd-05", "cross_domain", ("portfolio_vsm", "devops"),
        "Detect VSM management concerns across OKRs and search Jira engineering backlog tickets",
        ("portfolio_vsm.detect_management_concerns", "devops.search_jira_engineering_tickets"),
    ),
    EvalQueryCase(
        "xd-06", "cross_domain", ("portfolio_vsm", "postgres"),
        "List blocked VSM engineering tickets and inspect PostgreSQL recent audit events for incidents",
        ("portfolio_vsm.list_blocked_engineering_tickets", "postgres.list_recent_audit_events"),
    ),
    EvalQueryCase(
        "xd-07", "cross_domain", ("knowledge_graph", "snowflake"),
        "Run Qdrant hybrid vector search alongside Snowflake Cortex compliance document retrieval",
        ("knowledge_graph.qdrant_hybrid_vector_search", "snowflake.cortex_search_docs"),
    ),
    EvalQueryCase(
        "xd-08", "cross_domain", ("supply_chain", "postgres"),
        "Query Kinaxis Maestro gating supplies and reconcile pending cash settlements in Postgres",
        ("supply_chain.query_maestro_gating_supplies", "postgres.get_pending_settlements"),
    ),
    EvalQueryCase(
        "xd-09", "cross_domain", ("crm_rest", "snowflake"),
        "Check client KYC profile and retrieve CRA RRSP contribution rules from Snowflake",
        ("crm_rest.get_client_kyc_profile", "snowflake.fetch_rrsp_contribution_limits"),
    ),
    EvalQueryCase(
        "xd-10", "cross_domain", ("informatica", "knowledge_graph"),
        "Check Informatica RAG gate lock status before reindexing the Qdrant vector collection",
        ("informatica.check_rag_gate_lock", "knowledge_graph.reindex_qdrant_collection"),
    ),
    EvalQueryCase(
        "xd-11", "cross_domain", ("devops", "portfolio_vsm"),
        "Open automated GitHub security PR for CVE and escalate blocked VSM work ticket",
        ("devops.open_automated_security_pr", "portfolio_vsm.escalate_blocked_work_ticket"),
    ),
    EvalQueryCase(
        "xd-12", "cross_domain", ("postgres", "crm_rest"),
        "Verify Postgres customer portfolio summary and lookup advisor book of business in CRM",
        ("postgres.get_customer_portfolio_summary", "crm_rest.lookup_advisor_book_of_business"),
    ),
    EvalQueryCase(
        "xd-13", "cross_domain", ("knowledge_graph", "crm_rest"),
        "Detect contradictory compliance policy chunks in graph and check PII guardrail status",
        ("knowledge_graph.detect_contradictory_policy_chunks", "crm_rest.check_pii_guardrail_status"),
    ),
    EvalQueryCase(
        "xd-14", "cross_domain", ("supply_chain", "informatica"),
        "Monitor Evidently ML demand feature drift and inspect Informatica source-to-target data lineage",
        ("supply_chain.monitor_evidently_feature_drift", "informatica.inspect_source_to_target_lineage"),
    ),
    EvalQueryCase(
        "xd-15", "cross_domain", ("snowflake", "devops"),
        "Validate Snowflake RBAC grants and rotate Azure service principal secrets safely",
        ("snowflake.validate_rbac_grants", "devops.rotate_service_principal_secret"),
    ),
    EvalQueryCase(
        "xd-16", "cross_domain", ("portfolio_vsm", "supply_chain"),
        "Reallocate strategic engineering portfolio capacity after simulating supply chain disruption scenario",
        ("portfolio_vsm.reallocate_portfolio_capacity", "supply_chain.simulate_what_if_scenario"),
    ),
    EvalQueryCase(
        "xd-17", "cross_domain", ("informatica", "postgres"),
        "Verify Informatica row count reconciliation against Postgres foreign key integrity checks",
        ("informatica.verify_row_count_reconciliation", "postgres.verify_foreign_key_integrity"),
    ),
    EvalQueryCase(
        "xd-18", "cross_domain", ("devops", "knowledge_graph"),
        "Inspect Docker sandbox logs for ingestion worker and evaluate RAG retrieval MRR metrics",
        ("devops.inspect_docker_sandbox_logs", "knowledge_graph.evaluate_retrieval_metrics"),
    ),
    EvalQueryCase(
        "xd-19", "cross_domain", ("crm_rest", "postgres"),
        "Freeze compromised payment card after detecting high-risk transaction anomaly in ledger",
        ("crm_rest.block_compromised_payment_card", "postgres.search_transaction_anomalies"),
    ),
    EvalQueryCase(
        "xd-20", "cross_domain", ("snowflake", "portfolio_vsm"),
        "Export compliance regulatory audit from Snowflake and generate executive steering brief",
        ("snowflake.export_compliance_extract", "portfolio_vsm.generate_executive_steering_brief"),
    ),
    EvalQueryCase(
        "xd-21", "cross_domain", ("knowledge_graph", "informatica"),
        "Extract structured PDF tables via Docling and trace Informatica pipeline source lineage",
        ("knowledge_graph.extract_docling_structured_table", "informatica.inspect_source_to_target_lineage"),
    ),
    EvalQueryCase(
        "xd-22", "cross_domain", ("postgres", "devops"),
        "Rollback Kubernetes deployment via ArgoCD and restore Postgres database state snapshot",
        ("devops.rollback_kubernetes_deployment", "postgres.restore_state_snapshot"),
    ),
    EvalQueryCase(
        "xd-23", "cross_domain", ("supply_chain", "snowflake"),
        "Fetch macroeconomic inflation indicators and query institutional fund equity holdings in Snowflake",
        ("supply_chain.get_macroeconomic_indicators", "snowflake.query_institutional_holdings"),
    ),
    EvalQueryCase(
        "xd-24", "cross_domain", ("crm_rest", "portfolio_vsm"),
        "Dispatch SMS client alert via Twilio and update OKR confidence status for wealth release",
        ("crm_rest.dispatch_twilio_sms_notification", "portfolio_vsm.update_okr_confidence_status"),
    ),
    EvalQueryCase(
        "xd-25", "cross_domain", ("devops", "crm_rest"),
        "Validate JSON Schema contract compatibility and inspect REST API circuit breaker telemetry",
        ("devops.validate_json_schema_contract", "crm_rest.inspect_rest_circuit_breaker"),
    ),
    EvalQueryCase(
        "xd-26", "cross_domain", ("snowflake", "knowledge_graph"),
        "Inspect warehouse staging table freshness and trace document citation provenance lineage",
        ("snowflake.get_staging_freshness", "knowledge_graph.trace_document_citation_provenance"),
    ),
    EvalQueryCase(
        "xd-27", "cross_domain", ("informatica", "devops"),
        "Get failed Informatica taskflow run logs and open Jira remediation ticket for triage",
        ("informatica.get_taskflow_run_logs", "devops.create_jira_remediation_ticket"),
    ),
    EvalQueryCase(
        "xd-28", "cross_domain", ("postgres", "snowflake"),
        "Execute guarded read-only SQL on Snowflake warehouse and explain Postgres ledger query cost",
        ("snowflake.execute_readonly_sql", "postgres.explain_query_cost"),
    ),
    EvalQueryCase(
        "xd-29", "cross_domain", ("supply_chain", "knowledge_graph"),
        "Inspect BOM assembly dependency tree alongside Neo4j Cypher multi-hop entity traversal",
        ("supply_chain.inspect_bom_dependency_tree", "knowledge_graph.neo4j_cypher_hop_traversal"),
    ),
    EvalQueryCase(
        "xd-30", "cross_domain", ("portfolio_vsm", "crm_rest"),
        "Compare planned vs actual engineering FTE capacity and book client review calendar slot",
        ("portfolio_vsm.compare_planned_vs_actual_capacity", "crm_rest.book_client_appointment_slot"),
    ),
    EvalQueryCase(
        "xd-31", "cross_domain", ("postgres", "informatica"),
        "Execute institutional outbound wire in Postgres and promote staging batch to gold tables",
        ("postgres.execute_outbound_wire", "informatica.promote_staging_to_gold"),
    ),
    EvalQueryCase(
        "xd-32", "cross_domain", ("devops", "snowflake"),
        "Check Kubecost Kubernetes cluster spend and monitor Snowflake virtual warehouse load",
        ("devops.query_kashops_cluster_costs", "snowflake.check_warehouse_load"),
    ),
    EvalQueryCase(
        "xd-33", "cross_domain", ("knowledge_graph", "postgres"),
        "Create Qdrant vector collection snapshot and list PostgreSQL database rollback snapshots",
        ("knowledge_graph.snapshot_vector_collection", "postgres.list_database_snapshots"),
    ),
    EvalQueryCase(
        "xd-34", "cross_domain", ("crm_rest", "devops"),
        "Audit Entra OAuth2 OBO token claims and inspect ArgoCD Kubernetes deployment sync state",
        ("crm_rest.audit_oauth2_obo_token_claims", "devops.get_argocd_sync_status"),
    ),
    EvalQueryCase(
        "xd-35", "cross_domain", ("supply_chain", "portfolio_vsm"),
        "Expedite supplier purchase order and approve strategic milestone scope change in VSM",
        ("supply_chain.expedite_purchase_order", "portfolio_vsm.approve_milestone_scope_change"),
    ),
    EvalQueryCase(
        "xd-36", "cross_domain", ("informatica", "crm_rest"),
        "Audit Informatica connector credentials expiry and revoke external partner webhook key",
        ("informatica.audit_connection_credentials", "crm_rest.revoke_external_api_webhook"),
    ),
    EvalQueryCase(
        "xd-37", "cross_domain", ("snowflake", "knowledge_graph"),
        "Inspect Snowflake table schema columns and merge duplicate corporate nodes in Neo4j graph",
        ("snowflake.inspect_table_schema", "knowledge_graph.merge_duplicate_graph_entities"),
    ),
    EvalQueryCase(
        "xd-38", "cross_domain", ("portfolio_vsm", "devops"),
        "Analyze sprint velocity bottlenecks and inspect GitHub Actions CI workflow run status",
        ("portfolio_vsm.analyze_sprint_velocity_bottlenecks", "devops.get_github_actions_workflow_runs"),
    ),
    EvalQueryCase(
        "xd-39", "cross_domain", ("postgres", "crm_rest"),
        "Update customer account risk tier after verifying CEBA loan repayment relief eligibility",
        ("postgres.update_account_risk_tier", "crm_rest.verify_ceba_cerb_relief_eligibility"),
    ),
    EvalQueryCase(
        "xd-40", "cross_domain", ("supply_chain", "devops"),
        "Trigger Optuna forecasting cluster retuning and inspect Kubernetes Helm chart replica values",
        ("supply_chain.trigger_optuna_cluster_retuning", "devops.inspect_helm_chart_values"),
    ),
]


FULL_EVAL_DATASET: List[EvalQueryCase] = SINGLE_DOMAIN_EVAL_CASES + CROSS_DOMAIN_EVAL_CASES


def evaluate_recall_at_k(
    router: EnterpriseMCPRouter,
    cases: Sequence[EvalQueryCase] = FULL_EVAL_DATASET,
    k_values: Sequence[int] = (3, 5, 8, 10, 25),
    scoring_mode: str = "hybrid",
    weights: Tuple[float, float, float] = (0.55, 0.35, 0.10),
    auto_widen: bool = False,
) -> Dict[str, Any]:
    """
    Evaluates macro-averaged Recall@k and Hit@k across the labeled dataset,
    reporting overall, single-domain, and cross-domain splits separately.
    """
    max_k = max(k_values)

    def _init_bucket() -> Dict[str, List[float]]:
        return {f"recall@{k}": [] for k in k_values} | {f"hit@{k}": [] for k in k_values}

    buckets: Dict[str, Dict[str, List[float]]] = {
        "overall": _init_bucket(),
        "single_domain": _init_bucket(),
        "cross_domain": _init_bucket(),
    }
    latencies: List[float] = []
    token_reductions: List[float] = []
    widened_count = 0

    for case in cases:
        res = router.route_by_query(
            query=case.query,
            k=max_k,
            scoring_mode=scoring_mode,
            weights=weights,
            auto_widen=False,
        )
        latencies.append(res["routing_latency_ms"])
        ranked_names = [t["name"] for t in res["routed_tools"]]
        expected_set = set(case.expected_tools)

        # Also measure exact k=5 token savings / widen-k behavior when requested
        if 5 in k_values:
            res_k5 = router.route_by_query(
                query=case.query,
                k=5,
                scoring_mode=scoring_mode,
                weights=weights,
                auto_widen=auto_widen,
            )
            token_reductions.append(res_k5["token_reduction_pct"])
            if res_k5.get("widened_k"):
                widened_count += 1
            names_k5_effective = [t["name"] for t in res_k5["routed_tools"]]
        else:
            names_k5_effective = ranked_names[:5]

        for k in k_values:
            top_names = set(names_k5_effective if (k == 5 and auto_widen) else ranked_names[:k])
            matched = len(expected_set & top_names)
            recall = matched / float(len(expected_set))
            hit = 1.0 if matched > 0 else 0.0
            for split_key in ("overall", case.category):
                buckets[split_key][f"recall@{k}"].append(recall)
                buckets[split_key][f"hit@{k}"].append(hit)

    def _summarize(bucket: Dict[str, List[float]], count: int) -> Dict[str, Any]:
        summary: Dict[str, Any] = {"query_count": count}
        for k in k_values:
            r_vals = bucket[f"recall@{k}"]
            h_vals = bucket[f"hit@{k}"]
            summary[f"recall@{k}"] = round(sum(r_vals) / max(1, len(r_vals)), 4)
            summary[f"hit@{k}"] = round(sum(h_vals) / max(1, len(h_vals)), 4)
        return summary

    single_n = sum(1 for c in cases if c.category == "single_domain")
    cross_n = sum(1 for c in cases if c.category == "cross_domain")
    return {
        "scoring_mode": scoring_mode,
        "weights": list(weights),
        "auto_widen": auto_widen,
        "widened_queries_at_k5": widened_count,
        "mean_routing_latency_ms": round(sum(latencies) / max(1, len(latencies)), 3),
        "mean_token_reduction_pct_at_k5": round(sum(token_reductions) / max(1, len(token_reductions)), 2) if token_reductions else 0.0,
        "overall": _summarize(buckets["overall"], len(cases)),
        "single_domain": _summarize(buckets["single_domain"], single_n),
        "cross_domain": _summarize(buckets["cross_domain"], cross_n),
    }


def run_full_routing_benchmark(router: EnterpriseMCPRouter) -> Dict[str, Any]:
    """
    Runs the complete honest Phase 2 benchmark suite:
    - Single-domain vs cross-domain Recall@{3,5,8,10,25}
    - Dense-only vs BM25-only vs Hybrid (0.55/0.35/0.10) vs Tuned Hybrid variants
    - Auto-widen k=5 fallback evaluation
    - Real tokenizer-measured full registry token baseline
    """
    ablation_configs: List[Tuple[str, str, Tuple[float, float, float], bool]] = [
        ("dense_only_hash64", "dense_only", (1.0, 0.0, 0.0), False),
        ("bm25_only", "bm25_only", (0.0, 1.0, 0.0), False),
        ("hybrid_default_55_35_10", "hybrid", (0.55, 0.35, 0.10), False),
        ("hybrid_lexical_heavy_30_60_10", "hybrid", (0.30, 0.60, 0.10), False),
        ("hybrid_balanced_25_65_10", "hybrid", (0.25, 0.65, 0.10), False),
        ("hybrid_widen_k5_fallback", "hybrid", (0.55, 0.35, 0.10), True),
    ]

    ablations: Dict[str, Any] = {}
    for label, mode, w, widen in ablation_configs:
        ablations[label] = evaluate_recall_at_k(
            router=router,
            cases=FULL_EVAL_DATASET,
            k_values=(3, 5, 8, 10, 25),
            scoring_mode=mode,
            weights=w,
            auto_widen=widen,
        )

    total_schema_tokens = sum(t.schema_tokens for t in router.tools.values())
    return {
        "dataset_size": len(FULL_EVAL_DATASET),
        "single_domain_count": len(SINGLE_DOMAIN_EVAL_CASES),
        "cross_domain_count": len(CROSS_DOMAIN_EVAL_CASES),
        "total_registered_tools": len(router.tools),
        "total_serialized_schema_tokens": total_schema_tokens,
        "ablations": ablations,
        "embedding_note": (
            "Dense scorer uses deterministic SHA-256 64-dim signed feature hashing (0 external model weight dependencies). "
            "Ablations quantify the gap vs Okapi BM25 and why production deployments should pair BM25 with a learned bi-encoder."
        ),
    }
