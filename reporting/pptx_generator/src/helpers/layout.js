// src/helpers/layout.js
// Layout utilities: cloneOpts (avoid pptxgenjs mutation bug), footer, section divider

/**
 * Deep-clone options object to prevent pptxgenjs from mutating shared references.
 * REQUIRED: pptxgenjs mutates option objects in-place (converts to EMU).
 * Sharing one options object across calls corrupts the second call.
 */
export function cloneOpts(opts) {
  return JSON.parse(JSON.stringify(opts));
}

/**
 * Add a standardized footer to a content slide.
 * Includes optional hairline (BCG, POLARIS), source line, page number.
 */
export function addFooter(slide, id, { source, pageNum, totalPages }) {
  if (id.rules.hairlineAboveFooter) {
    slide.addShape("line", {
      x: id.margins.x,
      y: id.margins.footerY - 0.05,
      w: 13.333 - 2 * id.margins.x,
      h: 0,
      line: { color: id.colors.line, width: 0.5 },
    });
  }

  if (source) {
    slide.addText(`Source: ${source}`, {
      x: id.margins.x,
      y: id.margins.footerY,
      w: 10,
      h: 0.25,
      fontFace: id.fonts.sans,
      fontSize: id.sizes.footnote,
      color: id.colors.muted,
      italic: false,
    });
  }

  if (pageNum) {
    const pageText = totalPages ? `${pageNum} / ${totalPages}` : `${pageNum}`;
    slide.addText(pageText, {
      x: 12.5,
      y: id.margins.footerY,
      w: 0.7,
      h: 0.25,
      fontFace: id.fonts.mono,
      fontSize: id.sizes.footnote,
      color: id.colors.muted,
      align: "right",
    });
  }
}

/**
 * Render the dark section-divider band (POLARIS, McKinsey, BCG covers).
 * Bain skips this — always light covers.
 */
export function addDarkBackground(slide, id) {
  slide.background = { color: id.colors.brand };
}

/**
 * Format an ISO date as locale-aware short form.
 * "2026-05-28" -> "28 May 2026" (en) or "28 Mei 2026" (id)
 */
export function formatDate(iso, lang = "en") {
  const d = new Date(iso);
  const months = {
    en: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
    id: ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"],
  };
  return `${d.getDate()} ${months[lang][d.getMonth()]} ${d.getFullYear()}`;
}

/**
 * Format IDR currency the Indonesian way: "Rp1.438,11 triliun"
 */
export function formatIDR(value, unit = "triliun") {
  const formatted = value.toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `Rp${formatted} ${unit}`;
}
