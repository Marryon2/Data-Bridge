from __future__ import annotations

import sys

from app.config import ROOT
from app.engine import process_input
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
    if not process_input(llm):
        print(f"Brak plików PDF w {ROOT.parent / 'input'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
