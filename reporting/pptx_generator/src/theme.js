// PolarisBI — design theme (MetaMind-grade consulting language)
export const C = {
  ink:    "1A2230",   // primary text near-black
  navy:   "0C2340",   // deep navy: cover, dark bands, table headers
  royal:  "164E96",   // primary brand blue: band headers, accents
  blue:   "2F6FE0",   // bright accent: links, active nav, highlights
  blueSoft:"E8F0FC",  // tint: icon circles, highlighted rows/cards
  blueLine:"BCD3F0",
  green:  "2E9E5B",   // positive / up
  amber:  "D98A1F",   // medium severity
  red:    "D64545",   // high severity
  gray:   "6B7689",   // muted text
  grayLt: "9AA4B6",   // lighter muted
  line:   "DCE2EC",   // hairline borders
  cardBg: "F6F8FC",   // soft card fill
  white:  "FFFFFF",
};

export const F = {
  display: "Poppins",          // titles, big numbers (use bold:true for 700)
  semi:    "Poppins SemiBold",  // band headers, sub-heads (600, no bold flag)
  body:    "Inter",             // body copy
  bodySemi:"Inter SemiBold",    // labels, emphasis
  bodyMed: "Inter Medium",
};

export const G = {
  W: 13.333, H: 7.5,
  M: 0.55,                       // page margin
  get CW() { return this.W - this.M * 2; },
  eyebrowY: 0.40,
  titleY: 0.70,
  contentTop: 1.95,
  navY: 7.02,
  sourceY: 6.64,
};

// bottom-nav sections
export const SECTIONS = ["MARKET", "PERFORMANCE", "COMPETITION", "ACTIONS"];
