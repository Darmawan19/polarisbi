// src/helpers/card.js
// Consistent card + icon circle primitives used across all slide builders

import { cloneOpts } from "./layout.js";

/**
 * Draw a card with optional accent strip (left or top edge).
 * opts: { fill, borderColor, borderWidth, accentColor, accentSide, accentSize }
 */
export function addCard(slide, id, x, y, w, h, opts = {}) {
  const fill        = opts.fill        || "FFFFFF";
  const borderColor = opts.borderColor || id.colors.line;
  const borderWidth = opts.borderWidth !== undefined ? opts.borderWidth : 0.75;
  const accentColor = opts.accentColor;
  const accentSide  = opts.accentSide  || "left";
  const accentSize  = opts.accentSize  || 0.1;

  slide.addShape("rect", cloneOpts({
    x, y, w, h,
    fill: { color: fill },
    line: { color: borderColor, width: borderWidth },
  }));

  if (accentColor && accentSide === "left") {
    slide.addShape("rect", cloneOpts({
      x, y, w: accentSize, h,
      fill: { color: accentColor },
      line: { color: accentColor },
    }));
  } else if (accentColor && accentSide === "top") {
    slide.addShape("rect", cloneOpts({
      x, y, w, h: accentSize,
      fill: { color: accentColor },
      line: { color: accentColor },
    }));
  }
}

/**
 * Add a circle background for an icon.
 * Returns the inner coordinates where the icon image should be placed.
 */
export function addIconCircle(slide, id, x, y, size, fillColor, lineColor = null) {
  slide.addShape("ellipse", cloneOpts({
    x, y, w: size, h: size,
    fill: { color: fillColor },
    line: { color: lineColor || fillColor, width: 0.5 },
  }));
  return {
    iconX: x + size * 0.22,
    iconY: y + size * 0.22,
    iconSize: size * 0.56,
  };
}
