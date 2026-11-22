from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# Jedyna reprezentacja nierozpoznanego dokumentu. Zmiana formatu pustego wyniku: tu.
EMPTY_DOCUMENT: dict = {}


def load_env() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def data_dir() -> Path | None:
    load_env()
    raw = os.environ.get("DATA_DIR", "").strip()
    return Path(raw) if raw else None


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=1)
def load_classes() -> tuple[dict, ...]:
    folder = ROOT / "config" / "classes"
    return tuple(_read_yaml(path) for path in sorted(folder.glob("*.yaml")))


@lru_cache(maxsize=1)
def load_model() -> dict:
    return _read_yaml(ROOT / "config" / "model.yaml")


@lru_cache(maxsize=1)
def load_tables() -> dict:
    tables = {}
    for path in (ROOT / "config").glob("*.yaml"):
        if path.name == "model.yaml":
            continue
        tables[path.stem] = _read_yaml(path)
    return tables
