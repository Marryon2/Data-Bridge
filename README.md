# Data Bridge

Lokalna aplikacja w Pythonie, która zamienia PDF-y z postępowań przed KIO na JSON. Rodzaj dokumentu rozpoznaje po treści, nie po nazwie pliku.

Obsługiwane klasy: `odwolanie`, `pelnomocnictwo`, `przelew` (potwierdzenie przelewu). Każdy inny dokument daje `{}`, czyli pusty obiekt, a nie pusty plik.

## Wymagania

- Python 3.13 lub nowszy
- opcjonalnie [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) z językiem polskim (`pol`), do skanów bez warstwy tekstowej
- opcjonalnie serwer LLM (domyślnie Ollama z modelem Bielik, patrz [Model](#model))

Bez Tesseracta i LLM aplikacja nadal działa w trybie reguł (regex + słowniki).

## Szybki start (Windows)

```bat
git clone https://github.com/Marryon2/Data-Bridge.git
cd Data-Bridge
copy .env.example .env
start.bat
```

`start.bat` po kolei:

1. Sprawdza Tesseract OCR. Jeśli go nie ma, instaluje go przez `winget` (`UB-Mannheim.TesseractOCR`, potrzebne potwierdzenie administratora). Bez Tesseracta skany PDF bez warstwy tekstowej dają pusty wynik.
2. Jeśli Tesseract nie ma języka polskiego, pobiera `pol.traineddata` do `.tessdata/` w projekcie.
3. Tworzy `.venv`, instaluje `requirements.txt` i uruchamia `python -m app`. Argumenty są przekazywane dalej, np. `start.bat --serve` otwiera formularz WWW.

Na nowym komputerze potrzebne są tylko Python 3.13+ i `winget`, który jest w Windows 10 i 11. Gdy instalacja Tesseracta się nie uda, `start.bat` wypisuje ostrzeżenie i uruchamia aplikację bez OCR.

## Szybki start (Linux / macOS)

```bash
git clone https://github.com/Marryon2/Data-Bridge.git
cd Data-Bridge
cp .env.example .env
sudo apt install tesseract-ocr tesseract-ocr-pol   # macOS: brew install tesseract tesseract-lang
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app
```

## Użycie

### Przetwarzanie wsadowe (CLI)

1. Włóż PDF-y do `input/<nazwa_sprawy>/*.pdf`, np. `input/sprawa_01/odwolanie.pdf`.
2. Uruchom `python -m app` (albo `start.bat`).
3. Wyniki trafiają do:
   - `output/<sprawa>/<nazwa_pliku>.json`: JSON dokumentu,
   - `trace/<sprawa>/<nazwa_pliku>.json`: ślad (cytat, strona, metoda, pewność każdego pola).

### Formularz w przeglądarce

```bat
.venv\Scripts\python.exe -m app --serve
```

Otwórz <http://localhost:8000> (port zmienisz w `.env` zmienną `PORT`), wgraj PDF i wybierz tryb:

| Przycisk | Co robi |
|---|---|
| **1. Skrypt** | odczyt PyMuPDF + reguły, bez AI |
| **2. AI** | odczyt PyMuPDF + model z `config/model.yaml` |

## Konfiguracja

Plik `.env` (wzór w `.env.example`):

| Zmienna | Znaczenie |
|---|---|
| `MISTRAL_API_KEY` | klucz, tylko jeśli używasz Mistral La Plateforme |
| `DATA_DIR` | katalog z danymi treningowymi (`dane/przyklad_XX/*.json`) dla scorera i części testów |
| `PORT` | port formularza WWW, domyślnie `8000` |

### Model

`config/model.yaml` wskazuje serwer LLM. Domyślnie jest to Ollama (natywne API `/api/chat`) z modelem `SpeakLeash/bielik-minitron-7B-v3.0-instruct:Q4_K_M`. Żeby użyć własnego serwera:

```bash
ollama pull SpeakLeash/bielik-minitron-7B-v3.0-instruct:Q4_K_M
```

Potem w `config/model.yaml` ustaw `endpoint: http://localhost:11434/api/chat`.

Mistral La Plateforme: `endpoint: https://api.mistral.ai/v1/chat/completions`, `name: ministral-3b-latest`, `api_key_env: MISTRAL_API_KEY`.

`extraction: llm` oznacza, że klasę i JSON zwraca model, a reguły wchodzą tylko wtedy, gdy serwer nie odpowie. `extraction: rules` oznacza same reguły.

## Docker

Obraz z Pythonem 3.13 i `tesseract-ocr-pol`. Katalogi `input/`, `output/` i `trace/` są montowane z hosta.

```bash
docker compose up --build                                               # CLI
docker compose run --service-ports odwolania2json python -m app --serve  # formularz WWW
```

## Testy i ocena

```bat
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m app.score --data "%DATA_DIR%"
```

Część testów i scorer wymagają danych treningowych w `DATA_DIR`. Bez nich te testy kończą się błędem `FileNotFoundError`.

Scorer liczy F1 na liściach JSON: stringi porównuje dokładnie, liczby `200` i `200.0` traktuje jako równe, `null` musi się równać `null`, a dodatkowy klucz obniża precyzję.

## Dokumentacja

- [Architektura](docs/architektura.md)
- [Konfiguracja klasy dokumentu](docs/konfiguracja-klasy.md)
- [Dodanie nowej klasy](docs/nowa-klasa.md)

## Licencja

[LICENSE](LICENSE)
