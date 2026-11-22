import threading
import time
import urllib.request

import app.engine as engine
import app.ui as ui


def test_upload_start_keeps_input_and_processes_only_new_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "INPUT", tmp_path / "input")
    monkeypatch.setattr(ui, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr(engine, "ROOT", tmp_path / "solution")  # prawdziwe process_input na tmp_path/input|output
    monkeypatch.setattr(engine, "process_pdf", lambda pdf, llm=None: ({"plik": pdf.name}, {"class": None}))
    monkeypatch.setenv("PORT", "8766")
    threading.Thread(target=ui.serve, daemon=True).start()
    for _ in range(50):
        try:
            urllib.request.urlopen("http://localhost:8766/")
            break
        except OSError:
            time.sleep(0.1)

    start = lambda: urllib.request.urlopen(
        urllib.request.Request("http://localhost:8766/start", b"", method="POST")).read().decode()
    boundary = "b0undary"
    body = "".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="pdf"; filename="{name}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n%PDF\r\n"
        for name in ["a.pdf", "../b.pdf", "notatka.txt"]
    ) + f"--{boundary}--\r\n"
    upload = lambda: urllib.request.urlopen(urllib.request.Request(
        "http://localhost:8766/upload", body.encode(), {"Content-Type": f"multipart/form-data; boundary={boundary}"}))
    tree = lambda root: sorted(p.relative_to(root).as_posix() for p in root.rglob("*.*"))

    empty = start()
    assert 'role="alert"' in empty and "przynajmniej jeden plik" in empty

    upload()
    # Każde wgranie w osobnym input/caseN; bez .txt i bez wyjścia poza input/.
    assert tree(ui.INPUT) == ["case1/a.pdf", "case1/b.pdf"]

    page = start()
    assert "<summary>a.json</summary>" in page and "<summary>b.json</summary>" in page and "Gotowe: 2" in page
    assert tree(ui.INPUT) == ["case1/a.pdf", "case1/b.pdf"]  # PDF-y zostają w input/
    assert tree(ui.OUTPUT) == ["case1/a.json", "case1/b.json"]

    again = start()  # nic nowego: bez ponownego przetwarzania case1
    assert "Brak nowych plików" in again and "<summary>" not in again

    upload()
    page = start()
    assert "Gotowe: 2" in page  # tylko case2
    assert tree(ui.OUTPUT) == ["case1/a.json", "case1/b.json", "case2/a.json", "case2/b.json"]
