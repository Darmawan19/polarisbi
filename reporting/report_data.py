"""
reporting/report_data.py — BRI Life FY2024 Industry Snapshot, consulting format.
Provides REPORT dict that build_docx.build() consumes directly.
Schema matches assemble_contract_reference.py output shape.
"""

# Pre-compute channel table rows
_CH_LABELS = ["Bancassurance", "Agency", "Telemarketing", "Digital", "Worksite"]
_CH_FY23   = [1.62, 0.94, 0.31, 0.18, 0.07]
_CH_FY24   = [2.28, 0.71, 0.22, 0.16, 0.05]

_ch_rows = []
for _l, _f23, _f24 in zip(_CH_LABELS, _CH_FY23, _CH_FY24):
    _pct = (_f24 - _f23) / _f23 * 100
    _ch_rows.append([_l, f"{_f23:.2f}", f"{_f24:.2f}",
                     f"{'+' if _pct >= 0 else ''}{_pct:.1f}%"])


REPORT = {
    "meta": {
        "eyebrow": "PolarisBI · Industry Intelligence",
        "title": "BRI Life FY2024 Industry Snapshot",
        "subtitle": "Performance review, competitive position & 2025 strategic outlook",
        "classification": "Confidential — PolarisBI Industry Intelligence",
        "author": "Lidharmawan Suryaatmadja",
        "date": "May 2026",
        "running_title": "BRI Life FY2024 Industry Snapshot",
        "footer": "PolarisBI · Industry Intelligence · Confidential",
        "filename": "PolarisBI-BRILife-FY2024-Report.docx",
    },

    "kpis": [
        {"label": "Premi Bruto FY24", "value": "Rp 8.9T",  "delta": "+14.1% YoY"},
        {"label": "APE FY24",         "value": "Rp 3.42T", "delta": "+11.2% YoY"},
        {"label": "RBC Ratio",        "value": "434.6%",   "delta": "3.6× OJK minimum"},
        {"label": "Net Profit FY24",  "value": "Rp 760M",  "delta": "+42.1% YoY"},
    ],

    "exec_summary": [
        (
            "Indonesia's life-insurance premiums grew 9.3% to Rp 238.7T in FY2024 — the "
            "strongest pace since OJK began tracking. BRI Life outpaced the market with "
            "+11.2% APE growth, reaching Rp 3.42T and holding the #5 position by APE while "
            "ranking #2 by growth velocity across the top 10."
        ),
        (
            "The defining theme of FY2024 was bancassurance concentration: BRI Life's channel "
            "mix shifted to 67% bancassurance APE (up from 51% in FY2023), leveraging BRI's "
            "33,000-outlet network 2.3× faster than industry average. Two near-term risks "
            "require management attention: a health claim ratio trending toward 130% and the "
            "mandatory PSAK 117 accounting transition scheduled for January 2025."
        ),
    ],

    "sections": [
        # ── 1. Market Context ──────────────────────────────────────────────────
        {
            "num": "1",
            "title": "Indonesia Life Insurance Market — FY2024",
            "intro": (
                "Indonesia's life-insurance market grew 9.3% in FY2024, with bancassurance "
                "emerging as the primary growth engine across the industry."
            ),
            "points": [
                (
                    "Rp 238.7T industry premium — strongest growth since OJK tracking began.",
                    "Indonesian life-insurance premiums grew 9.3% YoY in FY2024, driven by "
                    "rising middle-class penetration and bank-channel expansion.",
                ),
                (
                    "Bancassurance now accounts for 42% of new APE, a record industry share.",
                    "The bank channel has displaced agency as the largest source of new "
                    "business — a structural shift accelerated by bancassurance partnerships "
                    "across all major insurers.",
                ),
                (
                    "Health claim pressure is mounting across all 15 major players.",
                    "Industry 1H-2024 health claim ratio hit 139.5% (AAJI), squeezing "
                    "underwriting margins. BRI Life held at 121% but the ratio is rising "
                    "+6pp over 12 months.",
                ),
            ],
        },

        # ── 2. Distribution Channels ───────────────────────────────────────────
        {
            "num": "2",
            "title": "Performance Deep Dive — Distribution Channels",
            "intro": (
                "Bancassurance grew 41% YoY for BRI Life — 2.3× faster than the industry "
                "average — shifting the mix decisively toward the BRI bank channel."
            ),
            "points": [
                (
                    "Channel concentration accelerated structurally, not cyclically.",
                    "Bancassurance share of total APE grew from 51% (FY2023) to 67% "
                    "(FY2024). Agency, telemarketing, digital, and worksite channels all "
                    "contracted in absolute APE terms.",
                ),
                (
                    "BRI teller cross-sell reached double the industry bancassurance average.",
                    "Cross-sell via BRI tellers hit 8.4% in Q4, versus the 4.1% industry "
                    "bancassurance average, validating the embedded-distribution model.",
                ),
                (
                    "Q1-2025 pilot signals further conversion upside.",
                    "Q1-2025 trial in 50 BRI Premium branches shows a further +18% conversion "
                    "uplift versus the standard tier; full rollout is planned for Q2-2025.",
                ),
            ],
            "exhibit": {
                "type": "table",
                "caption": "Exhibit 2 — APE by Distribution Channel, FY2023 vs FY2024 (Rp Trillion)",
                "header": ["Channel", "FY2023 (Rp T)", "FY2024 (Rp T)", "Change"],
                "rows": _ch_rows,
                "source": "PolarisBI · report_data (2024)",
            },
        },

        # ── 3. Competitive Comparison ──────────────────────────────────────────
        {
            "num": "3",
            "title": "Competitive Comparison — BRI Life vs Top 3 Peers",
            "intro": (
                "BRI Life shows the strongest growth velocity and deepest bancassurance mix "
                "in the peer group, but trails Prudential and Allianz on absolute RBC and "
                "claim ratio."
            ),
            "points": [
                (
                    "BRI Life leads on growth velocity and channel concentration.",
                    "APE growth of +11.2% YoY ranks #2 in the industry, and a 67% "
                    "bancassurance mix is the highest among the top 5. These are structural "
                    "advantages from BRI's 33,000-outlet ecosystem.",
                ),
                (
                    "Underwriting efficiency and capital headroom lag the front-runners.",
                    "Claim ratio of 121% trails Prudential (108%) and Allianz (115%). "
                    "RBC of 434.6% is adequate but represents the thinnest absolute headroom "
                    "in the peer set ahead of the PSAK 117 transition.",
                ),
            ],
            "exhibit": {
                "type": "comparison",
                "caption": "Exhibit 3 — BRI Life vs Top 3 Peers, Key Metrics FY2024",
                "cols": ["BRI Life", "Prudential", "Allianz", "AIA"],
                "rows": [
                    ["Market Share (APE)",
                     ("11.4%", "#5"), ("18.2%", "#1"), ("13.7%", "#3"), ("12.6%", "#4")],
                    ["APE Growth YoY",
                     ("+11.2%", "#2"), ("+6.8%", "#6"), ("+8.4%", "#5"), ("+5.2%", "#8")],
                    ["RBC Ratio",
                     ("434.6%", "#3"), ("521%", "#1"), ("467%", "#2"), ("443%", "#3")],
                    ["Bancassurance Mix",
                     ("67%", "#1"), ("38%", "#5"), ("42%", "#4"), ("35%", "#6")],
                    ["Claim Ratio",
                     ("121%", "#4"), ("108%", "#1"), ("115%", "#2"), ("112%", "#1")],
                ],
                "source": "PolarisBI · report_data (2024)",
            },
        },

        # ── 4. Top 10 League Table ─────────────────────────────────────────────
        {
            "num": "4",
            "title": "Top 10 Life Insurers — FY2024 League Table",
            "intro": (
                "BRI Life ranks #5 by APE (Rp 3.42T) but #2 by growth velocity (+11.2% YoY) "
                "and #1 by bancassurance mix in the top 10."
            ),
            "points": [
                (
                    "BRI Life punches above its APE rank on growth and channel mix.",
                    "Among the top 10, only FWD Insurance (+14.6%) grew faster than BRI Life "
                    "(+11.2%). BRI Life's 67% bancassurance mix is distinctive value from the "
                    "BRI ecosystem. The watch item: claim ratio at 121% trails leaders "
                    "Prudential (108%) and Allianz (115%).",
                ),
            ],
            "exhibit": {
                "type": "table",
                "caption": "Exhibit 4 — Top 10 Life Insurers in Indonesia, FY2024 (sorted by APE)",
                "header": ["#", "Company", "APE", "YoY", "RBC", "Share", "Claim"],
                "rows": [
                    ["1",  "Prudential Life Assurance", "Rp 5.46T", "+6.8%",  "521%",   "18.2%", "108%"],
                    ["2",  "Allianz Life Indonesia",    "Rp 4.11T", "+8.4%",  "467%",   "13.7%", "115%"],
                    ["3",  "AIA Financial",             "Rp 3.78T", "+5.2%",  "443%",   "12.6%", "112%"],
                    ["4",  "Manulife Indonesia",        "Rp 3.51T", "+9.1%",  "456%",   "11.7%", "118%"],
                    ["5",  "BRI Life",                  "Rp 3.42T", "+11.2%", "434.6%", "11.4%", "121%"],
                    ["6",  "AXA Mandiri",               "Rp 2.18T", "+7.6%",  "412%",   "7.3%",  "119%"],
                    ["7",  "Sequis Life",               "Rp 1.71T", "+4.3%",  "398%",   "5.7%",  "124%"],
                    ["8",  "Sinarmas MSIG",             "Rp 1.32T", "+3.8%",  "387%",   "4.4%",  "127%"],
                    ["9",  "FWD Insurance",             "Rp 0.94T", "+14.6%", "356%",   "3.1%",  "131%"],
                    ["10", "Sun Life Financial",        "Rp 0.87T", "+5.9%",  "421%",   "2.9%",  "116%"],
                ],
                "highlight_row": 4,
                "source": "PolarisBI · report_data (2024)",
            },
        },

        # ── 5. Watch Areas ─────────────────────────────────────────────────────
        {
            "num": "5",
            "title": "Watch Areas — Risks to Monitor in 2025",
            "intro": "Three watch items that could materially shift the 2025 outlook.",
            "points": [
                (
                    "[HIGH] PSAK 117 transition (mandatory Jan 2025).",
                    "IFRS-17-equivalent forces re-measurement of insurance contracts; could "
                    "compress reported FY25 profit by 8–12% even with no underlying change. "
                    "Owner: Finance + Actuarial. Trigger: Audit committee review, Mar 2025.",
                ),
                (
                    "[MEDIUM] Health claim ratio trending toward 130%.",
                    "Industry-wide pressure from medical inflation and adverse selection on "
                    "new health products; BRI Life ratio up +6pp in 12 months. "
                    "Owner: Underwriting + Product. Trigger: Q2 2025 portfolio review.",
                ),
                (
                    "[LOW] BRI 2027 digital pivot may reduce branch foot traffic.",
                    "Bancassurance (67% of APE) depends on physical BRI outlets; long-term "
                    "threat if digital migration accelerates beyond the 2027 plan. "
                    "Owner: Strategy + Distribution. Trigger: BRI Group strategy refresh, Dec 2025.",
                ),
            ],
        },

        # ── 6. Recommendations ────────────────────────────────────────────────
        {
            "num": "6",
            "title": "Priority Recommendations",
            "intro": (
                "Three priority actions to convert FY2024 momentum into FY2025 "
                "market-share gains."
            ),
            "recs": [
                {
                    "title": "Launch Premium Bancassurance Tier in 50 BRI Premium branches",
                    "body": (
                        "Q1-2025 trial showed +18% conversion uplift vs standard tier; "
                        "addressable market of 1.2M premium customers underweighted in "
                        "the current portfolio."
                    ),
                    "owner": "Distribution + Product",
                    "timeline": "Q2 2025 rollout, full coverage by Q4",
                    "metric": "Premium APE share: 4% → 12% by FY25",
                },
                {
                    "title": "Tighten health underwriting bands for ages 50+",
                    "body": (
                        "Claim ratio escalation is concentrated in this cohort (157% vs "
                        "portfolio avg 121%); an 18-month repricing window exists before "
                        "product re-filing."
                    ),
                    "owner": "Underwriting",
                    "timeline": "Q2 2025 model update, Q3 product re-file",
                    "metric": "Claim ratio 121% → 115% by Q4 2025",
                },
                {
                    "title": "Pre-empt PSAK 117 communications to investors and OJK",
                    "body": (
                        "Mandatory Jan-2025 adoption; transparent comms reduces stock "
                        "reaction and signals proactive governance to the market."
                    ),
                    "owner": "IR + Finance",
                    "timeline": "Investor day Q1 2025, OJK briefing Feb",
                    "metric": "Zero negative analyst notes on PSAK 117",
                },
            ],
        },
    ],

    "methodology": {
        "intro": (
            "This briefing was compiled from OJK/AAJI published data, BRI Life annual "
            "reports, and the PolarisBI proprietary industry-aggregate database "
            "(synthetic data following OJK schema, 2024Q1–Q4)."
        ),
        "sources": [
            "OJK Statistik Perasuransian FY2024",
            "AAJI Press Release — 1H 2024 Industry Statistics",
            "BRI Life Annual Report FY2024",
            "PolarisBI DuckDB · industry_aggregate, channel_distribusi, klaim_kategori",
        ],
    },
}
