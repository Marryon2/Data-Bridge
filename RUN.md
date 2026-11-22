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
| LLM: Bielik 7.5B (`SpeakLeash/bielik-minitron-7B-v3.0-instruct:Q4_K_M`, otwarty model) przez API Ollama | adres `endpoint` w `config/model.yaml` | brak, serwer nie wymaga klucza |

Klucze API, jeśli model zostanie przełączony na usługę z kluczem, są w `/opt/solution/.env` (wzór: `.env.example`). Nazwę zmiennej z kluczem wskazuje `api_key_env` w `config/model.yaml`. Plik `.env` nie jest w repozytorium.

Gdy serwer LLM nie odpowiada, przetwarzanie i tak się kończy: dane wyciągają wtedy reguły z `config/classes/*.yaml`.
