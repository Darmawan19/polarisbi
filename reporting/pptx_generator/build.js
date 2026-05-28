import pptxgen from "pptxgenjs";
import { C, F, G } from "./src/theme.js";
import { makeLib } from "./src/lib.js";
import { DATA as D } from "./src/data.js";

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pptx.author = D.meta.author;
pptx.title = D.meta.title;
const L = makeLib(pptx);

// ============================================================ SLIDE 1 — COVER
(function cover() {
  const s = pptx.addSlide();
  L.bg(s, C.navy);
  // radar / polaris concentric motif (top-right)
  const cx = 11.95, cy = 1.0;
  [0.8, 1.55, 2.4, 3.35, 4.4].forEach((r, i) =>
    L.ell(s, { x: cx - r, y: cy - r, w: r * 2, h: r * 2,
      fill: { type: "none" }, line: { color: i % 2 ? "16335C" : "1E406E", width: 1.1 } })
  );
  L.ell(s, { x: cx - 0.07, y: cy - 0.07, w: 0.14, h: 0.14, fill: { color: C.blue }, line: { type: "none" } });

  // logo pill (top-left)
  L.rrect(s, { x: G.M, y: G.M, w: 3.5, h: 0.5, rectRadius: 0.25,
    fill: { type: "none" }, line: { color: "2A4A6A", width: 1.2 } });
  s.addText(
    [{ text: "Polaris", options: { color: C.white, bold: true } },
     { text: "BI", options: { color: C.blue, bold: true } },
     { text: "   ·   Industry Intelligence", options: { color: "9FB3D6", bold: false } }],
    { x: G.M, y: G.M, w: 3.5, h: 0.5, align: "center", valign: "middle",
      fontFace: F.display, fontSize: 12.5 });

  // eyebrow + title + subtitle
  L.txt(s, "BRI LIFE  ·  FY2024 INDUSTRY BRIEFING", {
    x: G.M, y: 2.55, w: 9, h: 0.3, fontFace: F.bodySemi, fontSize: 12, bold: true,
    color: C.blue, charSpacing: 2.6 });
  L.txt(s, D.meta.title, {
    x: G.M, y: 2.95, w: 8.8, h: 1.5, fontFace: F.display, fontSize: 40, bold: true,
    color: C.white, lineSpacingMultiple: 1.0 });
  L.txt(s, D.meta.subtitle, {
    x: G.M, y: 4.35, w: 8.2, h: 0.5, fontFace: F.body, fontSize: 15.5, color: "AEBFD8" });

  // KPI preview strip
  const stripY = 5.35, items = D.kpis, n = items.length, gap = 0.0;
  const w = (G.CW) / n;
  L.hline(s, G.M, stripY - 0.18, G.CW, "1E406E", 1);
  items.forEach((k, i) => {
    const x = G.M + i * w;
    if (i) s.addShape(L.S.line, { x, y: stripY + 0.05, w: 0, h: 0.9, line: { color: "1E406E", width: 1 } });
    L.txt(s, k.value, { x: x + (i ? 0.25 : 0), y: stripY, w: w - 0.3, h: 0.55,
      fontFace: F.display, fontSize: 25, bold: true, color: C.white, valign: "middle" });
    L.txt(s, k.label, { x: x + (i ? 0.25 : 0), y: stripY + 0.62, w: w - 0.3, h: 0.3,
      fontFace: F.body, fontSize: 10, color: "8FA4C6" });
  });

  // footer
  L.hline(s, G.M, 6.85, G.CW, "1E406E", 1);
  L.txt(s, `${D.meta.author}   ·   ${D.meta.org}`, {
    x: G.M, y: 6.98, w: 8, h: 0.3, fontFace: F.body, fontSize: 11, color: "9FB3D6" });
  L.txt(s, D.meta.date, {
    x: G.W - 3.05, y: 6.98, w: 2.5, h: 0.3, align: "right", fontFace: F.body, fontSize: 11, color: "9FB3D6" });
})();

// helper for standard content-slide chrome
function chrome(s, { eyebrow, title, section, page, source, subtitle }) {
  L.bg(s, C.white);
  L.eyebrow(s, eyebrow);
  L.logo(s);
  L.title(s, title);
  if (subtitle)
    L.txt(s, subtitle, { x: G.M, y: 1.62, w: 11, h: 0.32, fontFace: F.body, fontSize: 12.5,
      italic: true, color: C.gray });
  if (source) L.source(s, source);
  L.navbar(s, section, page);
}

// ============================================================ SLIDE 2 — MARKET
(function market() {
  const s = pptx.addSlide();
  chrome(s, { eyebrow: "Market Context", section: "MARKET", page: 2,
    title: "Indonesia's life-insurance market grew 9.3% in FY2024, with\nbancassurance emerging as the primary growth engine",
    source: "OJK Statistik Perasuransian FY2024; AAJI Q4 Bulletin" });

  // left card with chart
  const lx = G.M, lw = 6.75, ly = G.contentTop, lh = 4.35;
  L.card(s, { x: lx, y: ly, w: lw, h: lh, fill: C.cardBg });
  L.band(s, { x: lx, y: ly, w: lw, text: "Indonesia life-insurance gross premium  (Rp Trillion)", align: "left", size: 11.5 });
  s.addChart(pptx.ChartType.bar, [{ name: "Premium", labels: D.market.trend.labels, values: D.market.trend.values }], {
    x: lx + 0.2, y: ly + 0.62, w: lw - 0.45, h: lh - 0.95,
    barDir: "col", chartColors: [C.royal], barGapWidthPct: 55,
    showValue: true, dataLabelFontFace: F.bodySemi, dataLabelFontSize: 11, dataLabelColor: C.navy,
    dataLabelPosition: "outEnd", dataLabelFormatCode: '#,##0.0',
    showLegend: false, showTitle: false,
    catAxisLabelFontFace: F.body, catAxisLabelFontSize: 10.5, catAxisLabelColor: C.gray,
    catAxisLineShow: false, valAxisHidden: true, valGridLine: { style: "none" },
    valAxisMaxVal: 270, valAxisMinVal: 0,
  });

  // right: 3 fact cards
  const rx = 7.6, rw = G.W - G.M - rx, fy = G.contentTop, fh = 1.34, fgap = 0.16;
  D.market.facts.forEach((f, i) => {
    const y = fy + i * (fh + fgap);
    L.card(s, { x: rx, y, w: rw, h: fh, dashed: true });
    L.iconCircle(s, { x: rx + 0.22, y: y + 0.26, d: 0.62, icon: f.icon, color: "royal" });
    L.txt(s, f.h, { x: rx + 1.05, y: y + 0.18, w: rw - 1.25, h: 0.34,
      fontFace: F.semi, fontSize: 12.5, color: C.navy });
    L.txt(s, f.b, { x: rx + 1.05, y: y + 0.55, w: rw - 1.25, h: 0.7,
      fontFace: F.body, fontSize: 10, color: C.ink, lineSpacingMultiple: 1.08 });
  });
})();

// ===================================================== SLIDE 3 — EXEC SUMMARY
(function exec() {
  const s = pptx.addSlide();
  chrome(s, { eyebrow: "Executive Summary", section: "PERFORMANCE", page: 3,
    title: "BRI Life captured 11.4% of new APE in FY2024, driven by\nbancassurance acceleration across BRI's 33,000-outlet network",
    source: "OJK Statistik Perasuransian FY2024; AAJI Q4 Bulletin; BRI Life Annual Report" });

  const cols = D.scr, n = cols.length, gap = 0.35;
  const cw = (G.CW - gap * (n - 1)) / n, cy = 2.15, ch = 4.05;
  cols.forEach((c, i) => {
    const x = G.M + i * (cw + gap);
    L.card(s, { x, y: cy, w: cw, h: ch });
    L.rect(s, { x, y: cy, w: cw, h: 0.09, fill: { color: C.royal }, line: { type: "none" } }); // top accent
    L.iconCircle(s, { x: x + 0.3, y: cy + 0.35, d: 0.8, icon: c.icon, color: "royal" });
    L.txt(s, c.tag.toUpperCase(), { x: x + 1.25, y: cy + 0.5, w: cw - 1.5, h: 0.5,
      fontFace: F.semi, fontSize: 14, color: C.royal, charSpacing: 1.2, valign: "middle" });
    L.hline(s, x + 0.3, cy + 1.32, cw - 0.6, C.line, 1);
    // body sits in a fixed box; copy is trimmed to <=4 lines so it never reaches the divider
    L.txt(s, c.b, { x: x + 0.3, y: cy + 1.48, w: cw - 0.6, h: 1.2,
      fontFace: F.body, fontSize: 11, color: C.ink, lineSpacingMultiple: 1.16 });
    // bottom key figure — divider placed below the body box with a guaranteed gap
    const fy = cy + 2.82;
    L.hline(s, x + 0.3, fy, cw - 0.6, C.line, 1);
    L.txt(s, "KEY FIGURE", { x: x + 0.3, y: fy + 0.1, w: cw - 0.6, h: 0.2,
      fontFace: F.bodySemi, fontSize: 8.5, color: C.grayLt, charSpacing: 1.4, bold: true });
    L.txt(s, c.fig, { x: x + 0.28, y: fy + 0.3, w: cw - 0.5, h: 0.5,
      fontFace: F.display, fontSize: 28, bold: true, color: C.royal, valign: "middle" });
    L.txt(s, c.figLabel, { x: x + 0.3, y: fy + 0.84, w: cw - 0.55, h: 0.3,
      fontFace: F.body, fontSize: 9, color: C.gray, lineSpacingMultiple: 1.05 });
  });
})();

// ====================================================== SLIDE 4 — KPI DASHBOARD
(function kpi() {
  const s = pptx.addSlide();
  chrome(s, { eyebrow: "Performance · Key Metrics", section: "PERFORMANCE", page: 4,
    title: "Four metrics that prove the bancassurance thesis",
    source: "BRI Life Audited Financial Statements FY2024" });

  const n = D.kpis.length, gap = 0.3, tw = (G.CW - gap * (n - 1)) / n, ty = 1.95, th = 2.45;
  D.kpis.forEach((k, i) => {
    const x = G.M + i * (tw + gap);
    L.card(s, { x, y: ty, w: tw, h: th });
    L.rect(s, { x, y: ty, w: 0.08, h: th, fill: { color: C.royal }, line: { type: "none" } });
    L.iconCircle(s, { x: x + 0.28, y: ty + 0.28, d: 0.62, icon: k.icon, color: "royal" });
    L.txt(s, k.label.toUpperCase(), { x: x + 0.28, y: ty + 1.02, w: tw - 0.5, h: 0.3,
      fontFace: F.bodySemi, fontSize: 9.5, color: C.gray, charSpacing: 0.8 });
    L.txt(s, k.value, { x: x + 0.26, y: ty + 1.3, w: tw - 0.4, h: 0.6,
      fontFace: F.display, fontSize: 26, bold: true, color: C.navy, valign: "middle" });
    s.addText([{ text: "▲ ", options: { color: C.green } }, { text: k.delta, options: { color: C.green } }],
      { x: x + 0.28, y: ty + 1.95, w: tw - 0.5, h: 0.3, fontFace: F.bodySemi, fontSize: 10.5, bold: true });
  });

  // context band
  const cby = ty + th + 0.45;
  L.txt(s, "CONTEXT & INTERPRETATION", { x: G.M, y: cby, w: 6, h: 0.3,
    fontFace: F.bodySemi, fontSize: 10.5, color: C.royal, charSpacing: 1.6, bold: true });
  L.hline(s, G.M, cby + 0.34, 3.0, C.royal, 2);
  const ccn = D.kpiContext.length, cgap = 0.5, ccw = (G.CW - cgap * (ccn - 1)) / ccn, ccy = cby + 0.55;
  D.kpiContext.forEach((c, i) => {
    const x = G.M + i * (ccw + cgap);
    L.txt(s, c.h, { x, y: ccy, w: ccw, h: 0.3, fontFace: F.semi, fontSize: 12, color: C.navy });
    L.txt(s, c.b, { x, y: ccy + 0.36, w: ccw, h: 0.8, fontFace: F.body, fontSize: 10.5,
      color: C.ink, lineSpacingMultiple: 1.12 });
  });
})();

// ====================================================== SLIDE 5 — DEEP DIVE
(function deepdive() {
  const s = pptx.addSlide();
  chrome(s, { eyebrow: "Performance · Deep Dive", section: "PERFORMANCE", page: 5,
    title: "Bancassurance grew 41% YoY for BRI Life — 2.3× faster than\nthe industry average",
    subtitle: "APE contribution by distribution channel, FY2023 vs FY2024 (Rp Trillion)",
    source: "BRI Life Distribution Channel MIS; internal cross-sell data" });

  // chart card
  const lx = G.M, lw = 7.05, ly = 2.15, lh = 4.2;
  L.card(s, { x: lx, y: ly, w: lw, h: lh, fill: C.cardBg });
  s.addChart(pptx.ChartType.bar, [
    { name: "FY2023", labels: D.channels.labels, values: D.channels.fy23 },
    { name: "FY2024", labels: D.channels.labels, values: D.channels.fy24 },
  ], {
    x: lx + 0.15, y: ly + 0.2, w: lw - 0.35, h: lh - 0.95,
    barDir: "col", barGrouping: "clustered", chartColors: ["C7D2E2", C.royal], barGapWidthPct: 35,
    showValue: true, dataLabelFontFace: F.bodySemi, dataLabelFontSize: 8.5, dataLabelColor: C.navy,
    dataLabelPosition: "outEnd", dataLabelFormatCode: '0.00"T"',
    showLegend: true, legendPos: "t", legendFontFace: F.bodySemi, legendFontSize: 10, legendColor: C.gray,
    showTitle: false,
    catAxisLabelFontFace: F.body, catAxisLabelFontSize: 8.5, catAxisLabelColor: C.gray,
    catAxisLineShow: false, valAxisHidden: true, valGridLine: { style: "none" },
    valAxisMaxVal: 2.6, valAxisMinVal: 0,
  });
  // bottom highlight strip inside card
  L.band(s, { x: lx + 0.15, y: ly + lh - 0.62, w: lw - 0.3, h: 0.46,
    text: "▲  41% bancassurance APE growth, FY24 vs FY23", align: "center", size: 12 });

  // right insights
  const rx = 8.0, rw = G.W - G.M - rx, iy = 2.2;
  L.txt(s, "KEY INSIGHTS", { x: rx, y: iy, w: rw, h: 0.3, fontFace: F.bodySemi, fontSize: 11,
    color: C.royal, charSpacing: 1.6, bold: true });
  L.hline(s, rx, iy + 0.32, 1.7, C.royal, 2);
  const items = D.channels.insights, ih = 1.18, igap = 0.18, iy0 = iy + 0.55;
  items.forEach((it, i) => {
    const y = iy0 + i * (ih + igap);
    L.ell(s, { x: rx, y, w: 0.5, h: 0.5, fill: { color: C.royal }, line: { type: "none" } });
    L.txt(s, String(i + 1), { x: rx, y, w: 0.5, h: 0.5, align: "center", valign: "middle",
      fontFace: F.display, fontSize: 15, bold: true, color: C.white });
    L.txt(s, it.h, { x: rx + 0.68, y: y - 0.02, w: rw - 0.68, h: 0.3, fontFace: F.semi, fontSize: 12.5, color: C.navy });
    L.txt(s, it.b, { x: rx + 0.68, y: y + 0.3, w: rw - 0.68, h: 0.78, fontFace: F.body, fontSize: 10,
      color: C.ink, lineSpacingMultiple: 1.1 });
  });
})();

// ===================================================== SLIDE 6 — COMPARISON
(function comparison() {
  const s = pptx.addSlide();
  chrome(s, { eyebrow: "Competition", section: "COMPETITION", page: 6,
    title: "BRI Life vs top 3 peers — strong in growth velocity, behind on\nRBC efficiency",
    subtitle: "FY2024 key metrics, top 4 insurers by market share",
    source: "OJK Statistik Perasuransian Q4 2024; company filings" });

  const cmp = D.compare;
  const tx = G.M, ty = 2.25;
  const labelW = 2.7, colW = (G.CW - labelW) / cmp.cols.length;
  const headH = 0.56, rowH = 0.52;

  // header
  L.txt(s, "METRIC", { x: tx + 0.1, y: ty, w: labelW, h: headH, valign: "middle",
    fontFace: F.bodySemi, fontSize: 10, color: C.gray, charSpacing: 1.2 });
  cmp.cols.forEach((c, i) => {
    const x = tx + labelW + i * colW;
    const hl = i === cmp.highlight;
    L.rect(s, { x, y: ty, w: colW - 0.1, h: headH, fill: { color: hl ? C.navy : "EEF1F6" }, line: { type: "none" } });
    L.txt(s, c, { x, y: ty, w: colW - 0.1, h: headH, align: "center", valign: "middle",
      fontFace: F.semi, fontSize: 13, color: hl ? C.white : C.ink });
  });

  // rows
  cmp.rows.forEach((r, ri) => {
    const y = ty + headH + ri * rowH;
    L.txt(s, r.m, { x: tx + 0.1, y, w: labelW, h: rowH, valign: "middle",
      fontFace: F.body, fontSize: 11, color: C.gray });
    r.v.forEach((val, ci) => {
      const x = tx + labelW + ci * colW;
      const hl = ci === cmp.highlight;
      if (hl) L.rect(s, { x, y, w: colW - 0.1, h: rowH, fill: { color: C.blueSoft }, line: { type: "none" } });
      L.txt(s, val, { x: x + 0.12, y, w: colW - 1.0, h: rowH, valign: "middle", align: "left",
        fontFace: hl ? F.semi : F.bodyMed, fontSize: 13, color: hl ? C.royal : C.ink });
      // rank chip
      L.rrect(s, { x: x + colW - 0.92, y: y + rowH / 2 - 0.13, w: 0.62, h: 0.26, rectRadius: 0.13,
        fill: { color: hl ? "D7E4FA" : "EDEFF3" }, line: { type: "none" } });
      L.txt(s, r.rank[ci], { x: x + colW - 0.92, y: y + rowH / 2 - 0.13, w: 0.62, h: 0.26,
        align: "center", valign: "middle", fontFace: F.bodySemi, fontSize: 9, color: hl ? C.royal : C.gray });
    });
    if (ri < cmp.rows.length - 1) L.hline(s, tx, y + rowH, G.CW, C.line, 0.75);
  });

  // readout band
  const by = ty + headH + cmp.rows.length * rowH + 0.16;
  L.rect(s, { x: tx, y: by, w: G.CW, h: 0.82, fill: { color: C.cardBg }, line: { type: "none" } });
  L.rect(s, { x: tx, y: by, w: 0.09, h: 0.82, fill: { color: C.royal }, line: { type: "none" } });
  L.txt(s, "STRATEGIC READOUT", { x: tx + 0.3, y: by + 0.1, w: 8, h: 0.26,
    fontFace: F.bodySemi, fontSize: 10, color: C.royal, charSpacing: 1.4, bold: true });
  L.txt(s, cmp.readout, { x: tx + 0.3, y: by + 0.34, w: G.CW - 0.6, h: 0.44,
    fontFace: F.body, fontSize: 10.5, color: C.ink, lineSpacingMultiple: 1.08 });
})();

// ===================================================== SLIDE 7 — PEER TABLE
(function peers() {
  const s = pptx.addSlide();
  chrome(s, { eyebrow: "Competition · League Table", section: "COMPETITION", page: 7,
    title: "Top 10 life insurers in Indonesia, FY2024 — BRI Life ranks #5 by APE",
    subtitle: "Sorted by APE (Annualized Premium Equivalent), in Rp Trillion",
    source: "OJK Statistik Perasuransian Q4 2024; company filings (audited)" });

  const p = D.peers;
  const colW = [0.6, 3.95, 1.55, 1.3, 1.5, 1.45, 1.4];
  const headRow = p.header.map((h, i) => ({
    text: h, options: { fill: { color: C.navy }, color: C.white, bold: true, fontFace: F.semi,
      fontSize: 11.5, align: i <= 1 ? "left" : "right", valign: "middle" } }));
  const bodyRows = p.rows.map((r, ri) => {
    const hl = ri === p.highlightRow;
    return r.map((cell, ci) => ({
      text: cell,
      options: {
        fill: { color: hl ? C.blueSoft : (ri % 2 ? "F7F9FC" : C.white) },
        color: hl ? C.royal : (ci === 1 ? C.ink : C.ink),
        bold: hl, fontFace: hl ? F.bodySemi : (ci === 1 ? F.bodyMed : F.body),
        fontSize: 11, align: ci <= 1 ? "left" : "right", valign: "middle",
      },
    }));
  });
  s.addTable([headRow, ...bodyRows], {
    x: G.M, y: 2.15, w: G.CW, colW, rowH: 0.33,
    border: { type: "solid", color: C.line, pt: 0.5 },
    fontFace: F.body, valign: "middle", margin: [1, 6, 1, 6], autoPage: false,
  });

  // readout
  const by = 2.15 + 0.33 * 11 + 0.12;
  L.rect(s, { x: G.M, y: by, w: G.CW, h: 0.66, fill: { color: C.cardBg }, line: { type: "none" } });
  L.rect(s, { x: G.M, y: by, w: 0.09, h: 0.66, fill: { color: C.royal }, line: { type: "none" } });
  L.txt(s, "BRI LIFE — POSITIONING", { x: G.M + 0.3, y: by + 0.08, w: 8, h: 0.24,
    fontFace: F.bodySemi, fontSize: 9.5, color: C.royal, charSpacing: 1.4, bold: true });
  L.txt(s, p.readout, { x: G.M + 0.3, y: by + 0.3, w: G.CW - 0.6, h: 0.34,
    fontFace: F.body, fontSize: 10, color: C.ink, lineSpacingMultiple: 1.06 });
})();

// ===================================================== SLIDE 8 — WATCH AREAS
(function watch() {
  const s = pptx.addSlide();
  chrome(s, { eyebrow: "Actions · Risk Watch", section: "ACTIONS", page: 8,
    title: "Three watch items that could materially shift the 2025 outlook",
    subtitle: "Ranked by likely impact on BRI Life FY2025 net profit",
    source: "Internal risk register; PSAK 117 readiness audit" });

  const sevColor = { red: C.red, amber: C.amber, green: C.green };
  const cy0 = 2.15, ch = 1.36, gap = 0.18;
  D.watch.forEach((w, i) => {
    const y = cy0 + i * (ch + gap);
    L.card(s, { x: G.M, y, w: G.CW, h: ch });
    L.rect(s, { x: G.M, y, w: 0.1, h: ch, fill: { color: sevColor[w.color] }, line: { type: "none" } });
    L.iconCircle(s, { x: G.M + 0.32, y: y + ch / 2 - 0.31, d: 0.62, icon: w.icon, color: w.color,
      circleFill: w.color === "red" ? "FBE9E9" : w.color === "amber" ? "FBF1E0" : "E7F5EE" });
    // pill + heading
    L.pill(s, { x: G.M + 1.2, y: y + 0.2, w: 0.95, text: w.sev, fill: sevColor[w.color] });
    L.txt(s, w.h, { x: G.M + 2.3, y: y + 0.16, w: 6.4, h: 0.34, fontFace: F.semi, fontSize: 12.5, color: C.navy });
    L.txt(s, w.b, { x: G.M + 1.2, y: y + 0.56, w: 7.5, h: 0.72, fontFace: F.body, fontSize: 10,
      color: C.ink, lineSpacingMultiple: 1.08 });
    // meta right
    const mx = G.M + G.CW - 3.0;
    L.txt(s, "OWNER", { x: mx, y: y + 0.18, w: 2.8, h: 0.22, fontFace: F.bodySemi, fontSize: 8.5,
      color: C.grayLt, charSpacing: 1.2, bold: true });
    L.txt(s, w.owner, { x: mx, y: y + 0.38, w: 2.8, h: 0.26, fontFace: F.bodySemi, fontSize: 10.5, color: C.navy });
    L.txt(s, "NEXT TRIGGER", { x: mx, y: y + 0.72, w: 2.8, h: 0.22, fontFace: F.bodySemi, fontSize: 8.5,
      color: C.grayLt, charSpacing: 1.2, bold: true });
    L.txt(s, w.trigger, { x: mx, y: y + 0.92, w: 2.8, h: 0.3, fontFace: F.body, fontSize: 10, color: C.ink });
  });
})();

// =================================================== SLIDE 9 — RECOMMENDATIONS
(function recs() {
  const s = pptx.addSlide();
  chrome(s, { eyebrow: "Actions · Priority Moves", section: "ACTIONS", page: 9,
    title: "Three priority actions to convert FY2024 momentum into\nFY2025 market-share gains",
    source: "Strategy committee; internal portfolio analytics" });

  const cy0 = 2.05, ch = 1.43, gap = 0.18;
  D.recs.forEach((r, i) => {
    const y = cy0 + i * (ch + gap);
    L.card(s, { x: G.M, y, w: G.CW, h: ch });
    // number block
    L.rect(s, { x: G.M, y, w: 1.15, h: ch, fill: { color: C.royal }, line: { type: "none" } });
    L.txt(s, "PRIORITY", { x: G.M, y: y + 0.2, w: 1.15, h: 0.24, align: "center",
      fontFace: F.bodySemi, fontSize: 8, color: "AFC6EA", charSpacing: 1.4 });
    L.txt(s, r.n, { x: G.M, y: y + 0.36, w: 1.15, h: 0.9, align: "center", valign: "middle",
      fontFace: F.display, fontSize: 44, bold: true, color: C.white });
    // middle
    const tx = G.M + 1.4, tw = 6.7;
    L.txt(s, r.h, { x: tx, y: y + 0.18, w: tw, h: 0.5, fontFace: F.semi, fontSize: 13, color: C.navy,
      lineSpacingMultiple: 1.0 });
    L.txt(s, r.b, { x: tx, y: y + 0.72, w: tw, h: 0.6, fontFace: F.body, fontSize: 10,
      color: C.ink, lineSpacingMultiple: 1.08 });
    // meta right
    const mx = G.M + G.CW - 3.6, mw = 3.55;
    const meta = [["OWNER", r.owner], ["TIMELINE", r.timeline], ["SUCCESS METRIC", r.metric]];
    let my = y + 0.13;
    meta.forEach(([lab, val]) => {
      L.txt(s, lab, { x: mx, y: my, w: mw, h: 0.2, fontFace: F.bodySemi, fontSize: 8,
        color: C.royal, charSpacing: 1.2, bold: true });
      L.txt(s, val, { x: mx, y: my + 0.17, w: mw, h: 0.26, fontFace: F.body, fontSize: 9,
        color: C.ink, lineSpacingMultiple: 1.0 });
      my += 0.40;
    });
  });
})();

// ----- export
const OUT = "out/PolarisBI-BRILife-FY2024.pptx";
await pptx.writeFile({ fileName: OUT });
console.log("WROTE", OUT);
