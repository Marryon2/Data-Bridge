"""Poprawki tekstu ze skanu (tylko ścieżka OCR): pola o znanym formacie i głosowanie nazw w obrębie dokumentu."""

from __future__ import annotations

import re

# --- Warstwa 2: pola o znanym formacie ---------------------------------------------------------

# Tesseract czyta „@” jako G, Q, © albo „(a)”. Adres poza tym ma same małe litery, więc wielka litera w środku zdradza „@”.
_EMAIL_BROKEN = re.compile(
    r"(?<![\w@.])([a-z0-9][a-z0-9._%+\-]*?)(?:[GQ©®]|\(a\)|\(at\))([a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)*\.[a-z]{2,})(?![\w@])"
)

# Litery, które OCR myli z cyframi. Tylko kierunek litera -> cyfra: te pola są czysto cyfrowe.
_TO_DIGIT = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "l": "1", "I": "1", "|": "1", "i": "1",
                           "S": "5", "s": "5", "B": "8", "Z": "2", "z": "2", "g": "9"})
_DIGITISH = "0-9OoDQlI|iSsBZzg"
# Etykieta -> długości wartości. Wartość może mieć myślniki i spacje („999-295-65-50”).
_LABELLED = re.compile(rf"(?i)\b(NIP|REGON|KRS|PESEL)(\s*(?:nr\.?)?\s*[:.]?\s*)((?:[{_DIGITISH}][ \-]?){{8,15}}[{_DIGITISH}])")
_LENGTHS = {"nip": {10}, "regon": {9, 14}, "krs": {10}, "pesel": {11}}
# Rachunek: 26 znaków (spacje dozwolone), z czego najwyżej 3 to litery-sobowtóry.
_IBAN_LIKE = re.compile(rf"(?<![\w])((?:PL\s?)?(?:[{_DIGITISH}]\s?){{25}}[{_DIGITISH}])(?![\w])")


def fix_emails(text: str) -> str:
    return _EMAIL_BROKEN.sub(r"\1@\2", text)


def _digits_fixed(raw: str, lengths: set[int]) -> str | None:
    mapped = raw.translate(_TO_DIGIT)
    plain = re.sub(r"[ \-]", "", mapped)
    return mapped if plain.isdigit() and len(plain) in lengths else None


def fix_numbers(text: str) -> str:
    """Litery-sobowtóry w NIP/REGON/KRS/PESEL/IBAN -> cyfry. Sumy kontrolnej nie używa: dane syntetyczne jej nie spełniają."""

    def labelled(match: re.Match) -> str:
        raw = match.group(3)
        # Dopasowanie bywa za długie („9991022552 sp”): najdłuższy prefiks o właściwej liczbie cyfr.
        for end in range(len(raw), 0, -1):
            fixed = _digits_fixed(raw[:end], _LENGTHS[match.group(1).lower()])
            if fixed is not None:
                return match.group(1) + match.group(2) + fixed + raw[end:]
        return match.group(0)

    def iban(match: re.Match) -> str:
        raw = match.group(1)
        body = raw[2:] if raw.upper().startswith("PL") else raw
        if sum(not ch.isdigit() and not ch.isspace() for ch in body) > 3:
            return raw
        fixed = _digits_fixed(body, {26})
        return raw if fixed is None else raw[: len(raw) - len(body)] + fixed

    return _IBAN_LIKE.sub(iban, _LABELLED.sub(labelled, text))


def fix_text(text: str) -> str:
    return fix_numbers(fix_emails(text))


# --- Warstwa 3: nazwy własne – głosowanie wariantów w obrębie dokumentu -----------------------------


def _distance(a: str, b: str, limit: int) -> int:
    """Levenshtein z wczesnym wyjściem po przekroczeniu limitu."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def _variants(value: str, words: list[str]) -> dict[str, int]:
    """Fragmenty tekstu o tej samej liczbie słów co `value`, różniące się o 1–2 znaki -> liczba wystąpień."""
    size = len(value.split())
    limit = min(2, len(value) // 8)
    found: dict[str, int] = {}
    for start in range(len(words) - size + 1):
        chunk = " ".join(words[start : start + size])
        if chunk == value or _distance(chunk, value, limit) <= limit:
            found[chunk] = found.get(chunk, 0) + 1
    return found


def _confidence(variant: str, conf: dict[str, float]) -> float:
    scores = [conf[word] for word in variant.split() if word in conf]
    return sum(scores) / len(scores) if scores else -1.0


def vote_value(value, words: list[str], conf: dict[str, float]):
    """Wartość odczytana ze skanu zamieniona na wariant z tekstu, który występuje częściej
    (przy remisie: ten, którego słowa Tesseract odczytał pewniej). Liczby i e-maile pomija."""
    if not isinstance(value, str) or len(value) < 6 or re.search(r"[\d@]", value):
        return value
    found = _variants(value, words)
    if value not in found or len(found) < 2:
        return value  # wartość nie pochodzi wprost z OCR albo nie ma konkurencji
    rank = {variant: (count, _confidence(variant, conf)) for variant, count in found.items()}
    best = max(rank, key=rank.get)
    return best if rank[best] > rank[value] else value


def vote_document(document, words: list[str], conf: dict[str, float]):
    if isinstance(document, dict):
        return {key: vote_document(item, words, conf) for key, item in document.items()}
    if isinstance(document, list):
        return [vote_document(item, words, conf) for item in document]
    return vote_value(document, words, conf)
