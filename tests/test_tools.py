from app.models import Verdict
from app.tools import google_factcheck, local_corpus


def test_google_rating_mapping():
    assert google_factcheck._rating_to_verdict("Фейк") is Verdict.REFUTED
    assert google_factcheck._rating_to_verdict("False") is Verdict.REFUTED
    assert google_factcheck._rating_to_verdict("Правда") is Verdict.SUPPORTED
    assert google_factcheck._rating_to_verdict("что-то") is Verdict.NOT_FOUND


def test_google_no_key_is_graceful(monkeypatch):
    # Without a key the tool returns an empty result, never raises.
    from app import config

    monkeypatch.setattr(
        config.get_settings(), "google_factcheck_api_key", "", raising=False
    )
    out = google_factcheck.search("вакцина", "ru")
    assert out["matches"] == []
    assert out.get("error") == "no_api_key"


def test_local_corpus_matches_known_hoax():
    out = local_corpus.search("вакцина вызвала 5000 смертей в Алматы")
    assert out["verdict"] == "refuted"
    assert out["matches"], "expected at least one corpus match"
    assert out["matches"][0]["source"] == "Factcheck.kz"


def test_local_corpus_no_match_below_threshold():
    out = local_corpus.search("рецепт бешбармака с кониной")
    assert out["verdict"] is None
    assert out["matches"] == []
