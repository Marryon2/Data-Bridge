# Konfiguracja ekstrakcji klasy

Jedna klasa to jeden plik `config/classes/<klasa>.yaml`. Silnik nie zawiera nazw `odwolanie`, `pelnomocnictwo` ani `przelew`, więc nowa klasa nie wymaga zmian w kodzie: silnik wczytuje każdy plik z `config/classes/` przy starcie, a klasa pojawia się w klasyfikacji, w zapisie JSON i w prompcie modelu.

## Nowa klasa w 4 krokach

1. Dodaj `config/classes/<nazwa>.yaml`.
2. Ustal `positive`, `negative`, `threshold` i `schema` z nullami.
3. Dla każdego liścia podaj `description` (trafia do promptu modelu), a dla trybu reguł także `method`, przy regexie wzorzec i `normalizer`.
4. Jeśli opis jest słownikiem, dołóż plik w `config/` i wskaż go w `table`.

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
    method: regex
    description: Termin uzupełnienia dokumentów (YYYY-MM-DD).
    pattern: '(?i)w\s+terminie\s+do\s+(?P<value>\d{2}\.\d{2}\.\d{4})'
    normalizer: date
```

## Pola pliku klasy

W pliku są:

- `positive` i `negative`: wzorce na pierwszej stronie, waga i próg `threshold`. Waga co najmniej `veto` wyrzuca klasę. Tak odsiewany jest wyrok (`orzeka`, `wyrok`) i ogłoszenie TED.
- `schema`: pełny JSON z nullami. Taki obiekt jest zapisywany, gdy klasa zostanie rozpoznana.
- `description` przy polu: po co jest, zgodnie z komentarzem w oczekiwanym JSON.
- `method`:
  - `regex` — wzorzec z grupą `value`, zakres (`document`, `first_page`, `preamble` albo nazwa z `scopes`) i `normalizer` (`date`, `nip`, `regon`, `krs`, `iban`, `bzp`, `ted`, `amount`, `person`, `email`, `text`). `pattern` może być listą: wzorce są próbowane po kolei, wygrywa pierwszy trafiony. Nowy wariant dokumentu to zwykle jeden dodatkowy wzorzec na liście, bez zmiany kodu.
  - `candidate` — wybór z listy kandydatów po `hints` / `avoid`; suma kontrolna tylko przy remisie
  - `line` — pierwsza linia zakresu, z listą `skip`
  - `span` — tekst od etykiety do etykiety stopu
  - `first_match` — pierwsza fraza z tabeli, tu `config/czynnosci.yaml`
  - `lookup` — opis czynności wyłącznie z id, nie cytat
  - `flag` — 1/0 albo `null`, gdy lista ma jeden element (`if_single`)
- Opcje pola:
  - `normalizer: entity` — nazwa podmiotu bez adresu („X sp. z o.o., ul. …” → „X sp. z o.o.”), do pól `nazwa`.
  - `join_next` (metoda `line`) — regex; gdy następna linia mu pasuje, jest doklejana („sp. z” / „o.o.”).
  - `nominative: true` — imię i nazwisko sprowadzone do formy z podpisu („Hannę Kowalską” → „Hanna Kowalska”).
  - `only_if_empty: true` — zapasowa reguła dla tej samej ścieżki; działa tylko, gdy wcześniejsza nic nie znalazła. Ta sama ścieżka bez tej opcji nadpisuje wynik (np. jawna etykieta formularza wygrywa z opisem w zdaniu).
  - `first_match` wybiera frazę wymienioną najwcześniej w tekście; kolejność w tabeli rozstrzyga tylko remis pozycji.
- `scopes` — nazwane fragmenty tekstu: `start` (regex albo lista regexów próbowanych po kolei) i `end` (regex), `max_chars`, `before_chars` (ile znaków przed etykietą `start` dołączyć, np. data stojąca przed „polegającej na”) oraz `fallback_before` / `fallback_chars`, gdy `start` nie występuje.
- `lists` — powtarzalny blok. `clusters` grupuje podmioty wokół NIP (także zapisanego z myślnikami). `persons` wyjmuje imiona spod tytułu zawodowego i PESEL jako napis:
  - `patterns` to lista `{pattern, case}`. `{osoba}` w wzorcu oznacza „Imię Nazwisko” z wielkich liter.
  - `case: dative` („radcy prawnemu Annie Wiśniewskiej”) albo `case: accusative` („Pana Tomasza Nowickiego”) sprowadza nazwisko do mianownika. Najpierw szukana jest forma z podpisu w dokumencie, potem działają reguły końcówek.
- `or_filled` (metoda `flag`) — ścieżka pola; gdy zostało znalezione, flaga ma wartość `when_match`. Przykład: `przez-pelnomocnika` = 1, gdy pełnomocnik stoi w bocznej kolumnie poza blokiem Odwołującego.
- `prefer_after` (metoda `line`) — linia z numerem („1) X sp. z o.o. (Lider Konsorcjum)”) sama jest nazwą. Sama etykieta („1) Lider Konsorcjum:”) wskazuje linię pod nią.
- Tekst z PDF jest normalizowany przy ekstrakcji: twarda spacja → spacja, myślniki Unicode i miękki dywiz → „-”, miękki dywiz na końcu linii skleja przeniesiony wyraz, U+037E → „;”. Wzorce w YAML nie muszą tego obsługiwać.
- Kandydaty `candidate` są oceniane po etykietach przed wartością. Etykieta w tej samej lub poprzedniej linii waży więcej, więc „Data operacji: …” wygrywa z „Wydruk z dnia: …” wyżej na stronie.

`OdwolanieKIO.data` i `miejscowosc` mają wzorzec linii nagłówka. Data z zarzutu („w dniu 20 marca 2026”) nie wpada do tych pól. W 15 z 60 przykładów oba są null i tak ma zostać.

Identyfikatory (NIP, REGON, KRS, IBAN, data, kwota, BZP, TED, e-mail) są regexem. W trybie AI te same pola wypełnia model, a `description` z YAML trafia do jego promptu.

## Nowy szablon dokumentu

1. Zapisz tekst dokumentu jako `tests/fixtures/<nazwa>.txt` (strony rozdzielone znakiem `\f`) i oczekiwany wynik jako `tests/fixtures/<nazwa>.json`.
2. `python -m pytest tests/test_fixtures.py` pokaże pola, które się nie zgadzają.
3. Popraw wzorce w YAML, nie w kodzie. Potem uruchom `python -m app.score --data <repo organizatora>`, żeby sprawdzić, że zbiór treningowy i negatywy się nie pogorszyły.
