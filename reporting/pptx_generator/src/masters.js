// src/masters.js
// Slide master factory — defines reusable slide templates per identity

import { cloneOpts } from "./helpers/layout.js";

/**
 * Build all slide masters for a given identity.
 * Call once per presentation, after pres.layout is set.
 */
export function buildMasters(pres, id) {
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 inches

  // === 1. COVER master ===
  pres.defineSlideMaster(cloneOpts({
    title: "COVER",
    background: { color: id.rules.darkCover ? id.colors.brand : id.colors.paper },
    objects: [
      {
        text: {
          text: "POLARISBI",
          options: {
            x: id.margins.x,
            y: 0.4,
            w: 4,
            h: 0.3,
            fontFace: id.fonts.mono,
            fontSize: 9,
            color: id.rules.darkCover ? "FFFFFF" : id.colors.muted,
            charSpacing: 4,
            margin: 0,
          },
        },
      },
    ],
  }));

  // === 2. CONTENT master ===
  pres.defineSlideMaster(cloneOpts({
    title: "CONTENT",
    background: { color: id.colors.paper },
    objects: id.rules.hairlineAboveFooter
      ? [
          {
            line: {
              x: id.margins.x,
              y: id.margins.footerY - 0.05,
              w: 13.333 - 2 * id.margins.x,
              h: 0,
              line: { color: id.colors.line, width: 0.5 },
            },
          },
        ]
      : [],
    slideNumber: {
      x: 12.5,
      y: id.margins.footerY,
      w: 0.7,
      h: 0.25,
      fontFace: id.fonts.mono,
      fontSize: id.sizes.footnote,
      color: id.colors.muted,
      align: "right",
    },
  }));

  // === 3. SECTION DIVIDER master ===
  pres.defineSlideMaster(cloneOpts({
    title: "SECTION",
    background: { color: id.colors.ink },
    objects: [],
  }));

  // === 4. APPENDIX master ===
  pres.defineSlideMaster(cloneOpts({
    title: "APPENDIX",
    background: { color: id.colors.stripe || id.colors.paper },
    objects: [
      {
        text: {
          text: "APPENDIX",
          options: {
            x: id.margins.x,
            y: 0.4,
            w: 4,
            h: 0.3,
            fontFace: id.fonts.mono,
            fontSize: 9,
            color: id.colors.muted,
            charSpacing: 4,
            margin: 0,
          },
        },
      },
    ],
    slideNumber: {
      x: 12.5,
      y: id.margins.footerY,
      w: 0.7,
      h: 0.25,
      fontFace: id.fonts.mono,
      fontSize: id.sizes.footnote,
      color: id.colors.muted,
      align: "right",
    },
  }));
}
