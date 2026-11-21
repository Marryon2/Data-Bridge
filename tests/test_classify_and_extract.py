import json
from pathlib import Path

import pymupdf
import pytest

from app.classify import classify_text
from app.config import data_dir, load_classes
from app.engine import process_pdf
from app.extract import extract_pdf

DATA = data_dir() or Path(r"d:\System\Desktop\hacknation-2026")
DANE = DATA / "dane"

IN_CASE = [
    ("przyklad_04", "2025_S 112-383751.pdf"),
    ("przyklad_10", "2025-OJS107-00364525-pl-ts.pdf"),
    ("przyklad_24", "prowadzenie_postepowania_odwolawczego.pdf"),
    ("przyklad_37", "2025_BZP 00143067_01.pdf"),
]


pytestmark = pytest.mark.skipif(not DANE.is_dir(), reason="brak DATA_DIR")


def test_kio_judgment_and_notice_snippets_are_not_appeals():
    classes = list(load_classes())
    judgment = "Sygn. akt: KIO 2617/21\nPOSTANOWIENIE\norzeka:\nodrzuca odwołanie"
    notice = "See the notice on TED website\nOgłoszenie o zamówieniu lub ogłoszenie o koncesji\nOfficial Journal"
    appeal = "Odwołujący:\nFirma S.A.\nwnoszę odwołanie"
    assert classify_text(judgment, classes)[0] is None
    assert classify_text(notice, classes)[0] is None
    assert classify_text(appeal, classes)[0]["name"] == "odwolanie"


def test_negatives_are_empty_objects():
    folder = DANE / "negatywne"
    pdfs = list(folder.glob("*.pdf"))
    assert len(pdfs) == 12
    for pdf in pdfs:
        document, trace = process_pdf(pdf, llm=None)
        assert document == {}, pdf.name
        assert trace["class"] is None
    for case, name in IN_CASE:
        document, trace = process_pdf(DANE / case / name, llm=None)
        assert document == {}, name
        assert trace["class"] is None
    kio = process_pdf(folder / "KIO_KIO 2617-21.pdf", llm=None)[0]
    assert kio == {}


def test_extraction_gate_pymupdf_keeps_nips_and_diacritics():
    """PyMuPDF, nie pdftotext: NIP z gold jest w tekście, a polskie znaki nie spadają."""
    saw_oplata = False
    saw_gdansk = False
    saw_lodz = False
    checked = 0
    for index in range(1, 61):
        case = DANE / f"przyklad_{index:02d}"
        for pdf_name, gold_name in (
            ("odwolanie.pdf", "odwolanie.json"),
            ("pelnomocnictwo.pdf", "pelnomocnictwo.json"),
            ("potwierdzenie_przelewu.pdf", "przelew.json"),
        ):
            pdf = case / pdf_name
            gold = json.loads((case / gold_name).read_text(encoding="utf-8"))
            text = "\n".join(extract_pdf(pdf)["pages"])
            checked += 1
            nips = []

            def walk(node):
                if isinstance(node, dict):
                    for key, item in node.items():
                        if key == "nip" and isinstance(item, str):
                            nips.append(item)
                        else:
                            walk(item)
                elif isinstance(node, list):
                    for item in node:
                        walk(item)

            walk(gold)
            for nip in nips:
                assert nip in text, f"{pdf} brak NIP {nip}"
            if "opłata" in json.dumps(gold, ensure_ascii=False):
                assert "opłata" in text, pdf
                saw_oplata = True
            city = None
            if "OdwolanieKIO" in gold:
                city = gold["OdwolanieKIO"].get("miejscowosc")
            if city in {"Gdańsk", "Łódź"}:
                assert city in text, pdf
                saw_gdansk = saw_gdansk or city == "Gdańsk"
                saw_lodz = saw_lodz or city == "Łódź"
            doc = pymupdf.open(pdf)
            assert doc.page_count >= 1
            doc.close()
    assert checked == 180
    assert saw_oplata and saw_gdansk and saw_lodz
