// src/slides/recommendations.js
// Recommendations — numbered priority panel + action/rationale + meta panel

import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";
import { addCard } from "../helpers/card.js";

export default async function buildRecommendationsSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  if (id.rules.dataChips) addTopRightChip(slide, id, "Actions", "green");
  addActionTitle(slide, id, d.headline || "Recommendations");

  const items = d.items || [];
  const n = Math.max(items.length, 1);
  const availH = id.margins.footerY - id.margins.bodyY - 0.7;
  const gap = 0.18;
  const cardH = (availH - gap * (n - 1)) / n;
  const cardW = 13.333 - 2 * id.margins.x;
  const startY = id.margins.bodyY + 0.5;
  const accentColor = id.colors.brandAlt || id.colors.brand;
  const numW = 1.0;
  const metaW = 3.0;

  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const y = startY + i * (cardH + gap);

    // Card shell
    addCard(slide, id, id.margins.x, y, cardW, cardH, {
      fill: "FFFFFF", borderColor: id.colors.line,
    });

    // Priority panel (left, accent-filled)
    slide.addShape("rect", cloneOpts({
      x: id.margins.x, y, w: numW, h: cardH,
      fill: { color: accentColor }, line: { color: accentColor },
    }));
    slide.addText("PRIORITY", cloneOpts({
      x: id.margins.x, y: y + 0.18, w: numW, h: 0.22,
      fontFace: id.fonts.sans, fontSize: 7, bold: true,
      color: "FFFFFF", charSpacing: 4,
      align: "center", margin: 0,
    }));
    slide.addText(String(item.priority || i + 1), cloneOpts({
      x: id.margins.x, y: y + 0.4, w: numW, h: cardH - 0.5,
      fontFace: id.fonts.serif, fontSize: 48, bold: true,
      color: "FFFFFF", align: "center", valign: "middle", margin: 0,
    }));

    // Main content
    const mainX = id.margins.x + numW + 0.3;
    const mainW = cardW - numW - 0.3 - metaW - 0.2;

    slide.addText(item.action || "", cloneOpts({
      x: mainX, y: y + 0.2, w: mainW, h: 0.45,
      fontFace: id.fonts.sans, fontSize: 14, bold: true,
      color: id.colors.ink, align: "left", margin: 0,
    }));
    slide.addText(item.rationale || "", cloneOpts({
      x: mainX, y: y + 0.7, w: mainW, h: cardH - 0.85,
      fontFace: id.fonts.sans, fontSize: 11,
      color: id.colors.muted, align: "left", valign: "top", margin: 0,
    }));

    // Meta panel (right, stripe bg)
    const metaX = id.margins.x + cardW - metaW;
    slide.addShape("rect", cloneOpts({
      x: metaX, y, w: metaW, h: cardH,
      fill: { color: id.colors.stripe }, line: { color: id.colors.stripe },
    }));

    const metaFields = [
      ["OWNER",          item.owner],
      ["TIMELINE",       item.timeline],
      ["SUCCESS METRIC", item.metric],
    ].filter(([, v]) => v);

    const fieldH = (cardH - 0.3) / Math.max(metaFields.length, 1);
    metaFields.forEach(([label, value], mi) => {
      const my = y + 0.15 + mi * fieldH;
      slide.addText(label, cloneOpts({
        x: metaX + 0.18, y: my, w: metaW - 0.3, h: 0.18,
        fontFace: id.fonts.sans, fontSize: 8, bold: true,
        color: accentColor, charSpacing: 3, align: "left", margin: 0,
      }));
      slide.addText(value, cloneOpts({
        x: metaX + 0.18, y: my + 0.2, w: metaW - 0.3, h: fieldH - 0.25,
        fontFace: id.fonts.sans, fontSize: 10,
        color: id.colors.ink, align: "left", valign: "top", margin: 0,
      }));
    });
  }

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
