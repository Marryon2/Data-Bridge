"""Lokalny F1 liści. Nie jest na ścieżce ocenianej.

Aplikacja zapisuje stem PDF. Ten skorer paruje potwierdzenie_przelewu.pdf
z przelew.json po klasie, nie po nazwie pliku wynikowego.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app.engine import process_pdf

STEM_GOLD = {
    "odwolanie": "odwolanie.json",
    "pelnomocnictwo": "pelnomocnictwo.json",
    "potwierdzenie_przelewu": "przelew.json",
}


def canon(value):
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("b", value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ("n", float(value))
    return ("s", value)


def flatten(obj, prefix=""):
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten(value, path))
        return out
    if isinstance(obj, list):
        out = {}
        for index, value in enumerate(obj):
            out.update(flatten(value, f"{prefix}[{index}]"))
        return out
    return {prefix: obj}


def _leaf_counts(gold, pred) -> tuple[int, int, int]:
    paths = set(gold) | set(pred)
    tp = fp = fn = 0
    for path in paths:
        left = gold.get(path, ("missing",))
        right = pred.get(path, ("missing",))
        if left == right:
            tp += 1
        else:
            if path in pred:
                fp += 1
            if path in gold:
                fn += 1
    return tp, fp, fn


def _multiset_counts(gold, pred) -> tuple[int, int, int]:
    def grouped(flat):
        bags = defaultdict(Counter)
        for path, value in flat.items():
            bags[re.sub(r"\[\d+\]", "[]", path)][value] += 1
        return bags

    left, right = grouped(gold), grouped(pred)
    tp = fp = fn = 0
    for key in set(left) | set(right):
        a, b = left.get(key, Counter()), right.get(key, Counter())
        for value in set(a) | set(b):
            common = min(a[value], b[value])
            tp += common
            fp += b[value] - common
            fn += a[value] - common
    return tp, fp, fn


def f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0 and fp == 0 and fn == 0:
        return 1.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _canon_flat(obj) -> dict:
    return {path: canon(value) for path, value in flatten(obj).items()}


def score_pair(gold, pred) -> dict:
    g, p = _canon_flat(gold), _canon_flat(pred)
    tp, fp, fn = _leaf_counts(g, p)
    mtp, mfp, mfn = _multiset_counts(g, p)
    return {"tp": tp, "fp": fp, "fn": fn, "mtp": mtp, "mfp": mfp, "mfn": mfn, "gold": g, "pred": p}


def field_key(path: str) -> str:
    return re.sub(r"\[\d+\]", "[]", path)


def iter_cases(data: Path):
    dane = data / "dane" if (data / "dane").is_dir() else data
    for case in sorted(path for path in dane.iterdir() if path.is_dir() and path.name.startswith("przyklad_")):
        for pdf in sorted(case.glob("*.pdf")):
            gold_name = STEM_GOLD.get(pdf.stem)
            gold_path = case / gold_name if gold_name else None
            if gold_path and gold_path.is_file():
                gold = json.loads(gold_path.read_text(encoding="utf-8"))
            else:
                gold = {}
            yield pdf, gold
    negative = dane / "negatywne"
    if negative.is_dir():
        for pdf in sorted(negative.glob("*.pdf")):
            yield pdf, {}


def run_score(data: Path) -> dict:
    totals = Counter()
    multi = Counter()
    fields = defaultdict(Counter)
    negatives = {"n": 0, "ok": 0}
    for pdf, gold in iter_cases(data):
        pred, _trace = process_pdf(pdf, llm=None)
        if gold == {}:
            negatives["n"] += 1
            if pred == {}:
                negatives["ok"] += 1
        pair = score_pair(gold, pred)
        totals.update({key: pair[key] for key in ("tp", "fp", "fn")})
        multi.update({"tp": pair["mtp"], "fp": pair["mfp"], "fn": pair["mfn"]})
        keys = set(pair["gold"]) | set(pair["pred"])
        for path in keys:
            bucket = fields[field_key(path)]
            left = pair["gold"].get(path, ("missing",))
            right = pair["pred"].get(path, ("missing",))
            if left == right:
                bucket["tp"] += 1
            else:
                if path in pair["pred"]:
                    bucket["fp"] += 1
                if path in pair["gold"]:
                    bucket["fn"] += 1
    return {"ordered": totals, "multiset": multi, "fields": fields, "negatives": negatives}


def _format_f1(counts) -> str:
    return f"{f1(counts['tp'], counts['fp'], counts['fn']):.3f}  tp={counts['tp']} fp={counts['fp']} fn={counts['fn']}"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Lokalny F1 liści względem danych organizatora")
    parser.add_argument("--data", required=True, help="Katalog hacknation-2026 (z podkatalogiem dane)")
    args = parser.parse_args(argv)
    report = run_score(Path(args.data))
    print("ordered ", _format_f1(report["ordered"]))
    print("multiset", _format_f1(report["multiset"]))
    neg = report["negatives"]
    print(f"negatives {neg['ok']}/{neg['n']}")
    rows = []
    for name, counts in report["fields"].items():
        rows.append((f1(counts["tp"], counts["fp"], counts["fn"]), name, counts))
    for value, name, counts in sorted(rows):
        print(f"{value:.3f}  {name}  tp={counts['tp']} fp={counts['fp']} fn={counts['fn']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
