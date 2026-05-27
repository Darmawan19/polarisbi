// src/slides/watch_areas.js
// Watch areas — severity-coded cards with icons + structured Owner/Trigger panel

import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle, addSubtitle } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";
import { addCard, addIconCircle } from "../helpers/card.js";
import { iconToBase64Png } from "../helpers/icon.js";

const SEV_CONFIG = {
  high:   { icon: "shield-warning",   colorKey: "danger",  label: "HIGH",   chipVariant: "red" },
  medium: { icon: "clock-countdown",  colorKey: "warn",    label: "MEDIUM", chipVariant: "amber" },
  low:    { icon: "magnifying-glass", colorKey: "success", label: "LOW",    chipVariant: "green" },
};

export default async function buildWatchAreasSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  if (id.rules.dataChips) addTopRightChip(slide, id, "Risks", "amber");
  addActionTitle(slide, id, d.headline || "Watch Areas");
  if (d.subtitle) addSubtitle(slide, id, d.subtitle);

  const items = d.items || [];
  const n = Math.max(items.length, 1);
  const availH = id.margins.footerY - id.margins.bodyY - 0.7;
  const gap = 0.18;
  const cardH = (availH - gap * (n - 1)) / n;
  const cardW = 13.333 - 2 * id.margins.x;
  const startY = id.margins.bodyY + 0.6;

  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const y = startY + i * (cardH + gap);
    const sev = SEV_CONFIG[item.severity] || SEV_CONFIG.medium;
    const sevColor = id.colors[sev.colorKey];
    const iconBgFill = id.colors.chips?.[sev.chipVariant]?.fill || id.colors.stripe;

    addCard(slide, id, id.margins.x, y, cardW, cardH, {
      fill: "FFFFFF", borderColor: id.colors.line,
      accentColor: sevColor, accentSide: "left", accentSize: 0.12,
    });

    // Icon circle
    const circleSize = Math.min(cardH * 0.55, 0.65);
    const circleX = id.margins.x + 0.35;
    const circleY = y + (cardH - circleSize) / 2;
    const { iconX, iconY, iconSize } = addIconCircle(slide, id, circleX, circleY, circleSize, iconBgFill);
    try {
      const img = await iconToBase64Png(sev.icon, sevColor, 192);
      slide.addImage({ data: img, x: iconX, y: iconY, w: iconSize, h: iconSize });
    } catch (e) { /* skip */ }

    // Severity badge
    const contentX = circleX + circleSize + 0.28;
    slide.addShape("roundRect", cloneOpts({
      x: contentX, y: y + 0.17, w: 0.72, h: 0.25,
      fill: { color: sevColor }, line: { color: sevColor }, rectRadius: 0.12,
    }));
    slide.addText(sev.label, cloneOpts({
      x: contentX, y: y + 0.17, w: 0.72, h: 0.25,
      fontFace: id.fonts.sans, fontSize: 8, bold: true,
      color: "FFFFFF", charSpacing: 3,
      align: "center", valign: "middle", margin: 0,
    }));

    // Title
    slide.addText(item.title || "", cloneOpts({
      x: contentX, y: y + 0.48, w: 7.3, h: 0.42,
      fontFace: id.fonts.sans, fontSize: 14, bold: true,
      color: id.colors.ink, align: "left", margin: 0,
    }));

    // Description
    slide.addText(item.description || "", cloneOpts({
      x: contentX, y: y + 0.93, w: 7.3, h: cardH - 1.05,
      fontFace: id.fonts.sans, fontSize: 11,
      color: id.colors.muted, align: "left", valign: "top", margin: 0,
    }));

    // Owner + Trigger (right panel)
    const metaX = id.margins.x + cardW - 2.9;
    const metaW = 2.7;
    slide.addText("OWNER", cloneOpts({
      x: metaX, y: y + 0.22, w: metaW, h: 0.2,
      fontFace: id.fonts.sans, fontSize: 8, bold: true,
      color: id.colors.muted, charSpacing: 3, align: "left", margin: 0,
    }));
    slide.addText(item.owner || "—", cloneOpts({
      x: metaX, y: y + 0.43, w: metaW, h: 0.38,
      fontFace: id.fonts.sans, fontSize: 11, bold: true,
      color: id.colors.ink, align: "left", valign: "top", margin: 0,
    }));
    slide.addText("NEXT TRIGGER", cloneOpts({
      x: metaX, y: y + 0.88, w: metaW, h: 0.2,
      fontFace: id.fonts.sans, fontSize: 8, bold: true,
      color: id.colors.muted, charSpacing: 3, align: "left", margin: 0,
    }));
    slide.addText(item.trigger || "—", cloneOpts({
      x: metaX, y: y + 1.1, w: metaW, h: cardH - 1.2,
      fontFace: id.fonts.sans, fontSize: 10,
      color: id.colors.ink, align: "left", valign: "top", margin: 0,
    }));
  }

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
