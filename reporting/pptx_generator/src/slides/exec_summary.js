// src/slides/exec_summary.js
import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle, addSectionLabel, addBody } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";

export default async function buildExecSummarySlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  addActionTitle(slide, id, d.headline || "Executive Summary");
  if (id.rules.dataChips) addTopRightChip(slide, id, "EXEC SUMMARY", "blue");

  const n = 3;
  const gap = 0.2;
  const totalW = 13.333 - 2 * id.margins.x;
  const colW = (totalW - gap * (n - 1)) / n;
  const colY = id.margins.bodyY + 0.12;
  const textH = id.margins.footerY - colY - 0.55;

  const accents = [id.colors.neutral, id.colors.warn, id.colors.success];
  const labels  = ["Situation", "Complication", "Resolution"];

  labels.forEach((label, i) => {
    const x = id.margins.x + i * (colW + gap);

    addSectionLabel(slide, id, label, { x, y: colY, w: colW, h: 0.22 });

    slide.addShape("line", cloneOpts({
      x, y: colY + 0.28, w: colW * 0.35, h: 0,
      line: { color: accents[i], width: 1.5 },
    }));

    const textY = colY + 0.48;

    if (i === 2) {
      const bullets = Array.isArray(d.resolution) ? d.resolution : [];
      slide.addText(bullets.join("\n"), cloneOpts({
        x, y: textY, w: colW, h: textH,
        fontFace: id.fonts.sans, fontSize: id.sizes.body,
        color: id.colors.ink, align: "left", valign: "top",
        margin: [0, 0, 0, 8], bullet: true, paraSpaceAfter: 5,
      }));
    } else {
      const text = i === 0 ? (d.situation || "") : (d.complication || "");
      addBody(slide, id, text, {
        x, y: textY, w: colW, h: textH,
      });
    }
  });

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
