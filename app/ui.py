"""Cienki formularz: ten sam pipeline co CLI, podgląd JSON."""

from __future__ import annotations

import json
import time
from email import policy
from email.parser import BytesParser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import load_env, load_model
from app.engine import process_pdf
from app.llm import LLMClient

_PAGE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Odwołania2json</title>
<style>
/* Paleta i typografia w stylu serwisów administracji: bez godła i logotypów gov.pl. */
:root {
  --blue: #0052a5; --blue-hover: #006cd7; --red: #d5233f; --text: #1b1b1b;
  --muted: #767676; --line: #b7b7b7; --bg-soft: #f1f1f1; --focus: #ffc605;
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  font-family: "Open Sans", "Segoe UI", Arial, sans-serif; color: var(--text);
  line-height: 1.5; background: #fff; display: flex; flex-direction: column; min-height: 100vh;
}
a { color: var(--blue); }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
.wrap { max-width: 60rem; margin: 0 auto; padding: 0 1.5rem; width: 100%; }

.top { border-top: 4px solid var(--red); border-bottom: 1px solid var(--line); }
.top .wrap { display: flex; align-items: center; justify-content: space-between; min-height: 4.5rem; }
.brand { display: flex; flex-direction: column; text-decoration: none; color: var(--text); }
.brand strong { font-size: 1.25rem; letter-spacing: .01em; }
.brand span { font-size: .8125rem; color: var(--muted); }
.refresh {
  display: inline-flex; align-items: center; gap: .5rem; padding: .5rem 1rem;
  border: 1px solid var(--blue); border-radius: 3px; color: var(--blue);
  font-weight: 600; font-size: .875rem; text-decoration: none; background: #fff;
}
.refresh:hover { background: var(--blue); color: #fff; }
.refresh .icon { font-size: 1.125rem; line-height: 1; }

.crumbs { font-size: .8125rem; color: var(--muted); padding: 1rem 0 0; }
.crumbs a { color: var(--muted); }
main { flex: 1; padding-bottom: 3rem; }
h1 { font-size: 2rem; line-height: 1.25; margin: 1.5rem 0 .5rem; }
.lead { font-size: 1.0625rem; margin: 0 0 2rem; max-width: 44rem; }
h2 { font-size: 1.375rem; margin: 2.5rem 0 1rem; }

.drop {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: .75rem;
  min-height: 11rem; padding: 2rem; text-align: center; cursor: pointer;
  background: var(--bg-soft); border: 2px dashed var(--line); border-radius: 3px;
}
.drop:hover { border-color: var(--blue); }
.drop:focus-within { outline: 3px solid var(--focus); outline-offset: 2px; border-color: var(--blue); }
.drop input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.btn {
  display: inline-block; padding: .75rem 1.75rem; border-radius: 3px;
  background: var(--blue); color: #fff; font-weight: 600; font-size: 1rem;
}
.drop:hover .btn { background: var(--blue-hover); }
.hint { font-size: .875rem; color: var(--muted); }
.modes { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-top: 1rem; }
.mode {
  display: flex; flex-direction: column; align-items: flex-start; gap: .25rem; padding: 1rem 1.25rem;
  border: 2px solid var(--blue); border-radius: 3px; background: #fff; color: var(--blue);
  font-family: inherit; font-size: 1rem; font-weight: 600; line-height: 1.3; text-align: left; cursor: pointer;
}
.mode:hover { background: var(--blue); color: #fff; }
.mode small { font-weight: 400; font-size: .8125rem; opacity: .85; }
@media (max-width: 40rem) { .modes { grid-template-columns: 1fr; } }

.output { border: 1px solid var(--line); border-radius: 3px; min-height: 16rem; }
.output .empty {
  display: flex; align-items: center; justify-content: center; min-height: 16rem;
  margin: 0; color: var(--muted);
}
.result + .result { border-top: 1px solid var(--line); }
.result h3 {
  margin: 0; padding: .75rem 1.25rem; font-size: 1rem; background: var(--bg-soft);
  border-left: 4px solid var(--blue);
}
.result pre {
  margin: 0; padding: 1.25rem; overflow: auto; white-space: pre-wrap; word-break: break-word;
  font: .875rem/1.6 Consolas, "Courier New", monospace;
}

.foot { background: var(--bg-soft); border-top: 1px solid var(--line); font-size: .8125rem; color: var(--muted); }
.foot .wrap { padding-top: 1.25rem; padding-bottom: 1.25rem; }
</style>
</head>
<body>
<header class="top">
<div class="wrap">
<a class="brand" href="/"><strong>Odwołania2json</strong><span>Ekstrakcja danych z odwołań do KIO</span></a>
<a class="refresh" href="/" title="Odśwież stronę"><span class="icon" aria-hidden="true">&#8635;</span>Odśwież stronę</a>
</div>
</header>
<main>
<div class="wrap">
<nav class="crumbs" aria-label="Ścieżka"><a href="/">Strona główna</a> &rsaquo; Ekstrakcja danych</nav>
<h1>Przekształć dokumenty PDF w dane JSON</h1>
<p class="lead">Wgraj odwołanie, pełnomocnictwo albo potwierdzenie przelewu, a potem wybierz sposób przetwarzania. Wynik ma ten sam format JSON w każdym trybie, więc tryby można porównywać.</p>
<form method="post" enctype="multipart/form-data"
  onsubmit="if (event.submitter) event.submitter.querySelector('span').textContent = 'Przetwarzanie…';">
<label class="drop">
<span class="btn">Wybierz plik</span>
<span class="hint" id="drop-hint">Pliki PDF, można wybrać kilka naraz</span>
<input type="file" name="pdf" accept="application/pdf" multiple required
  onchange="document.getElementById('drop-hint').textContent = Array.from(this.files).map(f => f.name).join(', ');">
</label>
<div class="modes">
<button type="submit" name="mode" value="rules" class="mode"><span>1. Skrypt</span><small>reguły, odczyt PyMuPDF</small></button>
<button type="submit" name="mode" value="ai" class="mode"><span>2. AI</span><small>model Bielik (Ollama, config/model.yaml)</small></button>
</div>
</form>
<h2>Wynik</h2>
<section class="output" aria-live="polite">
<!--RESULTS-->
</section>
</div>
</main>
<footer class="foot"><div class="wrap">Odwołania2json · HackNation 2026 · przetwarzanie lokalne, pliki nie są zapisywane</div></footer>
</body>
</html>
"""
_EMPTY = '<p class="empty">Tu pojawi się plik JSON</p>'


def _form(body: bytes, content_type: str) -> tuple[list[tuple[str, bytes]], dict[str, str]]:
    """Pliki i zwykłe pola (np. mode) z formularza multipart."""
    files = _files(body, content_type)
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    message = BytesParser(policy=policy.default).parsebytes(header + body)
    fields = {}
    if message.is_multipart():
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if name and not part.get_filename():
                fields[name] = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
    return files, fields


def _run(mode: str, path: Path, ai: LLMClient) -> tuple[dict, str]:
    """Jeden plik w wybranym trybie; etykieta mówi, co faktycznie zrobiło JSON (AI może być niedostępne)."""
    if mode == "rules":
        document, _trace = process_pdf(path, llm=None)
        return document, "skrypt"
    document, trace = process_pdf(path, llm=ai)
    return document, "AI" if trace.get("method") == "llm" else "skrypt (AI niedostępne)"


def _files(body: bytes, content_type: str) -> list[tuple[str, bytes]]:
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    message = BytesParser(policy=policy.default).parsebytes(header + body)
    found = []
    if not message.is_multipart():
        return found
    for part in message.iter_parts():
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if filename and payload:
            found.append((Path(filename).name, payload))
    return found


def _html(blocks: list[tuple[str, dict]]) -> bytes:
    parts = []
    for name, document in blocks:
        rendered = json.dumps(document, ensure_ascii=False, indent=2)
        parts.append(f'<article class="result"><h3>{escape(name)}</h3><pre>{escape(rendered)}</pre></article>')
    page = _PAGE.replace("<!--RESULTS-->", "\n".join(parts) or _EMPTY)
    if blocks:
        # Zamienia wpis POST w historii na GET: odświeżenie pokazuje pusty formularz zamiast ponownego wysłania pliku.
        page = page.replace("</body>", "<script>history.replaceState(null, '', location.href);</script>\n</body>")
    return page.encode("utf-8")


def serve() -> None:
    load_env()
    import os

    port = int(os.environ.get("PORT", "8000"))
    # Przyciski AI zawsze w trybie llm, niezależnie od `extraction` w config/model.yaml.
    ai = LLMClient({**load_model(), "extraction": "llm"})

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _html([])
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            uploads, fields = _form(self.rfile.read(length), self.headers.get("Content-Type", ""))
            mode = fields.get("mode", "rules")
            blocks = []
            with TemporaryDirectory() as folder:
                for name, payload in uploads:
                    path = Path(folder) / name
                    path.write_bytes(payload)
                    started = time.perf_counter()
                    document, label = _run(mode, path, ai)
                    blocks.append((f"{name} · {label} · {time.perf_counter() - started:.1f} s", document))
            body = _html(blocks)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            print(f"[ui] {self.address_string()} {fmt % args}")

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
