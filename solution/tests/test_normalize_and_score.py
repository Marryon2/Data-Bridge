import os

from app.candidates import find_candidates
from app.normalize import as_bzp, as_date, as_iban, as_ted, nip_checksum_ok
from app.score import f1, score_pair


def test_synthetic_nip_is_kept_even_when_checksum_fails():
    text = "NIP: 9999284065 oraz NIP: 9999284066"
    nips = [item for item in find_candidates(text) if item.kind == "nip"]
    values = [item.value for item in nips]
    assert "9999284065" in values
    assert "9999284066" in values
    invalid = next(item for item in nips if item.value == "9999284066")
    assert invalid.checksum_ok is False
    assert nip_checksum_ok("9999284066") is False


def test_normalizers():
    assert as_date("7 marca 2026") == "2026-03-07"
    assert as_date("02.07.2026") == "2026-07-02"
    assert as_iban("PL68 4382 2304 9992 2952 6283 4736") == "68438223049992295262834736"
    assert as_bzp("2026/BZP 00999412/03") == "2026/BZP00999412/03"
    assert as_ted("2026/S 187-999584") == "999584-2026"
    assert as_ted("999137-2026") == "999137-2026"


def test_leaf_f1_nulls_numbers_and_extra_keys():
    gold = {"a": 200.0, "b": None, "c": ["x", "y"]}
    pred = {"a": 200, "b": None, "c": ["x", "y"], "d": 1}
    pair = score_pair(gold, pred)
    assert pair["tp"] == 4
    assert pair["fp"] == 1
    assert pair["fn"] == 0
    assert f1(pair["tp"], pair["fp"], pair["fn"]) < 1

    swapped = score_pair({"c": ["x", "y"]}, {"c": ["y", "x"]})
    assert swapped["tp"] == 0
    assert swapped["mtp"] == 2


def test_llm_without_key_returns_none(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    os.environ.pop("MISTRAL_API_KEY", None)
    from app.llm import LLMClient

    mistral = {"name": "m", "endpoint": "https://api.mistral.ai/v1/chat/completions", "api_key_env": "MISTRAL_API_KEY"}
    client = LLMClient(mistral)
    assert client.available is False
    assert client.complete_json("sys", "user") is None
    # Serwer bez klucza (Ollama): dostępny bez zmiennej środowiskowej.
    assert LLMClient({"name": "b", "endpoint": "http://localhost:11434/v1/chat/completions", "api_key_env": ""}).available


def test_consortium_name_broken_after_point_number_keeps_first_word():
    from app.config import load_classes
    from app.engine import process_pages

    text = (
        "PEŁNOMOCNICTWO\n"
        "Wykonawcy wspólnie ubiegający się o udzielenie zamówienia (Konsorcjum): 1) Torvex\n"
        "Budownictwo sp. z o.o., ul. Przemysłowa 8, 87-100 Toruń, KRS 9995540127, NIP 9992284611,\n"
        "REGON 999473016; 2) Hydromel Instalacje sp.j., ul. Lipowa 15, 85-016 Bydgoszcz, KRS\n"
        "9997108834, NIP 9994417025, REGON 999650438 (dalej łącznie: „Mocodawca”), reprezentowani\n"
        "przez osoby podpisane poniżej, udzielają pełnomocnictwa: adw. Piotr Zalewski\n"
    )
    data, _ = process_pages([text], classes=[c for c in load_classes() if c["name"] == "pelnomocnictwo"])
    names = [item["data"]["nazwa"] for item in data["mocodawca"]]
    assert names == ["Torvex Budownictwo sp. z o.o.", "Hydromel Instalacje sp.j."]


def test_to_nominative_dative_and_accusative():
    from app.normalize import to_nominative

    assert to_nominative("Annie Wiśniewskiej", "dative") == "Anna Wiśniewska"
    assert to_nominative("Piotrowi Zielińskiemu", "dative") == "Piotr Zieliński"
    assert to_nominative("Tomasza Nowickiego", "accusative") == "Tomasz Nowicki"
    assert to_nominative("Marka Nowaka", "accusative") == "Marek Nowak"
    assert to_nominative("Magdalenę Król", "accusative") == "Magdalena Król"
    assert to_nominative("Anna Nowak", None) == "Anna Nowak"


def test_candidates_hyphenated_nip_and_date_is_not_amount():
    from app.candidates import find_candidates

    found = find_candidates("NIP: 778-14-22-391\nWydruk z dnia: 22.06.2026\nKwota: 7 500,00 zł")
    assert [c.value for c in found if c.kind == "nip"] == ["7781422391"]
    assert [c.raw for c in found if c.kind == "amount"] == ["7 500,00"]


def test_guess_case_and_pdf_lookalike_characters():
    from app.extract import _clean
    from app.normalize import guess_case

    assert guess_case("Katarzynie Lewandowskiej") == "dative"
    assert guess_case("Agnieszkę Pawlak") == "accusative"
    assert guess_case("Anna Nowak") is None
    # Twarda spacja, miękki dywiz w środku i na końcu linii (przeniesienie wyrazu), „;” z mapy fontu.
    assert _clean("Delta\xadMed\xa0S.A.\u037e złoże\xad\nnia") == "Delta-Med S.A.; złożenia"
