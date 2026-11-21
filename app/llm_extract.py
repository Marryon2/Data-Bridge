"""Tryb AI (extraction: llm w config/model.yaml): klasa i JSON z modelu, potem walidacja względem tekstu dokumentu.

Model dostaje schemat klasy z opisami pól z YAML. Odpowiedź jest dopasowywana do schematu, normalizowana
tymi samymi funkcjami co reguły i sprawdzana z tekstem: identyfikatory spoza dokumentu są odrzucane,
polskie znaki wracają z dokumentu („Wisniewska” -> „Wiśniewska”), opis czynności pochodzi ze słownika.
"""

from __future__ import annotations

import copy
import json
import re

from app.classify import _score
from app.config import EMPTY_DOCUMENT
from app.normalize import NORMALIZERS, as_text

# Normalizator po nazwie klucza w schemacie (ostatni człon ścieżki).
_BY_KEY = {
    "data": "date", "data_operacji": "date", "czynnosc_dzien": "date", "kwota": "amount",
    "nip": "nip", "regon": "regon", "krs": "krs", "z_rachunku": "iban", "na_rachunek": "iban",
    "numer_bzp": "bzp", "numer_ted": "ted", "mail": "email", "imie_nazwisko": "person",
    "czynnosc_powod_id": "int", "przez-pelnomocnika": "int", "prowadzacy_postepowanie": "int",
}
# Identyfikatory przyjmowane tylko, gdy ich cyfry stoją w dokumencie (model nie może ich wymyślić).
_IDS = {"nip", "regon", "krs", "pesel", "z_rachunku", "na_rachunek", "numer_bzp", "numer_ted"}
# Pola tekstowe przyjmowane tylko, gdy stoją w dokumencie (bez względu na polskie znaki i wielkość liter).
# Bez imion: model sprowadza je do mianownika, więc mogą nie występować dosłownie.
_GROUNDED = {"nazwa", "numer_postepowania", "tytul", "numer_transakcji", "miejscowosc", "mail"}
_FOLD = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
_CLIP = 14000

_SYSTEM = (
    "Wyciągasz dane z polskiego dokumentu do JSON. Zwróć wyłącznie JSON o dokładnie takiej strukturze jak wzór; "
    "w miejscu opisu pola wpisz wartość z dokumentu. Przepisuj tekst dosłownie, z polskimi znakami. "
    "Gdy dokument nie podaje wartości, wpisz null. Daty w formacie YYYY-MM-DD. "
    "NIP, REGON, KRS, PESEL i numery rachunków jako same cyfry. Kwota jako liczba. "
    "Listy mogą mieć więcej elementów niż we wzorze."
)


def _descriptions(spec: dict) -> dict[str, str]:
    """Ścieżka bez indeksów list -> opis pola z YAML."""
    found: dict[str, str] = {}
    for field in spec.get("fields") or []:
        found.setdefault(field["path"], field.get("description", ""))
    for listing in spec.get("lists") or []:
        found.setdefault(listing["path"], listing.get("description", ""))
        for field in listing.get("fields") or []:
            found.setdefault(f"{listing['path']}.{field['path']}", field.get("description", ""))
    # llm_descriptions w YAML (według komentarzy organizatora) ma pierwszeństwo przed opisami reguł.
    found.update(spec.get("llm_descriptions") or {})
    return found


def _template(node, path: str, desc: dict[str, str]):
    if isinstance(node, dict):
        return {key: _template(value, f"{path}.{key}" if path else key, desc) for key, value in node.items()}
    if isinstance(node, list):
        return [_template(node[0], path, desc)]
    return desc.get(path) or "wartość albo null"


def _conform(schema, value):
    """Odpowiedź modelu w kształcie schematu: brakujące klucze null, zbędne pominięte."""
    if isinstance(schema, dict):
        source = value if isinstance(value, dict) else {}
        return {key: _conform(sub, source.get(key)) for key, sub in schema.items()}
    if isinstance(schema, list):
        items = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
        return [_conform(schema[0], item) for item in items] or [_conform(schema[0], None)]
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    return value


def _compact(text: str) -> str:
    return re.sub(r"[\s\-/.]", "", text).upper()


def _restore(value: str, flat: str, folded: str) -> str:
    """Wartość bez polskich znaków wraca w brzmieniu z dokumentu (zamiana znaków 1:1 zachowuje pozycje)."""
    if value in flat:
        return value
    index = folded.find(value.translate(_FOLD).lower())
    return flat[index : index + len(value)] if index >= 0 else value


def _clean_leaf(key: str, value, flat: str, folded: str, digits: str, templates: set[str]):
    if value is None:
        return None
    if isinstance(value, str) and (value.strip().lower() in {"", "null", "none", "brak", "-"} or value in templates):
        return None
    norm = _BY_KEY.get(key)
    try:
        if key == "pesel":
            value = re.sub(r"\D", "", str(value))
            value = value if len(value) == 11 else None
        elif norm == "int":
            value = int(float(value))
        elif norm:
            value = NORMALIZERS[norm](str(value))
        else:
            value = as_text(str(value))
    except (TypeError, ValueError):
        return None
    # Identyfikator ma stać w dokumencie w tej samej postaci (bez spacji, myślników, ukośników, kropek).
    # TED po normalizacji ma inną kolejność niż w dokumencie („2026/S 145-498812” -> „498812-2026”).
    check = str(value).split("-")[0] if key == "numer_ted" and value else _compact(str(value))
    if key in _IDS and value and check not in digits:
        return None
    # E-mail bywa przełamany na myślniku („pawlak-” / „kancelaria.example”): porównanie bez spacji.
    haystack = folded.replace(" ", "") if key == "mail" else folded
    if key in _GROUNDED and isinstance(value, str) and value.translate(_FOLD).lower() not in haystack:
        return None
    if key == "czynnosc_powod_id" and value is not None and not 1 <= value <= 12:
        return None
    if norm == "person" and value and not all(word.translate(_FOLD).lower()[:4] in folded for word in value.split()):
        return None  # osoba spoza dokumentu (rdzeń imienia lub nazwiska nie występuje w tekście)
    if norm == "person" and value:
        # Jedno pole = jedna osoba: „Aleksandra Marciniak, Jolanta Zajkowski” -> pierwsza.
        value = re.split(r"\s*[,;]\s*|\s+(?:i|oraz)\s+", value)[0] or None
    if isinstance(value, str) and norm in (None, "person"):
        value = _restore(value, flat, folded)
    return value


def _clean(node, path: str, flat: str, folded: str, digits: str, templates: set[str], enums: dict):
    if isinstance(node, dict):
        return {k: _clean(v, f"{path}.{k}" if path else k, flat, folded, digits, templates, enums) for k, v in node.items()}
    if isinstance(node, list):
        return [_clean(item, path, flat, folded, digits, templates, enums) for item in node]
    value = _clean_leaf(path.rsplit(".", 1)[-1], node, flat, folded, digits, templates)
    if path in enums and value not in enums[path]:
        return None
    return value


def _apply_if_single(data: dict, spec: dict) -> None:
    """Pole z `if_single` (np. prowadzacy_postepowanie) przy liście jednoelementowej ma tę wartość, jak w regułach."""
    from app.engine import _get, _set

    for listing in spec.get("lists") or []:
        items = _get(data, listing["path"])
        if not isinstance(items, list) or len(items) != 1:
            continue
        for field in listing.get("fields") or []:
            if "if_single" in field:
                _set(items[0], field["path"], field["if_single"])


def classify(llm, first_page: str, classes: list[dict]):
    """Zwraca (spec albo None dla „none”, czy_odpowiedział)."""
    lines = "\n".join(f"- {spec['name']}: {spec.get('description', '')}" for spec in classes)
    raw = llm.complete_json(
        'Klasyfikujesz polski dokument. Zwróć JSON {"class": "<nazwa klasy>"}.',
        f"Klasy:\n{lines}\n- none: każdy inny dokument: wyrok lub postanowienie KIO, ogłoszenie o zamówieniu, "
        f"prezentacja, szkolenie, poradnik, opis procedury, decyzja, faktura, broszura\n\n"
        f"Pierwsza strona dokumentu:\n{first_page[:5000]}",
    )
    if not raw:
        return None, False
    chosen = str(raw.get("class") or "none").strip().lower()
    for spec in classes:
        if spec["name"] == chosen:
            return spec, True
    return None, True


def extract(llm, spec: dict, pages: list[str], tables: dict) -> dict | None:
    from app.engine import _lookup, _set  # leniwy import: engine importuje ten moduł w trybie AI

    desc = _descriptions(spec)
    template = _template(spec["schema"], "", desc)
    notes = [f"- {listing['path']}: {listing.get('description', '')}" for listing in spec.get("lists") or []]
    for field in spec.get("fields") or []:
        if field.get("table") and tables.get(field["table"], {}).get("opis"):
            items = "; ".join(f"{k}={v}" for k, v in tables[field["table"]]["opis"].items())
            notes.append(f"- {field['path']}: wybierz identyfikator ze słownika: {items}")
    text = "\n".join(pages)
    raw = llm.complete_json(
        _SYSTEM,
        f"Wzór JSON (w miejscu wartości opis pola):\n{json.dumps(template, ensure_ascii=False, indent=1)}\n\n"
        + ("Uwagi:\n" + "\n".join(notes) + "\n\n" if notes else "")
        + f"Dokument:\n{text[:_CLIP]}",
    )
    if not raw:
        return None
    flat = re.sub(r"\s+", " ", text)
    templates = set(desc.values()) | {"wartość albo null"}
    enums = spec.get("llm_enum") or {}
    data = _clean(_conform(spec["schema"], raw), "", flat, flat.translate(_FOLD).lower(), _compact(text), templates, enums)
    # llm_max_items: np. Odwołujący = tylko lider konsorcjum (pierwszy element).
    from app.engine import _get, _set
    for path, limit in (spec.get("llm_max_items") or {}).items():
        items = _get(data, path)
        if isinstance(items, list):
            _set(data, path, items[: int(limit)])
    _apply_if_single(data, spec)
    for field in spec.get("fields") or []:
        if field.get("method") == "lookup":
            _set(data, field["path"], _lookup(data, field, tables))
    return data


def process(llm, pages: list[str], classes: list[dict], tables: dict) -> tuple[dict, dict] | None:
    """None = model nie odpowiedział; wtedy engine przechodzi na reguły."""
    spec, answered = classify(llm, pages[0] if pages else "", classes)
    if not answered:
        return None
    # Wzorce wykluczające z YAML (wyrok, ogłoszenie TED…) obowiązują także po klasyfikacji przez model.
    if spec is not None and _score(pages[0] if pages else "", spec) < 0:
        spec = None
    trace = {"class": None, "confidence": None, "fields": [], "ocr": None, "method": "llm"}
    if spec is None:
        return copy.deepcopy(EMPTY_DOCUMENT), trace
    data = extract(llm, spec, pages, tables)
    if data is None:
        return None
    trace["class"] = spec["name"]
    return data, trace
