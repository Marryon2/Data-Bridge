from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf

MIN_LETTERS = 40
# shortcut: OCR tylko pierwszych 2 stron, podnieś limit gdy skan ma treść głębiej
OCR_PAGES = 2
_PAGE_MARK = re.compile(r"(?m)^Strona\s+\d+\s+z\s+\d+\s*$")
_warned = False


def _letters(text: str) -> int:
    return sum(ch.isalpha() for ch in text)


# Znaki z warstwy tekstowej PDF, które wyglądają jak zwykłe: twarda spacja, myślniki Unicode, „;” z mapy fontu.
_LOOKALIKE = str.maketrans({"\xa0": " ", " ": " ", "‐": "-", "‑": "-", "\xad": "-", ";": ";"})


def _clean(text: str) -> str:
    # Miękki dywiz na końcu linii to przeniesienie wyrazu („złoże\xad\nnia”) – sklej wyraz.
    text = re.sub(r"(?<=[^\W\d_])\xad\n(?=[^\W\d_])", "", text or "").translate(_LOOKALIKE)
    return _PAGE_MARK.sub("", text)


def _tesseract_note() -> str:
    global _warned
    if not _warned:
        print("Tesseract nie jest zainstalowany; pominięto OCR. Warstwa tekstowa zostaje.")
        _warned = True
    return "tesseract-missing"


def _ocr(doc) -> tuple[list[str] | None, str]:
    exe = shutil.which("tesseract")
    if not exe:
        return None, _tesseract_note()
    pages: list[str] = []
    limit = min(OCR_PAGES, doc.page_count)
    try:
        for index in range(limit):
            pixmap = doc[index].get_pixmap(dpi=200)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
                image = handle.name
            pixmap.save(image)
            try:
                proc = subprocess.run(
                    [exe, image, "stdout", "-l", "pol"],
                    check=False,
                    capture_output=True,
                )
            finally:
                Path(image).unlink(missing_ok=True)
            if proc.returncode != 0:
                return None, "tesseract-error"
            pages.append(proc.stdout.decode("utf-8", errors="replace"))
    except OSError:
        return None, "tesseract-error"
    for index in range(limit, doc.page_count):
        pages.append(doc[index].get_text("text") or "")
    return pages, "tesseract-pol"


def extract_pdf(path: str | Path) -> dict:
    doc = pymupdf.open(path)
    try:
        pages = [_clean(page.get_text("text") or "") for page in doc]
        ocr = None
        if _letters("\n".join(pages)) < MIN_LETTERS:
            ocr_pages, ocr = _ocr(doc)
            if ocr_pages:
                pages = [_clean(page) for page in ocr_pages]
        return {"pages": pages, "ocr": ocr}
    finally:
        doc.close()
