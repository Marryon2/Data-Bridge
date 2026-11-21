from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import ROOT
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
    input_root = ROOT / "input"
    output_root = ROOT / "output"
    trace_root = ROOT / "trace"
    pdfs = sorted(input_root.glob("*/*.pdf"))
    if not pdfs:
        print(f"Brak PDF w {input_root}/<sprawa>/*.pdf")
        return 0
    for pdf in pdfs:
        document, trace = process_pdf(pdf, llm=llm)
        destination = output_root / pdf.parent.name / f"{pdf.stem}.json"
        traced = trace_root / pdf.parent.name / f"{pdf.stem}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        traced.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        traced.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        label = f"{trace.get('class') or 'none'}, {'AI' if trace.get('method') == 'llm' else 'reguły'}"
        print(f"{pdf.parent.name}/{pdf.name} -> {destination.relative_to(ROOT)} ({label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
