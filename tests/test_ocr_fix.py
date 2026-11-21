from app.ocr_fix import fix_emails, fix_numbers, vote_document, vote_value


def test_email_at_sign_misread():
    assert fix_emails("e-mail: jan.nowakGnowak-legal.example") == "e-mail: jan.nowak@nowak-legal.example"
    assert fix_emails("biuroQfirma.pl, tel.") == "biuro@firma.pl, tel."
    assert fix_emails("kontakt(a)urzad.gov.pl") == "kontakt@urzad.gov.pl"


def test_email_untouched_when_valid_or_not_an_address():
    assert fix_emails("Grzegorz.Nowak@firma.pl") == "Grzegorz.Nowak@firma.pl"
    assert fix_emails("www.nowak-legal.example") == "www.nowak-legal.example"
    assert fix_emails("Gdańsk i Gdynia") == "Gdańsk i Gdynia"


def test_numbers_letters_to_digits_after_label():
    assert fix_numbers("NIP: 1Z3-456-78-9O, REGON") == "NIP: 123-456-78-90, REGON"
    assert fix_numbers("REGON: 12345678S") == "REGON: 123456785"
    assert fix_numbers("KRS: OOOO123456 sp. k.") == "KRS: 0000123456 sp. k."


def test_numbers_left_alone_when_length_wrong_or_no_label():
    assert fix_numbers("NIP: 12345") == "NIP: 12345"
    assert fix_numbers("2026/BZP 00123456/01") == "2026/BZP 00123456/01"
    assert fix_numbers("KRS: 1234567890") == "KRS: 1234567890"


def test_iban_with_few_misread_letters():
    assert fix_numbers("nr 12 1O2O 3456 7890 1234 5678 9O12 ok") == "nr 12 1020 3456 7890 1234 5678 9012 ok"


def test_vote_majority_and_confidence_tiebreak():
    words = "Firma Krzak Budowa sp. k. pisze , a Krzak Budowa sp. k. oraz Krzał Budowa sp. k.".split()
    assert vote_value("Krzał Budowa sp. k.", words, {}) == "Krzak Budowa sp. k."
    tie = "Lipa Sport sp. j. oraz Lipą Sport sp. j.".split()
    conf = {"Lipa": 95.0, "Lipą": 40.0}
    assert vote_value("Lipą Sport sp. j.", tie, conf) == "Lipa Sport sp. j."
    assert vote_value("Lipa Sport sp. j.", tie, conf) == "Lipa Sport sp. j."


def test_vote_skips_numbers_emails_and_values_absent_from_text():
    words = "NIP 1234567890 NIP 1234567899 Jan Kowalski".split()
    assert vote_value("1234567890", words, {}) == "1234567890"
    assert vote_value("Jan Kowalska", words, {}) == "Jan Kowalska"
    assert vote_document({"a": [{"b": None, "c": 1}]}, words, {}) == {"a": [{"b": None, "c": 1}]}
