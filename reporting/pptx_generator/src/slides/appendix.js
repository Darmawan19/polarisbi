// src/slides/appendix.js
import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addSectionLabel } from "../helpers/text.js";

export default async function buildAppendixSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  // Stripe background
  slide.background = { color: id.colors.stripe };

  // "APPENDIX" label top-left
  slide.addText("APPENDIX", cloneOpts({
    x: id.margins.x, y: id.margins.y, w: 4, h: 0.22,
    fontFace: id.fonts.sans, fontSize: 8, bold: true,
    color: id.colors.muted, charSpacing: 4, align: "left", margin: 0,
  }));

  // Headline
  slide.addText(d.headline || "Appendix", cloneOpts({
    x: id.margins.x, y: id.margins.y + 0.28, w: 13.333 - 2 * id.margins.x, h: 0.45,
    fontFace: (id.name === "McKinsey" || id.name === "PolarisBI") ? id.fonts.serif : id.fonts.sans,
    fontSize: id.sizes.title, bold: true, color: id.colors.ink,
    align: "left", valign: "top", margin: 0,
  }));

  // 3-column layout
  const sections = d.sections || [];
  const n = Math.max(sections.length, 1);
  const gap = 0.2;
  const totalW = 13.333 - 2 * id.margins.x;
  const colW = (totalW - gap * (n - 1)) / n;
  const colY = id.margins.y + 0.9;
  const colH = id.margins.footerY - colY - 0.3;

  sections.forEach((section, i) => {
    const x = id.margins.x + i * (colW + gap);

    // White card bg
    slide.addShape("rect", cloneOpts({
      x, y: colY, w: colW, h: colH,
      fill: { color: "FFFFFF" }, line: { color: id.colors.line, width: 0.25 },
    }));

    // Section title
    addSectionLabel(slide, id, section.title || "", {
      x: x + 0.15, y: colY + 0.12, w: colW - 0.3, h: 0.22,
    });

    slide.addShape("line", cloneOpts({
      x: x + 0.15, y: colY + 0.38, w: colW * 0.3, h: 0,
      line: { color: id.colors.brandAlt || id.colors.brand, width: 1 },
    }));

    // Items as bullet list
    const items = section.items || [];
    slide.addText(items.join("\n"), cloneOpts({
      x: x + 0.15, y: colY + 0.5, w: colW - 0.3, h: colH - 0.6,
      fontFace: id.fonts.sans, fontSize: id.sizes.body,
      color: id.colors.ink, align: "left", valign: "top",
      margin: [0, 0, 0, 6], bullet: true, paraSpaceAfter: 4,
    }));
  });

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
