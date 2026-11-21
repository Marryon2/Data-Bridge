from __future__ import annotations

import re


def _score(text: str, spec: dict) -> int:
    for rule in spec.get("negative") or []:
        if re.search(rule["pattern"], text, re.I):
            if rule.get("weight", 0) >= spec.get("veto", 50):
                return -1
    score = 0
    for rule in spec.get("positive") or []:
        if re.search(rule["pattern"], text, re.I | re.S):
            score += int(rule.get("weight", 1))
    return score


def classify_text(text: str, classes: list[dict]) -> tuple[dict | None, int, list[dict]]:
    """Zwraca (klasa albo None, wynik, klasy w szarej strefie)."""
    scored = [( _score(text, spec), spec) for spec in classes]
    winners = [(score, spec) for score, spec in scored if score >= int(spec.get("threshold", 1))]
    if winners:
        winners.sort(key=lambda item: (item[0], int(item[1].get("threshold", 0))), reverse=True)
        return winners[0][1], winners[0][0], []
    grey = [
        spec
        for score, spec in scored
        if int(spec.get("grey", 0)) <= score < int(spec.get("threshold", 1)) and score > 0
    ]
    best = max((score for score, _ in scored), default=0)
    return None, best, grey
