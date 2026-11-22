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

1. Włóż PDF-y do `input/` obok katalogu projektu (`/opt/input/` przy projekcie w `/opt/solution`), np. `input/case1/odwolanie_nr_1.pdf`. Przetwarzany jest każdy PDF z `input/`, na dowolnej głębokości.
2. Uruchom `python -m app` (albo `start.bat`).
3. Wyniki trafiają pod tę samą ścieżkę co plik wejściowy:
   - `output/case1/odwolanie_nr_1.json` (też obok projektu): JSON dokumentu,
   - `trace/case1/odwolanie_nr_1.json`: ślad (cytat, strona, metoda, pewność każdego pola).

### Formularz w przeglądarce

```bat
.venv\Scripts\python.exe -m app --serve
```

Otwórz <http://localhost:8000> (port zmienisz w `.env` zmienną `PORT`). **Wgraj pliki do input** zapisuje PDF-y w `input/`, **Start** przetwarza wszystko z `input/`, a gdy wszystkie JSON-y są już w `output/`, pokazuje je w polu Output i usuwa przetworzone PDF-y z `input/`. Tekst czyta PyMuPDF (skany: Tesseract OCR), dane wyciąga model z `config/model.yaml`. Gdy serwer AI nie odpowiada, wynik pochodzi z reguł, a etykieta mówi „skrypt (AI niedostępne)”.

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

Obraz z Pythonem 3.13 i `tesseract-ocr-pol`. Montowane z hosta: `../input` i `../output` (obok projektu) oraz `trace/`.

```bash
docker compose build                                                    # raz, przy wdrożeniu
docker compose run --rm -T odwolania2json                               # CLI: input/ -> output/
docker compose run --service-ports odwolania2json python -m app --serve  # formularz WWW
```

## Wdrożenie na serwer oceny (`/opt`)

Oceniający uruchamiają komendę z `/opt/RUN.md`. Układ na serwerze:

```
/opt/
├── RUN.md       ← kopia RUN.md z repozytorium
├── input/       ← dokumenty od oceniających
├── output/      ← wyniki
└── solution/    ← to repozytorium
```

```bash
cd /opt/solution               # katalog już istnieje, dlatego git init zamiast git clone
git init -q
git remote add origin https://github.com/Marryon2/Data-Bridge.git
git fetch -q origin main
git checkout -f -B main origin/main
sudo cp RUN.md /opt/RUN.md
sudo mkdir -p /opt/input /opt/output
sudo cp .env.example .env          # opcjonalnie: klucze API
sudo docker compose build          # obraz z Pythonem 3.13 i Tesseractem; w czasie oceny nic się nie pobiera
```

Test dokładnie tak, jak zrobią to oceniający (także po `sudo reboot`):

```bash
sudo rm -rf /opt/output/* && sudo mkdir -p /opt/input/case1 && sudo cp <przykładowe PDF-y> /opt/input/case1/
cd /opt/solution && sudo docker compose run --rm -T odwolania2json
ls -R /opt/output/
```

Komenda nie korzysta z usługi działającej w tle: kontener startuje z komendą i kończy się po ostatnim pliku.

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

## Licencja

[LICENSE](LICENSE)
