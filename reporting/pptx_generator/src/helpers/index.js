// src/helpers/index.js
// Single import surface for all helpers

export { cloneOpts, addFooter, addDarkBackground, formatDate } from "./layout.js";
export { addActionTitle, addSubtitle, addBody, addInlineCallout, addSectionLabel } from "./text.js";
export { addStatHero, addKpiTile } from "./stat.js";
export { addChip, addTopRightChip } from "./chip.js";
export { addColumnChart, addBarChart, addLineChart, addGroupedColumnChart } from "./chart.js";
export { iconToBase64Png, addIcon, AVAILABLE_ICONS } from "./icon.js";
export { formatNumber, CHART_NUMFMT } from "./formatters.js";
export { addCard, addIconCircle } from "./card.js";
