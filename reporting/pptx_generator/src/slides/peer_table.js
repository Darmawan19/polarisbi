// src/slides/peer_table.js
// Peer table — native addTable with row highlight + commentary band

import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle, addSubtitle } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";
import { addCard } from "../helpers/card.js";

export default async function buildPeerTableSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  if (id.rules.dataChips) addTopRightChip(slide, id, "Peer Table", "gray");
  addActionTitle(slide, id, d.headline || "Peer Comparison");
  if (d.subtitle) addSubtitle(slide, id, d.subtitle);

  const cols = d.columns || [];
  const rows = d.rows  || [];
  if (cols.length === 0 || rows.length === 0) {
    addFooter(slide, id, { pageNum: context.pageNum, totalPages: context.totalPages });
    return;
  }

  const totalW = 13.333 - 2 * id.margins.x;
  const specSum = cols.reduce((s, c) => s + (c.width || 1), 0);
  const colW = cols.map(c => ((c.width || 1) / specSum) * totalW);

  const accentColor  = id.colors.brandAlt || id.colors.brand;
  const highlightFill = id.colors.chips?.blue?.fill || "E8F1FB";

  const headerRow = cols.map(c => ({
    text: c.label || "",
    options: {
      fontFace: id.fonts.sans, fontSize: 10, bold: true,
      color: "FFFFFF",
      fill: { color: id.colors.brand },
      align: c.key === "company" ? "left" : "center",
      valign: "middle",
    },
  }));

  const dataRows = rows.map(row => {
    const isH = row.highlight === true;
    return cols.map(c => ({
      text: String(row[c.key] ?? ""),
      options: {
        fontFace: c.key === "company" || c.key === "rank" ? id.fonts.sans : id.fonts.mono,
        fontSize: 10,
        bold: isH,
        color: isH ? accentColor : id.colors.ink,
        fill: { color: isH ? highlightFill : "FFFFFF" },
        align: c.key === "company" ? "left" : "center",
        valign: "middle",
      },
    }));
  });

  const tableY = id.margins.bodyY + 0.55;
  const rowH = 0.34;

  slide.addTable([headerRow, ...dataRows], cloneOpts({
    x: id.margins.x,
    y: tableY,
    w: totalW,
    rowH,
    colW,
    border: { type: "solid", color: id.colors.line, pt: 0.5 },
  }));

  // === Commentary band ===
  const tableHeight = rowH * (rows.length + 1);
  const bandY = tableY + tableHeight + 0.3;
  const bandH = id.margins.footerY - bandY - 0.25;

  if (bandH > 0.45) {
    const highlightRow = rows.find(r => r.highlight);
    const company = highlightRow?.company || "";

    addCard(slide, id, id.margins.x, bandY, totalW, bandH, {
      fill: id.colors.stripe, borderColor: id.colors.line,
      accentColor, accentSide: "left", accentSize: 0.08,
    });

    slide.addText(`${company.toUpperCase()}  —  POSITIONING`, cloneOpts({
      x: id.margins.x + 0.25, y: bandY + 0.15, w: 8, h: 0.25,
      fontFace: id.fonts.sans, fontSize: 9, bold: true,
      color: accentColor, charSpacing: 4, align: "left", margin: 0,
    }));

    const commentary = d.commentary || "Ranked #5 by APE but #2 by growth velocity (+11.2% YoY) and #1 by bancassurance mix — strong growth from BRI ecosystem leverage.";
    slide.addText(commentary, cloneOpts({
      x: id.margins.x + 0.25, y: bandY + 0.46, w: totalW - 0.5, h: bandH - 0.58,
      fontFace: id.fonts.sans, fontSize: 11,
      color: id.colors.ink, align: "left", valign: "top", margin: 0,
    }));
  }

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
