// src/helpers/chip.js
// POLARIS data category chips — auto-width to prevent wrapping

import { cloneOpts } from "./layout.js";

function chipWidth(label) {
  // ~0.075 inches per char at 8pt with charSpacing 3
  return Math.max(0.7, label.length * 0.075 + 0.3);
}

export function addChip(slide, id, x, y, label, variant = "blue") {
  if (!id.rules.dataChips || !id.colors.chips) return;

  const chip = id.colors.chips[variant] || id.colors.chips.gray;
  const w = chipWidth(label);
  const h = 0.26;

  slide.addShape("roundRect", cloneOpts({
    x, y, w, h,
    fill: { color: chip.fill },
    line: { color: chip.fill },
    rectRadius: 0.13,
  }));

  slide.addText(label.toUpperCase(), cloneOpts({
    x, y, w, h,
    fontFace: id.fonts.sans,
    fontSize: 8,
    bold: true,
    color: chip.text,
    align: "center",
    valign: "middle",
    charSpacing: 3,
    margin: 0,
  }));
}

/**
 * Place chip top-right, above the title area (y=0.18 is in the margin band).
 */
export function addTopRightChip(slide, id, label, variant = "blue") {
  const w = chipWidth(label);
  const x = 13.333 - id.margins.x - w;
  addChip(slide, id, x, 0.18, label, variant);
}
