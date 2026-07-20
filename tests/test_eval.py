from scripts.eval import GATES, run_eval


def test_eval_meets_gates():
    report = run_eval()
    assert report["cases"] >= 8
    assert report["lang_accuracy"] >= GATES["lang_accuracy"]
    assert report["manip_false_positives"] <= GATES["manip_false_positives"]
    assert report["opinion_accuracy"] >= GATES["opinion_accuracy"]
    # Surface any residual gaps in the assertion message for CI logs.
    assert report["manip_recall"] >= 0.8, report["mismatches"]
