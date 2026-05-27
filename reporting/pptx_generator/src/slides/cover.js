// src/slides/cover.js
import { cloneOpts, addDarkBackground, formatDate } from "../helpers/layout.js";

export default async function buildCoverSlide(pres, id, context) {
  const slide = pres.addSlide();
  const isDark = id.rules.darkCover;

  if (isDark) {
    addDarkBackground(slide, id);
  }

  const titleColor = isDark ? "FFFFFF" : id.colors.ink;
  const subColor   = isDark ? id.colors.neutral : id.colors.muted;
  const metaColor  = isDark ? id.colors.muted : id.colors.neutral;
  const divColor   = isDark ? "2A3A4A" : id.colors.line;

  // McKinsey: twin horizontal accent lines
  if (id.name === "McKinsey") {
    for (const lineY of [0.55, 7.1]) {
      slide.addShape("line", cloneOpts({
        x: 0.5, y: lineY, w: 12.333, h: 0,
        line: { color: id.colors.brandAlt, width: 2 },
      }));
    }
  }

  // BCG: 2x2 ghost squares bottom-right
  if (id.name === "BCG") {
    const ghost = isDark ? "1A3D2E" : "E4EDE8";
    for (const [gx, gy] of [[10.6, 4.7], [11.5, 4.7], [10.6, 5.65], [11.5, 5.65]]) {
      slide.addShape("rect", cloneOpts({
        x: gx, y: gy, w: 0.8, h: 0.8,
        fill: { color: ghost }, line: { color: ghost },
      }));
    }
  }

  // POLARIS: vertical left tint bar
  if (id.name === "PolarisBI") {
    slide.addShape("rect", cloneOpts({
      x: 0, y: 0, w: 0.18, h: 7.5,
      fill: { color: id.colors.clientTint },
      line: { color: id.colors.clientTint },
    }));
  }

  const xOff = id.name === "PolarisBI" ? 0.08 : 0;
  const mx = id.margins.x + xOff;

  // Eyebrow
  slide.addText("POLARISBI", cloneOpts({
    x: mx, y: 0.32, w: 5, h: 0.22,
    fontFace: id.fonts.sans, fontSize: 8, bold: true,
    color: isDark ? id.colors.brandAlt : id.colors.brand,
    charSpacing: 4, align: "left", margin: 0,
  }));

  // Main title
  slide.addText(context.title || "Untitled", cloneOpts({
    x: mx, y: 1.8, w: 11.2, h: 2.1,
    fontFace: (id.name === "McKinsey" || id.name === "PolarisBI") ? id.fonts.serif : id.fonts.sans,
    fontSize: id.sizes.coverTitle, bold: true, color: titleColor,
    align: "left", valign: "top", margin: 0,
  }));

  // Subtitle
  if (context.subtitle) {
    slide.addText(context.subtitle, cloneOpts({
      x: mx, y: 4.05, w: 10.5, h: 0.4,
      fontFace: id.fonts.sans, fontSize: id.sizes.subtitle,
      italic: true, color: subColor, align: "left", margin: 0,
    }));
  }

  // Divider
  slide.addShape("line", cloneOpts({
    x: mx, y: 4.6, w: 11.2, h: 0,
    line: { color: divColor, width: 0.5 },
  }));

  // Meta row: client | author | date
  const lang = context.language || "en";
  const dateStr = context.date ? formatDate(context.date, lang) : "";
  const meta = [context.client, context.author, dateStr].filter(Boolean).join("   |   ");

  slide.addText(meta, cloneOpts({
    x: mx, y: 4.72, w: 11.2, h: 0.3,
    fontFace: id.fonts.sans, fontSize: 10,
    color: metaColor, align: "left", margin: 0,
  }));
}
