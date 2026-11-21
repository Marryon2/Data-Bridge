# Nowa klasa bez zmiany kodu ekstrakcji

1. Dodaj `config/classes/<nazwa>.yaml`.
2. Ustal `positive`, `negative`, `threshold` i `schema` z nullami.
3. Dla każdego liścia podaj `method`, `description`, a przy regexie wzorzec i `normalizer`.
4. Jeśli opis jest słownikiem, dołóż plik w `config/` i wskaż go w `table`.
5. Nie edytuj `app/engine.py`, `app/classify.py` ani `app/candidates.py`, dopóki wystarcza istniejąca metoda (`regex`, `candidate`, `line`, `span`, `flag`, `lookup`, `first_match`, `clusters`, `persons`, `semantic`).

Silnik wczytuje każdy plik z `config/classes/` przy starcie. Nowa klasa pojawia się w klasyfikacji, w zapisie JSON i w prompcie LLM.

Przykład minimalny:

```yaml
name: wezwanie
description: Wezwanie do uzupełnienia dokumentów
threshold: 3
positive:
  - pattern: 'wezwanie do uzupełnienia'
    weight: 4
negative:
  - pattern: '(?<!\w)orzeka'
    weight: 100
veto: 50
schema:
  wezwanie:
    numer: null
    termin: null
fields:
  - path: wezwanie.numer
    method: regex
    description: Numer pisma z nagłówka.
    pattern: '(?i)znak\s*[:.]?\s*(?P<value>[A-Z0-9./-]{4,})'
    normalizer: text
  - path: wezwanie.termin
    method: semantic
    description: Termin uzupełnienia, gdy nie ma stałej etykiety.
```

Pole `semantic` wymaga `MISTRAL_API_KEY`. Bez klucza zostanie `null`, a reszta klasy i tak się zapisze.

Model zmieniasz w `config/model.yaml` (`name`, `endpoint`). Domyślnie najmniejszy Mistral z trybem JSON. Większy tylko po zmierzonym spadku F1 na `python -m app.score`.
