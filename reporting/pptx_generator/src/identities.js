// src/identities.js
// 4-identity design token system for PolarisBI PPTX Generator
// Source: research/PolarisBI 4-Identity Design System Spec (May 2026)

export const IDENTITIES = {
  mckinsey: {
    name: "McKinsey",
    colors: {
      brand:    "051C2C",
      brandAlt: "2251FF",
      ink:      "000000",
      muted:    "666666",
      neutral:  "B3B3B3",
      line:     "E5E5E5",
      paper:    "FFFFFF",
      stripe:   "F2F2F2",
      success:  "27AE60",
      warn:     "D68910",
      danger:   "C0392B",
    },
    fonts: { serif: "Georgia", sans: "Arial", mono: "Consolas" },
    sizes: { title: 22, subtitle: 13, body: 11, footnote: 8, stat: 60, divider: 40, coverTitle: 36 },
    margins: { x: 0.5, y: 0.35, bodyY: 1.4, footerY: 7.05 },
    chart: { palette: ["051C2C","B3B3B3","666666","2251FF","D9D9D9","8C8C8C"] },
    rules: {
      underlineSubtitle: false,
      hairlineAboveFooter: false,
      darkCover: true,
      heavyWhitespace: false,
      dataChips: false,
      inlineCallouts: false,
      statHeroSerif: true,
    },
  },

  bcg: {
    name: "BCG",
    colors: {
      brand:    "147B58",
      brandAlt: "00532F",
      ink:      "212121",
      muted:    "5F6368",
      neutral:  "B0B0B0",
      line:     "E1E5E1",
      paper:    "FFFFFF",
      stripe:   "F4F6F5",
      success:  "27AE60",
      warn:     "D68910",
      danger:   "C0392B",
    },
    fonts: { serif: "Georgia", sans: "Arial", mono: "Consolas" },
    sizes: { title: 20, subtitle: 12, body: 11, footnote: 8, stat: 48, divider: 36, coverTitle: 36 },
    margins: { x: 0.5, y: 0.4, bodyY: 1.4, footerY: 7.05 },
    chart: { palette: ["147B58","B0B0B0","5F6368","00532F","D9D9D9","8C8C8C"] },
    rules: {
      underlineSubtitle: true,
      hairlineAboveFooter: true,
      darkCover: true,
      heavyWhitespace: false,
      dataChips: false,
      inlineCallouts: false,
      statHeroSerif: false,
      calloutBoxes: true,
    },
  },

  bain: {
    name: "Bain",
    colors: {
      brand:    "CB2026",
      brandAlt: "EE3224",
      ink:      "1A1A1A",
      muted:    "5A5A5A",
      neutral:  "BDBDBD",
      line:     "E5E5E5",
      paper:    "FFFFFF",
      stripe:   "F5F5F5",
      success:  "27AE60",
      warn:     "D68910",
      danger:   "C0392B",
    },
    fonts: { serif: "Georgia", sans: "Arial", mono: "Consolas" },
    sizes: { title: 22, subtitle: 13, body: 11, footnote: 8, stat: 72, divider: 44, coverTitle: 40 },
    margins: { x: 0.7, y: 0.4, bodyY: 1.4, footerY: 7.05 },
    chart: { palette: ["CB2026","BDBDBD","5A5A5A","EE3224","D9D9D9","8C8C8C"] },
    rules: {
      underlineSubtitle: false,
      hairlineAboveFooter: false,
      darkCover: false,
      heavyWhitespace: true,
      dataChips: false,
      inlineCallouts: false,
      statHeroSerif: false,
    },
  },

  polaris: {
    name: "PolarisBI",
    colors: {
      brand:               "0C1C23",
      brandAlt:            "1F78B4",
      signal:              "1F78B4",
      clientTint:          "0857C3",
      clientTintSecondary: "307FE2",
      clientTintAccent:    "71C5EB",
      ink:                 "0C1C23",
      paper:               "FAFAF7",
      muted:               "666B6F",
      neutral:             "B3B6B9",
      line:                "E1E5E8",
      success:             "33A02C",
      warn:                "FF7F00",
      danger:              "E31A1C",
      stripe:              "F4F5F6",
      chips: {
        blue:  { fill: "E8F1FB", text: "1F4F7A" },
        green: { fill: "E9F5EA", text: "1F5E2A" },
        amber: { fill: "FDF1E1", text: "7A4A0F" },
        gray:  { fill: "EDEEEF", text: "3A3D40" },
        red:   { fill: "FCE8E8", text: "7A1F1F" },
      },
    },
    fonts: { serif: "Georgia", sans: "Arial", mono: "Consolas" },
    sizes: { title: 22, subtitle: 13, body: 11, footnote: 8, stat: 80, divider: 44, coverTitle: 36 },
    margins: { x: 0.75, y: 0.4, bodyY: 1.45, footerY: 7.0 },
    chart: { palette: ["1F78B4","E31A1C","33A02C","FF7F00","6A3D9A","666B6F"] },
    rules: {
      underlineSubtitle: false,
      hairlineAboveFooter: true,
      darkCover: true,
      heavyWhitespace: false,
      dataChips: true,
      inlineCallouts: true,
      statHeroSerif: true,
    },
  },
};

export function getIdentity(name) {
  const key = (name || "polaris").toLowerCase();
  if (!IDENTITIES[key]) {
    console.warn(`[identity] Unknown identity "${name}", falling back to polaris`);
    return IDENTITIES.polaris;
  }
  return IDENTITIES[key];
}

export const VALID_IDENTITIES = Object.keys(IDENTITIES);
