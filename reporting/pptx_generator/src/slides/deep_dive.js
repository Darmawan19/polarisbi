// src/slides/deep_dive.js
// Deep dive — chart with decimal formatting + numbered insights + callout card

import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle, addSubtitle } from "../helpers/text.js";
import { addGroupedColumnChart, addColumnChart, addLineChart, addBarChart } from "../helpers/chart.js";
import { addTopRightChip } from "../helpers/chip.js";
import { addCard } from "../helpers/card.js";
import { CHART_NUMFMT } from "../helpers/formatters.js";

export default async function buildDeepDiveSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  if (id.rules.dataChips) addTopRightChip(slide, id, "Deep Dive", "blue");
  addActionTitle(slide, id, d.headline || "Deep Dive");
  if (d.subtitle) addSubtitle(slide, id, d.subtitle);

  const chartW = 7.4;
  const chartX = id.margins.x;
  const panelX = chartX + chartW + 0.3;
  const panelW = 13.333 - id.margins.x - panelX;
  const chartY = id.margins.bodyY + 0.55;
  const chartH = 4.5;
  const accentColor = id.colors.brandAlt || id.colors.brand;
  const numFmt = d.numFmt || CHART_NUMFMT.decimal;

  // Chart card bg
  addCard(slide, id, chartX - 0.1, chartY - 0.1, chartW + 0.2, chartH + 0.2, {
    fill: "FFFFFF", borderColor: id.colors.line, borderWidth: 0.5,
  });

  // Chart
  if (d.chartData?.length > 0) {
    const type = d.chartType || "column";
    const opts = { numFmt };
    if      (type === "groupedColumn") addGroupedColumnChart(slide, pres, id, chartX, chartY, chartW, chartH, d.chartData, opts);
    else if (type === "bar")           addBarChart(slide, pres, id, chartX, chartY, chartW, chartH, d.chartData, opts);
    else if (type === "line")          addLineChart(slide, pres, id, chartX, chartY, chartW, chartH, d.chartData, opts);
    else                               addColumnChart(slide, pres, id, chartX, chartY, chartW, chartH, d.chartData, opts);
  }

  // === Insights panel (right) ===
  slide.addText("KEY INSIGHTS", cloneOpts({
    x: panelX, y: chartY, w: panelW, h: 0.25,
    fontFace: id.fonts.sans, fontSize: 9, bold: true,
    color: id.colors.muted, charSpacing: 4, align: "left", margin: 0,
  }));
  slide.addShape("line", cloneOpts({
    x: panelX, y: chartY + 0.3, w: 1.5, h: 0,
    line: { color: accentColor, width: 1.5 },
  }));

  const insights = d.insights || [];
  let iy = chartY + 0.55;
  for (let i = 0; i < Math.min(insights.length, 3); i++) {
    const ins = insights[i];

    // Numbered circle
    slide.addShape("ellipse", cloneOpts({
      x: panelX, y: iy + 0.02, w: 0.32, h: 0.32,
      fill: { color: accentColor }, line: { color: accentColor },
    }));
    slide.addText(String(i + 1), cloneOpts({
      x: panelX, y: iy + 0.02, w: 0.32, h: 0.32,
      fontFace: id.fonts.sans, fontSize: 11, bold: true,
      color: "FFFFFF", align: "center", valign: "middle", margin: 0,
    }));

    // Insight label + text
    slide.addText(ins.label || "", cloneOpts({
      x: panelX + 0.45, y: iy, w: panelW - 0.5, h: 0.28,
      fontFace: id.fonts.sans, fontSize: 11, bold: true,
      color: id.colors.ink, align: "left", margin: 0,
    }));
    slide.addText(ins.text || "", cloneOpts({
      x: panelX + 0.45, y: iy + 0.3, w: panelW - 0.5, h: 0.82,
      fontFace: id.fonts.sans, fontSize: 10,
      color: id.colors.muted, align: "left", valign: "top", margin: 0,
    }));
    iy += 1.25;
  }

  // === Callout card (below chart, full chart width) ===
  if (d.callout) {
    const cbY = chartY + chartH + 0.3;
    const cbH = 0.85;

    addCard(slide, id, chartX, cbY, chartW, cbH, {
      fill: id.colors.chips?.blue?.fill || id.colors.stripe,
      borderColor: accentColor,
      borderWidth: 1.5,
    });

    slide.addText(d.callout.value, cloneOpts({
      x: chartX + 0.2, y: cbY, w: 2.2, h: cbH,
      fontFace: id.rules.statHeroSerif ? id.fonts.serif : id.fonts.sans,
      fontSize: 32, bold: true, color: accentColor,
      align: "left", valign: "middle", margin: 0,
    }));
    slide.addText(d.callout.label || "", cloneOpts({
      x: chartX + 2.5, y: cbY, w: chartW - 2.7, h: cbH,
      fontFace: id.fonts.sans, fontSize: 13,
      color: id.colors.ink, align: "left", valign: "middle", margin: 0,
    }));
  }

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
