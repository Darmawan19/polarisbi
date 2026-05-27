// src/slides/kpi_dashboard.js
// 4 KPI tiles with icons + delta arrows + context band below

import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";
import { addCard, addIconCircle } from "../helpers/card.js";
import { iconToBase64Png } from "../helpers/icon.js";

const KPI_ICON_MAP = {
  premi:    "currency-circle-dollar",
  premium:  "currency-circle-dollar",
  ape:      "trend-up",
  rbc:      "shield-warning",
  profit:   "chart-line",
  growth:   "trend-up",
  margin:   "target",
  share:    "users-three",
  ratio:    "target",
};
const DEFAULT_ICON = "chart-bar";

function pickIcon(label) {
  const lower = (label || "").toLowerCase();
  for (const [key, icon] of Object.entries(KPI_ICON_MAP)) {
    if (lower.includes(key)) return icon;
  }
  return DEFAULT_ICON;
}

export default async function buildKpiDashboardSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  if (id.rules.dataChips) addTopRightChip(slide, id, "Dashboard", "blue");
  addActionTitle(slide, id, d.headline || "KPI Dashboard");

  const kpis = (d.kpis || []).slice(0, 4);
  const n = kpis.length || 1;
  const totalW = 13.333 - 2 * id.margins.x;
  const gap = 0.2;
  const tileW = (totalW - gap * (n - 1)) / n;
  const tileH = 2.8;
  const tileY = id.margins.bodyY + 0.6;
  const accentColor = id.colors.brandAlt || id.colors.brand;
  const chipFill = id.colors.chips?.blue?.fill || id.colors.stripe;

  for (let i = 0; i < kpis.length; i++) {
    const kpi = kpis[i];
    const x = id.margins.x + i * (tileW + gap);

    addCard(slide, id, x, tileY, tileW, tileH, {
      fill: "FFFFFF",
      borderColor: id.colors.line,
      borderWidth: 0.75,
      accentColor,
      accentSide: "left",
      accentSize: 0.08,
    });

    // Icon circle (top-left of tile)
    const iconName = pickIcon(kpi.label || "");
    const { iconX, iconY, iconSize } = addIconCircle(
      slide, id, x + 0.35, tileY + 0.3, 0.5, chipFill
    );
    try {
      const img = await iconToBase64Png(iconName, accentColor, 192);
      slide.addImage({ data: img, x: iconX, y: iconY, w: iconSize, h: iconSize });
    } catch (e) { /* skip */ }

    // Label (small caps)
    slide.addText((kpi.label || "").toUpperCase(), cloneOpts({
      x: x + 1.05, y: tileY + 0.34, w: tileW - 1.2, h: 0.25,
      fontFace: id.fonts.sans, fontSize: 9, bold: true,
      color: id.colors.muted, charSpacing: 2,
      align: "left", valign: "top", margin: 0,
    }));

    // Big value
    slide.addText(kpi.value || "—", cloneOpts({
      x: x + 0.3, y: tileY + 0.95, w: tileW - 0.5, h: 0.95,
      fontFace: id.rules.statHeroSerif ? id.fonts.serif : id.fonts.sans,
      fontSize: 32, bold: true, color: id.colors.ink,
      align: "left", valign: "middle", margin: 0,
    }));

    // Delta row
    const isPos = kpi.positive !== false;
    slide.addText(`${isPos ? "▲" : "▼"}  ${kpi.delta || ""}`, cloneOpts({
      x: x + 0.3, y: tileY + tileH - 0.6, w: tileW - 0.5, h: 0.3,
      fontFace: id.fonts.mono, fontSize: 11, bold: true,
      color: isPos ? id.colors.success : id.colors.danger,
      align: "left", valign: "middle", margin: 0,
    }));
  }

  // === Context band below tiles ===
  const bandY = tileY + tileH + 0.35;
  const bandH = id.margins.footerY - bandY - 0.25;

  slide.addText("CONTEXT  &  INTERPRETATION", cloneOpts({
    x: id.margins.x, y: bandY, w: 6, h: 0.22,
    fontFace: id.fonts.sans, fontSize: 9, bold: true,
    color: id.colors.muted, charSpacing: 4, align: "left", margin: 0,
  }));
  slide.addShape("line", cloneOpts({
    x: id.margins.x, y: bandY + 0.27, w: 2.5, h: 0,
    line: { color: accentColor, width: 1 },
  }));

  const ctxItems = d.context || [
    { title: "Why these matter",  text: "These four metrics prove the bancassurance thesis — premium growth driven by channel mix, with risk-adjusted profitability intact." },
    { title: "Peer benchmark",    text: "BRI Life APE growth +11.2% ranks #2 in top 10. RBC 434.6% exceeds OJK minimum by 3.6x — significant product expansion headroom." },
    { title: "Forward signal",    text: "FY 2025 hinges on sustaining bancassurance velocity against rising industry health claim ratios trending toward 140%." },
  ];
  const ctxColW = (totalW - 0.4) / 3;
  ctxItems.slice(0, 3).forEach((c, i) => {
    const cx = id.margins.x + i * (ctxColW + 0.2);
    slide.addText(c.title, cloneOpts({
      x: cx, y: bandY + 0.45, w: ctxColW, h: 0.3,
      fontFace: id.fonts.sans, fontSize: 11, bold: true,
      color: accentColor, align: "left", valign: "top", margin: 0,
    }));
    slide.addText(c.text, cloneOpts({
      x: cx, y: bandY + 0.78, w: ctxColW, h: bandH - 0.8,
      fontFace: id.fonts.sans, fontSize: 10,
      color: id.colors.ink, align: "left", valign: "top", margin: 0,
    }));
  });

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
