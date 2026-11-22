"""Poprawki tekstu ze skanu (tylko ścieżka OCR): pola o znanym formacie i głosowanie nazw w obrębie dokumentu."""

from __future__ import annotations

import re

# --- Warstwa 2: pola o znanym formacie ---------------------------------------------------------

# Tesseract czyta „@” jako G, Q, ©, „G©”, „g©”, „(a)” albo „( ”. Adres poza tym ma same małe litery,
# więc wielka litera albo symbol w środku zdradza „@”.
_EMAIL_BROKEN = re.compile(
    r"(?<![\w@.])([a-z0-9][a-z0-9._%+\-]*?)(?:[GQ©®]{1,2}|g[©®]|\((?:a|at)?\)|\(\s)([a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)*\.[a-z]{2,})(?![\w@])"
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


# Adres po etykiecie „e-mail:” bez „@”. Gdzie stało „@”, mówi domena znana z innego miejsca dokumentu
# (strona www albo inny adres); OCR zamienia „@” na 1–2 znaki z tego zbioru („o”, „g©”…).
_EMAIL_LABELLED = re.compile(r"(?i)(e-?mail\s*:?\s*)([^\s@,;]{5,}?)([.,;]?)(?=\s|$)")
_AT_LIKE = set("oaeg9GQ0©®@")
_LOCAL = re.compile(r"[a-z0-9][a-z0-9._%+\-]*")


def _known_domains(text: str) -> list[str]:
    lowered = text.lower()
    found = re.findall(r"@([a-z0-9\-]+(?:\.[a-z0-9\-]+)+)", lowered) + re.findall(r"\bwww\.([a-z0-9\-]+(?:\.[a-z0-9\-]+)+)", lowered)
    return sorted({domain.rstrip(".") for domain in found}, key=len, reverse=True)


def fix_emails(text: str) -> str:
    text = _EMAIL_BROKEN.sub(r"\1@\2", text)
    domains = _known_domains(text)

    def labelled(match: re.Match) -> str:
        token = match.group(2)
        for domain in domains:
            if not token.lower().endswith(domain) or len(token) <= len(domain) + 1:
                continue
            prefix = token[: -len(domain)]
            for k in (2, 1):  # dwa znaki tylko z symbolem („g©”), inaczej zjadłby literę adresu
                junk, local = prefix[-k:], prefix[:-k]
                if all(c in _AT_LIKE for c in junk) and (k == 1 or any(not c.isalnum() for c in junk)) and _LOCAL.fullmatch(local):
                    return match.group(1) + local + "@" + token[-len(domain):] + match.group(3)
        return match.group(0)

    return _EMAIL_LABELLED.sub(labelled, text)


# „&” w nazwach („Krawczyk & Bąk”) OCR czyta jako 8, 6, „8:” albo „6:”. Tylko między dwoma wyrazami z wielkiej litery
# i nie po słowach, po których zwykle stoi numer („Rozdział 6 Opis”).
_AMPERSAND = re.compile(r"\b([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+) (?:[86]|&):? (?=[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+\b)")
_NUMBERED = {"Rozdział", "Załącznik", "Punkt", "Pakiet", "Część", "Zadanie", "Etap", "Tom", "Dział", "Strona",
             "Paragraf", "Artykuł", "Lot", "Grupa", "Pozycja", "Numer", "Formularz", "Wzór", "Tabela", "Ust", "Pkt", "Art"}


def fix_ampersand(text: str) -> str:
    return _AMPERSAND.sub(lambda m: m.group(0) if m.group(1) in _NUMBERED else f"{m.group(1)} & ", text)


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
    return fix_ampersand(fix_numbers(fix_emails(text)))


# --- Układ strony: dwie kolumny obok siebie -------------------------------------------------------

def layout_text(lines: list[list[tuple[int, int, int, int, str]]]) -> str | None:
    """Wiersze z TSV Tesseracta: [(x_od, x_do, y_od, y_do, słowo), ...] w kolejności czytania.
    Tesseract czyta nagłówek „ODWOŁUJĄCY: … ZAMAWIAJĄCY: …” wiersz po wierszu przez obie kolumny i skleja strony.
    Ciąg ≥2 wierszy z dużą przerwą w tym samym miejscu to dwie kolumny: najpierw cała lewa, potem cała prawa.
    Ciąg kończy wiersz przecinający przerwę albo pusta linia nad wierszem (nowa sekcja pisma).
    None, gdy na stronie nie ma kolumn (wtedy zostaje zwykły tekst Tesseracta)."""

    def height(words):
        return sorted(w[3] - w[2] for w in words)[len(words) // 2]

    def split(words):
        for i in range(len(words) - 1):
            if words[i + 1][0] - words[i][1] > max(40, 2 * height(words)):
                return words[: i + 1], words[i + 1 :]
        return None

    def join(words):
        return " ".join(w[4] for w in words)

    out: list[str] = []
    run: list[tuple[list, list | None]] = []  # (lewa, prawa albo None) dla wierszy w bieżącym ciągu
    gutter, found, bottom = None, False, 0

    def flush():
        nonlocal run, gutter, found
        if sum(bool(left) and bool(right) for left, right in run) >= 2:
            found = True
            out.extend(join(left) for left, _ in run if left)
            out.extend(join(right) for _, right in run if right)
        else:
            out.extend(join((left or []) + (right or [])) for left, right in run)
        run, gutter = [], None

    for words in lines:
        if not words:
            continue
        parts = split(words)
        top = min(w[2] for w in words)
        if gutter is not None and top - bottom > 0.75 * height(words):
            flush()  # pusta linia: koniec bloku kolumn
        bottom = max(w[3] for w in words)
        if parts and gutter is not None and abs(parts[1][0][0] - gutter) <= 40:
            run.append(parts)
        elif gutter is not None and words[-1][1] < gutter - 10:
            run.append((words, None))  # wiersz tylko w lewej kolumnie
        elif gutter is not None and words[0][0] >= gutter - 40:
            run.append(([], words))  # wiersz tylko w prawej kolumnie
        else:
            flush()
            if parts:
                run, gutter = [parts], parts[1][0][0]
            else:
                out.append(join(words))
    flush()
    return "\n".join(out) if found else None


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
        # Interpunkcja przy krawędzi należy do zdania, nie do nazwy („S.A.,” -> „S.A.”).
        chunk = " ".join(words[start : start + size]).strip(",;:")
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
