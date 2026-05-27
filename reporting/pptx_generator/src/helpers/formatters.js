// src/helpers/formatters.js
// Number, currency, percentage formatting

/**
 * Format a number with locale-aware separators.
 * 1438.11 -> "1,438.11" (en-US) or "1.438,11" (id-ID)
 */
export function formatNumber(value, locale = "en-US", decimals = 2) {
  if (typeof value !== "number") return String(value);
  return value.toLocaleString(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Format IDR: 1438.11 -> "Rp 1.438,11 T"
 */
export function formatIDR(value, unit = "T", locale = "id-ID") {
  const formatted = formatNumber(value, locale, 2);
  return `Rp ${formatted}${unit ? " " + unit : ""}`;
}

/**
 * Chart data label format codes for pptxgenjs dataLabelFormatCode.
 * These control how numbers appear on chart bars/lines.
 */
export const CHART_NUMFMT = {
  trillions: `#,##0.0"T"`,
  billions:  `#,##0"B"`,
  millions:  `#,##0"M"`,
  percent:   "0.0%",
  decimal:   "#,##0.00",
  integer:   "#,##0",
};
