from app.tools import factcheck_parser as fp


def test_verdict_label_mapping():
    assert fp._extract_verdict("... ЛОЖЬ | что-то ...") == "refuted"
    assert fp._extract_verdict("Заголовок: Фейк про вакцины") == "refuted"
    assert fp._extract_verdict("Полуправда о ценах") == "not_found"
    assert fp._extract_verdict("Это правда, подтверждено") == "supported"
    assert fp._extract_verdict("Обычная новость без вердикта") is None


def test_meta_extraction():
    html = (
        '<meta property="og:title" content="Проверка заявления">'
        '<meta name="og:description" content="Краткое описание">'
    )
    assert fp._meta(html, "og:title") == "Проверка заявления"
    assert fp._meta(html, "og:description") == "Краткое описание"
    assert fp._meta(html, "missing") == ""
