// src/slides/comparison.js
// Comparison — label col + company cols + rank pills + strategic readout band

import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle, addSubtitle } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";
import { addCard } from "../helpers/card.js";

export default async function buildComparisonSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  if (id.rules.dataChips) addTopRightChip(slide, id, "Comparison", "gray");
  addActionTitle(slide, id, d.headline || "Comparison");
  if (d.subtitle) addSubtitle(slide, id, d.subtitle);

  const cols = d.columns || [];
  const n = cols.length;
  if (n === 0) {
    addFooter(slide, id, { pageNum: context.pageNum, totalPages: context.totalPages });
    return;
  }

  const metricNames = (cols[0].metrics || []).map(m => m.name);
  const totalW = 13.333 - 2 * id.margins.x;
  const labelW = 2.0;
  const gap = 0.08;
  const colW = (totalW - labelW - gap * n) / n;
  const headerH = 0.5;
  const rowH = 0.55;
  const tableX = id.margins.x;
  const tableY = id.margins.bodyY + 0.6;
  const accentColor = id.colors.brandAlt || id.colors.brand;

  // Header: metric label column
  slide.addText("METRIC", cloneOpts({
    x: tableX, y: tableY, w: labelW, h: headerH,
    fontFace: id.fonts.sans, fontSize: 9, bold: true,
    color: id.colors.muted, charSpacing: 3,
    align: "left", valign: "middle", margin: [0, 0, 0, 10],
  }));

  // Header: company columns
  cols.forEach((col, ci) => {
    const x = tableX + labelW + gap + ci * (colW + gap);
    const isH = col.highlight === true;
    slide.addShape("rect", cloneOpts({
      x, y: tableY, w: colW, h: headerH,
      fill: { color: isH ? id.colors.brand : id.colors.stripe },
      line: { color: isH ? id.colors.brand : id.colors.stripe },
    }));
    slide.addText(col.label || "", cloneOpts({
      x, y: tableY, w: colW, h: headerH,
      fontFace: id.fonts.sans, fontSize: 12, bold: true,
      color: isH ? "FFFFFF" : id.colors.ink,
      align: "center", valign: "middle", margin: 0,
    }));
  });

  // Data rows
  metricNames.forEach((mName, mi) => {
    const rowY = tableY + headerH + mi * rowH;
    const altBg = mi % 2 === 0 ? "FFFFFF" : id.colors.stripe;

    slide.addText(mName, cloneOpts({
      x: tableX + 0.1, y: rowY, w: labelW - 0.1, h: rowH,
      fontFace: id.fonts.sans, fontSize: 10, color: id.colors.muted,
      align: "left", valign: "middle", margin: 0,
    }));

    cols.forEach((col, ci) => {
      const x = tableX + labelW + gap + ci * (colW + gap);
      const isH = col.highlight === true;
      const metric = (col.metrics || [])[mi] || {};

      slide.addShape("rect", cloneOpts({
        x, y: rowY, w: colW, h: rowH,
        fill: { color: isH ? (id.colors.chips?.blue?.fill || id.colors.stripe) : altBg },
        line: { color: id.colors.line, width: 0.25 },
      }));

      // Value (mono, bold for highlight)
      slide.addText(metric.value || "—", cloneOpts({
        x: x + 0.1, y: rowY, w: colW * 0.6, h: rowH,
        fontFace: id.fonts.mono, fontSize: 13,
        bold: isH, color: isH ? accentColor : id.colors.ink,
        align: "center", valign: "middle", margin: 0,
      }));

      // Rank pill (right side)
      if (metric.rank) {
        const rankW = 0.5;
        const rankX = x + colW - rankW - 0.08;
        const rankY = rowY + (rowH - 0.24) / 2;
        slide.addShape("roundRect", cloneOpts({
          x: rankX, y: rankY, w: rankW, h: 0.24,
          fill: { color: id.colors.stripe },
          line: { color: id.colors.stripe },
          rectRadius: 0.12,
        }));
        slide.addText(metric.rank, cloneOpts({
          x: rankX, y: rankY, w: rankW, h: 0.24,
          fontFace: id.fonts.mono, fontSize: 8, bold: true,
          color: id.colors.muted,
          align: "center", valign: "middle", margin: 0,
        }));
      }
    });
  });

  // === Strategic readout band ===
  const tableBottom = tableY + headerH + rowH * metricNames.length;
  const bandY = tableBottom + 0.3;
  const bandH = id.margins.footerY - bandY - 0.2;

  if (bandH > 0.5) {
    addCard(slide, id, tableX, bandY, totalW, bandH, {
      fill: id.colors.stripe, borderColor: id.colors.line,
      accentColor, accentSide: "left", accentSize: 0.08,
    });

    slide.addText("STRATEGIC READOUT", cloneOpts({
      x: tableX + 0.25, y: bandY + 0.15, w: 4, h: 0.22,
      fontFace: id.fonts.sans, fontSize: 9, bold: true,
      color: accentColor, charSpacing: 4, align: "left", margin: 0,
    }));

    const readout = d.readout || "Highlight column shows top growth velocity and strongest bancassurance mix — strategic focus: defend growth advantage while closing the underwriting gap.";
    slide.addText(readout, cloneOpts({
      x: tableX + 0.25, y: bandY + 0.45, w: totalW - 0.5, h: bandH - 0.55,
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
