// src/slides/comparison.js
import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle, addSubtitle, addSectionLabel } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";

export default async function buildComparisonSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  addActionTitle(slide, id, d.headline || "Comparison");
  if (d.subtitle) addSubtitle(slide, id, d.subtitle);
  if (id.rules.dataChips) addTopRightChip(slide, id, "COMPARISON", "gray");

  const cols = d.columns || [];
  const n = cols.length;
  if (n === 0) {
    addFooter(slide, id, { pageNum: context.pageNum, totalPages: context.totalPages });
    return;
  }

  const metricNames = (cols[0].metrics || []).map(m => m.name);
  const totalW = 13.333 - 2 * id.margins.x;
  const labelW = 2.4;
  const gap = 0.1;
  const colW = (totalW - labelW - gap * n) / n;
  const headerH = 0.42;
  const rowH = 0.5;
  const tableX = id.margins.x;
  const tableY = id.margins.bodyY + 0.58;

  // Header: empty label cell
  slide.addShape("rect", cloneOpts({
    x: tableX, y: tableY, w: labelW, h: headerH,
    fill: { color: id.colors.stripe }, line: { color: id.colors.line, width: 0.25 },
  }));

  // Header: company columns
  cols.forEach((col, ci) => {
    const x = tableX + labelW + gap + ci * (colW + gap);
    const isH = col.highlight === true;
    slide.addShape("rect", cloneOpts({
      x, y: tableY, w: colW, h: headerH,
      fill: { color: isH ? id.colors.brand : id.colors.stripe },
      line: { color: id.colors.line, width: 0.25 },
    }));
    slide.addText(col.label || "", cloneOpts({
      x, y: tableY, w: colW, h: headerH,
      fontFace: id.fonts.sans, fontSize: 11, bold: true,
      color: isH ? "FFFFFF" : id.colors.ink,
      align: "center", valign: "middle", margin: 0,
    }));
  });

  // Data rows
  metricNames.forEach((mName, mi) => {
    const rowY = tableY + headerH + mi * rowH;
    const altBg = mi % 2 === 0 ? "FFFFFF" : id.colors.stripe;

    // Label cell
    slide.addShape("rect", cloneOpts({
      x: tableX, y: rowY, w: labelW, h: rowH,
      fill: { color: altBg }, line: { color: id.colors.line, width: 0.25 },
    }));
    slide.addText(mName, cloneOpts({
      x: tableX + 0.1, y: rowY, w: labelW - 0.1, h: rowH,
      fontFace: id.fonts.sans, fontSize: 9, color: id.colors.muted,
      align: "left", valign: "middle", margin: 0,
    }));

    // Value cells
    cols.forEach((col, ci) => {
      const x = tableX + labelW + gap + ci * (colW + gap);
      const isH = col.highlight === true;
      const metric = (col.metrics || [])[mi] || {};
      const cellBg = isH ? (mi % 2 === 0 ? id.colors.stripe : "FFFFFF") : altBg;

      slide.addShape("rect", cloneOpts({
        x, y: rowY, w: colW, h: rowH,
        fill: { color: cellBg }, line: { color: id.colors.line, width: 0.25 },
      }));
      slide.addText(metric.value || "-", cloneOpts({
        x: x + 0.1, y: rowY, w: colW * 0.65, h: rowH,
        fontFace: id.fonts.sans, fontSize: 11,
        bold: isH, color: isH ? (id.colors.brandAlt || id.colors.brand) : id.colors.ink,
        align: "center", valign: "middle", margin: 0,
      }));
      if (metric.rank) {
        slide.addText(metric.rank, cloneOpts({
          x: x + colW * 0.65, y: rowY, w: colW * 0.35, h: rowH,
          fontFace: id.fonts.mono, fontSize: 8, color: id.colors.muted,
          align: "center", valign: "middle", margin: 0,
        }));
      }
    });
  });

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
