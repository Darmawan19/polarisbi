"""Single entry point for all report generation."""

import shutil
import subprocess
from pathlib import Path

from reporting import converters

_REPO_ROOT = Path(__file__).resolve().parent.parent
DECK_DIR   = _REPO_ROOT / "reporting" / "pptx_generator"
DECK_PPTX  = DECK_DIR / "out" / "PolarisBI-BRILife-FY2024.pptx"

DOC_OUT_DIR = _REPO_ROOT / "reporting" / "document" / "out"


def _ensure_deck():
    if not DECK_PPTX.exists():
        node = shutil.which("node") or "node"
        subprocess.run([node, "build.js"], cwd=str(DECK_DIR), check=True)


def generate_report(kind: str, fmt: str, report=None) -> Path:
    if kind == "deck":
        _ensure_deck()
        if fmt == "pptx":
            return DECK_PPTX
        if fmt == "pdf":
            return converters.to_pdf(DECK_PPTX)
        raise ValueError(f"Unsupported fmt '{fmt}' for kind 'deck'. Supported: pptx, pdf")

    if kind == "document":
        from reporting.document import build_docx
        docx_path = build_docx.build(report=report)   # None → static REPORT
        if fmt == "docx":
            return docx_path
        if fmt == "pdf":
            return converters.to_pdf(docx_path)
        raise ValueError(f"Unsupported fmt '{fmt}' for kind 'document'. Supported: docx, pdf")

    raise ValueError(f"Unknown kind '{kind}'. Supported: deck, document")
