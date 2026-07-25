from scripts.eval import GATES, run_eval


def test_eval_meets_gates():
    report = run_eval()
    assert report["cases"] >= 10
    for key, threshold in GATES.items():
        assert report[key] >= threshold, (key, report[key], report["mismatches"])
    # Detector should have near-perfect recall and only the documented FP.
    assert report["manip_fn"] == 0, report["mismatches"]
    assert report["manip_fp"] <= 1, report["mismatches"]
