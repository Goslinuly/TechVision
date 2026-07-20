from app.orchestrator import analyze
from app.services import metrics


def test_metrics_record_and_snapshot():
    metrics.reset()
    analyze("Врачи скрывают, что вакцина вызвала 5000 смертей в Алматы")
    analyze("Средняя зарплата превысила 400 тысяч тенге")
    snap = metrics.snapshot()
    assert snap["checks_total"] == 2
    assert snap["messages_with_manipulation"] >= 1
    assert 0.0 <= snap["manipulation_rate"] <= 1.0
    assert sum(snap["by_language"].values()) == 2
    assert snap["checkable_verdicts"]  # at least one checkable claim counted
