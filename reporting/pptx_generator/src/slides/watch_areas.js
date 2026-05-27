// src/slides/watch_areas.js
import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle, addSubtitle } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";

export default async function buildWatchAreasSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  addActionTitle(slide, id, d.headline || "Watch Areas");
  if (d.subtitle) addSubtitle(slide, id, d.subtitle);
  if (id.rules.dataChips) addTopRightChip(slide, id, "RISK WATCH", "amber");

  const items = d.items || [];
  const n = Math.max(items.length, 1);
  const availH = id.margins.footerY - id.margins.bodyY - 0.58;
  const gapBetween = 0.1;
  const cardH = (availH - gapBetween * (n - 1)) / n;
  const cardW = 13.333 - 2 * id.margins.x;

  const sevColor = {
    high:   id.colors.danger,
    medium: id.colors.warn,
    low:    id.colors.success,
  };

  items.forEach((item, i) => {
    const y = id.margins.bodyY + 0.48 + i * (cardH + gapBetween);
    const sev = sevColor[item.severity] || id.colors.neutral;

    // Card bg
    slide.addShape("rect", cloneOpts({
      x: id.margins.x, y, w: cardW, h: cardH,
      fill: { color: id.colors.stripe }, line: { color: id.colors.line, width: 0.25 },
    }));

    // Severity accent bar (left edge)
    slide.addShape("rect", cloneOpts({
      x: id.margins.x, y, w: 0.12, h: cardH,
      fill: { color: sev }, line: { color: sev },
    }));

    const cx = id.margins.x + 0.22;

    // Severity badge
    slide.addText((item.severity || "").toUpperCase(), cloneOpts({
      x: cx, y: y + 0.08, w: 0.7, h: 0.18,
      fontFace: id.fonts.sans, fontSize: 7, bold: true,
      color: sev, charSpacing: 3, align: "left", margin: 0,
    }));

    // Title
    slide.addText(item.title || "", cloneOpts({
      x: cx, y: y + 0.27, w: 7.5, h: 0.32,
      fontFace: id.fonts.sans, fontSize: 12, bold: true,
      color: id.colors.ink, align: "left", margin: 0,
    }));

    // Description
    slide.addText(item.description || "", cloneOpts({
      x: cx, y: y + 0.62, w: 7.5, h: cardH - 0.72,
      fontFace: id.fonts.sans, fontSize: id.sizes.body,
      color: id.colors.muted, align: "left", valign: "top", margin: 0,
    }));

    // Owner + Trigger (right)
    const rx = 8.6;
    const rw = 13.333 - id.margins.x - rx;
    slide.addText("Owner: " + (item.owner || "—"), cloneOpts({
      x: rx, y: y + 0.15, w: rw, h: 0.25,
      fontFace: id.fonts.sans, fontSize: 9,
      color: id.colors.muted, align: "left", margin: 0,
    }));
    slide.addText("Trigger: " + (item.trigger || "—"), cloneOpts({
      x: rx, y: y + 0.45, w: rw, h: 0.25,
      fontFace: id.fonts.sans, fontSize: 9,
      color: id.colors.muted, align: "left", margin: 0,
    }));
  });

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
