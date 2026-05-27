// src/slides/appendix.js
// Appendix — icon-headed cards, stripe bg, methodology/definitions/caveats

import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addSectionLabel } from "../helpers/text.js";
import { addCard, addIconCircle } from "../helpers/card.js";
import { iconToBase64Png } from "../helpers/icon.js";

const SECTION_ICONS = {
  "data sources": "magnifying-glass",
  "definitions":  "target",
  "caveats":      "shield-warning",
};

function pickIcon(title) {
  const lower = (title || "").toLowerCase();
  for (const [key, icon] of Object.entries(SECTION_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return "chart-bar";
}

export default async function buildAppendixSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  slide.background = { color: id.colors.stripe };

  const accentColor = id.colors.brandAlt || id.colors.brand;

  // Eyebrow
  slide.addText("APPENDIX  ·  METHODOLOGY", cloneOpts({
    x: id.margins.x, y: id.margins.y, w: 7, h: 0.22,
    fontFace: id.fonts.sans, fontSize: 9, bold: true,
    color: accentColor, charSpacing: 4, align: "left", margin: 0,
  }));

  // Headline
  slide.addText(d.headline || "Methodology, data sources, and definitions", cloneOpts({
    x: id.margins.x, y: id.margins.y + 0.3, w: 13.333 - 2 * id.margins.x, h: 0.55,
    fontFace: (id.name === "McKinsey" || id.name === "PolarisBI") ? id.fonts.serif : id.fonts.sans,
    fontSize: id.sizes.title, bold: true, color: id.colors.ink,
    align: "left", valign: "top", margin: 0,
  }));

  // 3-column card grid
  const sections = d.sections || [];
  const n = Math.max(sections.length, 1);
  const gap = 0.25;
  const totalW = 13.333 - 2 * id.margins.x;
  const colW = (totalW - gap * (n - 1)) / n;
  const colY = id.margins.bodyY + 0.38;
  const colH = id.margins.footerY - colY - 0.25;
  const chipFill = id.colors.chips?.blue?.fill || id.colors.stripe;

  for (let i = 0; i < sections.length; i++) {
    const section = sections[i];
    const x = id.margins.x + i * (colW + gap);

    addCard(slide, id, x, colY, colW, colH, {
      fill: "FFFFFF", borderColor: id.colors.line,
      accentColor, accentSide: "top", accentSize: 0.08,
    });

    // Icon circle
    const circleSize = 0.5;
    const circleX = x + 0.25;
    const circleY = colY + 0.24;
    const { iconX, iconY, iconSize } = addIconCircle(slide, id, circleX, circleY, circleSize, chipFill);
    try {
      const img = await iconToBase64Png(pickIcon(section.title), accentColor, 192);
      slide.addImage({ data: img, x: iconX, y: iconY, w: iconSize, h: iconSize });
    } catch (e) { /* skip */ }

    // Section title
    slide.addText((section.title || "").toUpperCase(), cloneOpts({
      x: x + 0.9, y: colY + 0.34, w: colW - 1.0, h: 0.3,
      fontFace: id.fonts.sans, fontSize: 11, bold: true,
      color: id.colors.ink, charSpacing: 2,
      align: "left", margin: 0,
    }));

    // Bullet items
    const items = section.items || [];
    if (items.length > 0) {
      slide.addText(items.join("\n"), cloneOpts({
        x: x + 0.3, y: colY + 0.92, w: colW - 0.6, h: colH - 1.05,
        fontFace: id.fonts.sans, fontSize: 10,
        color: id.colors.ink, align: "left", valign: "top",
        margin: [0, 0, 0, 6], bullet: true, paraSpaceAfter: 4,
      }));
    }
  }

  // Source footer
  slide.addText(d.source || "Methodology v1.0", cloneOpts({
    x: id.margins.x, y: id.margins.footerY, w: 10, h: 0.25,
    fontFace: id.fonts.mono, fontSize: id.sizes.footnote,
    color: id.colors.muted, align: "left", margin: 0,
  }));
}
