# Architektura

Jedna ścieżka dla CLI, `start.bat`, Dockera i formularza HTTP. Każdy PDF jest osobnym dokumentem. Sprawy się nie scala.

1. **Tekst.** `app/extract.py` czyta warstwę PyMuPDF. `pdftotext` psuje polskie znaki na tym zbiorze (Tj hex w przykładach 1–39, tablice TJ w 40–60). PyMuPDF obsługuje obie. OCR (`tesseract -l pol`) włącza się tylko wtedy, gdy w warstwie jest za mało liter. Brak Tesseracta nie przerywa ścieżki tekstowej: program pisze o tym na stdout i jedzie dalej.
2. **Kandydaci.** `app/candidates.py` zbiera NIP, REGON, KRS, PESEL, IBAN, daty, kwoty, BZP, TED, e-mail i numer transakcji razem z oknem kontekstu. Suma kontrolna NIP, REGON i IBAN rozstrzyga tylko remis. Wartość syntetyczna, na przykład `9999284065`, zostaje.
3. **Klasa.** `app/classify.py` punktuje pierwszą stronę regułami z `config/classes/*.yaml`. Słowa negatywne (`orzeka`, `wyrok`, `sygn. akt`, Official Journal, ogłoszenie TED) są obowiązkowe, bo wyrok KIO i ogłoszenie też zawierają słowo „odwołanie”. Poniżej progu wynikiem jest `{}`. Szara strefa może zawołać LLM, jeśli jest klucz.
4. **Ekstrakcja.** `app/engine.py` nie zna nazw trzech klas. Czyta listę pól, zakresy, listy i normalizatory. `czynnosc_opis` jest wyłącznie słownikiem id 1–12 z `config/czynnosci.yaml`, łącznie z id 12, którego nie ma w treningu. Data i miejscowość odwołania biorą się tylko z linii nagłówka (`X, dnia …` albo `X DD.MM.RRRR`), nie z daty w treści zarzutu.
5. **Semantyka.** Pole `method: semantic` dostaje model z `config/model.yaml`. Do promptu idą kandydaci oraz wycinek: nagłówek i pierwszy zarzut, najwyżej trzy pierwsze strony. Model nie może wstawić identyfikatora spoza listy kandydatów. Bez klucza te pola zostają `null`. Wynik modelu nie jest zmyślany.
6. **Zapis.** JSON klasy (ze nullami) albo `{}` trafia do `output/<sprawa>/<stem>.json`. Cytat, strona, metoda (`regex` / `llm` / `lookup`) i pewność trafiają do `trace/`.

Normalizacja (`app/normalize.py`): data ISO, TED `NNNNNN-YYYY`, BZP bez spacji, kwota jako liczba, IBAN 26 cyfr bez PL, tytuły zawodowe `r. pr.` i `adw.` schodzą z imienia i nazwiska.
