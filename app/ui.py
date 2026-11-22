"""Cienki formularz: ten sam pipeline co CLI, podgląd JSON."""

from __future__ import annotations

import json
import sys
import threading
import time
import webbrowser
from email import policy
from email.parser import BytesParser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.config import ROOT, load_env, load_model
from app.engine import process_input
from app.llm import LLMClient

INPUT, OUTPUT = ROOT / "input", ROOT / "output"

_PAGE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Odwołania2json</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap">
<style>
/* Wartości przepisane z arkuszy gov.pl (main.css, govpl_template.css), bez godła, logotypów i nazwy serwisu. */
* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  font-family: "Open Sans", sans-serif; font-size: 1rem; line-height: 1.5; color: #1b1b1b; background: #fff;
  -webkit-font-smoothing: antialiased; display: flex; flex-direction: column; min-height: 100vh;
}
a { color: #0052a5; text-decoration: none; }
a:hover { color: #006cd7; text-decoration: underline; }
:focus-visible { outline: none; box-shadow: 0 0 0 2px #0452a8, 0 0 0 4px #fff, 0 0 0 6px #0452a8; }
h1, h2, h3 { font-weight: bold; line-height: 1.3; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* Jedna wyśrodkowana kolumna (szerokość kolumny treści gov.pl: 66% z 73em) dla okruszków, treści i stopki.
   width jest potrzebne, bo body to flex-kolumna: bez niego kontenery kurczą się do treści i rozjeżdżają. */
.main-container { display: block; width: calc(100% - 2.2em); max-width: 48em; margin: 14px auto 28px; }

.govpl { display: flex; align-items: center; background: #fff; border-bottom: .125rem solid #f1f1f1; }
.govpl__header { flex: 1; display: flex; align-items: center; }
.govpl__logotype {
  color: #1b1b1b; text-decoration: none; font-size: 1.18125rem; font-weight: bold;
  margin: .875rem 1rem .625rem .5rem; padding-top: .25rem;
}
.govpl__logotype:hover { color: #1b1b1b; text-decoration: underline; }
.govpl__portal-name { display: none; align-items: center; font-size: .875rem; align-self: stretch; }
.govpl__portal-name::before { content: ""; flex: 0 0 2px; height: 63%; background: #d5233f; margin-right: 1.8125rem; }
@media (min-width: 43.75rem) {
  .govpl__logotype { font-size: 1.71875rem; margin: .8125rem 1.8125rem .8125rem 2rem; padding-top: .5rem; }
  .govpl__portal-name { display: flex; }
}
.govpl__panel-login { margin: .625rem .75rem; align-self: center; padding-left: .9em; padding-right: .9em; text-transform: none; font-weight: 600; }

.breadcrumbs ul { display: flex; flex-wrap: wrap; list-style: none; margin: 0; padding: 0; font-size: .875em; }
.breadcrumbs li + li::before { content: "\\203A"; color: #0052a5; margin: 0 .5em; font-weight: bold; }
.breadcrumbs li:last-child { color: #1b1b1b; }

main { flex: 1; }
.service-card > h1 { font-size: 2em; margin: .5em 0 .75em; }
.service-card h2 { font-size: 1.5em; margin: 1.5em 0 .5em; }
.service-card p { margin: 1.5em 0; }

.btn {
  display: inline-block; font: bold 1rem/1.5 "Open Sans", sans-serif; color: #fff; text-align: center; vertical-align: middle;
  user-select: none; background: #0052a5; border: .125rem solid #0052a5; border-radius: .25rem;
  padding: .4375rem 1.75rem; text-transform: uppercase; text-decoration: none; cursor: pointer;
}
.btn:hover { color: #fff; text-decoration: none; background: #006cd7; border-color: #006cd7; }
.btn:disabled { background: #656565; border-color: #656565; cursor: progress; }
.btn.btn-secondary { color: #0052a5; border-color: #0052a5; background: #fff; }
.btn.btn-secondary:hover { color: #006cd7; border-color: #006cd7; background: #fff; }
.service-card .btn { width: 100%; }
.upload { position: relative; display: block; }
.upload input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.upload:focus-within .btn { box-shadow: 0 0 0 2px #0452a8, 0 0 0 4px #fff, 0 0 0 6px #0452a8; }
.status { font-size: .875em; color: #656565; margin: .75em 0 1.5em; }
.start { margin: 0; }

.warn { margin: 1.5em 0; padding: 1em 1.25em; border-left: .25rem solid #d5233f; background: #f1f1f1; }
.alert { margin: 1em 0 0; padding: 1em 1.25em; border: .125rem solid #d5233f; border-left-width: .5rem; background: #fdecee; }

.accordion { list-style: none; padding: 0; margin: 1.56256em 0 0; }
.accordion > li { border-top: 1px solid #f1f1f1; padding: .93756em 0; }
.accordion > li:last-child { border-bottom: 1px solid #f1f1f1; }
.accordion summary {
  list-style: none; cursor: pointer; display: flex; align-items: center; font-size: 1.25em; font-weight: 700;
  line-height: 1.875em; padding: .93756em .12506em; color: #0052a5;
}
.accordion summary::-webkit-details-marker { display: none; }
.accordion summary:hover { color: #006cd7; }
.accordion summary::after { content: "\\2304"; margin-left: auto; font-size: 1.3rem; }
.accordion details[open] summary { color: #1b1b1b; }
.accordion details[open] summary::after { content: "\\2303"; }
.accordion pre {
  margin: 0 0 1em; padding: 1em; background: #f1f1f1; overflow: auto; white-space: pre-wrap; word-break: break-word;
  font: .875rem/1.6 Consolas, "Courier New", monospace;
}
.empty { color: #656565; margin: 1.5em 0; }

.footer { border-top: solid #d5233f .1875rem; font-size: .875em; }
.footer .main-container { padding-top: 1.6em; padding-bottom: 2.50006em; }

/* Ułatwienia dostępu: skala to font-size na <html> (cała strona jest w rem/em), kontrast to klasa na <html>.
   Kontrast wg gov.pl/web/dostepnosc-cyfrowa/kontrast-kolorow (WCAG AA): tekst >= 4,5:1, duży tekst i ramki/przyciski >= 3:1.
   Najsłabsze pary w trybie zwykłym: #006cd7/#fff 5,09:1, #767676/#fff 4,54:1 (ramki A/Kontrast); tryb kontrastu >= 19,5:1. */
.govpl { flex-wrap: wrap; }
.a11y { display: flex; gap: .25rem; align-items: center; margin: .625rem 0 .625rem .75rem; }
.a11y button {
  font: bold .875rem/1 "Open Sans", sans-serif; color: #0052a5; background: #fff; cursor: pointer;
  border: .0625rem solid #767676; border-radius: .25rem; padding: .4375rem .625rem; min-width: 2.75rem; min-height: 2.75rem;
}
.a11y button:hover { border-color: #006cd7; color: #006cd7; }
.a11y button[aria-pressed="true"] { background: #0052a5; border-color: #0052a5; color: #fff; }

html.contrast body, html.contrast .govpl, html.contrast .a11y button, html.contrast .btn.btn-secondary { background: #000; color: #fff; }
html.contrast a, html.contrast a:hover, html.contrast .accordion summary, html.contrast .accordion summary:hover,
html.contrast .breadcrumbs li + li::before, html.contrast .a11y button, html.contrast .btn.btn-secondary { color: #ff0; }
html.contrast .accordion details[open] summary, html.contrast .breadcrumbs li:last-child, html.contrast .govpl__logotype,
html.contrast .status, html.contrast .empty { color: #fff; }
html.contrast .btn, html.contrast .a11y button[aria-pressed="true"] { background: #ff0; border-color: #ff0; color: #000; }
html.contrast .btn.btn-secondary, html.contrast .a11y button { border-color: #ff0; }
html.contrast .btn:hover { background: #000; color: #ff0; }
html.contrast .btn:disabled { background: #fff; border-color: #fff; color: #000; }
html.contrast .warn, html.contrast .accordion pre { background: #000; color: #fff; border: .0625rem solid #fff; }
html.contrast .warn { border-left: .25rem solid #ff0; }
html.contrast .alert { background: #000; color: #fff; border-color: #ff0; }
html.contrast .govpl, html.contrast .accordion > li { border-color: #fff; }
html.contrast .govpl__portal-name::before { background-color: #ff0; }
html.contrast .footer { background: #000; border-top-color: #ff0; }
html.contrast :focus-visible { box-shadow: 0 0 0 2px #000, 0 0 0 5px #ff0; }
</style>
<script>
(function () {  /* przed rysowaniem strony: bez mignięcia domyślnego wyglądu */
  var d = document.documentElement;
  if (localStorage.getItem("contrast") === "1") d.classList.add("contrast");
  d.style.fontSize = (localStorage.getItem("scale") || "100") + "%";
})();
function a11yMark() {
  var d = document.documentElement, scale = localStorage.getItem("scale") || "100";
  document.querySelectorAll("[data-scale]").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.scale === scale); });
  document.getElementById("contrast").setAttribute("aria-pressed", d.classList.contains("contrast"));
}
function setScale(value) {
  document.documentElement.style.fontSize = value + "%"; localStorage.setItem("scale", value); a11yMark();
}
function toggleContrast() {
  localStorage.setItem("contrast", document.documentElement.classList.toggle("contrast") ? "1" : "0"); a11yMark();
}
</script>
</head>
<body>
<header class="govpl">
<div class="govpl__header">
<a class="govpl__logotype" href="/">Odwołania2json</a>
<span class="govpl__portal-name">Ekstrakcja danych z odwołań do KIO</span>
</div>
<div class="a11y" role="group" aria-label="Ułatwienia dostępu">
<button type="button" data-scale="100" onclick="setScale('100')" aria-label="Normalny rozmiar tekstu">A</button>
<button type="button" data-scale="125" onclick="setScale('125')" aria-label="Większy tekst">A+</button>
<button type="button" data-scale="150" onclick="setScale('150')" aria-label="Największy tekst">A++</button>
<button type="button" id="contrast" onclick="toggleContrast()" aria-label="Wysoki kontrast">Kontrast</button>
</div>
<a class="govpl__panel-login btn btn-secondary" href="/">Odśwież stronę</a>
</header>
<nav class="breadcrumbs main-container" aria-label="Ścieżka okruszków">
<ul><li><a href="/">Strona główna</a></li><li>Ekstrakcja danych</li></ul>
</nav>
<main class="main-container" id="main-content">
<div class="service-card">
<h1>Przekształć dokumenty PDF w dane JSON</h1>
<p>Wgraj pliki PDF do folderu <code>input</code>, a potem kliknij <strong>Start</strong>. Każde wgranie trafia do osobnego folderu (<code>input/case1</code>, <code>input/case2</code>, …), a wyniki do folderu o tej samej nazwie w <code>output</code>. Start przetwarza tylko pliki, które nie mają jeszcze wyniku. Gdy wszystkie pliki JSON zostaną zapisane, pojawią się poniżej. Pliki PDF zostają w folderze <code>input</code>.</p>
<form method="post" action="/upload" enctype="multipart/form-data">
<label class="upload">
<span class="btn btn-secondary">Wgraj pliki do input</span>
<input type="file" name="pdf" accept="application/pdf,.pdf" multiple required onchange="this.form.submit()">
</label>
<noscript><button type="submit" class="btn">Wyślij</button></noscript>
</form>
<p class="status" aria-live="polite"><!--WAITING--></p>
<form class="start" method="post" action="/start" onsubmit="var b = this.querySelector('button'); b.disabled = true; b.textContent = 'Przetwarzanie…';">
<button type="submit" class="btn">Start</button>
</form>
<!--ALERT-->
<div class="warn" role="note"><strong>Uwaga:</strong> jeżeli program nie będzie w stanie połączyć się z AI, użyje skryptów lokalnych, a precyzja wyników może być niższa.</div>
<h2>Output</h2>
<section aria-live="polite">
<!--RESULTS-->
</section>
</div>
</main>
<footer class="footer"><div class="main-container">Odwołania2json · HackNation 2026 · przetwarzanie lokalne, pliki trafiają do folderów input i output</div></footer>
<script>a11yMark();</script>
</body>
</html>
"""
_EMPTY = '<p class="empty">Tu pojawią się gotowe pliki JSON</p>'


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


def _inputs() -> list[str]:
    return sorted(p.relative_to(INPUT).as_posix() for p in INPUT.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def _waiting() -> list[str]:
    """PDF-y z input/ bez wyniku w output/: tylko je przetwarza Start."""
    return [name for name in _inputs() if not (OUTPUT / name).with_suffix(".json").exists()]


def _next_case() -> Path:
    """Folder na jedno wgranie: input/caseN, N o jeden większe od najwyższego w input/ i output/.

    Liczy też output/: gdy ktoś usunie input/caseN, output/caseN zostaje i nie może zostać nadpisany.
    """
    used = [
        int(p.name[4:])
        for root in (INPUT, OUTPUT) if root.is_dir()
        for p in root.iterdir() if p.is_dir() and p.name.startswith("case") and p.name[4:].isdigit()
    ]
    return INPUT / f"case{max(used, default=0) + 1}"


def _html(blocks: list[tuple[str, dict]], note: str = "", alert: str = "") -> bytes:
    parts = []
    for name, document in blocks:
        rendered = json.dumps(document, ensure_ascii=False, indent=2)
        parts.append(f'<li><details><summary>{escape(name)}</summary><pre>{escape(rendered)}</pre></details></li>')
    waiting = _waiting()
    if note:
        status = note
    elif waiting:
        status = f"Do przetworzenia ({len(waiting)}): " + ", ".join(waiting)
    else:
        status = "Wszystkie pliki z input mają już wyniki w output." if _inputs() else "Folder input jest pusty."
    results = '<ul class="accordion">' + "\n".join(parts) + "</ul>" if parts else _EMPTY
    page = _PAGE.replace("<!--RESULTS-->", results).replace("<!--WAITING-->", escape(status))
    if alert:
        title, _, text = alert.partition(": ")
        page = page.replace("<!--ALERT-->", f'<div class="alert" role="alert"><strong>{escape(title)}:</strong> {escape(text)}</div>')
    if blocks or note or alert:
        # Zamienia wpis POST w historii na GET: odświeżenie nie uruchamia przetwarzania ponownie.
        page = page.replace("</body>", "<script>history.replaceState(null, '', '/');</script>\n</body>")
    return page.encode("utf-8")


def serve() -> None:
    load_env()
    import os

    port = int(os.environ.get("PORT", "8000"))
    # Przyciski AI zawsze w trybie llm, niezależnie od `extraction` w config/model.yaml.
    ai = LLMClient({**load_model(), "extraction": "llm"})
    if not ai.available:
        print("LLM niedostępny (brak klucza lub endpointu w .env / config/model.yaml): działają same reguły.", flush=True)
    busy = threading.Lock()  # jedno przetwarzanie naraz: drugi Start nie może brać tych samych plików
    uploading = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._send(_html([]))

        def _send(self, body: bytes):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if self.path == "/upload":
                # _files zostawia samą nazwę pliku: bez ścieżek spoza input/.
                pdfs = [(n, p) for n, p in _files(body, self.headers.get("Content-Type", "")) if n.lower().endswith(".pdf")]
                if pdfs:
                    with uploading:  # dwa równoległe wgrania nie mogą dostać tego samego caseN
                        case = _next_case()
                        case.mkdir(parents=True)
                    for name, payload in pdfs:
                        (case / name).write_bytes(payload)
                self.send_response(303)  # po wgraniu wraca na stronę z listą plików w input/
                self.send_header("Location", "/")
                self.end_headers()
                return
            if not _waiting():
                alert = (
                    "Brak nowych plików: wszystkie pliki z input mają już wyniki w output. Wgraj nowe pliki przed naciśnięciem Start."
                    if _inputs() else "Brak plików: wgraj przynajmniej jeden plik PDF przed naciśnięciem Start."
                )
                self._send(_html([], alert=alert))
                return
            if busy.locked():
                self._send(_html([], "Przetwarzanie już trwa. Poczekaj na wynik."))
                return
            with busy:
                started = time.perf_counter()
                # PDF-y zostają w input/caseN; przetwarzane są tylko te bez wyniku w output/.
                results = process_input(ai, pending_only=True)
            blocks = [(json_path.name, document) for _, json_path, document in results]
            self._send(_html(blocks, f"Gotowe: {len(results)} plików w {time.perf_counter() - started:.1f} s."))

        def log_message(self, fmt, *args):
            print(f"[ui] {self.address_string()} {fmt % args}")

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Strona działa: http://localhost:{port}  (zamknij to okno, aby zatrzymać)", flush=True)
    if "--open" in sys.argv:  # start.bat: przeglądarka dopiero, gdy serwer już słucha
        webbrowser.open(f"http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    serve()
