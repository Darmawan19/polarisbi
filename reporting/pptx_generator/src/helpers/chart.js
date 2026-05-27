// src/helpers/chart.js
// Native PowerPoint chart wrappers with identity palette

import { cloneOpts } from "./layout.js";

function baseChartOpts(id) {
  return {
    chartColors: id.chart.palette,
    catAxisLabelFontFace: id.fonts.sans,
    catAxisLabelFontSize: 9,
    catAxisLabelColor: id.colors.muted,
    valAxisLabelFontFace: id.fonts.sans,
    valAxisLabelFontSize: 9,
    valAxisLabelColor: id.colors.muted,
    valGridLine: { style: "solid", size: 0.5, color: id.colors.line },
    catGridLine: { style: "none" },
    showLegend: false,
    border: { type: "none" },
    plotArea: { fill: { type: "none" } },
    dataLabelFontFace: id.fonts.sans,
    dataLabelFontSize: 9,
    dataLabelColor: id.colors.ink,
  };
}

/**
 * Column bar chart (vertical bars).
 */
export function addColumnChart(slide, pres, id, x, y, w, h, data, opts = {}) {
  slide.addChart(pres.charts.BAR, data, cloneOpts({
    x, y, w, h,
    barDir: "col",
    showValue: true,
    dataLabelPosition: "outEnd",
    ...baseChartOpts(id),
    ...opts,
  }));
}

/**
 * Horizontal bar chart.
 */
export function addBarChart(slide, pres, id, x, y, w, h, data, opts = {}) {
  slide.addChart(pres.charts.BAR, data, cloneOpts({
    x, y, w, h,
    barDir: "bar",
    showValue: true,
    dataLabelPosition: "outEnd",
    ...baseChartOpts(id),
    ...opts,
  }));
}

/**
 * Line chart with smoothed curves.
 */
export function addLineChart(slide, pres, id, x, y, w, h, data, opts = {}) {
  slide.addChart(pres.charts.LINE, data, cloneOpts({
    x, y, w, h,
    lineSize: 2.5,
    lineSmooth: true,
    showValue: false,
    ...baseChartOpts(id),
    ...opts,
  }));
}

/**
 * Grouped column chart (multi-series).
 */
export function addGroupedColumnChart(slide, pres, id, x, y, w, h, data, opts = {}) {
  slide.addChart(pres.charts.BAR, data, cloneOpts({
    x, y, w, h,
    barDir: "col",
    barGrouping: "clustered",
    showValue: true,
    dataLabelPosition: "outEnd",
    showLegend: true,
    legendPos: "t",
    legendFontFace: id.fonts.sans,
    legendFontSize: 9,
    legendColor: id.colors.muted,
    ...baseChartOpts(id),
    ...opts,
  }));
}
