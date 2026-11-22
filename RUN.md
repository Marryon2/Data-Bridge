# RUN

Komenda:

```bash
cd /opt/solution && sudo docker compose run --rm -T odwolania2json
```

Układ katalogów: kod w `/opt/solution`, dane w `/opt/input` i `/opt/output`.

- Przetwarza wszystkie pliki PDF z `/opt/input/`, także w podkatalogach (`/opt/input/case1/odwolanie_nr_1.pdf`).
- Wynik zapisuje do `/opt/output/` pod tą samą ścieżką i nazwą: `/opt/output/case1/odwolanie_nr_1.json`.
- Dokument, który nie jest odwołaniem, pełnomocnictwem ani potwierdzeniem przelewu, dostaje pusty JSON `{}`.
- Nie zadaje pytań i kończy się sama po ostatnim pliku. Postęp wypisuje po jednej linii na plik.
- Ślad ekstrakcji każdego pola (cytat, strona, metoda) trafia do `/opt/solution/trace/`.

## Z czego korzysta

| Usługa | Gdzie | Klucz |
|---|---|---|
| Obraz Dockera `odwolania2json:latest` (Python 3.13, zależności z `requirements.txt`) | zbudowany wcześniej na tym serwerze | – |
| OCR skanów: Tesseract z językiem polskim | lokalnie, w obrazie | – |
| LLM: Bielik 7B (`speakleash/bielik-minitron-7b-v3.0-instruct`, otwarty model) na **RunPod Serverless** (vLLM, API zgodne z OpenAI) | `https://api.runpod.ai/v2/<RUNPOD_ENDPOINT_ID>/openai/v1/chat/completions` (`config/model.yaml`) | `RUNPOD_API_KEY` w `/opt/solution/.env` |

Klucz API i ID endpointu są w `/opt/solution/.env` (wzór: `.env.example`), nie w kodzie ani w repozytorium:

```
RUNPOD_API_KEY=rpa_...
RUNPOD_ENDPOINT_ID=...
```

Docker przekazuje je do kontenera przez `env_file` w `docker-compose.yml`. Pierwsze zapytanie po dłuższej przerwie może czekać na start maszyny RunPod (tzw. cold start); limit czasu to 300 s na zapytanie.

Gdy serwer LLM nie odpowiada, przetwarzanie i tak się kończy: dane wyciągają wtedy reguły z `config/classes/*.yaml`.
