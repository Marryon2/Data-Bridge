from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor

from app.config import ROOT, load_model
from app.engine import process_pdf
from app.llm import LLMClient


def main() -> int:
    # Windows przy przekierowanym stdout używa cp1252 i wywraca się na polskich znakach.
    sys.stdout.reconfigure(encoding="utf-8")
    if "--serve" in sys.argv:
        from app.ui import serve

        serve()
        return 0
    llm = LLMClient()
    if not llm.available:
        print("LLM niedostępny (brak klucza lub endpointu w config/model.yaml): działają same reguły.")
        llm = None
    # input/ i output/ leżą obok projektu (/opt/input, /opt/solution); w kontenerze ROOT=/app, więc /input i /output.
    input_root = ROOT.parent / "input"
    output_root = ROOT.parent / "output"
    trace_root = ROOT / "trace"
    # Każdy PDF z input/ na dowolnej głębokości (input/case1/x.pdf, input/x.PDF); output/ powtarza tę samą ścieżkę.
    pdfs = sorted(p for p in input_root.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"Brak plików PDF w {input_root}")
        return 0
    # Kilka plików naraz: OCR jednego idzie w czasie, gdy inny czeka na model (API z równoległością przyspiesza więcej).
    workers = max(1, int((llm.model if llm else load_model()).get("workers", 1)))
    with ThreadPoolExecutor(workers) as pool:
        for pdf, (document, trace) in zip(pdfs, pool.map(lambda pdf: process_pdf(pdf, llm=llm), pdfs)):
            relative = pdf.relative_to(input_root).with_suffix(".json")
            destination, traced = output_root / relative, trace_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            traced.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            traced.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            label = f"{trace.get('class') or 'none'}, {'AI' if trace.get('method') == 'llm' else 'reguły'}"
            print(f"{pdf.relative_to(input_root)} -> {destination.relative_to(ROOT.parent)} ({label})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
