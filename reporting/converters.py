"""PDF conversion via LibreOffice headless."""

import shutil
import subprocess
from pathlib import Path

_SOFFICE_FALLBACK = r"C:\Program Files\LibreOffice\program\soffice.exe"


def find_soffice() -> str:
    on_path = shutil.which("soffice")
    if on_path:
        return on_path
    return _SOFFICE_FALLBACK


def to_pdf(src_path: Path) -> Path:
    soffice = find_soffice()
    if not Path(soffice).exists() and not shutil.which(soffice):
        raise RuntimeError(
            f"LibreOffice not found at '{soffice}'. "
            "Install LibreOffice or add soffice to PATH."
        )
    out_dir = src_path.parent
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(src_path)],
        check=True,
        capture_output=True,
    )
    pdf_path = out_dir / (src_path.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError(f"LibreOffice conversion produced no output at {pdf_path}")
    return pdf_path
