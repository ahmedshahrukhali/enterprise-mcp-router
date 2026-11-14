"""
Embedded Interactive Web Control Plane UI (Tailwind CSS + Chart.js)
for Enterprise-MCP-Router (`projects/enterprise-mcp-router`).
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise-MCP-Router | FastMCP Semantic Gateway & VSM Control Plane</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { background-color: #0b0f19; color: #e2e8f0; font-family: 'Inter', system-ui, sans-serif; }
    .card { background: #111827; border: 1px solid #1f2937; border-radius: 0.75rem; }
    .tab-btn.active { border-bottom: 2px solid #38bdf8; color: #38bdf8; font-weight: 600; }
    .badge { font-size: 0.72rem; padding: 0.15rem 0.5rem; border-radius: 9999px; font-weight: 600; }
    pre { background: #090d16; border: 1px solid #1e293b; border-radius: 0.5rem; padding: 0.75rem; overflow-x: auto; font-size: 0.78rem; }
  </style>
</head>
<body class="min-h-screen flex flex-col">
  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-950/90 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-7xl mx-auto px-6 py-4 flex flex-wrap items-center justify-between gap-4">
      <div>
        <div class="flex items-center gap-3">
          <span class="h-3 w-3 rounded-full bg-emerald-400 animate-pulse"></span>
          <h1 class="text-xl font-bold tracking-tight text-white">Enterprise-MCP-Router <span class="text-sky-400 font-mono text-sm">v2.2.0 (FastMCP / JSON-RPC 2.0 + SSE)</span></h1>
        </div>
        <p class="text-xs text-slate-400 mt-1">
          120-Tool Hybrid BM25 + 64-Dim Dense Router (8 Domains) • Value Stream OKR & Ticket Copilot • JSON Schema + RBAC/HITL • Relational SQLite/Postgres • Claude Sonnet Bedrock
        </p>
      </div>
      <div class="flex items-center gap-3 text-xs">
        <span class="px-3 py-1.5 rounded-md bg-sky-950/80 border border-sky-800 text-sky-300 font-mono">120 Registered MCP Tools (8 Domains)</span>
        <span class="px-3 py-1.5 rounded-md bg-emerald-950/80 border border-emerald-800 text-emerald-300 font-mono">RBAC + SCHEMA + HITL: ENFORCED</span>
        <a href="/docs" class="px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition">OpenAPI /docs ↗</a>
      </div>
    </div>
    <!-- Navigation Tabs -->
    <div class="max-w-7xl mx-auto px-6 flex gap-6 text-sm text-slate-400 overflow-x-auto">
      <button onclick="switchTab('router')" id="tab-router" class="tab-btn active py-2.5 whitespace-nowrap">1. Semantic Tool Router (120 → Top-k)</button>
      <button onclick="switchTab('vsm')" id="tab-vsm" class="tab-btn py-2.5 whitespace-nowrap">2. Value Stream & OKR Copilot (VSM)</button>
      <button onclick="switchTab('governance')" id="tab-governance" class="tab-btn py-2.5 whitespace-nowrap">3. RBAC & HITL Approval Gate</button>
      <button onclick="switchTab('connectors')" id="tab-connectors" class="tab-btn py-2.5 whitespace-nowrap">4. Snowflake, IICS & SQLite/PostgreSQL</button>
      <button onclick="switchTab('bedrock')" id="tab-bedrock" class="tab-btn py-2.5 whitespace-nowrap">5. Bedrock Claude Sonnet & Bridges</button>
      <button onclick="switchTab('telemetry')" id="tab-telemetry" class="tab-btn py-2.5 whitespace-nowrap">6. OpenTelemetry & L2 Runbooks</button>
    </div>
  </header>

  <main class="max-w-7xl mx-auto w-full px-6 py-6 flex-1 space-y-6">
    <!-- TAB 1: SEMANTIC ROUTER -->
    <section id="panel-router" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="card p-5 lg:col-span-2 space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-semibold text-white">64-Dim Dense + Okapi BM25 + RRF Hybrid MCP Router</h2>
            <span class="badge bg-sky-950 text-sky-300 border border-sky-800">Okapi BM25 + 64d RRF</span>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div class="md:col-span-3">
              <label class="text-xs text-slate-400 block mb-1">Agent Natural Language Intent / Turn Prompt</label>
              <input id="route-query" type="text" value="Identify management concerns across at-risk OKRs, product portfolios, and blocked engineering work tickets"
                class="w-full px-3 py-2 rounded bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-sky-500" />
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">Top-k Tools</label>
              <select id="route-topk" class="w-full px-3 py-2 rounded bg-slate-900 border border-slate-700 text-sm text-white">
                <option value="3">Top 3 Tools</option>
                <option value="5" selected>Top 5 Tools</option>
                <option value="8">Top 8 Tools</option>
                <option value="10">Top 10 Tools</option>
              </select>
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <button onclick="runSemanticRoute()" class="px-4 py-2 rounded bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold transition">Route Top-k MCP Tools</button>
            <button onclick="setPresetQuery('Identify management concerns across at-risk OKRs, product portfolios, and blocked engineering work tickets')" class="px-3 py-1.5 rounded bg-violet-950/90 hover:bg-violet-900 border border-violet-800 text-xs text-violet-200">Preset: Value Stream (OKRs, Portfolios & Tickets)</button>
            <button onclick="setPresetQuery('Query Snowflake Cortex Search for Fidelity RRSP compliance rules and check fund NAV in Gold schema')" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300">Preset: Snowflake Cortex</button>
            <button onclick="setPresetQuery('Validate Informatica Cloud IICS ELT taskflow SLA and staging row counts before RAG sync')" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300">Preset: Informatica IICS ELT</button>
            <button onclick="setPresetQuery('Execute outbound wire transfer in PostgreSQL treasury ledger and create state snapshot')" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300">Preset: PostgreSQL Ledger & Wire</button>
            <button onclick="setPresetQuery('Aggregate Snyk CVE vulnerabilities across GitHub repos and open automated Docker tested PR')" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300">Preset: DevSecOps CVE Agent</button>
          </div>
          <div id="routed-tools-list" class="space-y-2 pt-2"></div>
        </div>

        <div class="card p-5 space-y-4">
          <h2 class="text-base font-semibold text-white">Context-Window Bloat Reduction</h2>
          <div class="grid grid-cols-2 gap-3 text-center">
            <div class="p-3 rounded bg-slate-900/90 border border-slate-800">
              <div class="text-xs text-slate-400">Full 120-Tool Registry</div>
              <div id="metric-full-tokens" class="text-lg font-bold text-rose-400 font-mono">18,600 tok</div>
            </div>
            <div class="p-3 rounded bg-slate-900/90 border border-slate-800">
              <div class="text-xs text-slate-400">Routed Top-k Schemas</div>
              <div id="metric-routed-tokens" class="text-lg font-bold text-emerald-400 font-mono">780 tok</div>
            </div>
            <div class="p-3 rounded bg-slate-900/90 border border-slate-800">
              <div class="text-xs text-slate-400">Token Savings</div>
              <div id="metric-reduction-pct" class="text-lg font-bold text-sky-400 font-mono">95.8%</div>
            </div>
            <div class="p-3 rounded bg-slate-900/90 border border-slate-800">
              <div class="text-xs text-slate-400">Measured Latency</div>
              <div id="metric-route-latency" class="text-lg font-bold text-amber-300 font-mono">0.85 ms</div>
            </div>
          </div>
          <canvas id="tokenChart" height="190"></canvas>
        </div>
      </div>
    </section>

    <!-- TAB 2: VALUE STREAM & OKR COPILOT (VSM) -->
    <section id="panel-vsm" class="hidden space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="card p-5 lg:col-span-2 space-y-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 class="text-base font-semibold text-white">Value Stream Management — Management Concern Advisor</h2>
              <p class="text-xs text-slate-400">Joins Product Portfolios, OKRs, and Engineering Work Tickets in SQLite3 and synthesizes governed actions via Claude Sonnet.</p>
            </div>
            <button onclick="runVsmConcernAnalysis()" class="px-4 py-2 rounded bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition">
              Identify Management Concerns & Suggest Actions (Claude Sonnet)
            </button>
          </div>
          <div id="vsm-kpis" class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center"></div>
          <div id="vsm-concerns-list" class="space-y-3"></div>
        </div>

        <div class="card p-5 space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-semibold text-white">Relational VSM SQL Explorer</h2>
            <span class="badge bg-emerald-950 text-emerald-300">SQLite3 Read-Only</span>
          </div>
          <textarea id="vsm-sql" rows="5" class="w-full p-2.5 rounded bg-slate-900 border border-slate-700 text-xs font-mono text-white">SELECT p.portfolio_id, p.name, o.okr_id, o.status, COUNT(t.ticket_id) AS blocked_tickets FROM product_portfolios p JOIN objectives_okrs o ON p.portfolio_id = o.portfolio_id LEFT JOIN engineering_tickets t ON o.okr_id = t.okr_id AND t.status = 'BLOCKED' GROUP BY p.portfolio_id, o.okr_id ORDER BY blocked_tickets DESC</textarea>
          <button onclick="runVsmSql()" class="px-3 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-xs text-white font-semibold">Execute Relational JOIN Query</button>
          <pre id="vsm-sql-output">// Relational VSM JOIN query results will appear here...</pre>
        </div>
      </div>

      <div class="card p-5 space-y-3">
        <h3 class="text-sm font-semibold text-white">Connected Portfolios, OKRs & Engineering Tickets</h3>
        <div id="vsm-overview-tables" class="grid grid-cols-1 lg:grid-cols-3 gap-4 text-xs"></div>
      </div>
    </section>

    <!-- TAB 3: RBAC & HITL GOVERNANCE -->
    <section id="panel-governance" class="hidden space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="card p-5 space-y-4">
          <h2 class="text-base font-semibold text-white">Deterministic OAuth2 RBAC, Schema Contract & HITL Gate Simulator</h2>
          <div class="space-y-3">
            <div>
              <label class="text-xs text-slate-400 block mb-1">Target MCP Tool</label>
              <select id="gov-tool" class="w-full px-3 py-2 rounded bg-slate-900 border border-slate-700 text-sm text-white">
                <option value="postgres.execute_outbound_wire">postgres.execute_outbound_wire (Mutating | Role: platform_admin)</option>
                <option value="portfolio_vsm.reallocate_portfolio_capacity">portfolio_vsm.reallocate_portfolio_capacity (Mutating | Role: platform_admin)</option>
                <option value="portfolio_vsm.escalate_blocked_work_ticket">portfolio_vsm.escalate_blocked_work_ticket (Mutating | Role: data_engineer)</option>
                <option value="snowflake.cortex_search_docs">snowflake.cortex_search_docs (Read-Only | Role: ai_platform_reader)</option>
                <option value="informatica.retrigger_failed_taskflow">informatica.retrigger_failed_taskflow (Mutating | Role: data_engineer)</option>
                <option value="devops.trigger_argocd_rollout">devops.trigger_argocd_rollout (Mutating | Role: platform_admin)</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">Caller OAuth2 Role Scope</label>
              <select id="gov-role" class="w-full px-3 py-2 rounded bg-slate-900 border border-slate-700 text-sm text-white">
                <option value="analyst">analyst</option>
                <option value="ai_platform_reader">ai_platform_reader</option>
                <option value="data_engineer">data_engineer</option>
                <option value="platform_admin" selected>platform_admin</option>
              </select>
            </div>
            <div class="flex items-center gap-2">
              <input id="gov-hitl" type="checkbox" class="rounded bg-slate-900 border-slate-700" />
              <label for="gov-hitl" class="text-xs text-slate-300">Include Verified Human-in-the-Loop (HITL) Approval Token</label>
            </div>
            <div class="flex flex-wrap gap-3">
              <button onclick="runAuthorizeCheck()" class="px-4 py-2 rounded bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold">Evaluate Authorization Gate</button>
              <button onclick="createHitlTicket()" class="px-4 py-2 rounded bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold">Queue HITL Interrupt Ticket</button>
              <button onclick="validateSchemaSample()" class="px-4 py-2 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold">Validate JSON Schema Contract</button>
            </div>
          </div>
          <pre id="gov-output">// Authorization decision, schema validation & audit trace will appear here...</pre>
        </div>

        <div class="card p-5 space-y-4">
          <h2 class="text-base font-semibold text-white">Active Human-in-the-Loop (HITL) Interrupt Queue</h2>
          <p class="text-xs text-slate-400">Mutating MCP calls pause execution and emit an interrupt ticket until approved by an authorized operator.</p>
          <div id="hitl-queue-list" class="space-y-3"></div>
        </div>
      </div>
    </section>

    <!-- TAB 4: SNOWFLAKE CORTEX, INFORMATICA IICS & SQLITE/POSTGRES -->
    <section id="panel-connectors" class="hidden space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Snowflake -->
        <div class="card p-5 space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold text-white">Snowflake Read-Only SQL Guard & Cortex Search</h3>
            <span class="badge bg-sky-950 text-sky-300">Literal-Safe Guard</span>
          </div>
          <textarea id="sf-sql" rows="3" class="w-full p-2 rounded bg-slate-900 border border-slate-700 text-xs font-mono text-white">SELECT fund_id, nav, aum_cad_m FROM PORTFOLIO_GOLD.FUNDS WHERE active = 1</textarea>
          <div class="flex flex-wrap gap-2">
            <button onclick="validateSnowflakeSQL()" class="px-3 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-xs text-white font-semibold">Validate SQL</button>
            <button onclick="document.getElementById('sf-sql').value='SELECT * FROM PORTFOLIO_GOLD.FUNDS; DROP TABLE FUNDS'; validateSnowflakeSQL();" class="px-3 py-1.5 rounded bg-rose-900/80 hover:bg-rose-800 text-xs text-rose-200">Test DDL Injection</button>
          </div>
          <pre id="sf-output">// Snowflake validation output...</pre>
        </div>

        <!-- Informatica IICS -->
        <div class="card p-5 space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold text-white">Informatica Cloud (IICS) ELT SLA Validator</h3>
            <span class="badge bg-indigo-950 text-indigo-300">Pre-RAG Gate</span>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div>
              <label class="text-slate-400">Taskflow Status</label>
              <select id="iics-status" class="w-full p-1.5 rounded bg-slate-900 border border-slate-700 text-white">
                <option value="SUCCESS">SUCCESS</option>
                <option value="FAILED">FAILED</option>
              </select>
            </div>
            <div>
              <label class="text-slate-400">Freshness Lag (min)</label>
              <input id="iics-lag" type="number" value="8" class="w-full p-1.5 rounded bg-slate-900 border border-slate-700 text-white" />
            </div>
          </div>
          <button onclick="validateIICS()" class="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold">Validate IICS ELT Webhook</button>
          <pre id="iics-output">// Informatica Cloud (IICS) validation output...</pre>
        </div>

        <!-- PostgreSQL / SQLite3 Snapshot -->
        <div class="card p-5 space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold text-white">Relational Ledger (SQLite3/Postgres) & Snapshots</h3>
            <span class="badge bg-emerald-950 text-emerald-300">Real SQL + Authorizer</span>
          </div>
          <div class="flex flex-wrap gap-2">
            <button onclick="queryPostgres('SELECT account_id, portfolio_name, balance_usd, risk_tier FROM accounts ORDER BY balance_usd DESC')" class="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-xs text-white font-semibold">Query Accounts</button>
            <button onclick="queryPostgres('SELECT risk_tier, COUNT(*) AS accounts, SUM(balance_usd) AS total_usd FROM accounts GROUP BY risk_tier')" class="px-3 py-1.5 rounded bg-sky-700 hover:bg-sky-600 text-xs text-white font-semibold">GROUP BY Risk Tier</button>
            <button onclick="snapshotPostgres('create')" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200">Create Snapshot</button>
            <button onclick="snapshotPostgres('restore')" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200">Restore Baseline</button>
          </div>
          <pre id="pg-output">// Relational SQL ledger & snapshot output...</pre>
        </div>
      </div>
    </section>

    <!-- TAB 5: BEDROCK AGENTCORE & BRIDGES -->
    <section id="panel-bedrock" class="hidden space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="card p-5 space-y-4">
          <h2 class="text-base font-semibold text-white">Amazon Bedrock / AgentCore Structured Output & Self-Healing Retry</h2>
          <p class="text-xs text-slate-400">Invokes <code class="text-sky-400">anthropic.claude-sonnet-4-20250514</code> (Converse API) with deterministic schema key verification and automated self-healing retry when attempt #1 omits a required field.</p>
          <button onclick="runBedrockInvoke()" class="px-4 py-2 rounded bg-sky-600 hover:bg-sky-500 text-xs text-white font-semibold">Invoke Bedrock Structured Output (With Retry Simulation)</button>
          <pre id="bedrock-output">// Bedrock Converse API & structured schema verification trace...</pre>
        </div>
        <div class="card p-5 space-y-4">
          <h2 class="text-base font-semibold text-white">Multi-Framework Agent Tool Bridges</h2>
          <div class="flex gap-2">
            <button onclick="loadBridge('langgraph')" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-sky-300 font-mono">LangGraph ToolNode</button>
            <button onclick="loadBridge('smolagents')" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-amber-300 font-mono">HF smolagents CodeAgent</button>
            <button onclick="loadBridge('crewai')" class="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-emerald-300 font-mono">CrewAI StructuredTool</button>
          </div>
          <pre id="bridge-output">// Select an agent framework bridge above...</pre>
        </div>
      </div>
    </section>

    <!-- TAB 6: OPENTELEMETRY & RUNBOOKS -->
    <section id="panel-telemetry" class="hidden space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="card p-5 space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-semibold text-white">OpenTelemetry Trace Spans & Token Budget Governance</h2>
            <button onclick="recordSampleSpan()" class="px-3 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-xs text-white font-semibold">+ Emit Trace Span</button>
          </div>
          <pre id="telemetry-output">// Loading OpenTelemetry metrics...</pre>
        </div>
        <div class="card p-5 space-y-4">
          <h2 class="text-base font-semibold text-white">Standardized L2 Operational Support Runbook Generator</h2>
          <div class="flex gap-2">
            <select id="runbook-type" class="flex-1 px-3 py-2 rounded bg-slate-900 border border-slate-700 text-xs text-white">
              <option value="iics_taskflow_failed">iics_taskflow_failed (SEV-2 ELT SLA Breach)</option>
              <option value="snowflake_query_timeout">snowflake_query_timeout (SEV-2 Warehouse / Cortex)</option>
              <option value="bedrock_throttling_or_schema_error">bedrock_throttling_or_schema_error (SEV-2 Model / Schema)</option>
              <option value="hitl_approval_timeout">hitl_approval_timeout (SEV-3 Governance Gate)</option>
              <option value="postgres_connection_pool_exhausted">postgres_connection_pool_exhausted (SEV-1 DB Pool)</option>
              <option value="rbac_privilege_escalation_attempt">rbac_privilege_escalation_attempt (SEV-1 Security)</option>
            </select>
            <button onclick="lookupRunbook()" class="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-xs text-white font-semibold">Generate Runbook</button>
          </div>
          <pre id="runbook-output">// Select an incident class to generate L2 triage steps...</pre>
        </div>
      </div>
    </section>
  </main>

  <script>
    let tokenChartInstance = null;

    function switchTab(tab) {
      ['router', 'vsm', 'governance', 'connectors', 'bedrock', 'telemetry'].forEach(t => {
        document.getElementById('panel-' + t).classList.toggle('hidden', t !== tab);
        document.getElementById('tab-' + t).classList.toggle('active', t === tab);
      });
      if (tab === 'vsm') { refreshVsmOverview(); runVsmConcernAnalysis(); runVsmSql(); }
      if (tab === 'governance') refreshHitlQueue();
      if (tab === 'bedrock') loadBridge('langgraph');
      if (tab === 'telemetry') { refreshTelemetry(); lookupRunbook(); }
    }

    function setPresetQuery(q) {
      document.getElementById('route-query').value = q;
      runSemanticRoute();
    }

    async function runSemanticRoute() {
      const query = document.getElementById('route-query').value;
      const top_k = parseInt(document.getElementById('route-topk').value, 10);
      const res = await fetch('/api/v1/router/search', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ query, top_k })
      });
      const data = await res.json();
      document.getElementById('metric-full-tokens').textContent = data.full_registry_tokens.toLocaleString() + ' tok';
      document.getElementById('metric-routed-tokens').textContent = data.routed_tokens.toLocaleString() + ' tok';
      document.getElementById('metric-reduction-pct').textContent = data.token_reduction_pct + '%';
      document.getElementById('metric-route-latency').textContent = data.routing_latency_ms + ' ms';

      const container = document.getElementById('routed-tools-list');
      container.innerHTML = data.routed_tools.map((t, idx) => `
        <div class="p-3 rounded bg-slate-900/90 border border-slate-800 flex items-start justify-between gap-4">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-xs font-mono text-sky-400 font-bold">#${idx + 1} ${t.name}</span>
              <span class="badge bg-slate-800 text-slate-300">${t.domain}</span>
              <span class="badge ${t.is_mutating ? 'bg-amber-950 text-amber-300 border border-amber-800' : 'bg-emerald-950 text-emerald-300 border border-emerald-800'}">
                ${t.is_mutating ? 'MUTATING (HITL Gate)' : 'READ-ONLY'}
              </span>
              <span class="badge bg-indigo-950 text-indigo-300">role: ${t.required_role}</span>
            </div>
            <p class="text-xs text-slate-400 mt-1">${t.description}</p>
          </div>
          <div class="text-right font-mono shrink-0">
            <div class="text-xs text-emerald-400 font-bold">fused: ${t.similarity_score}</div>
            <div class="text-[11px] text-sky-300">dense: ${t.dense_score ?? '-'} | bm25: ${t.bm25_score ?? '-'}</div>
            <div class="text-[11px] text-slate-500">${t.schema_tokens} tok</div>
          </div>
        </div>
      `).join('');

      const ctx = document.getElementById('tokenChart').getContext('2d');
      if (tokenChartInstance) tokenChartInstance.destroy();
      tokenChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['All 120 MCP Tools', `Routed Top-${top_k} Tools`],
          datasets: [{
            label: 'Prompt Context Schema Tokens',
            data: [data.full_registry_tokens, data.routed_tokens],
            backgroundColor: ['#f43f5e', '#10b981'],
            borderRadius: 6
          }]
        },
        options: {
          plugins: { legend: { display: false } },
          scales: {
            y: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' } },
            x: { ticks: { color: '#94a3b8' }, grid: { display: false } }
          }
        }
      });
    }

    async function refreshVsmOverview() {
      const res = await fetch('/api/v1/vsm/overview');
      const data = await res.json();
      const s = data.summary;
      document.getElementById('vsm-kpis').innerHTML = `
        <div class="p-3 rounded bg-slate-900 border border-slate-800">
          <div class="text-[11px] text-slate-400">Portfolios At Risk</div>
          <div class="text-base font-bold text-amber-400 font-mono">${s.at_risk_portfolios} / ${s.total_portfolios}</div>
        </div>
        <div class="p-3 rounded bg-slate-900 border border-slate-800">
          <div class="text-[11px] text-slate-400">OKRs At/Off Track</div>
          <div class="text-base font-bold text-rose-400 font-mono">${s.at_risk_okrs} / ${s.total_okrs}</div>
        </div>
        <div class="p-3 rounded bg-slate-900 border border-slate-800">
          <div class="text-[11px] text-slate-400">Blocked Work Tickets</div>
          <div class="text-base font-bold text-rose-400 font-mono">${s.blocked_tickets_count}</div>
        </div>
        <div class="p-3 rounded bg-slate-900 border border-slate-800">
          <div class="text-[11px] text-slate-400">Avg Flow Efficiency</div>
          <div class="text-base font-bold text-sky-400 font-mono">${s.avg_flow_efficiency_pct}%</div>
        </div>
      `;

      document.getElementById('vsm-overview-tables').innerHTML = `
        <div class="space-y-2">
          <div class="font-semibold text-sky-300">Product Portfolios</div>
          ${data.product_portfolios.map(p => `
            <div class="p-2.5 rounded bg-slate-900 border border-slate-800">
              <div class="flex justify-between font-mono text-[11px]">
                <span class="text-white font-bold">${p.portfolio_id} • ${p.name}</span>
                <span class="${p.health_status === 'ON_TRACK' ? 'text-emerald-400' : 'text-amber-400'}">${p.health_status}</span>
              </div>
              <div class="text-slate-400 mt-1">Cap: ${p.capacity_utilization_pct}% | Flow Eff: ${p.flow_efficiency_pct}% | Cycle: ${p.cycle_time_days}d</div>
            </div>
          `).join('')}
        </div>
        <div class="space-y-2">
          <div class="font-semibold text-violet-300">Objectives & Key Results (OKRs)</div>
          ${data.objectives_okrs.map(o => `
            <div class="p-2.5 rounded bg-slate-900 border border-slate-800">
              <div class="flex justify-between font-mono text-[11px]">
                <span class="text-white font-bold">${o.okr_id} (${o.portfolio_id})</span>
                <span class="${o.status === 'ON_TRACK' ? 'text-emerald-400' : 'text-rose-400'}">${o.status}</span>
              </div>
              <div class="text-slate-300 mt-1">${o.objective}</div>
              <div class="text-slate-500 mt-0.5">Progress: ${o.progress_pct}% / ${o.target_pct}% | Conf: ${o.confidence_score}</div>
            </div>
          `).join('')}
        </div>
        <div class="space-y-2">
          <div class="font-semibold text-rose-300">Engineering Work Tickets</div>
          ${data.engineering_tickets.map(t => `
            <div class="p-2.5 rounded bg-slate-900 border border-slate-800">
              <div class="flex justify-between font-mono text-[11px]">
                <span class="text-white font-bold">${t.ticket_id} (${t.okr_id})</span>
                <span class="${t.status === 'BLOCKED' ? 'text-rose-400' : 'text-emerald-400'}">${t.status}${t.blocked_days > 0 ? ' (' + t.blocked_days + 'd)' : ''}</span>
              </div>
              <div class="text-slate-300 mt-1">${t.title}</div>
              ${t.blocker_reason ? `<div class="text-amber-300/90 mt-0.5">Blocker: ${t.blocker_reason}</div>` : ''}
            </div>
          `).join('')}
        </div>
      `;
    }

    async function runVsmConcernAnalysis() {
      const res = await fetch('/api/v1/vsm/analyze-concerns', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          query: 'Identify management concerns across OKRs, product portfolios, and blocked engineering tickets and suggest actions'
        })
      });
      const data = await res.json();
      const box = document.getElementById('vsm-concerns-list');
      box.innerHTML = `
        <div class="p-3 rounded bg-violet-950/40 border border-violet-800/70 text-xs text-violet-100">
          <span class="font-bold">Claude Sonnet Summary (${data.risk_tier}):</span> ${data.executive_summary}
        </div>
      ` + data.concerns.map(c => `
        <div class="p-3 rounded bg-slate-900 border border-slate-800 space-y-2">
          <div class="flex items-center justify-between gap-2">
            <span class="font-mono text-xs text-white font-bold">${c.concern_id} • ${c.portfolio_id} (${c.affected_okr_id})</span>
            <span class="badge ${c.severity === 'CRITICAL' ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-amber-950 text-amber-300 border border-amber-800'}">${c.severity}</span>
          </div>
          <p class="text-xs text-slate-300">${c.management_concern}</p>
          <p class="text-xs text-emerald-300"><strong>Suggested Action:</strong> ${c.suggested_action}</p>
          <div class="flex flex-wrap items-center justify-between gap-2 pt-1">
            <code class="text-[11px] text-sky-300">${c.recommended_mcp_tool}(${JSON.stringify(c.tool_arguments)})</code>
            <button onclick='queueRecommendedAction(${JSON.stringify(c.recommended_mcp_tool)}, ${JSON.stringify(c.tool_arguments)}, ${JSON.stringify(c.suggested_action)})'
              class="px-3 py-1 rounded bg-amber-600 hover:bg-amber-500 text-xs text-white font-semibold">
              Queue Action in HITL Gate
            </button>
          </div>
        </div>
      `).join('');
    }

    async function queueRecommendedAction(tool_name, args, justification) {
      const res = await fetch('/api/v1/governance/hitl/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          tool_name,
          requested_by: 'vsm_copilot_claude_sonnet',
          user_roles: ['platform_admin', 'data_engineer'],
          arguments: args,
          justification
        })
      });
      const ticket = await res.json();
      alert('Queued HITL Approval Ticket: ' + ticket.ticket_id + ' for ' + tool_name);
    }

    async function runVsmSql() {
      const sql = document.getElementById('vsm-sql').value;
      const res = await fetch('/api/v1/vsm/query', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ sql, role: 'analyst' })
      });
      document.getElementById('vsm-sql-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function runAuthorizeCheck() {
      const tool_name = document.getElementById('gov-tool').value;
      const role = document.getElementById('gov-role').value;
      const hitl_approved = document.getElementById('gov-hitl').checked;
      const res = await fetch('/api/v1/governance/authorize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ tool_name, user_roles: [role], hitl_approved })
      });
      const data = await res.json();
      document.getElementById('gov-output').textContent = JSON.stringify(data, null, 2);
    }

    async function validateSchemaSample() {
      const tool_name = document.getElementById('gov-tool').value;
      const sampleArgs = tool_name === 'postgres.execute_outbound_wire'
        ? { from_account: 'ACC-9001', to_account: 'ACC-9003', amount_usd: 25000.0, environment: 'prod' }
        : { query_or_id: 'PF-101', portfolio_id: 'PF-101', ticket_id: 'ENG-401', delta_fte: 1.5 };
      const res = await fetch('/api/v1/governance/validate-schema', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ tool_name, arguments: sampleArgs })
      });
      document.getElementById('gov-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function createHitlTicket() {
      const tool_name = document.getElementById('gov-tool').value;
      const role = document.getElementById('gov-role').value;
      const res = await fetch('/api/v1/governance/hitl/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          tool_name,
          requested_by: 'langgraph_prod_agent',
          user_roles: [role],
          arguments: { from_account: 'ACC-9001', to_account: 'ACC-9003', amount_usd: 25000 }
        })
      });
      const data = await res.json();
      document.getElementById('gov-output').textContent = JSON.stringify(data, null, 2);
      refreshHitlQueue();
    }

    async function resolveHitl(ticket_id, decision) {
      await fetch('/api/v1/governance/hitl/resolve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ticket_id, reviewer: 'sr_ops_approver@enterprise.io', decision })
      });
      refreshHitlQueue();
    }

    async function refreshHitlQueue() {
      const res = await fetch('/api/v1/governance/hitl');
      const data = await res.json();
      const box = document.getElementById('hitl-queue-list');
      if (!data.tickets || data.tickets.length === 0) {
        box.innerHTML = '<div class="text-xs text-slate-500">No HITL tickets queued yet. Click "Queue HITL Interrupt Ticket" on the left.</div>';
        return;
      }
      box.innerHTML = data.tickets.map(t => `
        <div class="p-3 rounded bg-slate-900 border border-slate-800 space-y-2">
          <div class="flex items-center justify-between">
            <span class="font-mono text-xs text-amber-300 font-bold">${t.ticket_id} • ${t.tool_name}</span>
            <span class="badge ${t.status === 'APPROVED' ? 'bg-emerald-950 text-emerald-300' : (t.status === 'REJECTED' ? 'bg-rose-950 text-rose-300' : 'bg-amber-950 text-amber-300')}">${t.status}</span>
          </div>
          <div class="text-xs text-slate-400">Requested by: <code class="text-slate-200">${t.requested_by}</code> | Role: <code class="text-slate-200">${t.required_role}</code></div>
          ${t.status === 'PENDING_APPROVAL' ? `
            <div class="flex gap-2 pt-1">
              <button onclick="resolveHitl('${t.ticket_id}', 'APPROVED')" class="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-xs text-white font-semibold">Approve Execution</button>
              <button onclick="resolveHitl('${t.ticket_id}', 'REJECTED')" class="px-2.5 py-1 rounded bg-rose-700 hover:bg-rose-600 text-xs text-white font-semibold">Reject</button>
            </div>
          ` : `<div class="text-[11px] text-slate-500">Reviewed by ${t.reviewer} at ${t.resolved_at}</div>`}
        </div>
      `).join('');
    }

    async function validateSnowflakeSQL() {
      const sql = document.getElementById('sf-sql').value;
      const res = await fetch('/api/v1/connectors/snowflake/validate-sql', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ sql, role: 'ai_platform_reader', schema_name: 'PORTFOLIO_GOLD' })
      });
      document.getElementById('sf-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function validateIICS() {
      const status = document.getElementById('iics-status').value;
      const freshness_lag_minutes = parseInt(document.getElementById('iics-lag').value, 10);
      const res = await fetch('/api/v1/connectors/informatica/validate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ taskflow_name: 'tf_snowflake_fund_docs_elt', status, rows_processed: status === 'SUCCESS' ? 1450 : 0, freshness_lag_minutes })
      });
      document.getElementById('iics-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function queryPostgres(customSql) {
      const sql = customSql || 'SELECT account_id, portfolio_name, balance_usd, risk_tier FROM accounts ORDER BY balance_usd DESC';
      const res = await fetch('/api/v1/connectors/postgres/query', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ sql, role: 'analyst' })
      });
      document.getElementById('pg-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function snapshotPostgres(action) {
      const endpoint = action === 'create' ? '/api/v1/connectors/postgres/snapshot/create' : '/api/v1/connectors/postgres/snapshot/restore';
      const name = action === 'create' ? 'pre_agent_mutation_snap_01' : 'baseline_boot_snapshot';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ snapshot_name: name })
      });
      document.getElementById('pg-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function runBedrockInvoke() {
      const res = await fetch('/api/v1/adapters/bedrock/invoke', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          prompt: 'Analyze portfolio compliance for Fund POL-101 and output structured risk assessment.',
          required_keys: ['summary', 'risk_tier', 'recommended_action', 'confidence_score'],
          simulate_flaky_first_attempt: true
        })
      });
      document.getElementById('bedrock-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function loadBridge(framework) {
      const res = await fetch('/api/v1/adapters/bridges/' + framework);
      document.getElementById('bridge-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function refreshTelemetry() {
      const res = await fetch('/api/v1/telemetry/summary');
      document.getElementById('telemetry-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function recordSampleSpan() {
      await fetch('/api/v1/telemetry/span', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          span_name: 'mcp.tool.snowflake_cortex_search',
          use_case: 'advisor_rag_assistant',
          latency_ms: Math.round(95 + Math.random() * 120),
          status: 'OK',
          prompt_tokens: 540,
          completion_tokens: 190
        })
      });
      refreshTelemetry();
    }

    async function lookupRunbook() {
      const incident_type = document.getElementById('runbook-type').value;
      const res = await fetch('/api/v1/telemetry/runbook', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ incident_type, component: 'Enterprise_MCP_Gateway' })
      });
      document.getElementById('runbook-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    window.addEventListener('DOMContentLoaded', () => {
      runSemanticRoute();
      validateSnowflakeSQL();
      validateIICS();
      queryPostgres();
    });
  </script>
</body>
</html>
"""
