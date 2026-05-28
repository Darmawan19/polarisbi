// build_session.js — PolarisBI dynamic "session" deck.
// Builds a deck from an Ask-AI session: cover + one finding slide per question
// + recommendations. Reuses the SAME design system as the static deck (theme/lib),
// so the look matches build.js. The static build.js is untouched.
//
// Usage:  node build_session.js <data.json> [out.pptx]
// data.json schema:
// {
//   "meta": { "title", "subtitle", "eyebrow"?, "author"?, "date"? },
//   "findings": [
//     { "question", "takeaway", "analysis",
//       "exhibit": { "type":"chart", "caption", "seriesName", "labels":[], "values":[number] }
//                 | { "type":"table", "caption", "header":[], "rows":[[...]], "highlightRow"?:int, "source"? } }
//   ],
//   "recommendations": [ { "n","h","b","owner","timeline","metric" } ]   // optional
// }
import pptxgen from "pptxgenjs";
import fs from "fs";
import { C, F, G } from "./src/theme.js";
import { makeLib } from "./src/lib.js";

const inPath = process.argv[2];
const outPath = process.argv[3] || "out/PolarisBI-Session-Deck.pptx";
if (!inPath) { console.error("usage: node build_session.js <data.json> [out.pptx]"); process.exit(1); }
const D = JSON.parse(fs.readFileSync(inPath, "utf-8"));
const DEFAULT_SOURCE = "DuckDB · OJK-schema (synthetic, 2024Q1–Q4)";

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = (D.meta && D.meta.author) || "PolarisBI";
pptx.title = (D.meta && D.meta.title) || "PolarisBI Session Report";
const L = makeLib(pptx);

let PAGE = 1; // cover is conceptual page 1; first content slide becomes 2

// ---- session footer (no SECTIONS navbar; left label + page block) -----------
function sfooter(s, leftText) {
  L.hline(s, G.M, G.navY - 0.06, G.CW, C.line, 1);
  L.txt(s, leftText, { x: G.M, y: G.navY, w: 9, h: 0.3,
    fontFace: F.bodySemi, fontSize: 9, color: C.grayLt, charSpacing: 1.2 });
  L.rect(s, { x: G.W - 0.95, y: G.navY - 0.04, w: 0.5, h: 0.38, fill: { color: C.navy }, line: { type: "none" } });
  L.txt(s, String(PAGE), { x: G.W - 0.95, y: G.navY - 0.04, w: 0.5, h: 0.38, align: "center", valign: "middle",
    fontFace: F.display, fontSize: 13, bold: true, color: C.white });
}

function schrome(s, { eyebrow, title, subtitle, source }) {
  PAGE++;
  L.bg(s, C.white);
  L.eyebrow(s, eyebrow);
  L.logo(s);
  L.title(s, title);
  if (subtitle)
    L.txt(s, subtitle, { x: G.M, y: 1.58, w: 11.2, h: 0.34, fontFace: F.body, fontSize: 12, italic: true, color: C.gray });
  if (source) L.source(s, source);
  sfooter(s, "PolarisBI · Generated from Ask-AI session");
}

// ============================================================ COVER
(function cover() {
  const s = pptx.addSlide();
  L.bg(s, C.navy);
  const cx = 11.95, cy = 1.0;
  [0.8, 1.55, 2.4, 3.35, 4.4].forEach((r, i) =>
    L.ell(s, { x: cx - r, y: cy - r, w: r * 2, h: r * 2,
      fill: { type: "none" }, line: { color: i % 2 ? "16335C" : "1E406E", width: 1.1 } }));
  L.ell(s, { x: cx - 0.07, y: cy - 0.07, w: 0.14, h: 0.14, fill: { color: C.blue }, line: { type: "none" } });

  L.rrect(s, { x: G.M, y: G.M, w: 3.7, h: 0.5, rectRadius: 0.25, fill: { type: "none" }, line: { color: "2A4A6A", width: 1.2 } });
  s.addText(
    [{ text: "Polaris", options: { color: C.white, bold: true } },
     { text: "BI", options: { color: C.blue, bold: true } },
     { text: "   ·   Industry Intelligence", options: { color: "9FB3D6", bold: false } }],
    { x: G.M, y: G.M, w: 3.7, h: 0.5, align: "center", valign: "middle", fontFace: F.display, fontSize: 12.5 });

  L.txt(s, ((D.meta && D.meta.eyebrow) || "Generated from your AI session").toUpperCase(), {
    x: G.M, y: 2.7, w: 10.5, h: 0.3, fontFace: F.bodySemi, fontSize: 12, bold: true, color: C.blue, charSpacing: 2.6 });
  L.txt(s, D.meta.title, {
    x: G.M, y: 3.1, w: 10.2, h: 1.5, fontFace: F.display, fontSize: 38, bold: true, color: C.white, lineSpacingMultiple: 1.0 });
  if (D.meta.subtitle)
    L.txt(s, D.meta.subtitle, { x: G.M, y: 4.55, w: 10.5, h: 0.5, fontFace: F.body, fontSize: 14, color: "9FB3D6" });

  L.hline(s, G.M, 6.5, G.CW, "2A4A6A", 1);
  const n = (D.findings && D.findings.length) || 0;
  L.txt(s, `${n} finding${n !== 1 ? "s" : ""}  ·  live DuckDB data`, {
    x: G.M, y: 6.62, w: 7, h: 0.3, fontFace: F.bodySemi, fontSize: 10, color: "9FB3D6", charSpacing: 0.6 });
  L.txt(s, `${D.meta.author || ""}${D.meta.date ? "   ·   " + D.meta.date : ""}`, {
    x: G.W - G.M - 6, y: 6.62, w: 6, h: 0.3, align: "right", fontFace: F.body, fontSize: 10, color: C.white });
})();

// ============================================================ FINDING — CHART
function findingChart(f, i) {
  const s = pptx.addSlide();
  schrome(s, { eyebrow: `Finding ${i} · Ask-AI`, title: f.takeaway,
    subtitle: `\u201C${f.question}\u201D`, source: f.exhibit.source || DEFAULT_SOURCE });

  const lx = G.M, ly = 2.1, lw = 7.15, lh = 4.25;
  L.card(s, { x: lx, y: ly, w: lw, h: lh, fill: C.cardBg });
  L.band(s, { x: lx, y: ly, w: lw, text: f.exhibit.caption || "", align: "left", size: 11 });
  s.addChart(pptx.ChartType.bar,
    [{ name: f.exhibit.seriesName || "Value", labels: f.exhibit.labels, values: f.exhibit.values }], {
      x: lx + 0.2, y: ly + 0.62, w: lw - 0.45, h: lh - 0.95,
      barDir: "col", chartColors: [C.royal], barGapWidthPct: 55,
      showValue: true, dataLabelFontFace: F.bodySemi, dataLabelFontSize: 11, dataLabelColor: C.navy,
      dataLabelPosition: "outEnd", dataLabelFormatCode: f.exhibit.valueFormat || "#,##0.0",
      showLegend: false, showTitle: false,
      catAxisLabelFontFace: F.body, catAxisLabelFontSize: 10.5, catAxisLabelColor: C.gray,
      catAxisLineShow: false, valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0,
    });

  const rx = 8.0, rw = G.W - G.M - rx, ry = 2.1, rh = 4.25;
  L.card(s, { x: rx, y: ry, w: rw, h: rh });
  L.txt(s, "READOUT", { x: rx + 0.28, y: ry + 0.28, w: rw - 0.5, h: 0.24,
    fontFace: F.bodySemi, fontSize: 9.5, bold: true, color: C.royal, charSpacing: 1.4 });
  L.txt(s, f.analysis, { x: rx + 0.28, y: ry + 0.62, w: rw - 0.56, h: rh - 0.95,
    fontFace: F.body, fontSize: 11, color: C.ink, lineSpacingMultiple: 1.22, valign: "top" });
}

// ============================================================ FINDING — TABLE
function findingTable(f, i) {
  const s = pptx.addSlide();
  const ex = f.exhibit;
  schrome(s, { eyebrow: `Finding ${i} · Ask-AI`, title: f.takeaway,
    subtitle: `\u201C${f.question}\u201D`, source: ex.source || DEFAULT_SOURCE });

  L.txt(s, ex.caption || "", { x: G.M, y: 1.98, w: G.CW, h: 0.26,
    fontFace: F.bodySemi, fontSize: 10, color: C.gray, charSpacing: 0.6 });

  const ncol = ex.header.length;
  const rows = (ex.rows || []).slice(0, 10);
  const first = ncol <= 3 ? 4.6 : 3.6;
  const rest = (G.CW - first) / (ncol - 1);
  const colW = [first, ...Array(ncol - 1).fill(rest)];

  const ty = 2.32, readoutH = 0.98, bottomLimit = 6.35;
  const avail = bottomLimit - ty - readoutH - 0.1;
  const rowH = Math.min(0.34, avail / (rows.length + 1));

  const headRow = ex.header.map((h, ci) => ({ text: String(h),
    options: { fill: { color: C.navy }, color: C.white, bold: true, fontFace: F.semi,
      fontSize: 11, align: ci === 0 ? "left" : "right", valign: "middle" } }));
  const bodyRows = rows.map((r, ri) => {
    const hl = ri === ex.highlightRow;
    return r.map((cell, ci) => ({ text: String(cell),
      options: { fill: { color: hl ? C.blueSoft : (ri % 2 ? "F7F9FC" : C.white) },
        color: hl ? C.royal : C.ink, bold: hl, fontFace: hl ? F.bodySemi : F.body,
        fontSize: 11, align: ci === 0 ? "left" : "right", valign: "middle" } }));
  });
  s.addTable([headRow, ...bodyRows], {
    x: G.M, y: ty, w: G.CW, colW, rowH,
    border: { type: "solid", color: C.line, pt: 0.5 },
    fontFace: F.body, valign: "middle", margin: [1, 6, 1, 6], autoPage: false });

  const by = ty + rowH * (rows.length + 1) + 0.14;
  L.rect(s, { x: G.M, y: by, w: G.CW, h: readoutH, fill: { color: C.cardBg }, line: { type: "none" } });
  L.rect(s, { x: G.M, y: by, w: 0.09, h: readoutH, fill: { color: C.royal }, line: { type: "none" } });
  L.txt(s, "READOUT", { x: G.M + 0.3, y: by + 0.1, w: 8, h: 0.22,
    fontFace: F.bodySemi, fontSize: 9.5, color: C.royal, charSpacing: 1.4, bold: true });
  L.txt(s, f.analysis, { x: G.M + 0.3, y: by + 0.34, w: G.CW - 0.6, h: readoutH - 0.42,
    fontFace: F.body, fontSize: 10.5, color: C.ink, lineSpacingMultiple: 1.12, valign: "top" });
}

// ============================================================ RECOMMENDATIONS
function recsSlide(recs) {
  const s = pptx.addSlide();
  schrome(s, { eyebrow: "Recommendations · Ask-AI",
    title: "What this suggests", source: "Synthesised from the findings above" });

  const top = 2.15, gap = 0.18;
  const ch = (6.3 - top - gap * (recs.length - 1)) / recs.length;
  recs.forEach((r, idx) => {
    const y = top + idx * (ch + gap);
    L.card(s, { x: G.M, y, w: G.CW, h: ch, fill: C.white, line: C.line });
    L.rect(s, { x: G.M, y, w: 1.15, h: ch, fill: { color: C.royal }, line: { type: "none" } });
    L.txt(s, "PRIORITY", { x: G.M, y: y + 0.18, w: 1.15, h: 0.24, align: "center",
      fontFace: F.bodySemi, fontSize: 8, color: "AFC6EA", charSpacing: 1.4 });
    L.txt(s, String(r.n || idx + 1), { x: G.M, y: y + 0.34, w: 1.15, h: ch - 0.5, align: "center", valign: "middle",
      fontFace: F.display, fontSize: 40, bold: true, color: C.white });
    const tx = G.M + 1.4, tw = 6.7;
    L.txt(s, r.h, { x: tx, y: y + 0.2, w: tw, h: 0.5, fontFace: F.semi, fontSize: 13, color: C.navy, lineSpacingMultiple: 1.0 });
    L.txt(s, r.b, { x: tx, y: y + 0.76, w: tw, h: ch - 0.9, fontFace: F.body, fontSize: 10, color: C.ink, lineSpacingMultiple: 1.08 });
    const mx = G.M + G.CW - 3.6, mw = 3.55;
    const meta = [["OWNER", r.owner], ["TIMELINE", r.timeline], ["TARGET", r.metric]];
    let my = y + 0.18;
    meta.forEach(([lab, val]) => {
      if (!val) return;
      L.txt(s, lab, { x: mx, y: my, w: mw, h: 0.2, fontFace: F.bodySemi, fontSize: 8, color: C.royal, charSpacing: 1.2, bold: true });
      L.txt(s, val, { x: mx, y: my + 0.17, w: mw, h: 0.26, fontFace: F.body, fontSize: 9, color: C.ink, lineSpacingMultiple: 1.0 });
      my += 0.42;
    });
  });
}

// ============================================================ DRIVE
(D.findings || []).forEach((f, idx) => {
  const i = idx + 1;
  if (f.exhibit && f.exhibit.type === "chart") findingChart(f, i);
  else findingTable(f, i);
});
if (D.recommendations && D.recommendations.length) recsSlide(D.recommendations);

const OUT = outPath;
await pptx.writeFile({ fileName: OUT });
console.log("WROTE", OUT);
