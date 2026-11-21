"""Odczyt PDF przez serwer docling-serve (POST /v1/convert/file, wynik w Markdown). Adres: DOCLING_URL."""

from __future__ import annotations

import html
import json
import os
import urllib.request
import uuid
from pathlib import Path

from app.extract import _clean


def docling_pages(path: str | Path) -> list[str]:
    """Cały dokument jako jedna „strona” Markdown; ta sama normalizacja znaków co PyMuPDF."""
    url = os.environ.get("DOCLING_URL", "http://127.0.0.1:5001").rstrip("/") + "/v1/convert/file"
    boundary = uuid.uuid4().hex

    def field(name: str, value: str) -> bytes:
        return f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()

    body = (
        field("to_formats", "md")
        # shortcut: bez OCR docling (pierwsze użycie pobiera modele); włączyć dla skanów.
        + field("do_ocr", "false")
        + f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="dokument.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n".encode()
        + Path(path).read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(url, body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(request, timeout=600) as response:
        markdown = json.loads(response.read())["document"]["md_content"]
    # Docling zostawia encje HTML („&amp;”) i miękkie dywizy.
    return [_clean(html.unescape(markdown))]
