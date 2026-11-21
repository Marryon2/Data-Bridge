from __future__ import annotations

import re

MONTHS = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "wrzesnia": 9,
    "września": 9,
    "pazdziernika": 10,
    "października": 10,
    "listopada": 11,
    "grudnia": 12,
}

_TITLES = re.compile(
    r"(?i)\b(?:r\.\s*pr\.|r\.pr\.|adw\.|mec\.|adwokat|radca\s+prawny)\s*"
)


def collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def as_text(value: str) -> str | None:
    if value is None:
        return None
    text = collapse(str(value)).strip()
    text = re.sub(r"^[„\"']+", "", text)
    text = re.sub(r"[”\"']+\.?$", "", text)
    text = text.strip(" „”\"',;")
    return text or None


def as_person(value: str) -> str | None:
    if value is None:
        return None
    text = _TITLES.sub("", str(value))
    text = collapse(text).strip(" \t,;.")
    return text or None


# Końcówki imion i nazwisk po tytule w celowniku („radcy prawnemu Annie Wiśniewskiej”)
# i bierniku/dopełniaczu („Pana Tomasza Nowickiego”). Pierwsza pasująca końcówka wygrywa.
_ENDINGS = {
    "dative": [("skiemu", "ski"), ("ckiemu", "cki"), ("dzkiemu", "dzki"), ("owi", ""),
               ("skiej", "ska"), ("ckiej", "cka"), ("dzkiej", "dzka"), ("cie", "ta"), ("dze", "ga"),
               ("rze", "ra"), ("ce", "ka"), ("ii", "ia"), ("ji", "ja"), ("li", "la"), ("ie", "a")],
    "accusative": [("skiego", "ski"), ("ckiego", "cki"), ("dzkiego", "dzki"), ("iego", "i"), ("ego", "y"),
                   ("ę", "a"), ("ą", "a"), ("a", "")],
}


def guess_case(name: str) -> str | None:
    """Końcówki, których mianownik imienia i nazwiska praktycznie nie ma: -owi/-emu/-iej (celownik), -ę/-ą/-ego (biernik)."""
    words = name.split()
    if len(words) != 2:
        return None
    first, last = words
    if last.endswith(("owi", "emu", "iej")) or first.endswith(("owi", "ie")):
        return "dative"
    if first.endswith("ę") or last.endswith(("ą", "ego")):
        return "accusative"
    return None


def to_nominative(name: str, case: str | None) -> str:
    """„Annie Wiśniewskiej” -> „Anna Wiśniewska”, „Marka Nowaka” -> „Marek Nowak”.

    shortcut: reguły końcówek bez słownika (np. „Wróbla” -> „Wróbl”); trudne nazwiska rozstrzygnie LLM.
    """
    table = _ENDINGS.get(case or "")
    if not table:
        return name
    words = []
    for word in name.split():
        for end, repl in table:
            if word.endswith(end) and len(word) > len(end) + 1:
                word = word[: -len(end)] + repl
                # Ruchome „e”: Marka -> Marek, Pawłowi -> Paweł (spółgłoska przed końcowym k/ł).
                if end in ("a", "owi") and re.search(r"[^aeiouyąęó][kł]$", word):
                    word = word[:-1] + "e" + word[-1]
                break
        words.append(word)
    return " ".join(words)


def as_email(value: str) -> str | None:
    if not value:
        return None
    # Adres przełamany na myślniku („biuro@szymanski-\nkancelaria.example”) wraca do jednej linii.
    return re.sub(r"\s+", "", str(value)).lower()


def as_entity(value: str) -> str | None:
    """Nazwa podmiotu bez adresu i numerów: ucina od „, ul.”, kodu pocztowego, „| KRS” itp."""
    if value is None:
        return None
    text = collapse(str(value))
    text = re.split(r",\s*(?=(?:ul\.|al\.|pl\.|os\.|plac\b|\d{2}-\d{3}\b|KRS\b|NIP\b|REGON\b))|\s+\|\s+"
                    r"|\s+z\s+siedzibą\b|\s*\((?i:lider|partner|członek)", text)[0]
    return as_text(text)


def as_date(value: str) -> str | None:
    if value is None:
        return None
    raw = collapse(str(value)).lower()
    raw = re.sub(r"\s+r\.?$", "", raw)
    raw = re.sub(r"\s+roku$", "", raw).strip()
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    match = re.fullmatch(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", raw)
    if match:
        day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return f"{year:04d}-{month:02d}-{day:02d}"
    match = re.fullmatch(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", raw)
    if match and match.group(2) in MONTHS:
        return f"{int(match.group(3)):04d}-{MONTHS[match.group(2)]:02d}-{int(match.group(1)):02d}"
    return None


def as_amount(value: str) -> float | None:
    if value is None:
        return None
    raw = str(value).lower()
    raw = re.sub(r"(?i)pln|zł|zl", "", raw)
    raw = re.sub(r"[^\d,.\-]", "", raw)
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def as_iban(value: str) -> str | None:
    number = digits(str(value))
    if len(number) == 26:
        return number
    if len(number) > 26:
        return number[-26:]
    return None


def as_nip(value: str) -> str | None:
    number = digits(str(value))
    return number if len(number) == 10 else None


def as_regon(value: str) -> str | None:
    number = digits(str(value))
    return number if len(number) in (9, 14) else None


def as_krs(value: str) -> str | None:
    number = digits(str(value))
    return number if len(number) == 10 else None


def as_bzp(value: str) -> str | None:
    match = re.search(r"(\d{4})\s*/\s*BZP\s*(\d+)(?:\s*/\s*(\d{2}))?", str(value), re.I)
    if not match:
        return None
    out = f"{match.group(1)}/BZP{match.group(2)}"
    if match.group(3):
        out += f"/{match.group(3)}"
    return out


def as_ted(value: str) -> str | None:
    raw = str(value)
    spaced = re.search(r"(\d{4})\s*/\s*S\s*\d{1,3}\s*-\s*(\d{6})", raw, re.I)
    if spaced:
        return f"{spaced.group(2)}-{spaced.group(1)}"
    plain = re.search(r"(\d{6})\s*-\s*(\d{4})", raw)
    if plain:
        return f"{plain.group(1)}-{plain.group(2)}"
    return None


def as_int(value) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


NORMALIZERS = {
    "text": as_text,
    "entity": as_entity,
    "person": as_person,
    "email": as_email,
    "date": as_date,
    "amount": as_amount,
    "iban": as_iban,
    "nip": as_nip,
    "regon": as_regon,
    "krs": as_krs,
    "bzp": as_bzp,
    "ted": as_ted,
    "int": as_int,
}


def apply_normalizer(name: str | None, value):
    if value is None or not name:
        return value
    return NORMALIZERS[name](value)


def nip_checksum_ok(value: str) -> bool:
    if not re.fullmatch(r"\d{10}", value):
        return False
    weights = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    total = sum(int(d) * w for d, w in zip(value[:9], weights))
    check = total % 11
    return check != 10 and check == int(value[9])


def regon_checksum_ok(value: str) -> bool:
    if re.fullmatch(r"\d{9}", value):
        weights = (8, 9, 2, 3, 4, 5, 6, 7)
        check = sum(int(d) * w for d, w in zip(value[:8], weights)) % 11
        return (0 if check == 10 else check) == int(value[8])
    if re.fullmatch(r"\d{14}", value):
        weights = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)
        check = sum(int(d) * w for d, w in zip(value[:13], weights)) % 11
        return (0 if check == 10 else check) == int(value[13])
    return False


def iban_checksum_ok(value: str) -> bool:
    if not re.fullmatch(r"\d{26}", value):
        return False
    raw = "PL" + value
    moved = raw[4:] + raw[:4]
    number = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in moved)
    return int(number) % 97 == 1
