"""
Interactive Enterprise Web Control Plane UI for Enterprise-MCP-Router.
Clean, high-contrast Executive Light Mode single-file HTML/CSS/JS workspace featuring:
1. Verified HS256 JWT Session Persona Switcher (Analyst -> Data Engineer -> Platform Admin -> Super Admin)
2. Hybrid BM25 + Dense Semantic Router + 160-Query Honest Benchmark & Ablation Explorer
3. Value Stream Management (OKRs, Portfolios, Engineering Tickets & Concern Advisor)
4. Zero-Trust RBAC, Ticket-Bound HITL + Canonical Argument Hash Gate & SHA-256 Audit Chain Verifier
5. sqlglot AST SQL Guard, Snowflake Cortex, IICS Circuit-Breaker & SQLite/PostgreSQL Snapshots
6. FastMCP JSON-RPC 2.0 Pagination/Dispatch, Bedrock AgentCore & OpenTelemetry Observability
"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise-MCP-Router | Governed AI Tool Control Plane</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: #f8fafc;
      color: #0f172a;
    }
    .font-mono {
      font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
    }
    .surface-card {
      background-color: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 0.75rem;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    .code-well {
      background-color: #f8fafc;
      border: 1px solid #cbd5e1;
      color: #0f172a;
      border-radius: 0.5rem;
    }
    .input-light {
      background-color: #ffffff;
      border: 1px solid #cbd5e1;
      color: #0f172a;
      border-radius: 0.5rem;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .input-light:focus {
      outline: none;
      border-color: #4f46e5;
      box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
    }
    .tab-btn {
      color: #475569;
      background-color: transparent;
      border: 1px solid transparent;
    }
    .tab-btn:hover {
      color: #0f172a;
      background-color: #f1f5f9;
    }
    .tab-btn.active {
      background-color: #eef2ff;
      color: #3730a3;
      border-color: #c7d2fe;
      font-weight: 600;
    }
    .badge-light-indigo {
      background-color: #eef2ff;
      color: #3730a3;
      border: 1px solid #c7d2fe;
    }
    .badge-light-emerald {
      background-color: #ecfdf5;
      color: #065f46;
      border: 1px solid #a7f3d0;
    }
    .badge-light-amber {
      background-color: #fffbeb;
      color: #92400e;
      border: 1px solid #fde68a;
    }
    .badge-light-red {
      background-color: #fef2f2;
      color: #991b1b;
      border: 1px solid #fecaca;
    }
    .badge-light-slate {
      background-color: #f1f5f9;
      color: #334155;
      border: 1px solid #cbd5e1;
    }
  </style>
</head>
<body class="min-h-screen flex flex-col bg-slate-50 text-slate-900">

  <!-- Top Navigation Bar -->
  <header class="bg-white border-b border-slate-200 sticky top-0 z-40">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-sm">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-base sm:text-lg font-bold tracking-tight text-slate-900">Enterprise-MCP-Router</h1>
            <span class="px-2 py-0.5 text-[11px] font-semibold rounded-full badge-light-indigo">v2.3.0 Hardened</span>
          </div>
          <p class="text-xs text-slate-500">Zero-Trust MCP Control Plane · SQL AST Guard · Hybrid Tool Router · VSM Copilot</p>
        </div>
      </div>

      <!-- Verified JWT Session Switcher + System Status -->
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5">
          <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">JWT Session:</span>
          <select id="session-role-select" onchange="switchSessionPersona()" class="text-xs font-semibold text-indigo-700 bg-transparent focus:outline-none cursor-pointer">
            <option value="analyst">analyst (Read-Only)</option>
            <option value="data_engineer">data_engineer</option>
            <option value="compliance_officer">compliance_officer</option>
            <option value="platform_admin" selected>platform_admin</option>
            <option value="super_admin">super_admin</option>
          </select>
          <span id="jwt-status-pill" class="text-[11px] font-mono px-2 py-0.5 rounded badge-light-slate">issuing...</span>
        </div>

        <div class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg badge-light-emerald text-xs font-medium">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span id="health-status-label">120 Tools · Active</span>
        </div>

        <a href="/docs" target="_blank" class="px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 border border-slate-300 transition shadow-xs">
          Swagger /docs ↗
        </a>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-2.5 flex gap-1.5 overflow-x-auto">
      <button onclick="switchTab('router')" id="btn-router" class="tab-btn active px-3.5 py-1.5 rounded-lg text-xs sm:text-sm whitespace-nowrap transition">
        1. Semantic Router &amp; Eval
      </button>
      <button onclick="switchTab('vsm')" id="btn-vsm" class="tab-btn px-3.5 py-1.5 rounded-lg text-xs sm:text-sm whitespace-nowrap transition">
        2. Value Stream &amp; OKRs
      </button>
      <button onclick="switchTab('governance')" id="btn-governance" class="tab-btn px-3.5 py-1.5 rounded-lg text-xs sm:text-sm whitespace-nowrap transition">
        3. RBAC, Ticket HITL &amp; Audit
      </button>
      <button onclick="switchTab('connectors')" id="btn-connectors" class="tab-btn px-3.5 py-1.5 rounded-lg text-xs sm:text-sm whitespace-nowrap transition">
        4. SQL AST Guard &amp; Connectors
      </button>
      <button onclick="switchTab('mcp')" id="btn-mcp" class="tab-btn px-3.5 py-1.5 rounded-lg text-xs sm:text-sm whitespace-nowrap transition">
        5. MCP JSON-RPC &amp; SSE
      </button>
      <button onclick="switchTab('observability')" id="btn-observability" class="tab-btn px-3.5 py-1.5 rounded-lg text-xs sm:text-sm whitespace-nowrap transition">
        6. Bedrock &amp; OpenTelemetry
      </button>
    </div>
  </header>

  <main class="max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 space-y-6">

    <!-- Top KPI Strip -->
    <section class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="surface-card p-4">
        <div class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Catalog &amp; Token Baseline</div>
        <div class="mt-1 flex items-baseline gap-2">
          <span class="text-2xl font-bold text-slate-900" id="kpi-total-tools">120</span>
          <span class="text-xs font-medium text-indigo-600" id="kpi-full-tokens">33,453 tokens (measured)</span>
        </div>
        <p class="mt-1 text-xs text-slate-500">Serialized JSON Schema tokens across 8 namespaces</p>
      </div>
      <div class="surface-card p-4">
        <div class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Role-Filtered Routing Savings</div>
        <div class="mt-1 flex items-baseline gap-2">
          <span class="text-2xl font-bold text-emerald-700" id="kpi-token-savings">--%</span>
          <span class="text-xs font-mono text-slate-500" id="kpi-routed-tokens">top-5 slice</span>
        </div>
        <p class="mt-1 text-xs text-slate-500" id="kpi-role-scope">Scoped strictly by verified JWT roles</p>
      </div>
      <div class="surface-card p-4">
        <div class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Governance &amp; Audit Chain</div>
        <div class="mt-1 flex items-baseline gap-2">
          <span class="text-2xl font-bold text-amber-700" id="kpi-pending-hitl">--</span>
          <span class="text-xs font-semibold text-emerald-700" id="kpi-audit-chain">Chain: checking...</span>
        </div>
        <p class="mt-1 text-xs text-slate-500">Ticket + SHA-256 argument hash · Append-only SQLite</p>
      </div>
      <div class="surface-card p-4">
        <div class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">160-Query Recall@5 (Tuned)</div>
        <div class="mt-1 flex items-baseline gap-2">
          <span class="text-2xl font-bold text-indigo-700" id="kpi-recall5">--%</span>
          <span class="text-xs font-medium text-slate-500" id="kpi-route-latency">p50 ~3.2 ms</span>
        </div>
        <p class="mt-1 text-xs text-slate-500">Hybrid BM25+Dense (0.25/0.65/0.10) vs ablations</p>
      </div>
    </section>

    <!-- TAB 1: SEMANTIC ROUTER & EVALUATION -->
    <section id="tab-router" class="tab-panel space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div class="lg:col-span-5 surface-card p-5 space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-bold text-slate-900">Role-Aware Semantic Tool Router</h2>
            <span class="text-[11px] font-semibold px-2 py-0.5 rounded badge-light-indigo">Tuned Hybrid RRF</span>
          </div>
          <p class="text-xs text-slate-600 leading-relaxed">
            Routes natural language intents to the top-<code class="font-mono text-indigo-700">k</code> schemas authorized for your active JWT session. Switch the session role in the top header to verify <code class="font-mono">analyst</code> callers never see <code class="font-mono">platform_admin</code> tools.
          </p>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Natural Language Intent / Query</label>
            <textarea id="router-query" rows="3" class="input-light w-full p-2.5 text-sm">Validate Informatica taskflow SLA row counts and refresh Snowflake Cortex vector search index</textarea>
          </div>

          <div class="grid grid-cols-3 gap-2.5">
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Top-K</label>
              <input id="router-topk" type="number" min="1" max="25" value="5" class="input-light w-full px-2.5 py-2 text-sm" />
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Scorer Mode</label>
              <select id="router-scoring-mode" class="input-light w-full px-2 py-2 text-xs font-medium">
                <option value="hybrid" selected>hybrid (tuned)</option>
                <option value="bm25_only">bm25_only</option>
                <option value="dense_only">dense_only (hash64)</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Domain Filter</label>
              <select id="router-domain" class="input-light w-full px-2 py-2 text-xs font-medium">
                <option value="">All Accessible</option>
                <option value="snowflake">snowflake</option>
                <option value="informatica">informatica</option>
                <option value="postgres">postgres</option>
                <option value="portfolio_vsm">portfolio_vsm</option>
                <option value="devops">devops</option>
                <option value="supply_chain">supply_chain</option>
                <option value="crm_rest">crm_rest</option>
                <option value="knowledge_graph">knowledge_graph</option>
              </select>
            </div>
          </div>

          <label class="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
            <input id="router-autowiden" type="checkbox" checked class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
            <span>Enable <code class="font-mono text-indigo-700">auto_widen</code> fallback when top-5 confidence/margin is ambiguous</span>
          </label>

          <div class="flex flex-wrap gap-1.5">
            <button onclick="setRouterPreset('Execute outbound wire in PostgreSQL ledger')" class="text-[11px] bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded border border-slate-200 font-medium">Wire Transfer (Admin RBAC Test)</button>
            <button onclick="setRouterPreset('Detect executive management concerns across at-risk OKRs and blocked work')" class="text-[11px] bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded border border-slate-200 font-medium">VSM OKR Concerns</button>
            <button onclick="setRouterPreset('Query Kinaxis Maestro gating components causing BOM stockout delays')" class="text-[11px] bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded border border-slate-200 font-medium">Supply Chain Maestro</button>
          </div>

          <div class="flex gap-2">
            <button onclick="runSemanticRoute()" class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 px-4 rounded-lg text-sm transition shadow-xs">
              Route Semantic Tools
            </button>
            <button onclick="loadBenchmark()" class="bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 font-semibold py-2.5 px-3 rounded-lg text-xs transition">
              Run 160-Query Benchmark
            </button>
          </div>
        </div>

        <div class="lg:col-span-7 surface-card p-5 space-y-4">
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
            <h3 class="text-sm font-bold text-slate-900">Routed Candidate Tools &amp; Score Attribution</h3>
            <div id="router-meta" class="text-xs font-mono text-slate-600">Initializing...</div>
          </div>

          <div id="router-results-list" class="space-y-2.5 max-h-[370px] overflow-y-auto pr-1"></div>

          <!-- Feedback loop strip -->
          <div class="pt-3 border-t border-slate-200 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div class="text-slate-600">
              Model tool-selection feedback loop: <span id="feedback-stats-label" class="font-mono font-semibold text-slate-900">0 events</span>
            </div>
            <button onclick="submitSimulatedMissFeedback()" class="text-xs bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-200 px-2.5 py-1 rounded font-medium">
              Log Sample Routing Miss to Eval Queue
            </button>
          </div>
        </div>
      </div>

      <!-- Honest Benchmark & Ablation Card -->
      <div class="surface-card p-5 space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="text-sm font-bold text-slate-900">Honest 160-Query Evaluation Benchmark &amp; Ablation Matrix</h3>
            <p class="text-xs text-slate-500">120 single-domain + 40 cross-domain queries evaluated across Recall@{3, 5, 8, 10, 25}. Dense SHA-256 hash64 alone underperforms Okapi BM25; tuned weights (0.25/0.65/0.10) recover Recall@5.</p>
          </div>
          <span id="benchmark-status-badge" class="text-xs font-mono px-2.5 py-1 rounded badge-light-slate">Click "Run 160-Query Benchmark"</span>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 items-center">
          <div class="lg:col-span-5 h-56">
            <canvas id="benchmarkChart"></canvas>
          </div>
          <div class="lg:col-span-7 overflow-x-auto">
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr class="border-b border-slate-200 text-slate-500 uppercase text-[11px]">
                  <th class="py-2 pr-3">Configuration</th>
                  <th class="py-2 px-2">Recall@3</th>
                  <th class="py-2 px-2">Recall@5</th>
                  <th class="py-2 px-2">Recall@10</th>
                  <th class="py-2 px-2">Single@5</th>
                  <th class="py-2 px-2">Cross@5</th>
                </tr>
              </thead>
              <tbody id="benchmark-table-body" class="divide-y divide-slate-100 font-mono text-slate-800">
                <tr><td colspan="6" class="py-4 text-center text-slate-400">Loading benchmark data...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 2: VALUE STREAM MANAGEMENT -->
    <section id="tab-vsm" class="tab-panel hidden grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div class="lg:col-span-5 surface-card p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-base font-bold text-slate-900">Value Stream Management Advisor</h2>
          <span class="text-[11px] font-semibold px-2 py-0.5 rounded badge-light-emerald">OKRs · Portfolios · Tickets</span>
        </div>
        <p class="text-xs text-slate-600 leading-relaxed">
          Inspects at-risk OKRs, budget overruns, and blocked engineering tickets across product portfolios, synthesizing governed MCP action plans.
        </p>

        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">Steering / Risk Question</label>
          <textarea id="vsm-query" rows="3" class="input-light w-full p-2.5 text-sm">Identify management concerns across OKRs, product portfolios, and blocked engineering tickets and suggest actions</textarea>
        </div>

        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">Portfolio Scope</label>
          <select id="vsm-portfolio-filter" class="input-light w-full px-3 py-2 text-sm">
            <option value="">All Enterprise Portfolios</option>
            <option value="PF-101">PF-101 · Wealth Advisory &amp; RRSP AI</option>
            <option value="PF-202">PF-202 · Supply Chain Digital Twin</option>
            <option value="PF-303">PF-303 · Zero-Trust Core Ledger &amp; IAM</option>
          </select>
        </div>

        <button onclick="runVsmConcernAnalysis()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2.5 px-4 rounded-lg text-sm transition shadow-xs">
          Analyze Management Concerns
        </button>

        <div class="pt-3 border-t border-slate-200 space-y-2">
          <label class="block text-xs font-semibold text-slate-700">Relational SQL over VSM Tables (Read-Only)</label>
          <textarea id="vsm-sql-input" rows="3" class="input-light font-mono w-full p-2 text-xs">SELECT p.portfolio_id, p.name, o.objective, o.status, COUNT(t.ticket_id) AS blocked_tickets FROM product_portfolios p JOIN objectives_okrs o ON p.portfolio_id = o.portfolio_id LEFT JOIN engineering_tickets t ON o.okr_id = t.okr_id AND t.status = 'BLOCKED' GROUP BY p.portfolio_id, o.okr_id</textarea>
          <button onclick="runVsmSql()" class="w-full bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 font-semibold py-2 px-3 rounded-lg text-xs transition">
            Execute VSM SQL Query
          </button>
        </div>
      </div>

      <div class="lg:col-span-7 surface-card p-5 space-y-4">
        <div class="flex items-center justify-between border-b border-slate-200 pb-3">
          <h3 class="text-sm font-bold text-slate-900">Portfolio Health, Concerns &amp; Suggested MCP Actions</h3>
          <span id="vsm-status-badge" class="text-xs font-mono text-slate-500">Ready</span>
        </div>

        <div id="vsm-output-summary" class="text-sm text-slate-700 bg-slate-50 p-3.5 rounded-lg border border-slate-200">
          Loading VSM portfolio overview...
        </div>

        <div id="vsm-concerns-container" class="space-y-3 max-h-[290px] overflow-y-auto pr-1"></div>

        <div>
          <div class="text-xs font-semibold text-slate-500 mb-1">Raw JSON / SQL Inspection</div>
          <pre id="vsm-raw-json" class="code-well p-3 text-xs font-mono overflow-x-auto max-h-44">{}</pre>
        </div>
      </div>
    </section>

    <!-- TAB 3: ZERO-TRUST RBAC, TICKET HITL & HASH-CHAINED AUDIT -->
    <section id="tab-governance" class="tab-panel hidden space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div class="lg:col-span-6 surface-card p-5 space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-bold text-slate-900">Ticket &amp; Argument-Hash Bound Authorization</h2>
            <span class="text-[11px] font-semibold px-2 py-0.5 rounded badge-light-amber">No Client Bypass</span>
          </div>
          <p class="text-xs text-slate-600 leading-relaxed">
            Client-supplied <code class="font-mono line-through text-red-600">user_roles</code> and <code class="font-mono line-through text-red-600">hitl_approved</code> flags have been removed. Authorization relies exclusively on the verified JWT session in the header plus a server-issued single-use HITL ticket bound to the SHA-256 canonical hash of <code class="font-mono text-indigo-700">tool_name + arguments</code>.
          </p>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Target MCP Tool</label>
              <select id="gov-tool" class="input-light w-full px-3 py-2 text-xs font-mono">
                <option value="postgres.execute_outbound_wire">postgres.execute_outbound_wire (platform_admin, mutating)</option>
                <option value="snowflake.execute_readonly_sql">snowflake.execute_readonly_sql (ai_platform_reader, read-only)</option>
                <option value="portfolio_vsm.detect_management_concerns">portfolio_vsm.detect_management_concerns (analyst, read-only)</option>
                <option value="postgres.restore_state_snapshot">postgres.restore_state_snapshot (platform_admin, mutating)</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Approved HITL Ticket ID</label>
              <input id="gov-ticket-id" type="text" placeholder="e.g. HITL-A1B2C3D4" class="input-light w-full px-3 py-2 text-xs font-mono" />
            </div>
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Canonical Arguments JSON (Bound to Ticket SHA-256 Hash)</label>
            <textarea id="gov-arguments-json" rows="2" class="input-light font-mono w-full p-2.5 text-xs">{"from_account": "ACC-9001", "to_account": "ACC-9003", "amount_usd": 50000.0}</textarea>
          </div>

          <div class="flex flex-wrap gap-2">
            <button onclick="runAuthorizeCheck()" class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-3 rounded-lg text-xs sm:text-sm transition">
              Evaluate RBAC &amp; Ticket Gate
            </button>
            <button onclick="createHitlTicket()" class="bg-amber-600 hover:bg-amber-700 text-white font-semibold py-2 px-3 rounded-lg text-xs transition">
              + Create Bound HITL Ticket
            </button>
          </div>

          <pre id="gov-auth-output" class="code-well p-3 text-xs font-mono overflow-x-auto max-h-48">Authorization decision will appear here...</pre>
        </div>

        <div class="lg:col-span-6 surface-card p-5 space-y-4">
          <div class="flex items-center justify-between border-b border-slate-200 pb-3">
            <h3 class="text-sm font-bold text-slate-900">HITL Interrupt Queue (Separation of Duties + TTL)</h3>
            <button onclick="loadHitlQueue()" class="text-xs font-semibold text-indigo-700 hover:text-indigo-900">↻ Refresh</button>
          </div>
          <p class="text-xs text-slate-500">
            Approving as the creator attempts self-approval (blocked with <code class="font-mono text-red-700">403</code>). Click <strong>Approve as Peer Admin</strong> to mint a secondary <code class="font-mono">sr_ops_approver</code> reviewer JWT.
          </p>
          <div id="hitl-queue-list" class="space-y-3 max-h-[340px] overflow-y-auto pr-1"></div>
        </div>
      </div>

      <!-- Hash-Chained Audit Trail Verification -->
      <div class="surface-card p-5 space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="text-sm font-bold text-slate-900">Append-Only SHA-256 Hash-Chained Audit Log</h3>
            <p class="text-xs text-slate-500">Protected by SQLite <code class="font-mono">BEFORE UPDATE / BEFORE DELETE</code> triggers and chained <code class="font-mono">prev_hash -> entry_hash</code> digests.</p>
          </div>
          <div class="flex items-center gap-2">
            <span id="audit-chain-badge" class="text-xs font-mono px-2.5 py-1 rounded badge-light-emerald">Verifying...</span>
            <button onclick="verifyAuditChain()" class="bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 font-semibold py-1.5 px-3 rounded-lg text-xs transition">
              Verify Chain Integrity
            </button>
          </div>
        </div>
        <pre id="audit-chain-output" class="code-well p-3 text-xs font-mono overflow-x-auto max-h-48"></pre>
      </div>
    </section>

    <!-- TAB 4: SQL AST GUARD & DATA CONNECTORS -->
    <section id="tab-connectors" class="tab-panel hidden grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div class="lg:col-span-6 surface-card p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-base font-bold text-slate-900">sqlglot AST SQL Guard (Snowflake &amp; Postgres)</h2>
          <span class="text-[11px] font-semibold px-2 py-0.5 rounded badge-light-indigo">Single-SELECT Allow-List</span>
        </div>
        <p class="text-xs text-slate-600 leading-relaxed">
          Replaces fragile regex matching with AST parsing (<code class="font-mono">sqlglot</code> Snowflake dialect). Rejects multi-statements, mutations, <code class="font-mono">SELECT INTO</code>, <code class="font-mono">FOR UPDATE/SHARE</code> locks, and functions outside an explicit allow-list (catching <code class="font-mono">SYSTEM$*</code> / <code class="font-mono">pg_sleep</code>), while allowing quoted column identifiers like <code class="font-mono">"update"</code>.
        </p>

        <textarea id="sf-sql-input" rows="3" class="input-light font-mono w-full p-2.5 text-xs">SELECT fund_id, nav, aum_cad, "update" FROM PORTFOLIO_GOLD.FUNDS WHERE active = 1 LIMIT 25</textarea>

        <div class="flex flex-wrap gap-1.5">
          <button onclick="setSqlPreset('SELECT fund_id, nav, &quot;update&quot; FROM PORTFOLIO_GOLD.FUNDS LIMIT 10')" class="text-[11px] bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 px-2 py-1 rounded font-medium">✓ Quoted "update" Safe</button>
          <button onclick="setSqlPreset('SELECT SYSTEM$WHITELIST() FROM PORTFOLIO_GOLD.FUNDS')" class="text-[11px] bg-red-50 hover:bg-red-100 text-red-800 border border-red-200 px-2 py-1 rounded font-medium">✗ Block SYSTEM$* Call</button>
          <button onclick="setSqlPreset('SELECT * FROM PORTFOLIO_GOLD.FUNDS FOR UPDATE')" class="text-[11px] bg-red-50 hover:bg-red-100 text-red-800 border border-red-200 px-2 py-1 rounded font-medium">✗ Block FOR UPDATE Lock</button>
          <button onclick="setSqlPreset('SELECT 1; DROP TABLE PORTFOLIO_GOLD.FUNDS')" class="text-[11px] bg-red-50 hover:bg-red-100 text-red-800 border border-red-200 px-2 py-1 rounded font-medium">✗ Block Stacked DDL</button>
        </div>

        <button onclick="runSnowflakeSqlGuard()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-lg text-sm transition">
          Validate SQL AST &amp; Schema Allow-List
        </button>

        <div class="pt-3 border-t border-slate-200 flex gap-2">
          <input id="cortex-query" type="text" value="RRSP contribution compliance rules" class="input-light flex-1 px-3 py-2 text-xs" />
          <button onclick="runCortexSearch()" class="bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-lg text-xs font-semibold">Search Cortex</button>
        </div>
        <pre id="sf-output" class="code-well p-3 text-xs font-mono overflow-x-auto max-h-44">Snowflake guard result...</pre>
      </div>

      <div class="lg:col-span-6 surface-card p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-base font-bold text-slate-900">IICS Circuit-Breaker &amp; SQLite/Postgres Sandbox</h2>
          <span class="text-[11px] font-semibold px-2 py-0.5 rounded badge-light-slate">sqlite3.set_authorizer</span>
        </div>

        <div class="grid grid-cols-3 gap-2">
          <div>
            <label class="block text-[11px] font-semibold text-slate-600 mb-1">IICS Status</label>
            <select id="iics-status" class="input-light w-full px-2 py-1.5 text-xs">
              <option value="SUCCESS">SUCCESS</option>
              <option value="FAILED">FAILED</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] font-semibold text-slate-600 mb-1">Rows Processed</label>
            <input id="iics-rows" type="number" value="1450" class="input-light w-full px-2 py-1.5 text-xs" />
          </div>
          <div>
            <label class="block text-[11px] font-semibold text-slate-600 mb-1">Lag (min)</label>
            <input id="iics-lag" type="number" value="8" class="input-light w-full px-2 py-1.5 text-xs" />
          </div>
        </div>
        <button onclick="runIicsGate()" class="w-full bg-amber-600 hover:bg-amber-700 text-white font-semibold py-2 px-4 rounded-lg text-xs transition">
          Evaluate IICS Taskflow Pre-RAG Gate
        </button>

        <div class="pt-3 border-t border-slate-200 grid grid-cols-2 gap-2">
          <button onclick="runPostgresLedgerQuery()" class="bg-slate-800 hover:bg-slate-900 text-white font-semibold py-2 px-3 rounded-lg text-xs">Query Ledger (READ ONLY)</button>
          <button onclick="runPostgresSnapshot()" class="bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 font-semibold py-2 px-3 rounded-lg text-xs">Create Point-in-Time Snapshot</button>
        </div>

        <pre id="connectors-output" class="code-well p-3 text-xs font-mono overflow-x-auto max-h-56">IICS / Relational Sandbox telemetry...</pre>
      </div>
    </section>

    <!-- TAB 5: FASTMCP JSON-RPC 2.0 -->
    <section id="tab-mcp" class="tab-panel hidden grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div class="lg:col-span-5 surface-card p-5 space-y-4">
        <h2 class="text-base font-bold text-slate-900">FastMCP JSON-RPC 2.0 Composer</h2>
        <p class="text-xs text-slate-600">
          Supports cursor pagination (<code class="font-mono">tools/list</code> with <code class="font-mono">cursor</code>, <code class="font-mono">page_size</code>, <code class="font-mono">domain_filter</code>) and hardened <code class="font-mono">tools/call</code> (authenticated JWT + server-side ticket + arg hash).
        </p>

        <div class="flex flex-wrap gap-1.5">
          <button onclick="setRpcPreset('initialize')" class="text-xs bg-slate-100 hover:bg-slate-200 text-slate-800 px-2.5 py-1 rounded border border-slate-200 font-medium">initialize</button>
          <button onclick="setRpcPreset('tools_list_paginated')" class="text-xs bg-slate-100 hover:bg-slate-200 text-slate-800 px-2.5 py-1 rounded border border-slate-200 font-medium">tools/list (cursor + filter)</button>
          <button onclick="setRpcPreset('tools_call_vsm')" class="text-xs bg-emerald-50 hover:bg-emerald-100 text-emerald-800 px-2.5 py-1 rounded border border-emerald-200 font-medium">tools/call (VSM)</button>
          <button onclick="setRpcPreset('resources_list')" class="text-xs bg-slate-100 hover:bg-slate-200 text-slate-800 px-2.5 py-1 rounded border border-slate-200 font-medium">resources/list</button>
        </div>

        <textarea id="rpc-payload" rows="10" class="input-light font-mono w-full p-3 text-xs">{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {
    "domain_filter": "snowflake",
    "cursor": 0,
    "page_size": 5
  }
}</textarea>

        <button onclick="runJsonRpc()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 px-4 rounded-lg text-sm transition">
          Dispatch POST /mcp/jsonrpc
        </button>
      </div>

      <div class="lg:col-span-7 surface-card p-5 space-y-3">
        <div class="flex items-center justify-between border-b border-slate-200 pb-3">
          <h3 class="text-sm font-bold text-slate-900">JSON-RPC 2.0 Response</h3>
          <span class="text-xs font-mono text-slate-500">SSE Endpoint: /mcp/sse</span>
        </div>
        <pre id="rpc-output" class="code-well p-3 text-xs font-mono overflow-x-auto max-h-[400px]">Click Dispatch to execute MCP protocol call...</pre>
      </div>
    </section>

    <!-- TAB 6: BEDROCK & OPENTELEMETRY -->
    <section id="tab-observability" class="tab-panel hidden grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div class="lg:col-span-5 surface-card p-5 space-y-4">
        <h2 class="text-base font-bold text-slate-900">Bedrock AgentCore &amp; Framework Bridges</h2>
        <p class="text-xs text-slate-600">Structured schema self-healing retry loop (simulated fallback when AWS credentials are absent) plus schema export to LangGraph, smolagents, and CrewAI.</p>

        <button onclick="runBedrockRetry()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 px-4 rounded-lg text-xs sm:text-sm transition">
          Invoke Structured Retry (Simulate Flaky Attempt 1)
        </button>

        <div class="grid grid-cols-3 gap-2">
          <button onclick="loadBridge('langgraph')" class="bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 text-xs font-semibold py-2 rounded-lg">LangGraph</button>
          <button onclick="loadBridge('smolagents')" class="bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 text-xs font-semibold py-2 rounded-lg">smolagents</button>
          <button onclick="loadBridge('crewai')" class="bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 text-xs font-semibold py-2 rounded-lg">CrewAI</button>
        </div>

        <pre id="bedrock-output" class="code-well p-3 text-xs font-mono overflow-x-auto max-h-64">Click Invoke to run retry loop or export framework schemas...</pre>
      </div>

      <div class="lg:col-span-7 surface-card p-5 space-y-4">
        <div class="flex items-center justify-between border-b border-slate-200 pb-3">
          <h3 class="text-sm font-bold text-slate-900">OpenTelemetry Spans &amp; Token Budget Monitor</h3>
          <button onclick="loadTelemetry()" class="text-xs font-semibold text-indigo-700">↻ Refresh</button>
        </div>
        <div class="h-44">
          <canvas id="telemetryChart"></canvas>
        </div>
        <pre id="telemetry-output" class="code-well p-3 text-xs font-mono overflow-x-auto max-h-52">Loading OTel metrics...</pre>
      </div>
    </section>

  </main>

  <footer class="bg-white border-t border-slate-200 py-3 px-6 text-center text-xs text-slate-500">
    Enterprise-MCP-Router · Zero-Trust JWT RBAC, SHA-256 Argument-Bound HITL, sqlglot AST Guard &amp; Honest Benchmark Evaluation
  </footer>

  <script>
    let telemetryChartInstance = null;
    let benchmarkChartInstance = null;
    let sessionToken = null;
    let sessionUsername = 'platform_ops@enterprise.io';
    let lastRoutedNames = [];
    let lastQuery = '';

    async function apiFetch(url, options = {}) {
      const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
      if (sessionToken && !headers['Authorization']) {
        headers['Authorization'] = `Bearer ${sessionToken}`;
      }
      return fetch(url, { ...options, headers });
    }

    async function switchSessionPersona() {
      const role = document.getElementById('session-role-select').value;
      const usernameMap = {
        analyst: 'analyst_demo@enterprise.io',
        data_engineer: 'data_eng_demo@enterprise.io',
        compliance_officer: 'compliance_demo@enterprise.io',
        platform_admin: 'platform_ops@enterprise.io',
        super_admin: 'ciso_superadmin@enterprise.io',
      };
      sessionUsername = usernameMap[role] || 'demo_operator@enterprise.io';
      const pill = document.getElementById('jwt-status-pill');
      try {
        const res = await fetch('/api/v1/auth/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: sessionUsername, role }),
        });
        const data = await res.json();
        sessionToken = data.access_token;
        pill.textContent = `JWT: ${role}`;
        pill.className = 'text-[11px] font-mono px-2 py-0.5 rounded badge-light-indigo';
      } catch (e) {
        pill.textContent = 'JWT Error';
      }
      await runSemanticRoute();
      await loadHitlQueue();
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab-panel').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(`tab-${tabId}`).classList.remove('hidden');
      document.getElementById(`btn-${tabId}`).classList.add('active');
      if (tabId === 'vsm') loadVsmOverview();
      if (tabId === 'governance') {
        loadHitlQueue();
        verifyAuditChain();
      }
      if (tabId === 'observability') loadTelemetry();
    }

    async function refreshHealth() {
      const res = await apiFetch('/health');
      const data = await res.json();
      document.getElementById('kpi-total-tools').textContent = data.total_registered_tools;
      document.getElementById('kpi-pending-hitl').textContent = data.pending_hitl_tickets;
      document.getElementById('health-status-label').textContent = `${data.total_registered_tools} Tools · Healthy`;
    }

    function setRouterPreset(q) {
      document.getElementById('router-query').value = q;
      runSemanticRoute();
    }

    async function runSemanticRoute() {
      const query = document.getElementById('router-query').value;
      const top_k = parseInt(document.getElementById('router-topk').value || '5', 10);
      const scoring_mode = document.getElementById('router-scoring-mode').value;
      const domain_filter = document.getElementById('router-domain').value || null;
      const auto_widen = document.getElementById('router-autowiden').checked;

      const res = await apiFetch('/api/v1/router/search', {
        method: 'POST',
        body: JSON.stringify({ query, top_k, domain_filter, scoring_mode, auto_widen }),
      });
      const data = await res.json();
      lastQuery = query;
      lastRoutedNames = data.routed_tools.map(t => t.name);

      document.getElementById('kpi-full-tokens').textContent = `${data.full_registry_tokens.toLocaleString()} tokens (measured)`;
      document.getElementById('kpi-token-savings').textContent = `${data.token_reduction_pct}%`;
      document.getElementById('kpi-routed-tokens').textContent = `${data.routed_tokens.toLocaleString()} vs ${data.full_registry_tokens.toLocaleString()}`;
      document.getElementById('kpi-route-latency').textContent = `Latency: ${data.routing_latency_ms} ms`;
      document.getElementById('kpi-role-scope').textContent =
        `Accessible: ${data.total_accessible_tools}/${data.total_registered_tools} tools (${(data.caller_roles_applied || []).join(', ')})`;

      const widenLabel = data.widened_k ? ` · WIDENED k=${data.effective_k}` : ` · k=${data.effective_k}`;
      document.getElementById('router-meta').textContent =
        `${data.scoring_mode}${widenLabel} · ${data.routing_latency_ms} ms · -${data.token_reduction_pct}% tokens`;

      const container = document.getElementById('router-results-list');
      container.innerHTML = '';
      data.routed_tools.forEach((tool, idx) => {
        const mutBadge = tool.is_mutating
          ? '<span class="px-2 py-0.5 text-[10px] font-semibold rounded badge-light-amber">MUTATING · HITL</span>'
          : '<span class="px-2 py-0.5 text-[10px] font-semibold rounded badge-light-emerald">READ-ONLY</span>';
        container.innerHTML += `
          <div class="p-3 rounded-lg bg-slate-50 border border-slate-200 hover:border-indigo-300 transition">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="text-xs font-mono font-bold text-slate-400">#${idx + 1}</span>
                <span class="text-sm font-mono font-semibold text-indigo-700">${tool.name}</span>
                <span class="px-2 py-0.5 text-[10px] font-medium rounded badge-light-slate">${tool.domain}</span>
                ${mutBadge}
              </div>
              <div class="text-xs font-mono text-slate-700">
                score: <strong class="text-indigo-700">${tool.similarity_score}</strong> · bm25: ${tool.bm25_score} · ${tool.schema_tokens}t
              </div>
            </div>
            <p class="text-xs text-slate-600 mt-1.5">${tool.description}</p>
            <div class="mt-1.5 text-[11px] font-mono text-slate-500">required_role: <span class="text-slate-800 font-semibold">${tool.required_role}</span></div>
          </div>`;
      });
    }

    async function loadBenchmark() {
      const badge = document.getElementById('benchmark-status-badge');
      badge.textContent = 'Running 160-query benchmark...';
      const res = await apiFetch('/api/v1/router/benchmark');
      const data = await res.json();
      badge.textContent = `${data.dataset_size} queries (${data.single_domain_count} single / ${data.cross_domain_count} cross) · Measured`;
      badge.className = 'text-xs font-mono px-2.5 py-1 rounded badge-light-emerald';

      const tuned = data.ablations.hybrid_balanced_25_65_10;
      if (tuned) {
        document.getElementById('kpi-recall5').textContent = `${(tuned.overall['recall@5'] * 100).toFixed(1)}%`;
      }

      const tbody = document.getElementById('benchmark-table-body');
      tbody.innerHTML = '';
      Object.entries(data.ablations).forEach(([name, row]) => {
        tbody.innerHTML += `
          <tr class="hover:bg-slate-50">
            <td class="py-2 pr-3 font-semibold text-slate-800">${name}</td>
            <td class="py-2 px-2">${(row.overall['recall@3'] * 100).toFixed(1)}%</td>
            <td class="py-2 px-2 font-bold text-indigo-700">${(row.overall['recall@5'] * 100).toFixed(1)}%</td>
            <td class="py-2 px-2">${(row.overall['recall@10'] * 100).toFixed(1)}%</td>
            <td class="py-2 px-2 text-emerald-700">${(row.single_domain['recall@5'] * 100).toFixed(1)}%</td>
            <td class="py-2 px-2 text-amber-700">${(row.cross_domain['recall@5'] * 100).toFixed(1)}%</td>
          </tr>`;
      });

      const ctx = document.getElementById('benchmarkChart').getContext('2d');
      if (benchmarkChartInstance) benchmarkChartInstance.destroy();
      const ks = ['recall@3', 'recall@5', 'recall@8', 'recall@10', 'recall@25'];
      const series = [
        { label: 'Dense Only (hash64)', key: 'dense_only_hash64', color: '#dc2626' },
        { label: 'Hybrid (0.55/0.35/0.10)', key: 'hybrid_default_55_35_10', color: '#d97706' },
        { label: 'Hybrid Tuned (0.25/0.65/0.10)', key: 'hybrid_balanced_25_65_10', color: '#4f46e5' },
        { label: 'BM25 Only', key: 'bm25_only', color: '#059669' },
      ];
      benchmarkChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: ['k=3', 'k=5', 'k=8', 'k=10', 'k=25'],
          datasets: series.map(s => ({
            label: s.label,
            data: ks.map(k => +((data.ablations[s.key]?.overall[k] || 0) * 100).toFixed(2)),
            borderColor: s.color,
            backgroundColor: s.color,
            borderWidth: 2,
            tension: 0.2,
          })),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom', labels: { color: '#334155', font: { size: 10 } } } },
          scales: {
            y: { min: 60, max: 100, ticks: { color: '#475569' }, grid: { color: '#e2e8f0' } },
            x: { ticks: { color: '#475569' }, grid: { color: '#f1f5f9' } },
          },
        },
      });
    }

    async function submitSimulatedMissFeedback() {
      const res = await apiFetch('/api/v1/router/feedback', {
        method: 'POST',
        body: JSON.stringify({
          query: lastQuery || 'Evaluate AML wire compliance',
          routed_tools: lastRoutedNames,
          selected_tool: 'crm_rest.escalate_aml_suspicious_activity',
        }),
      });
      const data = await res.json();
      document.getElementById('feedback-stats-label').textContent =
        `total=${data.stats.total_feedback}, hits=${data.stats.hits}, miss_queue=${data.miss_queue_size}`;
    }

    async function loadVsmOverview() {
      const res = await apiFetch('/api/v1/vsm/overview');
      const data = await res.json();
      const kpis = data.kpis;
      document.getElementById('vsm-status-badge').textContent =
        `${kpis.total_portfolios} Portfolios · ${kpis.total_okrs} OKRs · ${kpis.blocked_tickets} Blocked`;
      document.getElementById('vsm-output-summary').innerHTML =
        `<div class="grid grid-cols-3 gap-3 text-center">
          <div class="bg-white p-2.5 rounded border border-slate-200"><div class="text-[11px] text-slate-500">Approved Budget</div><div class="text-base font-bold text-slate-900">$${kpis.total_budget_musd}M</div></div>
          <div class="bg-white p-2.5 rounded border border-slate-200"><div class="text-[11px] text-slate-500">YTD Spend</div><div class="text-base font-bold text-amber-700">$${kpis.total_spend_musd}M</div></div>
          <div class="bg-white p-2.5 rounded border border-slate-200"><div class="text-[11px] text-slate-500">Avg OKR Progress</div><div class="text-base font-bold text-emerald-700">${kpis.avg_okr_progress_pct}%</div></div>
        </div>`;
      document.getElementById('vsm-raw-json').textContent = JSON.stringify(data, null, 2);
    }

    async function runVsmConcernAnalysis() {
      const query = document.getElementById('vsm-query').value;
      const portfolio_id = document.getElementById('vsm-portfolio-filter').value || null;
      const res = await apiFetch('/api/v1/vsm/analyze-concerns', {
        method: 'POST',
        body: JSON.stringify({ query, portfolio_id }),
      });
      const data = await res.json();
      document.getElementById('vsm-output-summary').textContent = data.executive_summary;
      document.getElementById('vsm-status-badge').textContent =
        `${data.concerns_detected} Concerns · ${(data.routed_vsm_tools || []).length} VSM Tools`;

      const container = document.getElementById('vsm-concerns-container');
      container.innerHTML = '';
      data.concerns.forEach(c => {
        const badge = c.severity === 'CRITICAL' ? 'badge-light-red' : 'badge-light-amber';
        container.innerHTML += `
          <div class="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1.5">
            <div class="flex items-center justify-between gap-2">
              <span class="text-xs font-bold text-slate-900">${c.title}</span>
              <span class="px-2 py-0.5 text-[10px] font-semibold rounded ${badge}">${c.severity} · ${c.category}</span>
            </div>
            <p class="text-xs text-slate-600">${c.evidence}</p>
            <div class="text-xs font-mono text-indigo-700">Suggested: ${c.recommended_mcp_tool}</div>
          </div>`;
      });
      document.getElementById('vsm-raw-json').textContent = JSON.stringify(data, null, 2);
    }

    async function runVsmSql() {
      const sql = document.getElementById('vsm-sql-input').value;
      const res = await apiFetch('/api/v1/vsm/query', {
        method: 'POST',
        body: JSON.stringify({ sql, role: 'analyst' }),
      });
      document.getElementById('vsm-raw-json').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function runAuthorizeCheck() {
      const tool_name = document.getElementById('gov-tool').value;
      const hitl_ticket_id = document.getElementById('gov-ticket-id').value.trim() || null;
      let args = {};
      try {
        args = JSON.parse(document.getElementById('gov-arguments-json').value || '{}');
      } catch (e) {
        document.getElementById('gov-auth-output').textContent = 'Invalid JSON in arguments input: ' + e.message;
        return;
      }
      const res = await apiFetch('/api/v1/governance/authorize', {
        method: 'POST',
        body: JSON.stringify({ tool_name, hitl_ticket_id, arguments: args }),
      });
      const data = await res.json();
      document.getElementById('gov-auth-output').textContent = JSON.stringify(data, null, 2);
      await loadHitlQueue();
      await verifyAuditChain();
    }

    async function createHitlTicket() {
      const tool_name = document.getElementById('gov-tool').value;
      let args = {};
      try {
        args = JSON.parse(document.getElementById('gov-arguments-json').value || '{}');
      } catch (e) {
        document.getElementById('gov-auth-output').textContent = 'Invalid JSON in arguments input: ' + e.message;
        return;
      }
      const res = await apiFetch('/api/v1/governance/hitl/create', {
        method: 'POST',
        body: JSON.stringify({
          tool_name,
          arguments: args,
          justification: 'Verified UI governance submission',
        }),
      });
      const data = await res.json();
      if (data.ticket_id) {
        document.getElementById('gov-ticket-id').value = data.ticket_id;
      }
      document.getElementById('gov-auth-output').textContent = JSON.stringify(data, null, 2);
      await loadHitlQueue();
      await refreshHealth();
      await verifyAuditChain();
    }

    async function resolveHitl(ticket_id, decision, asPeerReviewer) {
      let headers = {};
      if (asPeerReviewer) {
        const tokRes = await fetch('/api/v1/auth/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: 'sr_ops_approver@enterprise.io', role: 'super_admin' }),
        });
        const tokData = await tokRes.json();
        headers['Authorization'] = `Bearer ${tokData.access_token}`;
      }
      const res = await apiFetch('/api/v1/governance/hitl/resolve', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          ticket_id,
          decision,
          notes: asPeerReviewer ? 'Peer-verified argument hash and change ticket' : 'Self-approval attempt',
        }),
      });
      const data = await res.json();
      document.getElementById('gov-auth-output').textContent = JSON.stringify({ http_status: res.status, ...data }, null, 2);
      if (res.ok) {
        document.getElementById('gov-ticket-id').value = ticket_id;
      }
      await loadHitlQueue();
      await refreshHealth();
      await verifyAuditChain();
    }

    async function loadHitlQueue() {
      const res = await apiFetch('/api/v1/governance/hitl');
      const data = await res.json();
      const container = document.getElementById('hitl-queue-list');
      container.innerHTML = '';
      data.tickets.forEach(t => {
        const statusClass =
          t.status === 'PENDING_APPROVAL' ? 'badge-light-amber' :
          t.status === 'APPROVED' ? 'badge-light-emerald' :
          t.status === 'CONSUMED' ? 'badge-light-indigo' : 'badge-light-red';
        const actions = t.status === 'PENDING_APPROVAL'
          ? `<div class="flex flex-wrap gap-1.5 mt-2">
               <button onclick="resolveHitl('${t.ticket_id}','APPROVED',true)" class="bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-semibold px-2.5 py-1 rounded">Approve as Peer Admin</button>
               <button onclick="resolveHitl('${t.ticket_id}','APPROVED',false)" class="bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 text-[11px] font-semibold px-2.5 py-1 rounded">Test Self-Approve</button>
               <button onclick="resolveHitl('${t.ticket_id}','REJECTED',true)" class="bg-red-600 hover:bg-red-700 text-white text-[11px] font-semibold px-2.5 py-1 rounded">Reject</button>
             </div>`
          : `<div class="mt-1.5 text-[11px] font-mono text-slate-500">Reviewer: ${t.reviewer || 'N/A'}</div>`;
        container.innerHTML += `
          <div class="p-3 rounded-lg bg-slate-50 border border-slate-200">
            <div class="flex items-center justify-between gap-2">
              <button onclick="document.getElementById('gov-ticket-id').value='${t.ticket_id}'" class="font-mono text-xs font-bold text-indigo-700 hover:underline">${t.ticket_id}</button>
              <span class="px-2 py-0.5 text-[10px] font-semibold rounded ${statusClass}">${t.status}</span>
            </div>
            <div class="text-xs font-mono text-slate-800 mt-1">${t.tool_name}</div>
            <div class="text-[11px] text-slate-500 mt-0.5">by ${t.requested_by} · arg_hash: <span class="font-mono">${(t.arguments_hash || '').slice(0, 16)}...</span></div>
            ${actions}
          </div>`;
      });
    }

    async function verifyAuditChain() {
      const res = await apiFetch('/api/v1/governance/audit-verify');
      const data = await res.json();
      const badge = document.getElementById('audit-chain-badge');
      const kpi = document.getElementById('kpi-audit-chain');
      if (data.valid) {
        badge.textContent = `VALID CHAIN · ${data.checked_events} entries`;
        badge.className = 'text-xs font-mono px-2.5 py-1 rounded badge-light-emerald';
        kpi.textContent = `Chain OK (${data.checked_events})`;
        kpi.className = 'text-xs font-semibold text-emerald-700';
      } else {
        badge.textContent = 'TAMPER DETECTED';
        badge.className = 'text-xs font-mono px-2.5 py-1 rounded badge-light-red';
        kpi.textContent = 'Chain INVALID';
        kpi.className = 'text-xs font-semibold text-red-700';
      }
      document.getElementById('audit-chain-output').textContent = JSON.stringify(data, null, 2);
    }

    function setSqlPreset(q) {
      document.getElementById('sf-sql-input').value = q;
      runSnowflakeSqlGuard();
    }

    async function runSnowflakeSqlGuard() {
      const sql = document.getElementById('sf-sql-input').value;
      const res = await apiFetch('/api/v1/connectors/snowflake/validate-sql', {
        method: 'POST',
        body: JSON.stringify({ sql, role: 'ai_platform_reader', schema_name: 'PORTFOLIO_GOLD' }),
      });
      document.getElementById('sf-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function runCortexSearch() {
      const query = document.getElementById('cortex-query').value;
      const res = await apiFetch('/api/v1/connectors/snowflake/cortex-search', {
        method: 'POST',
        body: JSON.stringify({ query, role: 'ai_platform_reader', top_k: 3 }),
      });
      document.getElementById('sf-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function runIicsGate() {
      const status = document.getElementById('iics-status').value;
      const rows_processed = parseInt(document.getElementById('iics-rows').value, 10);
      const freshness_lag_minutes = parseInt(document.getElementById('iics-lag').value, 10);
      const res = await apiFetch('/api/v1/connectors/informatica/validate', {
        method: 'POST',
        body: JSON.stringify({ taskflow_name: 'tf_snowflake_fund_docs_elt', status, rows_processed, freshness_lag_minutes }),
      });
      document.getElementById('connectors-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function runPostgresLedgerQuery() {
      const res = await apiFetch('/api/v1/connectors/postgres/query', {
        method: 'POST',
        body: JSON.stringify({ sql: 'SELECT account_id, portfolio_name, balance_usd, risk_tier FROM accounts ORDER BY balance_usd DESC', role: 'analyst' }),
      });
      document.getElementById('connectors-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function runPostgresSnapshot() {
      const res = await apiFetch('/api/v1/connectors/postgres/snapshot/create', {
        method: 'POST',
        body: JSON.stringify({ snapshot_name: 'ui_checkpoint_' + Date.now().toString().slice(-5) }),
      });
      document.getElementById('connectors-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    function setRpcPreset(kind) {
      const presets = {
        initialize: { jsonrpc: '2.0', id: 1, method: 'initialize', params: {} },
        tools_list_paginated: { jsonrpc: '2.0', id: 2, method: 'tools/list', params: { domain_filter: 'snowflake', cursor: 0, page_size: 5 } },
        tools_call_vsm: { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'portfolio_vsm.detect_management_concerns', arguments: { query: 'blocked OKRs' } } },
        resources_list: { jsonrpc: '2.0', id: 4, method: 'resources/list', params: {} },
      };
      document.getElementById('rpc-payload').value = JSON.stringify(presets[kind], null, 2);
    }

    async function runJsonRpc() {
      const raw = document.getElementById('rpc-payload').value;
      const res = await apiFetch('/mcp/jsonrpc', { method: 'POST', body: raw });
      document.getElementById('rpc-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function runBedrockRetry() {
      const res = await apiFetch('/api/v1/adapters/bedrock/invoke', {
        method: 'POST',
        body: JSON.stringify({ simulate_flaky_first_attempt: true }),
      });
      document.getElementById('bedrock-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function loadBridge(fw) {
      const res = await apiFetch(`/api/v1/adapters/bridges/${fw}`);
      document.getElementById('bedrock-output').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function loadTelemetry() {
      const res = await apiFetch('/api/v1/telemetry/summary');
      const data = await res.json();
      document.getElementById('telemetry-output').textContent = JSON.stringify(data, null, 2);

      const ctx = document.getElementById('telemetryChart').getContext('2d');
      if (telemetryChartInstance) telemetryChartInstance.destroy();
      const labels = Object.keys(data.tokens_by_use_case);
      const values = Object.values(data.tokens_by_use_case);
      telemetryChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: 'Total Tokens per Use Case',
            data: values,
            backgroundColor: ['#4f46e5', '#059669', '#0284c7'],
            borderRadius: 6,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { labels: { color: '#334155' } } },
          scales: {
            y: { ticks: { color: '#475569' }, grid: { color: '#e2e8f0' } },
            x: { ticks: { color: '#475569' }, grid: { display: false } },
          },
        },
      });
    }

    window.addEventListener('DOMContentLoaded', async () => {
      await switchSessionPersona();
      await refreshHealth();
      await verifyAuditChain();
      await loadBenchmark();
    });
  </script>
</body>
</html>
"""
