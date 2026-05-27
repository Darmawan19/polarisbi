// src/slides/deep_dive.js
import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle, addSubtitle, addSectionLabel, addBody } from "../helpers/text.js";
import { addGroupedColumnChart, addColumnChart, addLineChart, addBarChart } from "../helpers/chart.js";
import { addTopRightChip } from "../helpers/chip.js";

export default async function buildDeepDiveSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  addActionTitle(slide, id, d.headline || "Deep Dive");
  if (d.subtitle) addSubtitle(slide, id, d.subtitle);
  if (id.rules.dataChips) addTopRightChip(slide, id, "DEEP DIVE", "blue");

  const chartW = 7.8;
  const chartX = id.margins.x;
  const panelX = chartX + chartW + 0.3;
  const panelW = 13.333 - id.margins.x - panelX;
  const chartY = id.margins.bodyY + 0.58;
  const chartH = 4.0;

  // Chart
  if (d.chartData?.length > 0) {
    const type = d.chartType || "column";
    if (type === "groupedColumn") {
      addGroupedColumnChart(slide, pres, id, chartX, chartY, chartW, chartH, d.chartData);
    } else if (type === "bar") {
      addBarChart(slide, pres, id, chartX, chartY, chartW, chartH, d.chartData);
    } else if (type === "line") {
      addLineChart(slide, pres, id, chartX, chartY, chartW, chartH, d.chartData);
    } else {
      addColumnChart(slide, pres, id, chartX, chartY, chartW, chartH, d.chartData);
    }
  }

  // Insights panel
  const insights = d.insights || [];
  let iy = chartY;
  insights.forEach((insight, i) => {
    addSectionLabel(slide, id, insight.label || `Insight ${i + 1}`, {
      x: panelX, y: iy, w: panelW, h: 0.2,
    });
    addBody(slide, id, insight.text || "", {
      x: panelX, y: iy + 0.24, w: panelW, h: 0.55,
    });
    iy += 0.9;
  });

  // Callout box
  if (d.callout) {
    const cbY = chartY + chartH - 1.1;
    const chipFill = id.colors.chips?.blue?.fill || id.colors.stripe;
    const accentColor = id.colors.brandAlt || id.colors.brand;

    slide.addShape("rect", cloneOpts({
      x: panelX, y: cbY, w: panelW, h: 1.05,
      fill: { color: chipFill },
      line: { color: accentColor, width: 1.5 },
    }));
    slide.addText(d.callout.value, cloneOpts({
      x: panelX + 0.1, y: cbY + 0.04, w: panelW - 0.2, h: 0.6,
      fontFace: id.rules.statHeroSerif ? id.fonts.serif : id.fonts.sans,
      fontSize: 36, bold: true, color: accentColor,
      align: "center", valign: "top", margin: 0,
    }));
    slide.addText(d.callout.label || "", cloneOpts({
      x: panelX + 0.1, y: cbY + 0.65, w: panelW - 0.2, h: 0.3,
      fontFace: id.fonts.sans, fontSize: 8,
      color: id.colors.muted, align: "center", margin: 0,
    }));
  }

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
