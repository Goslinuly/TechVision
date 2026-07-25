"""Eval harness (§4, №4 «adversarial») — Criterion 2 evidence base.

Runs the orchestrator over a labeled gold set and scores:
  * language accuracy;
  * manipulation detection precision / recall / F1 against ground-truth labels
    (`manip_labels` = the complete set a human would mark per message);
  * opinion-flagging accuracy;
  * verdict hit rate (against the known Factcheck.kz corpus).

`run_eval()` returns a structured report. `python -m scripts.eval` prints a
scorecard and exits non-zero on a gate regression; `--report PATH` also writes a
markdown scorecard (committed as EVAL.md for the pitch).

Point it at the real LLM loop (GROQ_API_KEY / ANTHROPIC_API_KEY set) to measure
the production path instead of the deterministic mock.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.models import ClaimKind
from app.orchestrator import analyze
from app.tools import rhetoric
from app.services.lang import detect_lang

_EVAL = Path(__file__).resolve().parents[1] / "data" / "eval_set.json"

# Hard gates — the run fails below these.
GATES = {
    "lang_accuracy": 1.0,
    "opinion_accuracy": 0.8,
    "manip_precision": 0.85,
    "manip_recall": 0.85,
}


def run_eval(cases: list[dict] | None = None) -> dict:
    if cases is None:
        cases = json.loads(_EVAL.read_text(encoding="utf-8"))

    lang_ok = 0
    tp = fp = fn = 0
    opinion_total = opinion_ok = 0
    verdict_total = verdict_ok = 0
    mismatches: list[str] = []

    for c in cases:
        # Manipulation detection is scored directly on the detector (deterministic),
        # independent of the LLM path, so P/R/F1 measure the detector itself.
        lang = detect_lang(c["text"])
        detected = {m.technique for m in rhetoric.analyze(c["text"], lang)}
        gt = set(c.get("manip_labels", []))
        tp += len(gt & detected)
        fp += len(detected - gt)
        fn += len(gt - detected)
        for extra in sorted(detected - gt):
            mismatches.append(f"[{c['id']}] false positive '{extra}'")
        for miss in sorted(gt - detected):
            mismatches.append(f"[{c['id']}] missed '{miss}'")

        if lang.value == c["expect_lang"]:
            lang_ok += 1
        else:
            mismatches.append(f"[{c['id']}] lang {lang.value} != {c['expect_lang']}")

        # Opinion flagging + verdict come from the full orchestrator path.
        if "expect_has_opinion" in c or "expect_verdict_any" in c:
            card = analyze(c["text"])
            if "expect_has_opinion" in c:
                opinion_total += 1
                has_op = any(cl.kind is ClaimKind.OPINION for cl in card.claims)
                if has_op == c["expect_has_opinion"]:
                    opinion_ok += 1
                else:
                    mismatches.append(
                        f"[{c['id']}] opinion {has_op} != {c['expect_has_opinion']}"
                    )
            if "expect_verdict_any" in c:
                verdict_total += 1
                verdicts = {cl.verdict.value for cl in card.claims}
                if c["expect_verdict_any"] in verdicts:
                    verdict_ok += 1
                else:
                    mismatches.append(
                        f"[{c['id']}] no verdict '{c['expect_verdict_any']}' "
                        f"(got {sorted(verdicts)})"
                    )

    def ratio(n: int, d: int) -> float:
        return round(n / d, 3) if d else 1.0

    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 3) if (precision + recall) else 0.0

    return {
        "cases": len(cases),
        "lang_accuracy": ratio(lang_ok, len(cases)),
        "manip_precision": precision,
        "manip_recall": recall,
        "manip_f1": f1,
        "manip_tp": tp,
        "manip_fp": fp,
        "manip_fn": fn,
        "opinion_accuracy": ratio(opinion_ok, opinion_total),
        "verdict_hit_rate": ratio(verdict_ok, verdict_total),
        "mismatches": mismatches,
    }


def _passes_gates(r: dict) -> bool:
    return all(r[k] >= v for k, v in GATES.items())


def _markdown(r: dict) -> str:
    lines = [
        "# Aqıqat — Eval scorecard",
        "",
        f"Прогон по {r['cases']} размеченным кейсам (`data/eval_set.json`). "
        "Метрики манипуляций считаются напрямую по детектору против ground-truth "
        "разметки; язык/мнения/вердикт — по полному пайплайну.",
        "",
        "| Метрика | Значение |",
        "|---|---|",
        f"| Точность языка (kk/ru) | {r['lang_accuracy']} |",
        f"| Манипуляции: precision | {r['manip_precision']} |",
        f"| Манипуляции: recall | {r['manip_recall']} |",
        f"| Манипуляции: F1 | {r['manip_f1']} |",
        f"| TP / FP / FN | {r['manip_tp']} / {r['manip_fp']} / {r['manip_fn']} |",
        f"| Отделение мнений | {r['opinion_accuracy']} |",
        f"| Попадание вердикта (корпус) | {r['verdict_hit_rate']} |",
        "",
    ]
    if r["mismatches"]:
        lines += ["## Известные расхождения (честно)", ""]
        lines += [f"- {m}" for m in r["mismatches"]]
        lines += [""]
    lines += [
        "> Единичный false positive `unsourced_number` на нейтральной статистике —",
        "> задокументированное ограничение rule-based детектора (см. `salary-stat`).",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path, help="write a markdown scorecard here")
    args = ap.parse_args()

    r = run_eval()
    print("=" * 60)
    print(f"EVAL — {r['cases']} cases")
    print("-" * 60)
    for k in ("lang_accuracy", "manip_precision", "manip_recall", "manip_f1",
              "opinion_accuracy", "verdict_hit_rate"):
        print(f"  {k:20} {r[k]}")
    print(f"  TP/FP/FN            {r['manip_tp']}/{r['manip_fp']}/{r['manip_fn']}")
    if r["mismatches"]:
        print("-" * 60)
        for m in r["mismatches"]:
            print("  •", m)
    print("=" * 60)
    if args.report:
        args.report.write_text(_markdown(r), encoding="utf-8")
        print(f"scorecard → {args.report}")
    if _passes_gates(r):
        print("GATES: PASS")
        sys.exit(0)
    print("GATES: FAIL")
    sys.exit(1)


if __name__ == "__main__":
    main()
