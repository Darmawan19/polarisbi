// src/helpers/text.js
// Text primitives: action title, body, inline data callouts (POLARIS signature)

import { cloneOpts } from "./layout.js";

/**
 * Action title — the most important element on every content slide.
 * Full-sentence "so-what" insight, left-aligned, serif for McKinsey/POLARIS,
 * sans for BCG/Bain. Max 2 lines.
 */
export function addActionTitle(slide, id, text, opts = {}) {
  slide.addText(text, cloneOpts({
    x: id.margins.x,
    y: id.margins.y,
    w: 13.333 - 2 * id.margins.x,
    h: 0.8,
    fontFace: (id.name === "McKinsey" || id.name === "PolarisBI") ? id.fonts.serif : id.fonts.sans,
    fontSize: id.sizes.title,
    bold: true,
    color: id.colors.ink,
    align: "left",
    valign: "top",
    margin: 0,
    ...opts,
  }));
}

/**
 * Subtitle / takeaway line under action title.
 * Italic muted, BCG gets an underline accent.
 */
export function addSubtitle(slide, id, text, opts = {}) {
  slide.addText(text, cloneOpts({
    x: id.margins.x,
    y: id.margins.y + 0.85,
    w: 13.333 - 2 * id.margins.x,
    h: 0.35,
    fontFace: id.fonts.sans,
    fontSize: id.sizes.subtitle,
    italic: true,
    color: id.colors.muted,
    align: "left",
    valign: "top",
    margin: 0,
    ...opts,
  }));

  if (id.rules.underlineSubtitle) {
    slide.addShape("line", cloneOpts({
      x: id.margins.x,
      y: id.margins.y + 1.18,
      w: 2.5,
      h: 0,
      line: { color: id.colors.brand, width: 0.75 },
    }));
  }
}

/**
 * Plain body paragraph.
 */
export function addBody(slide, id, text, opts = {}) {
  slide.addText(text, cloneOpts({
    fontFace: id.fonts.sans,
    fontSize: id.sizes.body,
    color: id.colors.ink,
    align: "left",
    valign: "top",
    margin: 0,
    ...opts,
  }));
}

/**
 * Inline data callout (POLARIS signature).
 * Stripe Press style: bolded colored numbers inline with prose.
 * Input: array of {text, emphasis: bool} segments.
 */
export function addInlineCallout(slide, id, segments, opts = {}) {
  if (!id.rules.inlineCallouts) {
    const plainText = segments.map(s => s.text).join("");
    return addBody(slide, id, plainText, opts);
  }

  const runs = segments.map(seg => ({
    text: seg.text,
    options: seg.emphasis
      ? { bold: true, color: id.colors.signal || id.colors.brand }
      : { color: id.colors.ink },
  }));

  slide.addText(runs, cloneOpts({
    fontFace: id.fonts.sans,
    fontSize: id.sizes.body + 2,
    align: "left",
    valign: "top",
    margin: 0,
    ...opts,
  }));
}

/**
 * Section header label (small uppercase muted text above a body block).
 */
export function addSectionLabel(slide, id, text, opts = {}) {
  slide.addText(text.toUpperCase(), cloneOpts({
    fontFace: id.fonts.sans,
    fontSize: 9,
    bold: true,
    color: id.colors.muted,
    charSpacing: 4,
    align: "left",
    valign: "top",
    margin: 0,
    ...opts,
  }));
}
