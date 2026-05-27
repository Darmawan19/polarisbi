// src/slides/recommendations.js
import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";

export default async function buildRecommendationsSlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  addActionTitle(slide, id, d.headline || "Recommendations");
  if (id.rules.dataChips) addTopRightChip(slide, id, "ACTIONS", "green");

  const items = d.items || [];
  const n = Math.max(items.length, 1);
  const availH = id.margins.footerY - id.margins.bodyY - 0.35;
  const gapBetween = 0.12;
  const cardH = (availH - gapBetween * (n - 1)) / n;

  const numW   = 0.55;
  const metaW  = 3.2;
  const gap    = 0.25;
  const mainW  = 13.333 - 2 * id.margins.x - numW - metaW - 2 * gap;
  const mainX  = id.margins.x + numW + gap;
  const metaX  = mainX + mainW + gap;
  const accentColor = id.colors.brandAlt || id.colors.brand;

  items.forEach((item, i) => {
    const y = id.margins.bodyY + 0.18 + i * (cardH + gapBetween);

    // Priority number
    slide.addText(String(item.priority || i + 1), cloneOpts({
      x: id.margins.x, y, w: numW, h: cardH,
      fontFace: id.rules.statHeroSerif ? id.fonts.serif : id.fonts.sans,
      fontSize: 32, bold: true, color: accentColor,
      align: "center", valign: "middle", margin: 0,
    }));

    // Vertical divider after number
    slide.addShape("line", cloneOpts({
      x: id.margins.x + numW + 0.05, y: y + 0.06, w: 0, h: cardH - 0.12,
      line: { color: id.colors.line, width: 0.5 },
    }));

    // Action title
    slide.addText(item.action || "", cloneOpts({
      x: mainX, y: y + 0.05, w: mainW, h: 0.35,
      fontFace: id.fonts.sans, fontSize: 12, bold: true,
      color: id.colors.ink, align: "left", margin: 0,
    }));

    // Rationale
    slide.addText(item.rationale || "", cloneOpts({
      x: mainX, y: y + 0.44, w: mainW, h: cardH - 0.52,
      fontFace: id.fonts.sans, fontSize: id.sizes.body,
      color: id.colors.muted, align: "left", valign: "top", margin: 0,
    }));

    // Meta panel bg
    slide.addShape("rect", cloneOpts({
      x: metaX - 0.08, y, w: metaW + 0.08, h: cardH,
      fill: { color: id.colors.stripe }, line: { color: id.colors.stripe },
    }));

    // Meta fields: Owner / Timeline / Metric
    const metaFields = [
      ["Owner",    item.owner],
      ["Timeline", item.timeline],
      ["Metric",   item.metric],
    ].filter(([, v]) => v);

    const fieldH = cardH / Math.max(metaFields.length, 1);
    metaFields.forEach(([label, value], mi) => {
      const my = y + mi * fieldH + 0.04;
      slide.addText(label.toUpperCase(), cloneOpts({
        x: metaX, y: my, w: metaW, h: 0.18,
        fontFace: id.fonts.sans, fontSize: 7, bold: true,
        color: id.colors.muted, charSpacing: 3, align: "left", margin: 0,
      }));
      slide.addText(value, cloneOpts({
        x: metaX, y: my + 0.19, w: metaW, h: fieldH - 0.25,
        fontFace: id.fonts.sans, fontSize: 9,
        color: id.colors.ink, align: "left", valign: "top", margin: 0,
      }));
    });
  });

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
