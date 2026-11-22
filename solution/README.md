# Data Bridge

Lokalna aplikacja w Pythonie, która zamienia PDF-y z postępowań przed KIO na JSON. Rodzaj dokumentu rozpoznaje po treści, nie po nazwie pliku.

Obsługiwane klasy: `odwolanie`, `pelnomocnictwo`, `przelew` (potwierdzenie przelewu). Każdy inny dokument daje `{}`, czyli pusty obiekt, a nie pusty plik.

## Wymagania

- Python 3.13 lub nowszy
- opcjonalnie [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) z językiem polskim (`pol`), do skanów bez warstwy tekstowej
- opcjonalnie serwer LLM (domyślnie Bielik na RunPod Serverless, patrz [Model](#model))

Bez Tesseracta i LLM aplikacja nadal działa w trybie reguł (regex + słowniki).

## Jak uruchomić program (instrukcja dla każdego)

### Na Windowsie

1. **Zainstaluj Pythona.** Wejdź na [python.org](https://www.python.org/downloads/), pobierz najnowszą wersję i zainstaluj. Podczas instalacji zaznacz pole **„Add python.exe to PATH”**. To ważne.
2. **Pobierz program.** Na stronie projektu na GitHubie (https://github.com/Marryon2/Data-Bridge) kliknij zielony przycisk **„Code”**, potem **„Download ZIP”**. Rozpakuj go w dowolnym miejscu. W środku są foldery `input`, `output`, `solution` i plik `RUN.md`.
3. **Uruchom.** Wejdź do folderu **`solution`** i kliknij dwa razy plik **`start.bat`**.
   - Za pierwszym razem program sam pobierze to, czego potrzebuje. Może to potrwać kilka minut.
   - Jeśli Windows zapyta o zgodę na instalację, kliknij **„Tak”**.
4. Po chwili sama otworzy się przeglądarka ze stroną programu.

### Na Linuksie

1. Otwórz **Terminal** i wpisz to polecenie, żeby zainstalować potrzebne rzeczy:
   ```
   sudo apt install python3 python3-venv tesseract-ocr tesseract-ocr-pol
   ```
2. Pobierz program tak jak na Windowsie (**„Code”** → **„Download ZIP”**) i rozpakuj go.
3. W terminalu wejdź do folderu `solution` w rozpakowanym programie i wpisz po kolei:
   ```
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m app --serve --open
   ```
   Przy kolejnych uruchomieniach wystarczy samo ostatnie polecenie.
4. Przeglądarka otworzy stronę programu. Jeśli się nie otworzy, wpisz w niej adres **localhost:8000**.

### Jak korzystać

1. Kliknij **„Wgraj pliki do input”** i wybierz pliki PDF.
2. Kliknij **„Start”**.
3. Poczekaj. Gotowe wyniki pojawią się na dole strony. Kliknij nazwę pliku, żeby go rozwinąć.

**Pamiętaj:**
- Nie zamykaj czarnego okna (terminala), dopóki korzystasz z programu. Jego zamknięcie wyłącza program.
- Komputer musi mieć internet. Bez połączenia z serwerem AI program dalej działa, ale wyniki są mniej dokładne.

## Szybki start (Windows)

```bat
git clone https://github.com/Marryon2/Data-Bridge.git opt
cd opt\solution
copy .env.example .env
start.bat
```

`start.bat` (dwuklik) po kolei:

1. Sprawdza, czy jest Python. Nie instaluje go: gdy go brak, wypisuje, skąd go pobrać, i kończy.
2. Sprawdza Tesseract OCR. Jeśli go nie ma, instaluje go przez `winget` (`UB-Mannheim.TesseractOCR`, potrzebne potwierdzenie administratora). Bez Tesseracta skany PDF bez warstwy tekstowej dają pusty wynik.
3. Jeśli Tesseract nie ma języka polskiego, pobiera `pol.traineddata` do `.tessdata/` w projekcie.
4. Tworzy `.venv`, instaluje `requirements.txt`, uruchamia stronę WWW i otwiera ją w przeglądarce (<http://localhost:8000>). Zamknięcie okna konsoli zatrzymuje stronę.

`start.bat --cli` zamiast strony przetwarza od razu wszystkie PDF-y z `input/` (folder obok projektu) do `output/`.

Na nowym komputerze potrzebne są tylko Python 3.13+ (z zaznaczonym „Add python.exe to PATH”) i `winget`, który jest w Windows 10 i 11. Gdy instalacja Tesseracta się nie uda, `start.bat` wypisuje ostrzeżenie i uruchamia aplikację bez OCR.

## Szybki start (Linux / macOS)

```bash
git clone https://github.com/Marryon2/Data-Bridge.git opt
cd opt/solution
cp .env.example .env
sudo apt install tesseract-ocr tesseract-ocr-pol   # macOS: brew install tesseract tesseract-lang
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app
```

## Użycie

### Przetwarzanie wsadowe (CLI)

1. Włóż PDF-y do `input/` obok katalogu projektu (`/opt/input/` przy projekcie w `/opt/solution`), np. `input/case1/odwolanie_nr_1.pdf`. Przetwarzany jest każdy PDF z `input/`, na dowolnej głębokości.
2. Uruchom `python -m app` (albo `start.bat --cli`).
3. Wyniki trafiają pod tę samą ścieżkę co plik wejściowy:
   - `output/case1/odwolanie_nr_1.json` (też obok projektu): JSON dokumentu,
   - `trace/case1/odwolanie_nr_1.json`: ślad (cytat, strona, metoda, pewność każdego pola).

### Formularz w przeglądarce

```bat
.venv\Scripts\python.exe -m app --serve
```

Otwórz <http://localhost:8000> (port zmienisz w `.env` zmienną `PORT`). **Wgraj pliki do input** zapisuje PDF-y w nowym folderze `input/caseN` (każde wgranie osobno; N rośnie i nie powtarza folderu, który jest już w `output/`). **Start** przetwarza tylko PDF-y z `input/`, które nie mają jeszcze wyniku, zapisuje je w `output/caseN/<nazwa>.json` i, gdy wszystkie JSON-y są już zapisane, pokazuje je w polu Output. PDF-y zostają w `input/`. (CLI `python -m app` przetwarza zawsze wszystko.) Tekst czyta PyMuPDF (skany: Tesseract OCR), dane wyciąga model z `config/model.yaml`. Gdy serwer AI nie odpowiada, wynik pochodzi z reguł, a etykieta mówi „skrypt (AI niedostępne)”.

## Konfiguracja

Plik `.env` (wzór w `.env.example`):

| Zmienna | Znaczenie |
|---|---|
| `RUNPOD_API_KEY` | klucz RunPod (`rpa_...`) do modelu Bielik |
| `RUNPOD_ENDPOINT_ID` | ID endpointu RunPod Serverless z Bielikiem |
| `MISTRAL_API_KEY` | klucz, tylko jeśli używasz Mistral La Plateforme |
| `DATA_DIR` | katalog z danymi treningowymi (`dane/przyklad_XX/*.json`) dla scorera i części testów |
| `PORT` | port formularza WWW, domyślnie `8000` |

### Model

`config/model.yaml` wskazuje serwer LLM. Domyślnie jest to RunPod Serverless (vLLM, API zgodne z OpenAI) z modelem `speakleash/bielik-minitron-7b-v3.0-instruct`. Adres to `https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/openai/v1/chat/completions`: ID endpointu i klucz program bierze z `.env`. Bez nich działają same reguły.

Zamiast RunPod możesz użyć własnej Ollamy:

```bash
ollama pull SpeakLeash/bielik-minitron-7B-v3.0-instruct:Q4_K_M
```

Potem w `config/model.yaml` ustaw `name: SpeakLeash/bielik-minitron-7B-v3.0-instruct:Q4_K_M`, `endpoint: http://localhost:11434/api/chat` i `api_key_env: ""`.

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
├── RUN.md       ← komenda dla oceniających
├── input/       ← dokumenty od oceniających
├── output/      ← wyniki
└── solution/    ← kod aplikacji
```

```bash
cd /opt                        # repozytorium to cały /opt; katalog już istnieje, dlatego git init zamiast git clone
git init -q
git remote add origin https://github.com/Marryon2/Data-Bridge.git
git fetch -q origin main
git checkout -f -B main origin/main
cd /opt/solution
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

- [Dokumentacja techniczna](docs/dokumentacja-techniczna.md) (w tym model Bielik i przejście na Bielika przez API)
- [Architektura](docs/architektura.md)
- [Konfiguracja klasy dokumentu](docs/konfiguracja-klasy.md)

## Licencja

[LICENSE](LICENSE)
