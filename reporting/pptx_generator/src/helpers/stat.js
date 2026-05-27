// src/helpers/stat.js
// Big stat hero (Bain/POLARIS signature)

import { cloneOpts } from "./layout.js";

/**
 * Add a centered hero stat — the slide's single message.
 * - Bain: 72pt Arial bold red
 * - POLARIS: 80pt Georgia bold signal blue
 * - McKinsey: 60pt Georgia bold deep blue
 * - BCG: 48pt Arial bold forest green
 */
export function addStatHero(slide, id, value, label, change = null) {
  slide.addText(value, cloneOpts({
    x: 0.75,
    y: 2.2,
    w: 11.83,
    h: 2.5,
    fontFace: id.rules.statHeroSerif ? id.fonts.serif : id.fonts.sans,
    fontSize: id.sizes.stat,
    bold: true,
    color: id.colors.brand,
    align: "center",
    valign: "middle",
    margin: 0,
  }));

  slide.addText(label, cloneOpts({
    x: 0.75,
    y: 4.9,
    w: 11.83,
    h: 0.4,
    fontFace: id.fonts.sans,
    fontSize: 14,
    color: id.colors.muted,
    align: "center",
    valign: "top",
    margin: 0,
  }));

  if (change) {
    const isPositive = change.startsWith("+") || change.startsWith("▲");
    slide.addText(change, cloneOpts({
      x: 0.75,
      y: 5.4,
      w: 11.83,
      h: 0.3,
      fontFace: id.fonts.mono,
      fontSize: 11,
      color: isPositive ? id.colors.success : id.colors.danger,
      align: "center",
      valign: "top",
      margin: 0,
    }));
  }
}

/**
 * KPI tile — used in 4-tile dashboard.
 * Small box with big number, label, and delta.
 */
export function addKpiTile(slide, id, x, y, w, h, { value, label, delta, deltaPositive }) {
  slide.addShape("rect", cloneOpts({
    x, y, w, h,
    fill: { color: id.colors.stripe },
    line: { color: id.colors.stripe },
  }));

  slide.addText(value, cloneOpts({
    x: x + 0.2,
    y: y + 0.2,
    w: w - 0.4,
    h: h * 0.45,
    fontFace: id.rules.statHeroSerif ? id.fonts.serif : id.fonts.sans,
    fontSize: 32,
    bold: true,
    color: id.colors.brand,
    align: "left",
    valign: "top",
    margin: 0,
  }));

  slide.addText(label, cloneOpts({
    x: x + 0.2,
    y: y + h * 0.6,
    w: w - 0.4,
    h: 0.25,
    fontFace: id.fonts.sans,
    fontSize: 10,
    color: id.colors.muted,
    align: "left",
    valign: "top",
    margin: 0,
  }));

  if (delta) {
    slide.addText(delta, cloneOpts({
      x: x + 0.2,
      y: y + h * 0.82,
      w: w - 0.4,
      h: 0.25,
      fontFace: id.fonts.mono,
      fontSize: 10,
      bold: true,
      color: deltaPositive ? id.colors.success : id.colors.danger,
      align: "left",
      valign: "top",
      margin: 0,
    }));
  }
}
