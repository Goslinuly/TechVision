from app.tools import factcheck_parser as fp


def test_verdict_label_mapping():
    # Returns (verdict, human-readable rating) or None.
    assert fp._extract_verdict("... ЛОЖЬ | что-то ...") == ("refuted", "Ложь")
    assert fp._extract_verdict("Заголовок: Фейк про вакцины")[0] == "refuted"
    assert fp._extract_verdict("Полуправда о ценах") == ("not_found", "Полуправда")
    assert fp._extract_verdict("Это правда, подтверждено")[0] == "supported"
    assert fp._extract_verdict("Обычная новость без вердикта") is None


def test_prefix_stripping():
    assert fp._PREFIX.sub("", "ЛОЖЬ | Цены выросли").strip() == "Цены выросли"
    assert fp._PREFIX.sub("", "Обычный заголовок").strip() == "Обычный заголовок"


def test_meta_extraction():
    html = (
        '<meta property="og:title" content="Проверка заявления">'
        '<meta name="og:description" content="Краткое описание">'
    )
    assert fp._meta(html, "og:title") == "Проверка заявления"
    assert fp._meta(html, "og:description") == "Краткое описание"
    assert fp._meta(html, "missing") == ""
