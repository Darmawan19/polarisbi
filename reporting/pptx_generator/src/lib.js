// PolarisBI — slide primitive library
import { C, F, G, SECTIONS } from "./theme.js";

export function makeLib(pptx) {
  const S = pptx.ShapeType;
  const ICON = (name, color) => `out/icons/${name}__${color}.png`;

  // ---- atomic shapes -------------------------------------------------------
  const rect = (s, o) => s.addShape(S.rect, o);
  const rrect = (s, o) => s.addShape(S.roundRect, { rectRadius: 0.08, ...o });
  const ell = (s, o) => s.addShape(S.ellipse, o);
  const hline = (s, x, y, w, color = C.line, width = 1) =>
    s.addShape(S.line, { x, y, w, h: 0, line: { color, width } });

  // ---- text ---------------------------------------------------------------
  const txt = (s, text, o) =>
    s.addText(text, { fontFace: F.body, color: C.ink, fontSize: 11, valign: "top", ...o });

  // ---- page furniture ------------------------------------------------------
  function eyebrow(s, text, color = C.blue) {
    txt(s, text.toUpperCase(), {
      x: G.M, y: G.eyebrowY, w: G.CW, h: 0.28,
      fontFace: F.bodySemi, fontSize: 11, color, charSpacing: 2.4, bold: true,
    });
  }

  function title(s, text, color = C.navy) {
    txt(s, text, {
      x: G.M, y: G.titleY, w: 10.6, h: 1.05,
      fontFace: F.display, fontSize: 23, bold: true, color, lineSpacingMultiple: 1.02,
    });
  }

  function logo(s, dark = false) {
    const col = dark ? C.white : C.navy;
    s.addText(
      [
        { text: "Polaris", options: { color: col, bold: true } },
        { text: "BI", options: { color: C.blue, bold: true } },
      ],
      { x: G.W - 3.05, y: G.eyebrowY - 0.04, w: 2.0, h: 0.34, align: "right",
        fontFace: F.display, fontSize: 15, valign: "middle" }
    );
    ell(s, { x: G.W - 0.85, y: G.eyebrowY - 0.02, w: 0.30, h: 0.30,
      fill: { color: C.blue }, line: { type: "none" } });
    s.addImage({ path: ICON("target", "white"), x: G.W - 0.805, y: G.eyebrowY + 0.025, w: 0.21, h: 0.21 });
  }

  function navbar(s, activeSection, pageNum) {
    hline(s, G.M, G.navY - 0.06, G.CW, C.line, 1);
    const slotW = 2.0, startX = G.M + 0.05;
    SECTIONS.forEach((sec, i) => {
      const active = sec === activeSection;
      txt(s, sec, {
        x: startX + i * slotW, y: G.navY, w: slotW, h: 0.3,
        fontFace: F.bodySemi, fontSize: 9.5, charSpacing: 1.6,
        color: active ? C.blue : C.grayLt, bold: active, align: "left",
      });
    });
    // page block bottom-right
    rect(s, { x: G.W - 0.95, y: G.navY - 0.04, w: 0.5, h: 0.38, fill: { color: C.navy }, line: { type: "none" } });
    txt(s, String(pageNum), {
      x: G.W - 0.95, y: G.navY - 0.04, w: 0.5, h: 0.38, align: "center", valign: "middle",
      fontFace: F.display, fontSize: 13, bold: true, color: C.white,
    });
  }

  function source(s, text) {
    txt(s, "Source: " + text, {
      x: G.M, y: G.sourceY, w: G.CW - 1.2, h: 0.26,
      fontFace: F.body, fontSize: 8, italic: true, color: C.grayLt,
    });
  }

  // ---- components ----------------------------------------------------------
  // colored header band with white centered text
  function band(s, { x, y, w, h = 0.46, text, fill = C.royal, color = C.white, align = "center", size = 12.5 }) {
    rect(s, { x, y, w, h, fill: { color: fill }, line: { type: "none" } });
    txt(s, text, { x: x + 0.12, y, w: w - 0.24, h, align, valign: "middle",
      fontFace: F.semi, fontSize: size, color, charSpacing: 0.3 });
  }

  function card(s, { x, y, w, h, fill = C.white, line = C.line, dashed = false, width = 1, radius = 0.07 }) {
    rrect(s, { x, y, w, h, rectRadius: radius, fill: { color: fill },
      line: { color: line, width, dashType: dashed ? "dash" : "solid" } });
  }

  // icon inside a tinted circle
  function iconCircle(s, { x, y, d = 0.62, icon, color = "royal", circleFill = C.blueSoft, line = "none" }) {
    ell(s, { x, y, w: d, h: d, fill: { color: circleFill },
      line: line === "none" ? { type: "none" } : { color: line, width: 1 } });
    const pad = d * 0.27;
    s.addImage({ path: ICON(icon, color), x: x + pad, y: y + pad, w: d - pad * 2, h: d - pad * 2 });
  }

  // big stat: value + label (+ optional delta)
  function stat(s, { x, y, w, value, label, valueColor = C.navy, valueSize = 30, delta, deltaColor = C.green, align = "left" }) {
    txt(s, value, { x, y, w, h: 0.62, fontFace: F.display, fontSize: valueSize, bold: true,
      color: valueColor, align, valign: "middle" });
    let ly = y + 0.62;
    if (delta) {
      s.addText(
        [{ text: "▲ ", options: { color: deltaColor } }, { text: delta, options: { color: deltaColor } }],
        { x, y: ly, w, h: 0.26, fontFace: F.bodySemi, fontSize: 10.5, bold: true, align, valign: "middle" }
      );
      ly += 0.26;
    }
    txt(s, label, { x, y: ly, w, h: 0.3, fontFace: F.body, fontSize: 9.5, color: C.gray, align, valign: "top" });
  }

  function chevron(s, x, y, color = C.blue) {
    ell(s, { x, y, w: 0.42, h: 0.42, fill: { color }, line: { type: "none" } });
    s.addImage({ path: ICON("chevron-right", "white"), x: x + 0.10, y: y + 0.10, w: 0.22, h: 0.22 });
  }

  // styled bullet list
  function bullets(s, { x, y, w, h, items, fontSize = 10.5, color = C.ink, gap = 6, lh = 1.12 }) {
    const runs = items.map((it, i) => ({
      text: typeof it === "string" ? it : it.t,
      options: { bullet: { code: "2022", indent: 14 }, color,
        paraSpaceAfter: i === items.length - 1 ? 0 : gap, lineSpacingMultiple: lh },
    }));
    txt(s, runs, { x, y, w, h, fontFace: F.body, fontSize, valign: "top" });
  }

  function pill(s, { x, y, w, text, fill, color = C.white, size = 8.5 }) {
    rrect(s, { x, y, w, h: 0.26, rectRadius: 0.13, fill: { color }, line: { type: "none" } });
    txt(s, text.toUpperCase(), { x, y, w, h: 0.26, align: "center", valign: "middle",
      fontFace: F.bodySemi, fontSize: size, bold: true, color, charSpacing: 1.0 });
  }

  function bg(s, color = C.white) {
    rect(s, { x: 0, y: 0, w: G.W, h: G.H, fill: { color }, line: { type: "none" } });
  }

  return { S, ICON, rect, rrect, ell, hline, txt, eyebrow, title, logo, navbar,
    source, band, card, iconCircle, stat, chevron, bullets, pill, bg };
}
