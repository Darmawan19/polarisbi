// src/slides/cover.js
// Cover slide — full-bleed with data preview hook, report-type badge, meta row

import { cloneOpts, addDarkBackground, formatDate } from "../helpers/layout.js";
import { iconToBase64Png } from "../helpers/icon.js";

export default async function buildCoverSlide(pres, id, context) {
  const slide = pres.addSlide();
  const isDark = id.rules.darkCover;

  if (isDark) addDarkBackground(slide, id);

  const titleColor  = isDark ? "FFFFFF" : id.colors.ink;
  const subColor    = isDark ? id.colors.neutral : id.colors.muted;
  const metaColor   = isDark ? id.colors.muted : id.colors.neutral;
  const accentColor = isDark ? id.colors.brandAlt : id.colors.brand;

  // POLARIS: vertical left tint bar
  if (id.name === "PolarisBI") {
    slide.addShape("rect", cloneOpts({
      x: 0, y: 0, w: 0.22, h: 7.5,
      fill: { color: id.colors.clientTint },
      line: { color: id.colors.clientTint },
    }));
  }

  // McKinsey: top + bottom accent lines
  if (id.name === "McKinsey") {
    for (const lineY of [0.5, 7.0]) {
      slide.addShape("line", cloneOpts({
        x: 0.5, y: lineY, w: 12.333, h: 0,
        line: { color: id.colors.brandAlt, width: 2 },
      }));
    }
  }

  // BCG: 2x2 ghost squares bottom-right
  if (id.name === "BCG") {
    const ghost = isDark ? "1A3D2E" : "E4EDE8";
    for (const [gx, gy] of [[10.5, 4.8], [11.4, 4.8], [10.5, 5.75], [11.4, 5.75]]) {
      slide.addShape("rect", cloneOpts({
        x: gx, y: gy, w: 0.8, h: 0.8,
        fill: { color: ghost }, line: { color: ghost },
      }));
    }
  }

  const xOff = id.name === "PolarisBI" ? 0.12 : 0;
  const mx = id.margins.x + xOff;

  // === Eyebrow ===
  slide.addText("POLARISBI  ·  STRATEGIC INTELLIGENCE", cloneOpts({
    x: mx, y: 0.38, w: 9, h: 0.3,
    fontFace: id.fonts.sans, fontSize: 10, bold: true,
    color: accentColor, charSpacing: 5, align: "left", margin: 0,
  }));

  // === Report type badge (top-right) ===
  const badgeText = (context.reportType || "INDUSTRY ANALYSIS").toUpperCase();
  slide.addShape("rect", cloneOpts({
    x: 10.3, y: 0.38, w: 2.6, h: 0.34,
    fill: { color: accentColor }, line: { color: accentColor },
  }));
  slide.addText(badgeText, cloneOpts({
    x: 10.3, y: 0.38, w: 2.6, h: 0.34,
    fontFace: id.fonts.sans, fontSize: 9, bold: true,
    color: isDark ? id.colors.brand : "FFFFFF",
    charSpacing: 2, align: "center", valign: "middle", margin: 0,
  }));

  // === Main title ===
  slide.addText(context.title || "Untitled Report", cloneOpts({
    x: mx, y: 2.1, w: 11.5, h: 1.7,
    fontFace: (id.name === "McKinsey" || id.name === "PolarisBI") ? id.fonts.serif : id.fonts.sans,
    fontSize: id.sizes.coverTitle + 8,
    bold: true, color: titleColor,
    align: "left", valign: "top", margin: 0,
  }));

  // === Subtitle ===
  if (context.subtitle) {
    slide.addText(context.subtitle, cloneOpts({
      x: mx, y: 3.88, w: 11, h: 0.5,
      fontFace: id.fonts.sans, fontSize: 18,
      italic: true, color: subColor,
      align: "left", margin: 0,
    }));
  }

  // === Data preview section label ===
  const previewY = 5.1;
  slide.addText("KEY METRICS PREVIEW", cloneOpts({
    x: mx, y: previewY - 0.38, w: 6, h: 0.22,
    fontFace: id.fonts.sans, fontSize: 9, bold: true,
    color: subColor, charSpacing: 4, align: "left", margin: 0,
  }));

  // Divider
  slide.addShape("line", cloneOpts({
    x: mx, y: previewY - 0.08, w: 11.5, h: 0,
    line: { color: isDark ? "2A3A4A" : id.colors.line, width: 0.5 },
  }));

  // === 4 preview tiles ===
  const previews = context.preview || [
    { value: "Rp 8.9 T", label: "Premi Bruto FY24" },
    { value: "+14.1%",   label: "YoY Growth" },
    { value: "434.6%",   label: "RBC Ratio" },
    { value: "#5",       label: "Industry Rank" },
  ];
  const tileW = 2.65;
  const tileGap = 0.2;
  previews.slice(0, 4).forEach((p, i) => {
    const px = mx + i * (tileW + tileGap);
    slide.addText(p.value, cloneOpts({
      x: px, y: previewY + 0.05, w: tileW, h: 0.6,
      fontFace: (id.name === "McKinsey" || id.name === "PolarisBI") ? id.fonts.serif : id.fonts.sans,
      fontSize: 24, bold: true,
      color: i === 0 ? accentColor : titleColor,
      align: "left", valign: "top", margin: 0,
    }));
    slide.addText(p.label, cloneOpts({
      x: px, y: previewY + 0.65, w: tileW, h: 0.28,
      fontFace: id.fonts.sans, fontSize: 9,
      color: metaColor, align: "left", margin: 0,
    }));
  });

  // === Bottom meta row ===
  const dateStr = context.date ? formatDate(context.date, context.language || "en") : "";
  const metaLeft = [context.author, context.client].filter(Boolean).join("   ·   ");

  slide.addText(metaLeft, cloneOpts({
    x: mx, y: 6.88, w: 8, h: 0.25,
    fontFace: id.fonts.sans, fontSize: 10,
    color: metaColor, align: "left", margin: 0,
  }));
  slide.addText(dateStr, cloneOpts({
    x: 10.3, y: 6.88, w: 2.6, h: 0.25,
    fontFace: id.fonts.mono, fontSize: 10,
    color: metaColor, align: "right", margin: 0,
  }));
}
