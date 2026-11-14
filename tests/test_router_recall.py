"""
Semantic Routing Recall and False-Positive Resistance Benchmark.
Evaluates semantic routing precision and top-k recall across all 8 enterprise domains:
  1. snowflake
  2. informatica
  3. postgres
  4. devops
  5. supply_chain
  6. crm_rest
  7. knowledge_graph
  8. portfolio_vsm
"""
from src.router import EnterpriseMCPRouter

ROUTER_RECALL_TEST_CASES = [
    # Snowflake
    ("Query Snowflake Cortex Search for Canadian RRSP compliance rules", "snowflake"),
    ("Retrieve historical NAV and AUM for equity funds in PORTFOLIO_GOLD", "snowflake"),
    ("Audit Snowflake virtual warehouse credit burn rate and queue load", "snowflake"),

    # Informatica
    ("Validate Informatica Cloud IICS ELT taskflow SLA and row count lag", "informatica"),
    ("Trigger Informatica IICS mapping synchronization for fund documents", "informatica"),
    ("Check ETL staging pipeline freshness and ingestion webhook", "informatica"),

    # Postgres
    ("Execute outbound institutional bank wire transfer in PostgreSQL ledger", "postgres"),
    ("Create a point-in-time state snapshot of the account ledger", "postgres"),
    ("Query PostgreSQL accounts table for high risk portfolio balances", "postgres"),

    # DevOps
    ("Aggregate Snyk CVE vulnerability alerts across GitHub pull requests", "devops"),
    ("Inspect Argo CD Kubernetes deployment sync status and Docker builds", "devops"),
    ("Create a Jira ticket to patch critical Dependabot CVE alerts", "devops"),

    # Supply Chain
    ("Query Kinaxis Maestro gating supplies and calculate SKU demand forecast", "supply_chain"),
    ("Inspect S&OP replenishment schedule across manufacturing plants", "supply_chain"),
    ("Check Bill of Materials (BOM) inventory shortages for assembly", "supply_chain"),

    # CRM & REST
    ("Dispatch Twilio SMS notification for customer onboarding KYC update", "crm_rest"),
    ("Verify customer AML compliance profile via REST API gateway", "crm_rest"),
    ("Trigger outbound webhook for institutional customer support ticket", "crm_rest"),

    # Knowledge Graph
    ("Execute Neo4j Cypher multihop graph traversal for entity relationships", "knowledge_graph"),
    ("Query Qdrant hybrid vector index for policy chunk reranking", "knowledge_graph"),
    ("Traverse knowledge graph ontology for regulatory compliance", "knowledge_graph"),

    # Value Stream Management (VSM & OKRs)
    ("Detect management concerns across at-risk OKRs and VSM bottlenecks", "portfolio_vsm"),
    ("Compute Value Stream flow efficiency, velocity, and blocked engineering blockers", "portfolio_vsm"),
    ("Reallocate squad capacity across product roadmap epics to protect OKR milestones", "portfolio_vsm"),
]


def test_router_recall_across_all_domains():
    router = EnterpriseMCPRouter.from_enterprise_catalog()

    top1_correct = 0
    top3_correct = 0
    total = len(ROUTER_RECALL_TEST_CASES)

    for query, expected_domain in ROUTER_RECALL_TEST_CASES:
        res = router.route_by_query(query, k=3)
        routed = res["routed_tools"]
        top_domain = routed[0]["domain"]
        top3_domains = [t["domain"] for t in routed[:3]]

        if top_domain == expected_domain:
            top1_correct += 1
        if expected_domain in top3_domains:
            top3_correct += 1

    top1_acc = (top1_correct / total) * 100.0
    top3_acc = (top3_correct / total) * 100.0

    print(f"\n[Semantic Routing Benchmark] Top-1 Recall: {top1_acc:.1f}% ({top1_correct}/{total}) | Top-3 Recall: {top3_acc:.1f}% ({top3_correct}/{total})")

    assert top1_acc >= 90.0, f"Top-1 recall {top1_acc:.1f}% fell below 90%"
    assert top3_acc >= 95.0, f"Top-3 recall {top3_acc:.1f}% fell below 95%"


from src.registry.eval_dataset import FULL_EVAL_DATASET, run_full_routing_benchmark


def test_false_positive_resistance():
    """Verifies that English words containing 2-letter keywords as substrings do not trigger spurious routing."""
    router = EnterpriseMCPRouter.from_enterprise_catalog()

    # 'decision' contains 'ci', 'enterprise' contains 'pr', 'broadcast' contains 'cd'
    res = router.route_by_query("Enterprise executive decision support for fund portfolio rebalancing", k=3)
    routed_domains = [t["domain"] for t in res["routed_tools"]]

    # Primary intent is financial portfolio / funds -> should route to snowflake/postgres, NOT devops
    assert "devops" != routed_domains[0], f"Spurious match: 'decision'/'enterprise' routed to devops: {routed_domains}"


def test_honest_160_query_eval_benchmark_and_ablations():
    """Runs the full 160-query benchmark (120 single-domain + 40 cross-domain) and ablations."""
    router = EnterpriseMCPRouter.from_enterprise_catalog()
    assert len(FULL_EVAL_DATASET) == 160

    report = run_full_routing_benchmark(router)
    assert report["dataset_size"] == 160
    assert report["single_domain_count"] == 120
    assert report["cross_domain_count"] == 40
    assert report["total_registered_tools"] == 120
    assert report["total_serialized_schema_tokens"] > 25000

    abl = report["ablations"]
    assert "dense_only_hash64" in abl
    assert "bm25_only" in abl
    assert "hybrid_default_55_35_10" in abl
    assert "hybrid_balanced_25_65_10" in abl
    assert "hybrid_widen_k5_fallback" in abl

    tuned = abl["hybrid_balanced_25_65_10"]
    assert tuned["overall"]["recall@5"] >= 0.95
    assert tuned["single_domain"]["recall@5"] >= 0.97
    assert tuned["cross_domain"]["recall@5"] >= 0.90
    assert tuned["overall"]["recall@25"] >= 0.99
    assert abl["bm25_only"]["overall"]["recall@5"] > abl["dense_only_hash64"]["overall"]["recall@5"]


def test_role_filtered_routing_and_miss_feedback():
    """Analysts must never see platform_admin tools in routed results; misses queue for eval."""
    router = EnterpriseMCPRouter.from_enterprise_catalog()

    analyst_res = router.route_by_query(
        "Transfer institutional treasury funds via outbound wire and restore database snapshot",
        k=10,
        caller_roles=["analyst"],
    )
    assert all(
        t["required_role"] in ("analyst", "ai_platform_reader")
        for t in analyst_res["routed_tools"]
    )
    assert "postgres.execute_outbound_wire" not in [t["name"] for t in analyst_res["routed_tools"]]
    assert "postgres.restore_state_snapshot" not in [t["name"] for t in analyst_res["routed_tools"]]

    admin_res = router.route_by_query(
        "Transfer institutional treasury funds via outbound wire",
        k=5,
        caller_roles=["platform_admin"],
    )
    assert "postgres.execute_outbound_wire" in [t["name"] for t in admin_res["routed_tools"]]

    miss = router.record_tool_selection_feedback(
        query="Handle suspicious AML activity",
        routed_tools=["snowflake.cortex_search_docs"],
        selected_tool="crm_rest.escalate_aml_suspicious_activity",
    )
    assert miss["hit"] is False
    assert miss["miss_queue_size"] >= 1
