"""
Build a consulting-grade Word document for the BRI Life FY2024 industry briefing.
Brand-matched to the PPTX deck: navy/royal/inter/poppins palette.
"""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from reporting.report_data import REPORT

_OUT_DIR = Path(__file__).resolve().parent / "out"
_OUT_FILE = _OUT_DIR / "PolarisBI-BRILife-FY2024-Report.docx"

# ── Color helpers ─────────────────────────────────────────────────────────────

def _hex(h: str) -> RGBColor:
    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

C_NAVY     = _hex("0C2340")
C_ROYAL    = _hex("164E96")
C_BLUE     = _hex("2F6FE0")
C_BLUE_SOFT = _hex("E8F0FC")
C_GREEN    = _hex("2E9E5B")
C_AMBER    = _hex("D98A1F")
C_RED      = _hex("D64545")
C_GRAY     = _hex("6B7689")
C_GRAY_LT  = _hex("9AA4B6")
C_LINE     = _hex("DCE2EC")
C_CARD_BG  = _hex("F6F8FC")
C_WHITE    = _hex("FFFFFF")
C_INK      = _hex("1A2230")

SEV_COLOR = {"red": C_RED, "amber": C_AMBER, "green": C_GREEN}

# ── XML utilities ─────────────────────────────────────────────────────────────

def _set_cell_bg(cell, hex_color: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color.lstrip("#"))
    tcPr.append(shd)


def _set_cell_borders(cell, *, top=None, bottom=None, left=None, right=None):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for side, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        if val:
            el = OxmlElement(f"w:{side}")
            el.set(qn("w:val"), val.get("val", "single"))
            el.set(qn("w:sz"), str(val.get("sz", 4)))
            el.set(qn("w:color"), val.get("color", "auto"))
            borders.append(el)
    tcPr.append(borders)


def _set_table_border(table, hex_color: str = "DCE2EC", sz: int = 4):
    tbl = table._tbl
    tblPr = tbl.tblPr
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    tblBorders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:color"), hex_color.lstrip("#"))
        tblBorders.append(el)
    tblPr.append(tblBorders)


def _set_col_widths(table, widths_in: list[float]):
    """Apply column widths in inches to a table."""
    for i, col in enumerate(table.columns):
        if i < len(widths_in):
            col.width = Inches(widths_in[i])


def _set_cant_split(table):
    """Prevent any single row from splitting across a page boundary."""
    for row in table.rows:
        trPr = row._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit")
        trPr.append(cs)


def _keep_next(para):
    """Keep this paragraph on the same page as the one that follows it."""
    pPr = para._p.get_or_add_pPr()
    kn = OxmlElement("w:keepNext")
    pPr.append(kn)


def _para_spacing(para, before: int = 0, after: int = 0, line: int = None):
    pPr = para._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), str(before))
    spacing.set(qn("w:after"), str(after))
    if line:
        spacing.set(qn("w:line"), str(line))
        spacing.set(qn("w:lineRule"), "auto")
    pPr.append(spacing)


def _add_rule(doc, hex_color: str = "164E96", thickness_pt: int = 2):
    """A thin colored horizontal rule paragraph."""
    p = doc.add_paragraph()
    _para_spacing(p, before=0, after=80)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(thickness_pt * 4))
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), hex_color.lstrip("#"))
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


# ── Text helpers ──────────────────────────────────────────────────────────────

def _run(para, text: str, *, bold=False, italic=False, color=None,
         size=None, font="Inter"):
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.name = run.font.name  # keep existing, will be overridden
    run.font.name = font
    # Set east-asia and ascii to same font via XML so it applies in Word
    rPr = run._r.get_or_add_rPr()
    for tag in ("w:rFonts",):
        existing = rPr.find(qn(tag))
        if existing is not None:
            rPr.remove(existing)
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), font)
    rFonts.set(qn("w:hAnsi"), font)
    rFonts.set(qn("w:eastAsia"), font)
    rPr.insert(0, rFonts)
    if color:
        run.font.color.rgb = color
    if size:
        run.font.size = size
    return run


def _heading(doc, text: str, level: int = 1):
    """Section heading with royal-blue rule underneath."""
    p = doc.add_paragraph()
    _para_spacing(p, before=280, after=40)
    if level == 1:
        _run(p, text, bold=True, color=C_NAVY, size=Pt(16), font="Poppins")
    else:
        _run(p, text, bold=True, color=C_ROYAL, size=Pt(13), font="Poppins")
    _keep_next(p)
    rule = _add_rule(doc, "164E96" if level == 1 else "DCE2EC", thickness_pt=2 if level == 1 else 1)
    _keep_next(rule)
    return p


def _body(doc, text: str, *, color=None, size=Pt(10.5), italic=False, before=40, after=80):
    p = doc.add_paragraph()
    _para_spacing(p, before=before, after=after, line=276)  # 276 twips ≈ 1.15× line
    _run(p, text, color=color or C_INK, size=size, italic=italic)
    return p


def _label(doc, text: str, color=None):
    p = doc.add_paragraph()
    _para_spacing(p, before=0, after=20)
    _run(p, text.upper(), bold=True, color=color or C_GRAY_LT, size=Pt(8.5), font="Inter")
    return p


# ── Page layout ───────────────────────────────────────────────────────────────

def _set_margins(doc):
    for section in doc.sections:
        section.top_margin    = Inches(0.85)
        section.bottom_margin = Inches(0.85)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)


# ── Cover block ───────────────────────────────────────────────────────────────

def _build_cover(doc):
    meta = REPORT["meta"]

    # eyebrow
    ey = doc.add_paragraph()
    _para_spacing(ey, before=0, after=80)
    _run(ey, f"{meta['org'].upper()}  ·  {meta['period']}",
         bold=True, color=C_ROYAL, size=Pt(9.5), font="Inter")

    # title
    t = doc.add_paragraph()
    _para_spacing(t, before=80, after=60)
    _run(t, meta["title"], bold=True, color=C_NAVY, size=Pt(26), font="Poppins")

    # subtitle
    _body(doc, meta["subtitle"], color=C_GRAY, size=Pt(12), before=0, after=40)

    _add_rule(doc, "164E96", thickness_pt=3)

    # author + date on same line via tab
    p = doc.add_paragraph()
    _para_spacing(p, before=60, after=240)
    _run(p, meta["author"], color=C_INK, size=Pt(10))
    _run(p, f"   ·   {meta['date']}", color=C_GRAY_LT, size=Pt(10))


# ── KPI table ─────────────────────────────────────────────────────────────────

def _build_kpis(doc):
    _heading(doc, "Key Performance Indicators", level=1)

    kpis = REPORT["kpis"]
    table = doc.add_table(rows=2, cols=len(kpis))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_border(table, "DCE2EC", sz=4)
    _set_col_widths(table, [1.55] * len(kpis))
    _set_cant_split(table)

    # header row — metric labels
    for i, k in enumerate(kpis):
        cell = table.cell(0, i)
        _set_cell_bg(cell, "0C2340")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, k["label"].upper(), bold=True, color=C_WHITE, size=Pt(9), font="Inter")
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    # value row
    for i, k in enumerate(kpis):
        cell = table.cell(1, i)
        _set_cell_bg(cell, "E8F0FC" if i == 0 else "F6F8FC")
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, k["value"] + "\n", bold=True, color=C_NAVY, size=Pt(18), font="Poppins")
        _run(p, "▲ " + k["delta"], color=C_GREEN, size=Pt(9), font="Inter")

    for cell in table.rows[-1].cells:
        for p in cell.paragraphs:
            _keep_next(p)
    doc.add_paragraph()  # breathing room


# ── Executive summary (SCR) ───────────────────────────────────────────────────

def _build_exec_summary(doc):
    _heading(doc, "Executive Summary", level=1)
    _body(doc,
          "BRI Life captured 11.4% of new APE in FY2024, driven by bancassurance acceleration "
          "across BRI's 33,000-outlet network.",
          before=0, after=120)

    for item in REPORT["scr"]:
        color_map = {"Situation": C_ROYAL, "Complication": C_AMBER, "Resolution": C_GREEN}
        tag_color = color_map.get(item["tag"], C_ROYAL)

        # tag + figure on one line
        p = doc.add_paragraph()
        _para_spacing(p, before=120, after=20)
        _run(p, item["tag"].upper() + "  ", bold=True, color=tag_color, size=Pt(10), font="Inter")
        _run(p, item["fig"], bold=True, color=C_NAVY, size=Pt(22), font="Poppins")

        # fig label
        fl = doc.add_paragraph()
        _para_spacing(fl, before=0, after=40)
        _run(fl, item["fig_label"], italic=True, color=C_GRAY, size=Pt(9), font="Inter")

        # body
        _body(doc, item["body"], before=0, after=100)

        # subtle rule between SCR items (not after last)
        if item != REPORT["scr"][-1]:
            _add_rule(doc, "DCE2EC", thickness_pt=1)


# ── Market context ────────────────────────────────────────────────────────────

def _build_market(doc):
    _heading(doc, "Market Context", level=1)
    _body(doc, REPORT["market"]["headline"], before=0, after=100)
    for f in REPORT["market"]["facts"]:
        p = doc.add_paragraph()
        _para_spacing(p, before=80, after=20)
        _run(p, f["h"] + "  ", bold=True, color=C_NAVY, size=Pt(11), font="Poppins")
        _body(doc, f["b"], before=0, after=60)


# ── Channel deep-dive ─────────────────────────────────────────────────────────

def _build_channels(doc):
    _heading(doc, "Performance Deep Dive — Distribution Channels", level=1)
    ch = REPORT["channels"]
    _body(doc, ch["headline"], before=0, after=40)
    _body(doc, ch["subtitle"], italic=True, color=C_GRAY, size=Pt(9.5), before=0, after=100)

    # channel table: label | FY23 | FY24 | change
    table = doc.add_table(rows=len(ch["labels"]) + 1, cols=4)
    _set_table_border(table, "DCE2EC", sz=4)
    _set_col_widths(table, [2.0, 1.5, 1.5, 1.4])
    _set_cant_split(table)

    # header
    for ci, hdr in enumerate(["Channel", "FY2023 (Rp T)", "FY2024 (Rp T)", "Change"]):
        cell = table.cell(0, ci)
        _set_cell_bg(cell, "0C2340")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ci > 0 else WD_ALIGN_PARAGRAPH.LEFT
        _run(p, hdr, bold=True, color=C_WHITE, size=Pt(9.5), font="Inter")

    for ri, label in enumerate(ch["labels"]):
        fy23 = ch["fy23"][ri]
        fy24 = ch["fy24"][ri]
        pct = round((fy24 - fy23) / fy23 * 100, 1)
        change = f"+{pct}%" if pct >= 0 else f"{pct}%"
        change_color = C_GREEN if pct >= 0 else C_RED
        bg = "E8F0FC" if label == "Bancassurance" else "FFFFFF"
        for ci, (val, align) in enumerate([
            (label,      WD_ALIGN_PARAGRAPH.LEFT),
            (str(fy23),  WD_ALIGN_PARAGRAPH.CENTER),
            (str(fy24),  WD_ALIGN_PARAGRAPH.CENTER),
            (change,     WD_ALIGN_PARAGRAPH.CENTER),
        ]):
            cell = table.cell(ri + 1, ci)
            _set_cell_bg(cell, bg)
            p = cell.paragraphs[0]
            p.alignment = align
            col = C_ROYAL if label == "Bancassurance" else (change_color if ci == 3 else C_INK)
            _run(p, val, bold=(label == "Bancassurance"), color=col, size=Pt(10), font="Inter")

    for cell in table.rows[-1].cells:
        for p in cell.paragraphs:
            _keep_next(p)
    doc.add_paragraph()

    _heading(doc, "Key Insights", level=2)
    for ins in ch["insights"]:
        p = doc.add_paragraph()
        _para_spacing(p, before=80, after=20)
        _run(p, ins["h"] + "  ", bold=True, color=C_NAVY, size=Pt(11), font="Poppins")
        _body(doc, ins["b"], before=0, after=60)


# ── Competitive comparison ────────────────────────────────────────────────────

def _build_comparison(doc):
    _heading(doc, "Competitive Comparison", level=1)
    cmp = REPORT["compare"]
    _body(doc, cmp["headline"], before=0, after=100)

    cols = cmp["cols"]
    hl   = cmp["highlight"]

    table = doc.add_table(rows=len(cmp["rows"]) + 1, cols=len(cols) + 1)
    _set_table_border(table, "DCE2EC", sz=4)
    _set_col_widths(table, [1.8, 1.25, 1.15, 1.15, 1.05])
    _set_cant_split(table)

    # header
    cell = table.cell(0, 0)
    _set_cell_bg(cell, "0C2340")
    _run(cell.paragraphs[0], "METRIC", bold=True, color=C_WHITE, size=Pt(9), font="Inter")
    for ci, col in enumerate(cols):
        cell = table.cell(0, ci + 1)
        _set_cell_bg(cell, "0C2340" if ci == hl else "1A2230")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, col, bold=True, color=C_WHITE, size=Pt(10), font="Poppins")

    for ri, row in enumerate(cmp["rows"]):
        # metric label
        cell = table.cell(ri + 1, 0)
        _set_cell_bg(cell, "F6F8FC")
        _run(cell.paragraphs[0], row["metric"], color=C_GRAY, size=Pt(10), font="Inter")
        for ci, (val, rnk) in enumerate(zip(row["values"], row["rank"])):
            cell = table.cell(ri + 1, ci + 1)
            _set_cell_bg(cell, "E8F0FC" if ci == hl else "FFFFFF")
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _run(p, val + " ", bold=(ci == hl), color=C_ROYAL if ci == hl else C_INK,
                 size=Pt(10.5), font="Inter")
            _run(p, rnk, color=C_GRAY_LT, size=Pt(8.5), font="Inter")

    for cell in table.rows[-1].cells:
        for p in cell.paragraphs:
            _keep_next(p)
    spacer = doc.add_paragraph()
    _keep_next(spacer)
    # readout band
    ro = doc.add_paragraph()
    _para_spacing(ro, before=80, after=80)
    _run(ro, "STRATEGIC READOUT  ", bold=True, color=C_ROYAL, size=Pt(9), font="Inter")
    _run(ro, cmp["readout"], color=C_INK, size=Pt(10), font="Inter")


# ── Top-10 peers ──────────────────────────────────────────────────────────────

def _build_peers(doc):
    _heading(doc, "Top 10 League Table", level=1)
    peers = REPORT["peers"]
    _body(doc, peers["headline"], before=0, after=40)
    _body(doc, "Sorted by APE (Annualized Premium Equivalent), in Rp Trillion",
          italic=True, color=C_GRAY, size=Pt(9.5), before=0, after=100)

    hl = peers["highlight_row"]
    table = doc.add_table(rows=len(peers["rows"]) + 1, cols=len(peers["header"]))
    _set_table_border(table, "DCE2EC", sz=4)
    # #  Company  APE  YoY  RBC  Share  Claim
    _set_col_widths(table, [0.3, 2.35, 0.85, 0.65, 0.7, 0.65, 0.7])
    _set_cant_split(table)

    # header
    for ci, hdr in enumerate(peers["header"]):
        cell = table.cell(0, ci)
        _set_cell_bg(cell, "0C2340")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT if ci <= 1 else WD_ALIGN_PARAGRAPH.RIGHT
        _run(p, hdr, bold=True, color=C_WHITE, size=Pt(9.5), font="Inter")

    for ri, row in enumerate(peers["rows"]):
        bg = "E8F0FC" if ri == hl else ("F7F9FC" if ri % 2 else "FFFFFF")
        for ci, val in enumerate(row):
            cell = table.cell(ri + 1, ci)
            _set_cell_bg(cell, bg)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if ci <= 1 else WD_ALIGN_PARAGRAPH.RIGHT
            _run(p, val,
                 bold=(ri == hl),
                 color=C_ROYAL if ri == hl else C_INK,
                 size=Pt(10), font="Inter")

    for cell in table.rows[-1].cells:
        for p in cell.paragraphs:
            _keep_next(p)
    spacer = doc.add_paragraph()
    _keep_next(spacer)
    ro = doc.add_paragraph()
    _para_spacing(ro, before=80, after=80)
    _run(ro, "BRI LIFE — POSITIONING  ", bold=True, color=C_ROYAL, size=Pt(9), font="Inter")
    _run(ro, peers["readout"], color=C_INK, size=Pt(10), font="Inter")


# ── Watch areas ───────────────────────────────────────────────────────────────

def _build_watch(doc):
    _heading(doc, "Watch Areas", level=1)
    _body(doc, "Three watch items that could materially shift the 2025 outlook.",
          before=0, after=100)

    for item in REPORT["watch"]:
        sev_color = SEV_COLOR.get(item["color"], C_GRAY)
        p = doc.add_paragraph()
        _para_spacing(p, before=120, after=20)
        _run(p, f"[{item['sev'].upper()}]  ", bold=True, color=sev_color, size=Pt(9.5), font="Inter")
        _run(p, item["h"], bold=True, color=C_NAVY, size=Pt(12), font="Poppins")
        _body(doc, item["b"], before=0, after=40)
        meta = doc.add_paragraph()
        _para_spacing(meta, before=0, after=80)
        _run(meta, "OWNER  ", bold=True, color=C_GRAY_LT, size=Pt(8.5), font="Inter")
        _run(meta, item["owner"] + "    ", color=C_INK, size=Pt(10), font="Inter")
        _run(meta, "TRIGGER  ", bold=True, color=C_GRAY_LT, size=Pt(8.5), font="Inter")
        _run(meta, item["trigger"], color=C_INK, size=Pt(10), font="Inter")
        if item != REPORT["watch"][-1]:
            _add_rule(doc, "DCE2EC", thickness_pt=1)


# ── Recommendations ───────────────────────────────────────────────────────────

def _build_recs(doc):
    _heading(doc, "Priority Recommendations", level=1)
    _body(doc,
          "Three priority actions to convert FY2024 momentum into FY2025 market-share gains.",
          before=0, after=100)

    for rec in REPORT["recs"]:
        p = doc.add_paragraph()
        _para_spacing(p, before=120, after=20)
        _run(p, f"PRIORITY {rec['n']}  ", bold=True, color=C_ROYAL, size=Pt(10), font="Inter")
        _run(p, rec["h"], bold=True, color=C_NAVY, size=Pt(12), font="Poppins")
        _body(doc, rec["b"], before=0, after=40)
        meta = doc.add_paragraph()
        _para_spacing(meta, before=0, after=40)
        for label, val in [("OWNER", rec["owner"]), ("TIMELINE", rec["timeline"]), ("SUCCESS METRIC", rec["metric"])]:
            _run(meta, label + "  ", bold=True, color=C_GRAY_LT, size=Pt(8.5), font="Inter")
            _run(meta, val + "    ", color=C_INK, size=Pt(10), font="Inter")
        if rec != REPORT["recs"][-1]:
            _add_rule(doc, "DCE2EC", thickness_pt=1)


# ── Master build ──────────────────────────────────────────────────────────────

def build() -> Path:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()
    _set_margins(doc)

    # Remove default blank paragraph
    for p in doc.paragraphs:
        p._element.getparent().remove(p._element)

    _build_cover(doc)
    doc.add_page_break()

    _build_exec_summary(doc)
    doc.add_page_break()

    _build_kpis(doc)
    doc.add_page_break()

    _build_market(doc)
    doc.add_page_break()

    _build_channels(doc)
    doc.add_page_break()

    _build_comparison(doc)
    doc.add_page_break()

    _build_peers(doc)
    doc.add_page_break()

    _build_watch(doc)
    doc.add_page_break()

    _build_recs(doc)

    doc.save(str(_OUT_FILE))
    print(f"WROTE {_OUT_FILE}")
    return _OUT_FILE


if __name__ == "__main__":
    build()
