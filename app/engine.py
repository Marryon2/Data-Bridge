from __future__ import annotations

import copy
import re
from pathlib import Path

from app.candidates import find_candidates, hint_points as _hint_points, rank_candidates
from app.classify import classify_text
from app.config import EMPTY_DOCUMENT, load_classes, load_tables
from app.extract import extract_pdf
from app.normalize import apply_normalizer, as_krs, as_person, as_text, guess_case, to_nominative

_NAME_LINE = re.compile(
    r"^[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?"
    r"\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?$"
)
_ID_TYPES = {"nip", "regon", "krs", "pesel", "iban"}


def _get(obj, path: str):
    current = obj
    for part in path.split("."):
        current = current[part]
    return current


def _set(obj, path: str, value) -> None:
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def _scope_text(text: str, spec: dict) -> str:
    start = None
    starts = spec.get("start") or []
    # start może być listą: pierwszy wzorzec, który występuje w tekście, wyznacza zakres.
    for pattern in starts if isinstance(starts, list) else [starts]:
        start = re.search(pattern, text)
        if start:
            break
    if start:
        # before_chars: kontekst przed etykietą, np. data czynności stojąca przed „polegającej na”.
        lead = text[max(0, start.start() - int(spec.get("before_chars", 0))) : start.start()]
        rest = text[start.end() :]
        if spec.get("end"):
            end = re.search(spec["end"], rest)
            if end:
                return lead + rest[: end.start()]
        return lead + rest[: int(spec.get("max_chars", 2500))]
    if spec.get("fallback_before"):
        marker = re.search(spec["fallback_before"], text)
        if marker:
            begin = max(0, marker.start() - int(spec.get("fallback_chars", 400)))
            return text[begin : marker.start()]
    return ""


def _region(field: dict, text: str, pages: list[str], scopes: dict) -> str:
    name = field.get("scope") or "document"
    if name == "document":
        return text
    if name == "first_page":
        return pages[0] if pages else ""
    if name == "preamble":
        cut = re.search(r"(?i)wnoszę|zarzut nr 1", text)
        return text[: cut.start()] if cut else text[:6000]
    return _scope_text(text, scopes[name])


def _match_value(match: re.Match) -> str:
    grouped = match.groupdict()
    if grouped.get("value"):
        return grouped["value"]
    if match.lastindex:
        return match.group(1)
    return match.group(0)


def _choose_match(matches: list[re.Match], which: str | None) -> re.Match | None:
    if not matches:
        return None
    if which == "prefer_s_form":
        preferred = [item for item in matches if re.search(r"(?i)/s", item.group(0))]
        return (preferred or matches)[0]
    if which == "first_w_dniu":
        favored = [item for item in matches if item.group(0).lower().lstrip().startswith("w dniu")]
        return favored[0] if favored else matches[-1]
    if which == "last":
        return matches[-1]
    return matches[0]


def _page_of(pages: list[str], quote: str | None) -> int | None:
    if not quote:
        return None
    needle = re.sub(r"\s+", " ", quote).strip()[:80]
    if not needle:
        return None
    for index, page in enumerate(pages, start=1):
        if needle in re.sub(r"\s+", " ", page):
            return index
    return 1


def _trace(path: str, value, quote: str | None, method: str, pages: list[str]) -> dict:
    return {
        "path": path,
        "value": value,
        "quote": (quote or "")[:240],
        "page": _page_of(pages, quote),
        "method": method,
        "confidence": 0.8,
    }


def _regex_field(field: dict, text: str) -> tuple[object, str | None]:
    # pattern może być listą: wzorce próbowane po kolei, pierwszy trafiony wygrywa.
    patterns = field["pattern"] if isinstance(field["pattern"], list) else [field["pattern"]]
    for pattern in patterns:
        match = _choose_match(list(re.finditer(pattern, text)), field.get("which"))
        if match:
            value = apply_normalizer(field.get("normalizer"), _match_value(match))
            return value, match.group(0)
    return None, None


def _line_field(field: dict, text: str) -> tuple[object, str | None]:
    skips = field.get("skip") or []
    lines = text.splitlines()
    start = 0
    if field.get("prefer_after"):
        for index, line in enumerate(lines):
            if re.search(field["prefer_after"], line, re.I):
                numbered = re.match(r"\s*\d+[.)]\s*(.+)", line)
                # „1) X sp. z o.o. (Lider)” to nazwa; „1) Lider Konsorcjum:” to tylko etykieta nad nazwą.
                if numbered and not re.match(field["prefer_after"], numbered.group(1), re.I):
                    value = apply_normalizer(field.get("normalizer") or "text", numbered.group(1))
                    return value, line
                start = index + 1
                break
    for index in range(start, len(lines)):
        raw = lines[index].strip().lstrip(":").strip()
        if not raw:
            continue
        if any(re.search(pattern, raw, re.I) for pattern in skips):
            continue
        # join_next: dokleja następną linię, gdy zaczyna się od urwanej końcówki (np. „sp. z” / „o.o.”).
        following = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if field.get("join_next") and following and re.search(field["join_next"], following, re.I):
            raw = f"{raw} {following}"
        value = apply_normalizer(field.get("normalizer") or "text", raw)
        return value, raw
    return None, None


def _span_field(field: dict, text: str) -> tuple[object, str | None]:
    labels = sorted(field.get("starts") or [], key=len, reverse=True)
    if not labels:
        return None, None
    pattern = "|".join(re.escape(label) for label in labels)
    # Etykieta dwujęzyczna „Tytuł / Reference:” – angielski dopisek jest pomijany.
    label_re = re.compile(rf"(?im)^(?:{pattern})(?![A-Za-ząćęłńóśźż])\s*(?:/[^:\n]{{1,30}}:)?\.*\s*:?\s*(.*)$")
    match = label_re.search(text)
    if not match:
        return None, None
    stops = field.get("stops") or []
    stop_re = re.compile("(?i)^(?:" + "|".join(re.escape(item) for item in stops) + ")") if stops else None
    inline = match.group(1).strip()
    body = (inline + "\n" if inline else "") + text[match.end() :]
    kept = []
    for line in body.splitlines():
        if stop_re and stop_re.search(line.strip()):
            break
        kept.append(line)
    raw = "\n".join(kept)
    return apply_normalizer(field.get("normalizer") or "text", raw), raw


def _candidate_field(field: dict, candidates) -> tuple[object, str | None]:
    pool = [item for item in candidates if item.kind == field["kind"]]
    if not pool:
        return None, None
    hints = field.get("hints") or []
    avoid = field.get("avoid") or []
    ranked = rank_candidates(pool, hints, avoid)
    best = ranked[0]
    if _hint_points(best, hints, avoid) <= 0:
        ordered = sorted(pool, key=lambda item: item.start)
        fallback = field.get("fallback") or "first"
        if fallback == "second" and len(ordered) > 1:
            best = ordered[1]
        elif fallback == "last":
            best = ordered[-1]
        else:
            best = ordered[0]
    value = apply_normalizer(field.get("normalizer"), best.raw if field["kind"] != "tx" else best.value)
    if field["kind"] == "amount":
        value = apply_normalizer("amount", best.raw)
    return value, best.raw


def _flag_value(field: dict, text: str, list_len: int):
    if "if_single" in field and list_len <= 1:
        return field.get("if_single")
    matched = re.search(field["pattern"], text, re.I | re.S) if field.get("pattern") else None
    return field.get("when_match", 1) if matched else field.get("when_miss", 0)


def _split_chunks(section: str, pattern: str | None) -> list[str]:
    if not pattern:
        return [section]
    parts = re.split(pattern, section)
    if len(parts) <= 1:
        return [section]
    chunks = [part for part in parts[1:] if part.strip()]
    return chunks or [section]


_LEGAL_FORM = re.compile(
    r"(?i)sp\.\s*z\s*o\.\s*o\.(?:\s*sp\.\s*k\.)?|S\.A\.|sp\.\s*k\.|sp\.\s*j\.|sp\.k\.|sp\.j\."
    r"|spółka\s+(?:akcyjna|jawna|komandytowa|z\s+ograniczoną\s+odpowiedzialnością)"
)


def _company_from_flat(flat: str) -> tuple[str, int] | None:
    forms = list(_LEGAL_FORM.finditer(flat))
    if not forms:
        return None
    last = forms[-1]
    prefix = flat[: last.end()]
    cut = 0
    for mark in re.finditer(r"(?i)(?:^|[;:]|\d\)\s+|jest\s+|imieniu\s+|firmą\s+)", prefix):
        cut = mark.end()
    name = re.sub(r"^\d+\)\s*", "", prefix[cut:]).strip(" ,;")
    name = re.sub(r"(?i)^.*\b(?:krs|nip|regon)\s+\d+\s*[,;]?\s*(?:\d+\)\s*)?", "", name).strip(" ,;")
    if not name or re.search(r"(?i)\b(?:krs|nip|regon)\b|;", name):
        return None
    return name, last.end()


def _pattern_name(text: str, patterns: list[str]) -> str | None:
    best = None
    best_end = -1
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I | re.M):
            grouped = match.groupdict()
            value = grouped.get("value") or (match.group(1) if match.lastindex else None)
            if value and match.end() >= best_end:
                best = value
                best_end = match.end()
    return best


def _best_name(window: str, patterns: list[str]) -> str | None:
    raw = _pattern_name(window, patterns)
    flat = re.sub(r"\s+", " ", window)
    forms = list(_LEGAL_FORM.finditer(flat))
    company = _company_from_flat(flat)
    if len(forms) >= 2 and company:
        raw = company[0]
    elif raw and re.search(r"(?i)\b(?:krs|nip|regon)\b|;", raw) and company:
        raw = company[0]
    elif raw:
        index = window.rfind(raw.strip())
        previous = window[:index].splitlines() if index > 0 else []
        # Nazwa przełamana po „1) Torvex”: bierz tylko ogon linii po ostatnim numerze punktu.
        line = re.split(r"(?:^|\s)\d+\)\s*", previous[-1].strip())[-1] if previous else ""
        token = r"[A-ZĄĆĘŁŃÓŚŹŻ0-9][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż.-]*"
        parts = line.split()
        if line and parts and any(len(part) > 1 for part in parts) and re.fullmatch(rf"{token}(?:\s+{token})*", line):
            # Sama etykieta komórki tabeli („Firma”, „Nazwa”) nie jest początkiem nazwy.
            label = re.fullmatch(r"(?i)firma|nazwa(?:\s+firmy)?", line)
            if not label and not re.search(r"(?i)mocodawca|pełnomoc|konsorcjum|wykonawc|podpis|nip|krs|regon", line):
                raw = f"{line} {raw.strip()}"
    else:
        firm = re.search(r"(?i)pod firmą\s+(.+?),", flat)
        raw = firm.group(1) if firm else (company[0] if company else None)
    if not raw:
        return None
    raw = re.sub(r"(?i)^\d+[.)]\s*(?:nazwa|firma)?\s*:?\s*", "", raw)
    raw = re.sub(r"(?i)^(?:nazwa|firma)\s*(?::|\n)\s*|^mocodawca\s*:\s*", "", raw)
    # „Działając w imieniu spółki X sp. z o.o.” -> „X sp. z o.o.”
    raw = re.sub(r"(?i)^.*?\bw\s+imieniu\s+(?:spółki\s+)?", "", raw)
    return as_text(raw)


_SIGN_ROLE = re.compile(
    r"(?i)^(prokurent|prezes|wiceprezes|wspólnik|dyrektor|członek|pełnomocnik zarządu)\b"
)


def _attach_signers(text: str, items: list[dict], listing: dict) -> None:
    if not items:
        return
    lines = text.splitlines()
    groups: list[tuple[str | None, list[str]]] = []
    label = None
    bucket: list[str] = []

    def flush() -> None:
        if bucket:
            groups.append((label, list(bucket)))
            bucket.clear()

    for index, raw in enumerate(lines):
        line = raw.strip()
        marked = re.match(r"(?i)(?:w imieniu|za)\s+(.+?)\s*:?\s*$", line)
        if marked and not _NAME_LINE.fullmatch(line):
            flush()
            label = marked.group(1)
            continue
        nxt = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if _NAME_LINE.fullmatch(line) and _SIGN_ROLE.search(nxt):
            bucket.append(line)
    flush()
    if not groups:
        for item in items:
            person = item["data"].get("imie_nazwisko")
            if person:
                item["podpisujacy"] = [{"imie_nazwisko": person}]
        return
    if len(items) == 1:
        names = [name for _, found in groups for name in found]
        items[0]["podpisujacy"] = [{"imie_nazwisko": name} for name in names]
        return
    for group_label, names in groups:
        target = _match_party(items, group_label or "")
        if target is not None and names:
            items[target]["podpisujacy"] = [{"imie_nazwisko": name} for name in names]


def _match_party(items: list[dict], label: str) -> int | None:
    needle = label.lower()
    best_index = None
    best_len = 0
    for index, item in enumerate(items):
        name = (item["data"].get("nazwa") or "").lower()
        if name and (name in needle or needle in name) and len(name) > best_len:
            best_index = index
            best_len = len(name)
    if best_index is None and len(items) == 1:
        return 0
    return best_index


# „KRS 0000123456”, „KRS: …”, „KRS pod nr …”, „KRS pod numerem …”.
_KRS_LABEL = r"(?i)KRS(?:\s*:|\s+(?:pod\s+)?(?:nr|numerem)\.?)?\s*(\d{10})(?!\d)"


def _clusters(listing: dict, text: str, candidates) -> list[dict]:
    limit = len(text)
    lowered = text.lower()
    for phrase in listing.get("before") or []:
        index = lowered.find(phrase.lower())
        if index >= 0:
            limit = min(limit, index)
    window = int(listing.get("window", 320))
    items = []
    seen: set[str] = set()
    for cand in candidates:
        if cand.kind != listing.get("kind", "nip") or cand.start >= limit or cand.value in seen:
            continue
        seen.add(cand.value)
        win = text[max(0, cand.start - window) : cand.start]
        krs_match = None
        for match in re.finditer(_KRS_LABEL, win):
            krs_match = match
        krs = as_krs(krs_match.group(1)) if krs_match else None
        typ = "osoba_prawna" if krs else "osoba_fizyczna"
        imie = None
        if typ == "osoba_fizyczna" and listing.get("person_pattern"):
            person = None
            for match in re.finditer(listing["person_pattern"], win, re.I):
                person = match
            if person:
                imie = as_person(person.group("value"))
        items.append(
            {
                "data": {
                    "imie_nazwisko": imie,
                    "krs": krs,
                    "nazwa": _best_name(win, listing.get("name_patterns") or []),
                    "nip": cand.value,
                    "typ": typ,
                },
                "podpisujacy": [{"imie_nazwisko": None}],
            }
        )
    _attach_signers(text, items, listing)
    return items


_TITLED_NAME = re.compile(
    r"(?:r\.\s*pr\.|adw\.|mec\.|adwokat|radca\s+prawny)\s+"
    r"([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?)"
)


def _nominative(name: str, text: str) -> str:
    """„Hannę Kowalską” -> „Hanna Kowalska”, jeśli ta sama osoba stoi w dokumencie w innej formie po tytule.

    Bierze ostatnie wystąpienie o tych samych rdzeniach imienia i nazwiska: podpis na końcu pisma jest w mianowniku.
    """
    parts = name.split()
    if len(parts) != 2:
        return name
    stems = [part[:4].lower() for part in parts]
    found = name
    for match in _TITLED_NAME.finditer(text):
        other = match.group(1).split()
        if [part[:4].lower() for part in other] == stems:
            found = match.group(1)
    return found


_PERSON = (
    r"([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?"
    r"\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?)"
)


def _persons(listing: dict, text: str) -> list[dict]:
    """Każdy wzorzec ma grupę 1 z nazwiskiem ({osoba}) i `case`, gdy tytuł stoi w celowniku/bierniku."""
    hits = []
    for rule in listing["patterns"]:
        for match in re.finditer(rule["pattern"].replace("{osoba}", _PERSON), text):
            hits.append((match.start(), match, rule.get("case")))
    items = []
    seen: set[str] = set()
    for _, match, case in sorted(hits, key=lambda hit: hit[0]):
        name = as_person(match.group(1))
        case = case or (guess_case(name) if name else None)
        if name and case:
            # Forma z podpisu w dokumencie ma pierwszeństwo przed regułą końcówek.
            found = _nominative(name, text)
            name = found if found != name else to_nominative(name, case)
        if not name or name in seen:
            continue
        seen.add(name)
        pesel = None
        if listing.get("pesel_pattern"):
            near = re.search(listing["pesel_pattern"], text[match.end() : match.end() + 80])
            if near:
                pesel = near.group(1)
        items.append({"imie_nazwisko": name, "pesel": pesel})
    return items


def _lookup(data: dict, field: dict, tables: dict):
    current = _get(data, field["from"])
    if current is None:
        return None
    opis = tables[field["table"]]["opis"]
    return opis.get(int(current), opis.get(str(int(current))))


def _eval_scalar(field, text, pages, candidates, scopes, tables, owner):
    method = field.get("method")
    if method == "semantic":
        return None, None
    region = _region(field, text, pages, scopes)
    if method == "regex":
        return _regex_field(field, region)
    if method == "line":
        return _line_field(field, region)
    if method == "span":
        return _span_field(field, region)
    if method == "candidate":
        return _candidate_field(field, candidates)
    if method == "first_match":
        # shortcut: frazy z config/czynnosci.yaml pokrywają znane sformułowania, ustaw method:semantic gdy parafraza nie łapie id
        # Wygrywa fraza wymieniona najwcześniej w tekście; przy tej samej pozycji kolejność tabeli (węższe frazy wyżej).
        best = None
        for order, row in enumerate(tables[field["table"]]["match"]):
            hit = re.search(row["pattern"], region, re.I)
            if hit and (best is None or (hit.start(), order) < best[0]):
                best = ((hit.start(), order), row)
        return (int(best[1]["id"]), best[1]["pattern"]) if best else (None, None)
    if method == "lookup":
        return _lookup(owner, field, tables), None
    if method == "flag":
        return _flag_value(field, region, 1), None
    return None, None


def _semantic_paths(spec: dict) -> list[dict]:
    found = []
    for field in spec.get("fields") or []:
        if field.get("method") == "semantic":
            found.append(field)
    for listing in spec.get("lists") or []:
        for field in listing.get("fields") or []:
            if field.get("method") == "semantic":
                found.append(field)
    return found


def _candidate_values(candidates) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for item in candidates:
        grouped.setdefault(item.kind, set()).add(str(item.value))
    return grouped


def _merge_semantic(data: dict, filled: dict, fields: list[dict], candidates) -> None:
    known = _candidate_values(candidates)
    for field in fields:
        path = field["path"]
        try:
            value = _get(filled, path)
        except (KeyError, TypeError):
            continue
        kind = field.get("type")
        if kind in _ID_TYPES and value is not None and str(value) not in known.get(kind, set()):
            continue
        if value is not None:
            _set(data, path, value)


def _llm_classify(llm, text: str, classes: list[dict]):
    names = ", ".join(spec["name"] for spec in classes)
    raw = llm.complete_json(
        "Klasyfikujesz polski dokument zamówień publicznych. Zwróć JSON {\"class\": \"<nazwa>\"} albo {\"class\": \"none\"}.",
        f"Dozwolone klasy: {names}, none.\n\n{text[:4000]}",
    )
    if not raw:
        return None
    chosen = str(raw.get("class") or "none")
    for spec in classes:
        if spec["name"] == chosen:
            return spec
    return None


def _fill_semantic(llm, spec, data, pages, candidates, tables):
    fields = _semantic_paths(spec)
    if not fields:
        return
    if llm is None or not llm.available:
        return
    charge = ""
    if "charge" in (spec.get("scopes") or {}):
        charge = _scope_text("\n".join(pages), spec["scopes"]["charge"])
    clip = "\n".join(pages[:3])
    if charge and charge not in clip:
        clip += "\n" + charge
    listed = [
        {"kind": item.kind, "value": item.value, "context": re.sub(r"\s+", " ", item.context)[:160]}
        for item in candidates[:40]
    ]
    descriptions = [
        {"path": field["path"], "description": field.get("description", "")} for field in fields
    ]
    raw = llm.complete_json(
        "Uzupełniasz tylko pola semantic polskiego dokumentu. Zwróć JSON o tych ścieżkach. "
        "Nie wymyślaj NIP, REGON, KRS, PESEL, IBAN, BZP ani TED, jeśli nie ma ich na liście kandydatów. "
        "Daty w ISO YYYY-MM-DD. Gdy brak danych, null.",
        json_dumps_prompt(spec["name"], descriptions, data, listed, clip[:12000]),
    )
    if not raw:
        return
    _merge_semantic(data, raw, fields, candidates)
    for field in spec.get("fields") or []:
        if field.get("method") == "lookup":
            _set(data, field["path"], _lookup(data, field, tables))


def json_dumps_prompt(class_name, descriptions, data, listed, clip) -> str:
    import json

    return json.dumps(
        {
            "class": class_name,
            "fields": descriptions,
            "current": data,
            "candidates": listed,
            "clip": clip,
        },
        ensure_ascii=False,
    )


def process_pages(pages: list[str], llm=None, classes=None, tables=None) -> tuple[dict, dict]:
    classes = list(classes or load_classes())
    tables = tables or load_tables()
    if llm is not None and llm.available and llm.model.get("extraction") == "llm":
        from app.llm_extract import process as process_llm

        result = process_llm(llm, pages, classes, tables)
        if result is not None:
            return result
        # Model nie odpowiedział: reguły, żeby plik nie został bez wyniku.
    text = "\n".join(pages)
    first = pages[0] if pages else ""
    spec, score, grey = classify_text(first, classes)
    trace = {"class": None, "confidence": score, "fields": [], "ocr": None, "method": "rules"}
    if spec is None and grey and llm is not None and llm.available:
        spec = _llm_classify(llm, first, classes)
    if spec is None:
        return copy.deepcopy(EMPTY_DOCUMENT), trace
    trace["class"] = spec["name"]
    trace["confidence"] = score
    data = copy.deepcopy(spec["schema"])
    candidates = find_candidates(text)
    scopes = spec.get("scopes") or {}
    for field in spec.get("fields") or []:
        if field.get("method") in {"lookup", "semantic"}:
            continue
        value, quote = _eval_scalar(field, text, pages, candidates, scopes, tables, data)
        if value is not None:
            _set(data, field["path"], value)
            trace["fields"].append(_trace(field["path"], value, quote, field["method"], pages))
    for listing in spec.get("lists") or []:
        path = listing["path"]
        if listing.get("method") == "clusters":
            items = _clusters(listing, text, candidates)
            if items:
                _set(data, path, items)
                for index, item in enumerate(items):
                    trace["fields"].append(
                        _trace(f"{path}[{index}].data.nip", item["data"].get("nip"), item["data"].get("nip"), "regex", pages)
                    )
            continue
        if listing.get("method") == "persons":
            items = _persons(listing, text)
            if items:
                _set(data, path, items)
                for index, item in enumerate(items):
                    trace["fields"].append(
                        _trace(f"{path}[{index}].imie_nazwisko", item["imie_nazwisko"], item["imie_nazwisko"], "regex", pages)
                    )
            continue
        section = _scope_text(text, scopes[listing["scope"]])
        if not section.strip():
            continue
        chunks = _split_chunks(section, listing.get("split"))
        template = _get(spec["schema"], path)[0]
        items = []
        for chunk in chunks:
            item = copy.deepcopy(template)
            local = find_candidates(chunk)
            for field in listing.get("fields") or []:
                if field.get("method") in {"flag", "semantic"}:
                    continue
                # only_if_empty: zapasowa reguła dla tej samej ścieżki, np. kancelaria z nagłówka pisma.
                if field.get("only_if_empty") and _get(item, field["path"]) is not None:
                    continue
                value, quote = _eval_scalar(field, chunk, pages, local, {}, tables, item)
                if value is not None and field.get("nominative"):
                    value = _nominative(value, text)
                if value is not None:
                    _set(item, field["path"], value)
                    trace["fields"].append(
                        _trace(f"{path}[{len(items)}].{field['path']}", value, quote, field["method"], pages)
                    )
            items.append((item, chunk))
        built = []
        for index, (item, chunk) in enumerate(items):
            for field in listing.get("fields") or []:
                if field.get("method") != "flag":
                    continue
                value = _flag_value(field, chunk, len(items))
                if field.get("or_filled") and _get(item, field["or_filled"]) is not None:
                    value = field.get("when_match", 1)
                _set(item, field["path"], value)
                trace["fields"].append(_trace(f"{path}[{index}].{field['path']}", value, None, "regex", pages))
            built.append(item)
        if built:
            _set(data, path, built)
    for field in spec.get("fields") or []:
        if field.get("method") == "lookup":
            value = _lookup(data, field, tables)
            _set(data, field["path"], value)
            if value is not None:
                trace["fields"].append(_trace(field["path"], value, None, "lookup", pages))
    _fill_semantic(llm, spec, data, pages, candidates, tables)
    return data, trace


def process_pdf(path: str | Path, llm=None) -> tuple[dict, dict]:
    try:
        extracted = extract_pdf(path)
    except Exception as exc:  # uszkodzony PDF nie może przerwać wsadu
        return copy.deepcopy(EMPTY_DOCUMENT), {"class": None, "confidence": 0, "fields": [], "error": str(exc)}
    document, trace = process_pages(extracted["pages"], llm=llm)
    trace["ocr"] = extracted["ocr"]
    trace["source"] = Path(path).name
    return document, trace
