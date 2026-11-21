"""Wzory spoza zbioru organizatora: tests/fixtures/<nazwa>.txt (strony rozdzielone \\f) + <nazwa>.json.

Każdy nowy szablon dodany tutaj pilnuje, żeby kolejne zmiany reguł go nie zepsuły.
"""

import json
from pathlib import Path

import pytest

from app.engine import process_pages
from app.score import score_pair

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.txt"))


@pytest.mark.parametrize("txt", FIXTURES, ids=[path.stem for path in FIXTURES])
def test_fixture_matches_expected_json(txt):
    pages = txt.read_text(encoding="utf-8").split("\f")
    gold = json.loads(txt.with_suffix(".json").read_text(encoding="utf-8"))
    pred, _trace = process_pages(pages)
    pair = score_pair(gold, pred)
    wrong = sorted(path for path in pair["gold"] if pair["gold"][path] != pair["pred"].get(path))
    assert not wrong and pair["fp"] == 0, wrong
