import json

import app.__main__ as cli


def test_cli_processes_every_pdf_in_input_and_mirrors_paths(tmp_path, monkeypatch):
    for name in ["case1/odwolanie.pdf", "case1/sub/przelew.PDF", "luzem.pdf", "case1/notatka.txt"]:
        (tmp_path / "input" / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "input" / name).write_bytes(b"%PDF")
    monkeypatch.setattr(cli, "ROOT", tmp_path / "solution")  # input/ i output/ obok katalogu projektu
    monkeypatch.setattr(cli, "process_pdf", lambda pdf, llm=None: ({"plik": pdf.name}, {"class": None}))
    monkeypatch.setattr("sys.argv", ["app"])

    assert cli.main() == 0

    written = sorted(p.relative_to(tmp_path / "output").as_posix() for p in (tmp_path / "output").rglob("*.json"))
    assert written == ["case1/odwolanie.json", "case1/sub/przelew.json", "luzem.json"]
    assert json.loads((tmp_path / "output/case1/sub/przelew.json").read_text(encoding="utf-8")) == {"plik": "przelew.PDF"}
