from app.models import ClaimKind, Lang, MessageClass, Verdict
from app.orchestrator import analyze
from app.orchestrator.orchestrator import compute_confidence


def test_confidence_monotonic():
    none = compute_confidence({"verdict": None, "matches": []},
                              {"verdict": None, "matches": []})
    google_only = compute_confidence({"verdict": None, "matches": []},
                                     {"verdict": "refuted", "matches": [{}]})
    both = compute_confidence(
        {"verdict": "refuted", "matches": [{"similarity": 0.9}]},
        {"verdict": "refuted", "matches": [{}]},
    )
    assert none == 0.0
    assert 0 < google_only < both <= 1.0


def test_analyze_decomposes_and_flags_opinion():
    card = analyze(
        "Врачи скрывают, что вакцина X вызвала 5000 смертей в Алматы. "
        "Срочно перешлите всем!"
    )
    assert card.lang is Lang.RU
    assert card.message_class is MessageClass.MIXED
    # The "врачи скрывают" clause must be treated as opinion, not fact.
    opinions = [c for c in card.claims if c.kind is ClaimKind.OPINION]
    assert opinions
    assert all(o.verdict is Verdict.NOT_CHECKABLE for o in opinions)
    # Manipulation techniques with spans are present.
    assert card.manipulations
    assert any(m.technique == "fear_appeal" for m in card.manipulations)


def test_analyze_kazakh_language():
    card = analyze("Мемлекет зейнетақыны цифрлық теңгеге мәжбүрлеп ауыстырады")
    assert card.lang is Lang.KK
    assert card.claims


def test_card_has_shareable_url():
    card = analyze("Средняя зарплата превысила 400 тысяч тенге")
    card.id = "abcd"
    assert card.url == "/r/abcd"
