// BRI Life FY2024 industry briefing — content
export const DATA = {
  meta: {
    title: "BRI Life FY2024 Industry Snapshot",
    subtitle: "Performance review, competitive position & 2025 strategic outlook",
    author: "Lidharmawan Suryaatmadja",
    org: "PolarisBI · Industry Intelligence",
    date: "May 2026",
  },

  kpis: [
    { icon: "coins",        label: "Premi Bruto FY24", value: "Rp 8.9T", delta: "+14.1% YoY" },
    { icon: "trending-up",  label: "APE FY24",         value: "Rp 3.42T", delta: "+11.2% YoY" },
    { icon: "shield",       label: "RBC Ratio",        value: "434.6%", delta: "3.6× OJK min" },
    { icon: "activity",     label: "Net Profit FY24",  value: "Rp 760M", delta: "+42.1% YoY" },
  ],
  kpiContext: [
    { h: "Why these matter", b: "Premium growth driven by channel mix shift, with risk-adjusted profitability intact." },
    { h: "Peer benchmark", b: "APE growth +11.2% ranks #2 in the top 10; RBC exceeds OJK minimum by 3.6×." },
    { h: "Forward signal", b: "FY2025 hinges on sustaining bancassurance velocity against rising claim ratios." },
  ],

  market: {
    trend: { // Indonesia life-insurance gross premium, Rp Trillion
      labels: ["FY2021", "FY2022", "FY2023", "FY2024"],
      values: [205.0, 214.2, 218.5, 238.71],
    },
    facts: [
      { icon: "landmark", h: "Rp 238.7T industry premium", b: "Indonesian life-insurance premiums grew 9.3% YoY in FY2024 — the strongest since OJK began tracking." },
      { icon: "users",    h: "Bancassurance = 42% of new APE", b: "Bank channel is now the largest source of new business, a record industry share." },
      { icon: "alert-triangle", h: "Health claim pressure", b: "Industry 1H-2024 health claim ratio hit 139.5%, squeezing underwriting margins across 15 major players." },
    ],
  },

  scr: [
    { tag: "Situation", icon: "search", fig: "42%", figLabel: "bancassurance share of new-business APE — a record high",
      b: "Indonesia's life-insurance premiums grew 9.3% to Rp 238.7T in FY2024 — with bancassurance now 42% of new-business APE, a record high." },
    { tag: "Complication", icon: "alert-triangle", fig: "139.5%", figLabel: "industry health claim ratio, 1H-2024 (AAJI)",
      b: "Health claim ratio hit 139.5% in 1H-2024 (AAJI), squeezing underwriting margins across all 15 major players; BRI Life held at 121% but is rising." },
    { tag: "Resolution", icon: "target", fig: "434.6%", figLabel: "BRI Life RBC ratio — 3.6× the OJK minimum",
      b: "BRI Life bancassurance APE grew 41% YoY — 2.3× the industry average; #5 by share but #2 by growth velocity in the top 10." },
  ],

  channels: { // APE by distribution channel, Rp Trillion
    labels: ["Bancassurance", "Agency", "Telemarketing", "Digital", "Worksite"],
    fy23:   [1.62, 0.94, 0.31, 0.18, 0.07],
    fy24:   [2.28, 0.71, 0.22, 0.16, 0.05],
    insights: [
      { h: "Channel concentration", b: "Bancassurance share of total APE grew from 51% to 67% — a structural, not cyclical, mix shift." },
      { h: "BRI synergy", b: "Cross-sell via BRI tellers reached 8.4% in Q4, double the 4.1% industry bancassurance average." },
      { h: "Forward signal", b: "Q1-2025 trial in 50 BRI Premium branches shows a further +18% uplift; full rollout planned for Q2-2025." },
    ],
  },

  compare: {
    cols: ["BRI Life", "Prudential", "Allianz", "AIA"],
    highlight: 0,
    rows: [
      { m: "Market Share (APE)", v: ["11.4%", "18.2%", "13.7%", "12.6%"], rank: ["#5", "#1", "#3", "#4"] },
      { m: "APE Growth YoY",     v: ["+11.2%", "+6.8%", "+8.4%", "+5.2%"], rank: ["#2", "#6", "#5", "#8"] },
      { m: "RBC Ratio",          v: ["434.6%", "521%", "467%", "443%"], rank: ["#3", "#1", "#2", "#3"] },
      { m: "Bancassurance Mix",  v: ["67%", "38%", "42%", "35%"], rank: ["#1", "#5", "#4", "#6"] },
      { m: "Claim Ratio",        v: ["121%", "108%", "115%", "112%"], rank: ["#4", "#1", "#2", "#1"] },
    ],
    readout: "BRI Life shows the strongest growth velocity (+11.2% APE YoY, #2 in industry) and #1 bancassurance mix (67%) — but trails leaders on absolute RBC and claim ratio. Strategic focus: defend the growth advantage while closing the underwriting gap.",
  },

  peers: {
    header: ["#", "Company", "APE", "YoY", "RBC", "Share", "Claim"],
    rows: [
      ["1", "Prudential Life Assurance", "Rp 5.46T", "+6.8%", "521%", "18.2%", "108%"],
      ["2", "Allianz Life Indonesia", "Rp 4.11T", "+8.4%", "467%", "13.7%", "115%"],
      ["3", "AIA Financial", "Rp 3.78T", "+5.2%", "443%", "12.6%", "112%"],
      ["4", "Manulife Indonesia", "Rp 3.51T", "+9.1%", "456%", "11.7%", "118%"],
      ["5", "BRI Life", "Rp 3.42T", "+11.2%", "434.6%", "11.4%", "121%"],
      ["6", "AXA Mandiri", "Rp 2.18T", "+7.6%", "412%", "7.3%", "119%"],
      ["7", "Sequis Life", "Rp 1.71T", "+4.3%", "398%", "5.7%", "124%"],
      ["8", "Sinarmas MSIG", "Rp 1.32T", "+3.8%", "387%", "4.4%", "127%"],
      ["9", "FWD Insurance", "Rp 0.94T", "+14.6%", "356%", "3.1%", "131%"],
      ["10", "Sun Life Financial", "Rp 0.87T", "+5.9%", "421%", "2.9%", "116%"],
    ],
    highlightRow: 4,
    readout: "BRI Life ranks #5 by APE (Rp 3.42T) but #2 by growth velocity (+11.2% YoY) and #1 by bancassurance mix — distinctive value from BRI's 33,000-outlet ecosystem. Watch item: claim ratio at 121% trails leaders Prudential (108%) and Allianz (115%).",
  },

  watch: [
    { sev: "High", color: "red", icon: "alert-triangle",
      h: "PSAK 117 transition (mandatory Jan 2025)",
      b: "IFRS-17-equivalent forces re-measurement of insurance contracts; could compress reported FY25 profit by 8–12% even with no underlying change.",
      owner: "Finance + Actuarial", trigger: "Audit committee review, Mar 2025" },
    { sev: "Medium", color: "amber", icon: "clock",
      h: "Health claim ratio trending toward 130%",
      b: "Industry-wide pressure from medical inflation + adverse selection on new health products; BRI Life ratio up +6pp in 12 months.",
      owner: "Underwriting + Product", trigger: "Q2 2025 portfolio review" },
    { sev: "Low", color: "green", icon: "landmark",
      h: "BRI 2027 digital pivot may reduce branch foot traffic",
      b: "Bancassurance (67% of APE) depends on physical BRI outlets; long-term threat if digital migration accelerates beyond the 2027 plan.",
      owner: "Strategy + Distribution", trigger: "BRI Group strategy refresh, Dec 2025" },
  ],

  recs: [
    { n: "1", h: "Launch Premium Bancassurance Tier in 50 BRI Premium branches",
      b: "Q1-2025 trial showed +18% conversion uplift vs standard tier; addressable market of 1.2M premium customers underweighted in the current portfolio.",
      owner: "Distribution + Product", timeline: "Q2 2025 rollout, full coverage by Q4",
      metric: "Premium APE share: 4% → 12% by FY25" },
    { n: "2", h: "Tighten health underwriting bands for ages 50+",
      b: "Claim ratio escalation is concentrated in this cohort (157% vs portfolio avg 121%); an 18-month repricing window exists before product re-filing.",
      owner: "Underwriting", timeline: "Q2 2025 model update, Q3 product re-file",
      metric: "Claim ratio 121% → 115% by Q4 2025" },
    { n: "3", h: "Pre-empt PSAK 117 communications to investors and OJK",
      b: "Mandatory Jan-2025 adoption; transparent comms reduces stock reaction and signals proactive governance to the market.",
      owner: "IR + Finance", timeline: "Investor day Q1 2025, OJK briefing Feb",
      metric: "Zero negative analyst notes on PSAK 117" },
  ],
};
