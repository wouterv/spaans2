from app.checking import check_answer


def test_exact_match_is_correct():
    result = check_answer("casa", "casa")
    assert result.result == "correct"
    assert result.matched == "casa"


def test_case_is_ignored():
    assert check_answer("Casa", "casa").result == "correct"
    assert check_answer("casa", "CASA").result == "correct"


def test_surrounding_and_double_spaces_are_ignored():
    assert check_answer("el coche", "  el  coche ").result == "correct"


def test_wrong_answer():
    result = check_answer("casa", "coche")
    assert result.result == "wrong"
    assert result.correct_answer == "casa"
    assert result.matched is None


def test_empty_answer_is_wrong():
    assert check_answer("casa", "").result == "wrong"
    assert check_answer("casa", "   ").result == "wrong"


def test_any_synonym_counts_as_correct():
    stored = "coche; auto; carro"
    assert check_answer(stored, "auto").result == "correct"
    assert check_answer(stored, "carro").result == "correct"
    assert check_answer(stored, "fiets").result == "wrong"


def test_gender_pair_accepts_each_form_and_the_pair():
    stored = "de neef/de nicht"
    assert check_answer(stored, "de neef").result == "correct"
    assert check_answer(stored, "de nicht").result == "correct"
    assert check_answer(stored, "de neef/de nicht").result == "correct"
    assert check_answer(stored, "de tante").result == "wrong"


def test_gender_pair_spacing_around_slash_is_ignored():
    assert check_answer("el primo/la prima", "el primo / la prima").result == "correct"
    assert check_answer("el primo / la prima", "el primo/la prima").result == "correct"
    assert check_answer("el primo / la prima", "la prima").result == "correct"


def test_gender_pair_combines_with_synonyms():
    stored = "el primo/la prima; el pariente"
    assert check_answer(stored, "la prima").result == "correct"
    assert check_answer(stored, "el primo").result == "correct"
    assert check_answer(stored, "el pariente").result == "correct"
    assert check_answer(stored, "la pariente").result == "wrong"


def test_accent_hint_works_within_gender_pair():
    result = check_answer("el médico/la médica", "la medica")
    assert result.result == "correct_accent"
    assert result.matched == "la médica"


def test_form_asks_one_specific_gender_form():
    stored = "el primo/la prima"
    assert check_answer(stored, "el primo", form=0).result == "correct"
    assert check_answer(stored, "la prima", form=1).result == "correct"
    assert check_answer(stored, "la prima", form=0).result == "wrong"
    assert check_answer(stored, "el primo/la prima", form=0).result == "wrong"


def test_form_correct_answer_shows_only_that_form():
    assert check_answer("el primo/la prima", "x", form=0).correct_answer == "el primo"
    assert check_answer("el primo/la prima", "x", form=1).correct_answer == "la prima"


def test_form_keeps_synonyms_without_slash():
    stored = "el primo/la prima; el pariente"
    assert check_answer(stored, "el pariente", form=1).result == "correct"
    assert check_answer(stored, "x", form=1).correct_answer == "la prima; el pariente"


def test_form_without_pair_in_answer_changes_nothing():
    assert check_answer("rood", "rood", form=1).result == "correct"


def test_form_index_beyond_last_form_takes_last():
    assert check_answer("el primo/la prima", "la prima", form=5).result == "correct"


def test_accent_hint_works_with_form():
    result = check_answer("el médico/la médica", "la medica", form=1)
    assert result.result == "correct_accent"
    assert result.matched == "la médica"


def test_article_may_be_omitted_in_answer():
    assert check_answer("el coche", "coche").result == "correct"
    assert check_answer("het huis", "huis").result == "correct"
    assert check_answer("una manzana", "manzana").result == "correct"


def test_article_may_be_added_in_answer():
    assert check_answer("coche", "el coche").result == "correct"
    assert check_answer("huis", "het huis").result == "correct"


def test_wrong_article_stays_wrong():
    assert check_answer("el coche", "la coche").result == "wrong"
    assert check_answer("de neef", "het neef").result == "wrong"


def test_article_leniency_works_within_synonyms():
    assert check_answer("el coche; el auto", "auto").result == "correct"


def test_article_leniency_combines_with_accents():
    result = check_answer("el árbol", "arbol")
    assert result.result == "correct_accent"
    assert result.matched == "el árbol"


def test_article_alone_is_not_stripped_to_nothing():
    assert check_answer("el", "el").result == "correct"
    assert check_answer("el coche", "el").result == "wrong"


def test_form_question_is_also_lenient_about_articles():
    # Boek-notatie zet het lidwoord vaak alleen op de eerste vorm
    # (de oom/tante); het lidwoord mag dan ook bij een geslachtsvraag
    # aan één kant ontbreken.
    assert check_answer("de oom/tante", "oom", form=0).result == "correct"
    assert check_answer("de oom/tante", "de tante", form=1).result == "correct"
    stored = "de kleinzoon/kleindochter"
    assert check_answer(stored, "de kleindochter", form=1).result == "correct"
    assert check_answer(stored, "kleinzoon", form=0).result == "correct"


def test_form_question_keeps_wrong_word_wrong():
    assert check_answer("de oom/tante", "tante", form=0).result == "wrong"
    assert check_answer("el primo/la prima", "la prima", form=0).result == "wrong"


def test_form_question_requires_article_when_it_is_the_only_difference():
    # Bij el estudiante/la estudiante is het lidwoord het enige
    # geslachtsverschil; dan blijft het verplicht.
    stored = "el estudiante/la estudiante"
    assert check_answer(stored, "estudiante", form=0).result == "wrong"
    assert check_answer(stored, "el estudiante", form=0).result == "correct"


def test_missing_accent_is_correct_with_hint():
    result = check_answer("cómo", "como")
    assert result.result == "correct_accent"
    assert result.matched == "cómo"


def test_accent_hint_works_within_synonyms():
    result = check_answer("adiós; hasta luego", "adios")
    assert result.result == "correct_accent"
    assert result.matched == "adiós"


def test_exact_accented_answer_is_plain_correct():
    assert check_answer("cómo", "cómo").result == "correct"


def test_n_tilde_is_a_distinct_letter():
    # año vs ano zijn verschillende woorden: ñ moet echt getypt worden
    assert check_answer("año", "ano").result == "wrong"
    assert check_answer("año", "año").result == "correct"


def test_dieresis_is_lenient_like_accents():
    assert check_answer("pingüino", "pinguino").result == "correct_accent"


def test_multi_word_answer_with_accents():
    result = check_answer("¿cómo estás?; hoe gaat het", "como estas")
    assert result.result == "correct_accent"
    assert result.matched == "¿cómo estás?"


def test_punctuation_only_in_stored_answer_is_ignored():
    # Spaanse vraagtekens/uitroeptekens hoef je niet mee te typen
    assert check_answer("¿cómo estás?", "¿cómo estás?").result == "correct"
    assert check_answer("¿cómo estás?", "cómo estás").result == "correct"
