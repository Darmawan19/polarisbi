// src/slides/kpi_dashboard.js
import { addFooter } from "../helpers/layout.js";
import { addActionTitle } from "../helpers/text.js";
import { addKpiTile } from "../helpers/stat.js";
import { addTopRightChip } from "../helpers/chip.js";

export default async function buildKpiDashboardSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  addActionTitle(slide, id, d.headline || "KPI Dashboard");
  if (id.rules.dataChips) addTopRightChip(slide, id, "KPI DASHBOARD", "blue");

  const kpis = d.kpis || [];
  const n = kpis.length || 1;
  const gap = 0.18;
  const totalW = 13.333 - 2 * id.margins.x;
  const tileW = (totalW - gap * (n - 1)) / n;
  const tileH = 3.0;
  const tileY = id.margins.bodyY + 0.4;

  kpis.forEach((kpi, i) => {
    const x = id.margins.x + i * (tileW + gap);
    addKpiTile(slide, id, x, tileY, tileW, tileH, {
      value: kpi.value,
      label: kpi.label,
      delta: kpi.delta,
      deltaPositive: kpi.positive !== false,
    });
  });

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
