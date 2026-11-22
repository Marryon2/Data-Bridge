from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import pymupdf

from app.ocr_fix import fix_text, layout_text

MIN_LETTERS = 40
# shortcut: OCR tylko pierwszych 2 stron, podnieś limit gdy skan ma treść głębiej
OCR_PAGES = 2
_PAGE_MARK = re.compile(r"(?m)^Strona\s+\d+\s+z\s+\d+\s*$")
_warned = False
# PyMuPDF nie jest bezpieczny wątkowo: czytanie PDF pod blokadą; Tesseract (osobny proces) i AI idą równolegle.
_PDF_LOCK = threading.Lock()


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


def _ocr(images: list[bytes], rest: list[str]) -> tuple[list[str] | None, str, dict[str, float]]:
    """OCR obrazów PNG pierwszych stron (+ tekst pozostałych stron): strony, nota i średnia pewność Tesseracta (0–100) słów."""
    exe = shutil.which("tesseract")
    if not exe:
        return None, _tesseract_note(), {}
    pages: list[str] = []
    scores: dict[str, list[float]] = {}
    try:
        with tempfile.TemporaryDirectory() as work:
            for index, png in enumerate(images):
                image, base = Path(work, f"{index}.png"), Path(work, str(index))
                image.write_bytes(png)
                # Jeden przebieg, dwa wyniki: tekst jak dotąd i TSV z pewnością słów. Parametry -c zamiast
                # plików konfiguracyjnych „txt”/„tsv”, których nie ma w .tessdata/ pobranym przez start.bat.
                proc = subprocess.run(
                    [exe, str(image), str(base), "-l", "pol", "-c", "tessedit_create_txt=1", "-c", "tessedit_create_tsv=1"],
                    check=False,
                    capture_output=True,
                )
                if proc.returncode != 0:
                    return None, "tesseract-error", {}
                tsv = base.with_suffix(".tsv")
                # Bez TSV tekst zostaje, przepada tylko pewność słów i rozdzielanie kolumn.
                lines: dict[tuple[str, str, str], list[tuple[int, int, int, int, str]]] = {}
                for row in (tsv.read_text(encoding="utf-8", errors="replace") if tsv.exists() else "").splitlines()[1:]:
                    cells = row.split("\t")
                    if len(cells) == 12 and cells[11].strip() and float(cells[10]) >= 0:
                        word = cells[11].strip()
                        scores.setdefault(_clean(word), []).append(float(cells[10]))
                        left, top, width, height = (int(cells[i]) for i in (6, 7, 8, 9))
                        lines.setdefault((cells[2], cells[3], cells[4]), []).append((left, left + width, top, top + height, word))
                columns = layout_text(list(lines.values()))
                pages.append(columns if columns is not None else base.with_suffix(".txt").read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None, "tesseract-error", {}
    return pages + rest, "tesseract-pol", {word: sum(v) / len(v) for word, v in scores.items()}


def extract_pdf(path: str | Path) -> dict:
    images: list[bytes] = []
    rest: list[str] = []
    with _PDF_LOCK:
        doc = pymupdf.open(path)
        try:
            pages = [_clean(page.get_text("text") or "") for page in doc]
            scanned = _letters("\n".join(pages)) < MIN_LETTERS
            if scanned:
                limit = min(OCR_PAGES, doc.page_count)
                images = [doc[index].get_pixmap(dpi=200).tobytes("png") for index in range(limit)]
                rest = [doc[index].get_text("text") or "" for index in range(limit, doc.page_count)]
        finally:
            doc.close()
    ocr, confidence = None, {}
    if scanned:
        ocr_pages, ocr, confidence = _ocr(images, rest)
        if ocr_pages:
            pages = [fix_text(_clean(page)) for page in ocr_pages]
    return {"pages": pages, "ocr": ocr, "confidence": confidence}
