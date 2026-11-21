from __future__ import annotations

import re
from dataclasses import dataclass

from app.normalize import (
    as_amount,
    as_date,
    as_iban,
    as_krs,
    as_nip,
    as_regon,
    iban_checksum_ok,
    nip_checksum_ok,
    regon_checksum_ok,
)

# NIP także z myślnikami lub spacjami („778-14-22-391”).
_NIP = re.compile(r"(?i)NIP[:\s]*((?:\d[ -]?){9}\d)(?!\d)")
_REGON = re.compile(r"(?i)REGON[:\s]*(\d{9}|\d{14})(?!\d)")
_KRS = re.compile(r"(?i)KRS(?:\s*:|\s+(?:pod\s+)?(?:nr|numerem)\.?)?\s*(\d{10})(?!\d)")
_PESEL = re.compile(r"(?i)PESEL[:\s]*(\d{11})")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_IBAN = re.compile(r"(?i)(?<!\d)((?:PL[\s\-]*)?(?:\d[\s\-]*){26})(?!\d)")
# Kwota nie może być kawałkiem daty („22.06.2026”).
_AMOUNT = re.compile(r"(?i)(?<![\d.,])(\d{1,3}(?:\s\d{3})*|\d+)([.,]\d{2})(?!\d|[.,]\d)\s*(?:zł|pln)?")
_DATE_ISO = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
_DATE_NUM = re.compile(r"(?<!\d)(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})(?!\d)")
_DATE_WORD = re.compile(
    r"(?<!\d)(\d{1,2}\s+(?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|"
    r"września|października|listopada|grudnia)\s+\d{4})(?!\d)",
    re.I,
)
_TX = re.compile(
    r"(?i)(?:numer\s+(?:referencyjny|transakcji|operacji)(?:\s+operacji)?|nr\s+(?:ref\.?|transakcji|operacji)"
    r"|identyfikator\s+(?:operacji|transakcji)|id\s+transakcji|transaction\s+id)"
    # Dopisek po etykiecie („/ Transaction ID”) bez cyfr; wartość: litery, cyfry, „/”, „-”, co najmniej jedna cyfra.
    r"[^:\n\d]{0,30}?[:.]?\s*(?=[A-Z0-9\-/]{5,})([A-Z0-9][A-Z0-9\-/]*\d[A-Z0-9\-/]*)"
)
_TX_BARE = re.compile(r"\bCEN\d{8,16}\b")
_BZP = re.compile(r"(?i)\d{4}\s*/\s*BZP\s*\d+(?:\s*/\s*\d{2})?")
_TED = re.compile(r"(?i)\d{4}\s*/\s*S\s*\d{1,3}\s*-\s*\d{6}|\d{6}\s*-\s*\d{4}")


@dataclass
class Candidate:
    kind: str
    value: str
    raw: str
    start: int
    end: int
    context: str
    checksum_ok: bool | None = None


def _context(text: str, start: int, end: int) -> str:
    # Etykieta stoi przed wartością. Okno za dopasowaniem wciąga następną etykietę.
    return text[max(0, start - 220) : start]


def _add(found: list[Candidate], text: str, kind: str, raw: str, start: int, end: int, value: str, checksum=None):
    if not value:
        return
    found.append(
        Candidate(kind, value, raw, start, end, _context(text, start, end), checksum)
    )


def find_candidates(text: str) -> list[Candidate]:
    """Wszystkie kandydaty zostają. Suma kontrolna tylko rozstrzyga remis, nigdy nie odrzuca."""
    found: list[Candidate] = []
    for match in _NIP.finditer(text):
        value = as_nip(match.group(1))
        _add(found, text, "nip", match.group(1), match.start(1), match.end(1), value, nip_checksum_ok(value) if value else False)
    for match in _REGON.finditer(text):
        value = as_regon(match.group(1))
        _add(found, text, "regon", match.group(1), match.start(1), match.end(1), value, regon_checksum_ok(value) if value else False)
    for match in _KRS.finditer(text):
        value = as_krs(match.group(1))
        _add(found, text, "krs", match.group(1), match.start(1), match.end(1), value, None)
    for match in _PESEL.finditer(text):
        _add(found, text, "pesel", match.group(1), match.start(1), match.end(1), match.group(1), None)
    for match in _EMAIL.finditer(text):
        _add(found, text, "email", match.group(0), match.start(), match.end(), match.group(0).lower(), None)
    for match in _IBAN.finditer(text):
        value = as_iban(match.group(1))
        _add(found, text, "iban", match.group(1), match.start(1), match.end(1), value, iban_checksum_ok(value) if value else False)
    for match in _AMOUNT.finditer(text):
        raw = match.group(1) + match.group(2)
        amount = as_amount(raw)
        if amount is None or amount == 0:
            continue
        _add(found, text, "amount", raw, match.start(), match.end(), raw, None)
    for pattern in (_DATE_ISO, _DATE_NUM, _DATE_WORD):
        for match in pattern.finditer(text):
            if as_date(match.group(1)):
                _add(found, text, "date", match.group(1), match.start(1), match.end(1), match.group(1), None)
    seen_tx: set[tuple[int, str]] = set()
    for match in _TX.finditer(text):
        value = match.group(1).strip()
        seen_tx.add((match.start(1), value))
        _add(found, text, "tx", value, match.start(1), match.end(1), value, None)
    for match in _TX_BARE.finditer(text):
        if any(abs(match.start() - pos) < 5 for pos, _ in seen_tx):
            continue
        _add(found, text, "tx", match.group(0), match.start(), match.end(), match.group(0), None)
    for match in _BZP.finditer(text):
        _add(found, text, "bzp", match.group(0), match.start(), match.end(), match.group(0), None)
    for match in _TED.finditer(text):
        _add(found, text, "ted", match.group(0), match.start(), match.end(), match.group(0), None)
    return found


def hint_points(item: Candidate, hints: list[str], avoid: list[str]) -> float:
    ctx = item.context.lower()
    # Etykieta w tej samej albo poprzedniej linii liczy się bardziej niż ta sprzed 220 znaków.
    near = "\n".join(ctx.split("\n")[-2:])
    points = 0.0
    for hint in hints:
        if hint.lower() in ctx:
            points += 2 + (3 if hint.lower() in near else 0)
    for word in avoid:
        if word and word.lower() in ctx:
            points -= 3 + (3 if word.lower() in near else 0)
    return points


def rank_candidates(pool: list[Candidate], hints: list[str], avoid: list[str]) -> list[Candidate]:
    def score(item: Candidate) -> tuple:
        # Suma kontrolna tylko przy remisie punktacji etykiet.
        return (hint_points(item, hints, avoid), 1 if item.checksum_ok else 0, -item.start)

    return sorted(pool, key=score, reverse=True)
