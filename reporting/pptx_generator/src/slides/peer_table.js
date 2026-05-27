// src/slides/peer_table.js
import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle, addSubtitle } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";

export default async function buildPeerTableSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  addActionTitle(slide, id, d.headline || "Peer Comparison");
  if (d.subtitle) addSubtitle(slide, id, d.subtitle);
  if (id.rules.dataChips) addTopRightChip(slide, id, "PEER TABLE", "gray");

  const cols = d.columns || [];
  const rows = d.rows  || [];
  if (cols.length === 0 || rows.length === 0) {
    addFooter(slide, id, { pageNum: context.pageNum, totalPages: context.totalPages });
    return;
  }

  const totalW = 13.333 - 2 * id.margins.x;
  const specSum = cols.reduce((s, c) => s + (c.width || 1), 0);
  const colW = cols.map(c => ((c.width || 1) / specSum) * totalW);

  const highlightFill = id.colors.chips?.blue?.fill || "E8F1FB";
  const highlightText = id.colors.brandAlt || id.colors.brand;

  // Header row
  const headerRow = cols.map(c => ({
    text: c.label || "",
    options: {
      fontFace: id.fonts.sans, fontSize: 9, bold: true,
      color: "FFFFFF",
      fill: { color: id.colors.brand },
      align: "center", valign: "middle",
    },
  }));

  // Data rows
  const dataRows = rows.map(row => {
    const isH = row.highlight === true;
    return cols.map(c => ({
      text: String(row[c.key] ?? ""),
      options: {
        fontFace: id.fonts.sans, fontSize: 9,
        bold: isH,
        color: isH ? highlightText : id.colors.ink,
        fill: { color: isH ? highlightFill : "FFFFFF" },
        align: c.key === "company" ? "left" : "center",
        valign: "middle",
      },
    }));
  });

  slide.addTable([headerRow, ...dataRows], cloneOpts({
    x: id.margins.x,
    y: id.margins.bodyY + 0.55,
    w: totalW,
    rowH: 0.38,
    colW,
    border: { type: "solid", color: id.colors.line, pt: 0.5 },
  }));

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
