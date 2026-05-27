// src/helpers/icon.js
// Phosphor outline icons rendered as PNG for crisp PPTX embedding
// Pipeline: SVG string -> sharp rasterize at 4x -> base64 PNG -> slide.addImage

import sharp from "sharp";

const ICONS = {
  "chart-line": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><path d="M232,208H32V48" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/><polyline points="208 80 152 136 112 96 56 152" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`,
  "chart-bar": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><path d="M232,208H32V48" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/><rect x="56" y="120" width="40" height="64" stroke="{COLOR}" stroke-width="16" fill="none"/><rect x="112" y="80" width="40" height="104" stroke="{COLOR}" stroke-width="16" fill="none"/><rect x="168" y="40" width="40" height="144" stroke="{COLOR}" stroke-width="16" fill="none"/></svg>`,
  "trend-up": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><polyline points="224 80 152 152 112 112 32 192" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" fill="none"/><polyline points="224 144 224 80 160 80" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`,
  "trend-down": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><polyline points="224 176 152 104 112 144 32 64" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" fill="none"/><polyline points="224 112 224 176 160 176" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`,
  "target": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><circle cx="128" cy="128" r="96" stroke="{COLOR}" stroke-width="16" fill="none"/><circle cx="128" cy="128" r="56" stroke="{COLOR}" stroke-width="16" fill="none"/><circle cx="128" cy="128" r="16" stroke="{COLOR}" stroke-width="16" fill="none"/></svg>`,
  "shield-warning": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><path d="M40,114.79V56a8,8,0,0,1,8-8H208a8,8,0,0,1,8,8v58.79c0,84.06-71.31,111.88-85.49,116.5a7.71,7.71,0,0,1-5,0C111.31,226.67,40,198.85,40,114.79Z" stroke="{COLOR}" stroke-width="16" fill="none"/><line x1="128" y1="104" x2="128" y2="144" stroke="{COLOR}" stroke-width="16" stroke-linecap="round"/><circle cx="128" cy="180" r="10" fill="{COLOR}"/></svg>`,
  "lightning": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><path d="M96,240a8,8,0,0,1-7.9-9.27L99.45,160H72a16,16,0,0,1-14.16-23.4L103.4,32.42A8,8,0,0,1,110.55,28H184a8,8,0,0,1,7.9,9.27L180.55,96H208a16,16,0,0,1,12.91,25.4l-118.39,118A8,8,0,0,1,96,240Z" stroke="{COLOR}" stroke-width="16" fill="none"/></svg>`,
  "users-three": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><circle cx="128" cy="116" r="44" stroke="{COLOR}" stroke-width="16" fill="none"/><path d="M22.65,200a112,112,0,0,1,210.7,0" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" fill="none"/></svg>`,
  "currency-circle-dollar": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><circle cx="128" cy="128" r="96" stroke="{COLOR}" stroke-width="16" fill="none"/><line x1="128" y1="72" x2="128" y2="184" stroke="{COLOR}" stroke-width="16" stroke-linecap="round"/><path d="M104,168h36a20,20,0,0,0,0-40H116a20,20,0,0,1,0-40h36" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" fill="none"/></svg>`,
  "clock-countdown": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><circle cx="128" cy="128" r="96" stroke="{COLOR}" stroke-width="16" fill="none"/><polyline points="128 80 128 128 168 152" stroke="{COLOR}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`,
  "magnifying-glass": `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none"><circle cx="116" cy="116" r="84" stroke="{COLOR}" stroke-width="16" fill="none"/><line x1="175.39" y1="175.39" x2="224" y2="224" stroke="{COLOR}" stroke-width="16" stroke-linecap="round"/></svg>`,
};

/**
 * Rasterize a Phosphor icon SVG to base64 PNG.
 * @param {string} iconName - Key from ICONS map
 * @param {string} color - Hex color WITHOUT "#" prefix (e.g., "0C1C23")
 * @param {number} sizePx - Output PNG size in pixels
 * @returns {Promise<string>} base64 data URI ready for slide.addImage
 */
export async function iconToBase64Png(iconName, color = "0C1C23", sizePx = 256) {
  const template = ICONS[iconName];
  if (!template) {
    throw new Error(`Unknown icon: ${iconName}. Available: ${Object.keys(ICONS).join(", ")}`);
  }
  const svg = template.replace(/{COLOR}/g, `#${color}`);
  const pngBuffer = await sharp(Buffer.from(svg))
    .resize(sizePx, sizePx)
    .png()
    .toBuffer();
  return `image/png;base64,${pngBuffer.toString("base64")}`;
}

/**
 * Add a Phosphor icon to a slide at specified location.
 */
export async function addIcon(slide, iconName, x, y, w, h, color = "0C1C23") {
  const data = await iconToBase64Png(iconName, color, 256);
  slide.addImage({ data, x, y, w, h });
}

export const AVAILABLE_ICONS = Object.keys(ICONS);
