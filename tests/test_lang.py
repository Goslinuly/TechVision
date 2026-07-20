from app.models import Lang
from app.services.lang import detect_lang


def test_kazakh_specific_letters():
    assert detect_lang("Мемлекет зейнетақыны ауыстырады") is Lang.KK
    assert detect_lang("Бұл ақпарат жалған") is Lang.KK


def test_russian_default():
    assert detect_lang("Вакцина вызвала осложнения") is Lang.RU
    assert detect_lang("") is Lang.RU  # empty falls back to ru


def test_mixed_prefers_kazakh_marker():
    # A single Kazakh-only letter is enough to switch to kk.
    assert detect_lang("Срочно: билік жасырады") is Lang.KK
