from app.models import Lang
from app.tools import rhetoric


def test_fear_appeal_span_is_exact():
    text = "Врачи скрывают правду"
    items = rhetoric.analyze(text, Lang.RU)
    fear = [m for m in items if m.technique == "fear_appeal"]
    assert fear, "fear_appeal not detected"
    m = fear[0]
    # The reported span must slice back to the highlighted phrase.
    assert text[m.start : m.end] == m.span_text
    assert "скрыва" in m.span_text.lower()


def test_unsourced_number_detected_without_source():
    items = rhetoric.analyze("Вакцина вызвала 5000 смертей", Lang.RU)
    assert any(m.technique == "unsourced_number" for m in items)


def test_unsourced_number_suppressed_when_source_mentioned():
    items = rhetoric.analyze(
        "По данным Минздрава, зарегистрировано 5000 случаев", Lang.RU
    )
    assert not any(m.technique == "unsourced_number" for m in items)


def test_urgency_and_kazakh_labels():
    items = rhetoric.analyze("Срочно перешлите всем", Lang.RU)
    assert any(m.technique == "urgency" for m in items)
    kk = rhetoric.analyze("Жедел барлығына жіберіңдер", Lang.KK)
    assert any(m.technique == "urgency" for m in kk)


def test_false_dichotomy_multiword():
    items = rhetoric.analyze("Или ты с нами, или ты против народа", Lang.RU)
    assert any(m.technique == "false_dichotomy" for m in items)


def test_kk_us_vs_them_with_gap():
    # "билік ... жасыру" with a word in between must still be caught.
    items = rhetoric.analyze("билік ақиқатты жасырып отыр", Lang.KK)
    assert any(m.technique == "us_vs_them" for m in items)


def test_spans_are_sorted():
    items = rhetoric.analyze("Срочно! Врачи скрывают 5000 смертей", Lang.RU)
    starts = [m.start for m in items]
    assert starts == sorted(starts)
