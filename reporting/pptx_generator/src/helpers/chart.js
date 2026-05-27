// src/helpers/chart.js
// Native PowerPoint chart wrappers with identity palette + proper number formatting

import { cloneOpts } from "./layout.js";
import { CHART_NUMFMT } from "./formatters.js";

function baseChartOpts(id, numFmt) {
  return {
    chartColors: id.chart.palette,
    chartColorsOpacity: 100,
    catAxisLabelFontFace: id.fonts.sans,
    catAxisLabelFontSize: 9,
    catAxisLabelColor: id.colors.muted,
    catAxisLineColor: id.colors.line,
    valAxisLabelFontFace: id.fonts.sans,
    valAxisLabelFontSize: 9,
    valAxisLabelColor: id.colors.muted,
    valAxisLineShow: false,
    valGridLine: { style: "solid", size: 0.5, color: id.colors.line },
    catGridLine: { style: "none" },
    showLegend: false,
    border: { type: "none", pt: 0, color: "FFFFFF" },
    plotArea: { fill: { color: "FFFFFF" } },
    dataLabelFontFace: id.fonts.mono,
    dataLabelFontSize: 8,
    dataLabelColor: id.colors.ink,
    dataLabelFormatCode: numFmt || CHART_NUMFMT.decimal,
    valAxisLabelFormatCode: numFmt || CHART_NUMFMT.decimal,
    showValue: true,
    dataLabelPosition: "outEnd",
  };
}

export function addColumnChart(slide, pres, id, x, y, w, h, data, opts = {}) {
  const numFmt = opts.numFmt || CHART_NUMFMT.decimal;
  slide.addChart(pres.charts.BAR, data, cloneOpts({
    x, y, w, h,
    barDir: "col",
    ...baseChartOpts(id, numFmt),
    ...opts,
  }));
}

export function addBarChart(slide, pres, id, x, y, w, h, data, opts = {}) {
  const numFmt = opts.numFmt || CHART_NUMFMT.decimal;
  slide.addChart(pres.charts.BAR, data, cloneOpts({
    x, y, w, h,
    barDir: "bar",
    ...baseChartOpts(id, numFmt),
    ...opts,
  }));
}

export function addLineChart(slide, pres, id, x, y, w, h, data, opts = {}) {
  const numFmt = opts.numFmt || CHART_NUMFMT.decimal;
  slide.addChart(pres.charts.LINE, data, cloneOpts({
    x, y, w, h,
    lineSize: 2.5,
    lineSmooth: true,
    showValue: false,
    ...baseChartOpts(id, numFmt),
    ...opts,
  }));
}

export function addGroupedColumnChart(slide, pres, id, x, y, w, h, data, opts = {}) {
  const numFmt = opts.numFmt || CHART_NUMFMT.decimal;
  slide.addChart(pres.charts.BAR, data, cloneOpts({
    x, y, w, h,
    barDir: "col",
    barGrouping: "clustered",
    barGapWidthPct: 40,
    ...baseChartOpts(id, numFmt),
    showLegend: true,
    legendPos: "t",
    legendFontFace: id.fonts.sans,
    legendFontSize: 9,
    legendColor: id.colors.muted,
    ...opts,
  }));
}
