// src/helpers/chip.js
// POLARIS signature: data category chips (small colored pills)
// Only renders when id.rules.dataChips === true

import { cloneOpts } from "./layout.js";

/**
 * Add a small category chip to top-right of a slide.
 * variant: "blue" | "green" | "amber" | "gray" | "red"
 */
export function addChip(slide, id, x, y, label, variant = "blue") {
  if (!id.rules.dataChips || !id.colors.chips) return;

  const chip = id.colors.chips[variant] || id.colors.chips.gray;
  const w = 1.2;
  const h = 0.24;

  slide.addShape("roundRect", cloneOpts({
    x, y, w, h,
    fill: { color: chip.fill },
    line: { color: chip.fill },
    rectRadius: 0.12,
  }));

  slide.addText(label.toUpperCase(), cloneOpts({
    x, y, w, h,
    fontFace: id.fonts.sans,
    fontSize: 7,
    bold: true,
    color: chip.text,
    align: "center",
    valign: "middle",
    charSpacing: 4,
    margin: 0,
  }));
}

/**
 * Auto-place chip top-right of slide (standard position).
 */
export function addTopRightChip(slide, id, label, variant = "blue") {
  addChip(slide, id, 11.43, id.margins.y, label, variant);
}
