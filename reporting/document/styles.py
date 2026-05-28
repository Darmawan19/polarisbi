"""
Document styling constants — PolarisBI brand (aligned with reporting/pptx_generator/src/theme.js).
Replaces reporting/deck_design.py color/token values for the DOCX generator.
"""

from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ── Brand colors (hex → RGBColor) ────────────────────────────────────────────
C_INK        = RGBColor(0x1A, 0x22, 0x30)   # 1A2230 — primary text near-black
C_NAVY       = RGBColor(0x0C, 0x23, 0x40)   # 0C2340 — deep navy: headings, table headers
C_ROYAL      = RGBColor(0x16, 0x4E, 0x96)   # 164E96 — brand blue: section rules, accents
C_BLUE       = RGBColor(0x2F, 0x6F, 0xE0)   # 2F6FE0 — bright accent
C_BLUE_SOFT  = RGBColor(0xE8, 0xF0, 0xFC)   # E8F0FC — tint: highlighted rows
C_GREEN      = RGBColor(0x2E, 0x9E, 0x5B)   # 2E9E5B — positive / up
C_AMBER      = RGBColor(0xD9, 0x8A, 0x1F)   # D98A1F — medium severity
C_RED        = RGBColor(0xD6, 0x45, 0x45)   # D64545 — high severity
C_GRAY       = RGBColor(0x6B, 0x76, 0x89)   # 6B7689 — muted text
C_GRAY_LT    = RGBColor(0x9A, 0xA4, 0xB6)   # 9AA4B6 — lighter muted
C_LINE       = RGBColor(0xDC, 0xE2, 0xEC)   # DCE2EC — hairline borders
C_CARD_BG    = RGBColor(0xF6, 0xF8, 0xFC)   # F6F8FC — card fill
C_WHITE      = RGBColor(0xFF, 0xFF, 0xFF)

# Hex strings (for XML manipulation where RGBColor not accepted)
H_NAVY      = "0C2340"
H_ROYAL     = "164E96"
H_BLUE_SOFT = "E8F0FC"
H_CARD_BG   = "F6F8FC"
H_LINE      = "DCE2EC"
H_GREEN     = "2E9E5B"
H_AMBER     = "D98A1F"
H_RED       = "D64545"
H_WHITE     = "FFFFFF"
H_INK       = "1A2230"
H_GRAY      = "6B7689"
H_GRAY_LT   = "9AA4B6"

# ── Typography ────────────────────────────────────────────────────────────────
F_DISPLAY = "Poppins"       # headings / big numbers
F_SEMI    = "Poppins SemiBold"
F_BODY    = "Inter"         # body copy
F_BODY_MED = "Inter Medium"

# ── Sizes ─────────────────────────────────────────────────────────────────────
SZ_H1   = Pt(26)   # document title
SZ_H2   = Pt(16)   # section header
SZ_H3   = Pt(13)   # sub-header / card heading
SZ_BODY = Pt(10.5)
SZ_SM   = Pt(9)
SZ_KPI  = Pt(22)   # big metric value

# ── Layout ────────────────────────────────────────────────────────────────────
MARGIN_LR = Inches(1.0)
MARGIN_TB = Inches(0.85)
