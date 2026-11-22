import threading
import time
import urllib.request

import app.ui as ui


def test_upload_start_shows_jsons_and_empties_input(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "INPUT", tmp_path / "input")
    monkeypatch.setattr(ui, "OUTPUT", tmp_path / "output")
    monkeypatch.setenv("PORT", "8766")

    def fake_process_input(llm):
        # Wszystkie JSON-y zapisane, PDF-y jeszcze w input/: usuwanie dzieje się dopiero po powrocie.
        results = []
        for pdf in sorted(ui.INPUT.glob("*.pdf")):
            target = ui.OUTPUT / pdf.with_suffix(".json").name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}", encoding="utf-8")
            results.append((pdf, target, {"plik": pdf.name}))
        assert all(pdf.exists() for pdf, _, _ in results)
        return results

    monkeypatch.setattr(ui, "process_input", fake_process_input)
    threading.Thread(target=ui.serve, daemon=True).start()
    for _ in range(50):
        try:
            urllib.request.urlopen("http://localhost:8766/")
            break
        except OSError:
            time.sleep(0.1)

    boundary = "b0undary"
    body = "".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="pdf"; filename="{name}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n%PDF\r\n"
        for name in ["a.pdf", "../b.pdf", "notatka.txt"]
    ) + f"--{boundary}--\r\n"
    urllib.request.urlopen(urllib.request.Request(
        "http://localhost:8766/upload", body.encode(), {"Content-Type": f"multipart/form-data; boundary={boundary}"}))
    assert sorted(p.name for p in ui.INPUT.iterdir()) == ["a.pdf", "b.pdf"]  # bez .txt i bez wyjścia poza input/

    page = urllib.request.urlopen(urllib.request.Request("http://localhost:8766/start", b"", method="POST")).read().decode()
    assert "a.json" in page and "b.json" in page and "Gotowe: 2" in page
    assert list(ui.INPUT.iterdir()) == []
