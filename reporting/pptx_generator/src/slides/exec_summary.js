// src/slides/exec_summary.js
// Executive summary — 3-column SCR with icons, accent strips, full height

import { cloneOpts, addFooter } from "../helpers/layout.js";
import { addActionTitle } from "../helpers/text.js";
import { addTopRightChip } from "../helpers/chip.js";
import { addCard, addIconCircle } from "../helpers/card.js";
import { iconToBase64Png } from "../helpers/icon.js";

export default async function buildExecSummarySlide(pres, id, context) {
  const slide = pres.addSlide();
  const d = context.data || {};

  if (id.rules.dataChips) addTopRightChip(slide, id, "Exec Summary", "blue");
  addActionTitle(slide, id, d.headline || "Executive Summary");

  const totalW = 13.333 - 2 * id.margins.x;
  const gap = 0.25;
  const colW = (totalW - gap * 2) / 3;
  const colY = id.margins.bodyY + 0.5;
  const colH = id.margins.footerY - colY - 0.25;

  const sections = [
    { label: "Situation",    icon: "magnifying-glass", accent: id.colors.neutral,  content: d.situation   || "", type: "text" },
    { label: "Complication", icon: "shield-warning",   accent: id.colors.warn,     content: d.complication|| "", type: "text" },
    { label: "Resolution",   icon: "target",           accent: id.colors.success,  content: d.resolution  || [], type: "bullets" },
  ];

  for (let i = 0; i < sections.length; i++) {
    const sec = sections[i];
    const x = id.margins.x + i * (colW + gap);

    // Card with top accent strip
    addCard(slide, id, x, colY, colW, colH, {
      fill: id.colors.stripe,
      borderColor: id.colors.line,
      accentColor: sec.accent,
      accentSide: "top",
      accentSize: 0.12,
    });

    // Icon circle (centered horizontally)
    const circleSize = 0.6;
    const circleX = x + (colW - circleSize) / 2;
    const circleY = colY + 0.3;
    const { iconX, iconY, iconSize } = addIconCircle(
      slide, id, circleX, circleY, circleSize, "FFFFFF", sec.accent
    );
    try {
      const img = await iconToBase64Png(sec.icon, sec.accent, 192);
      slide.addImage({ data: img, x: iconX, y: iconY, w: iconSize, h: iconSize });
    } catch (e) { /* skip — icon pipeline failure is non-fatal */ }

    // Section label (centered, bold caps)
    slide.addText(sec.label.toUpperCase(), cloneOpts({
      x: x + 0.15, y: circleY + circleSize + 0.18, w: colW - 0.3, h: 0.28,
      fontFace: id.fonts.sans, fontSize: 10, bold: true,
      color: sec.accent, charSpacing: 4,
      align: "center", margin: 0,
    }));

    // Accent underline
    slide.addShape("line", cloneOpts({
      x: x + colW * 0.3, y: circleY + circleSize + 0.52,
      w: colW * 0.4, h: 0,
      line: { color: sec.accent, width: 1.5 },
    }));

    // Content
    const contentY = circleY + circleSize + 0.68;
    const contentH = colY + colH - contentY - 0.2;

    if (sec.type === "bullets") {
      const items = Array.isArray(sec.content) ? sec.content : [];
      slide.addText(items.join("\n"), cloneOpts({
        x: x + 0.3, y: contentY, w: colW - 0.6, h: contentH,
        fontFace: id.fonts.sans, fontSize: 11,
        color: id.colors.ink, align: "left", valign: "top",
        margin: [0, 0, 0, 8], bullet: true, paraSpaceAfter: 5,
      }));
    } else {
      slide.addText(sec.content, cloneOpts({
        x: x + 0.3, y: contentY, w: colW - 0.6, h: contentH,
        fontFace: id.fonts.sans, fontSize: 11,
        color: id.colors.ink, align: "left", valign: "top",
        margin: 0,
      }));
    }
  }

  addFooter(slide, id, {
    source: d.source,
    pageNum: context.pageNum,
    totalPages: context.totalPages,
  });
}
