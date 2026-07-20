"""Eval harness (§4, №4 «adversarial»).

Runs the orchestrator over a labeled gold set and scores:
  * language accuracy;
  * manipulation recall (expected techniques that were detected);
  * manipulation false positives (forbidden techniques that appeared — the
    adversarial signal: e.g. a number WITH a source must not trip
    unsourced_number);
  * opinion-flagging accuracy;
  * verdict hit rate (against the known Factcheck.kz corpus).

Doubles as a regression gate: `run_eval()` returns a structured report, and
`python -m scripts.eval` prints a scorecard + exits non-zero if a hard metric
regresses. Point it at the real Fable 5 loop (ANTHROPIC_API_KEY set) to measure
the production path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.models import ClaimKind
from app.orchestrator import analyze

_EVAL = Path(__file__).resolve().parents[1] / "data" / "eval_set.json"

# Hard gates — the run fails below these.
GATES = {"lang_accuracy": 1.0, "manip_false_positives": 0, "opinion_accuracy": 0.8}


def run_eval(cases: list[dict] | None = None) -> dict:
    if cases is None:
        cases = json.loads(_EVAL.read_text(encoding="utf-8"))

    lang_ok = 0
    manip_expected = manip_hit = 0
    manip_false_positives = 0
    opinion_total = opinion_ok = 0
    verdict_total = verdict_ok = 0
    mismatches: list[str] = []

    for c in cases:
        card = analyze(c["text"])
        detected = {m.technique for m in card.manipulations}

        if card.lang.value == c["expect_lang"]:
            lang_ok += 1
        else:
            mismatches.append(
                f"[{c['id']}] lang {card.lang.value} != {c['expect_lang']}"
            )

        for tech in c.get("expect_manipulations", []):
            manip_expected += 1
            if tech in detected:
                manip_hit += 1
            else:
                mismatches.append(f"[{c['id']}] missing manipulation '{tech}'")

        for tech in c.get("forbid_manipulations", []):
            if tech in detected:
                manip_false_positives += 1
                mismatches.append(
                    f"[{c['id']}] FALSE POSITIVE manipulation '{tech}'"
                )

        if "expect_has_opinion" in c:
            opinion_total += 1
            has_opinion = any(cl.kind is ClaimKind.OPINION for cl in card.claims)
            if has_opinion == c["expect_has_opinion"]:
                opinion_ok += 1
            else:
                mismatches.append(
                    f"[{c['id']}] opinion flag {has_opinion} != {c['expect_has_opinion']}"
                )

        if "expect_verdict_any" in c:
            verdict_total += 1
            verdicts = {cl.verdict.value for cl in card.claims}
            if c["expect_verdict_any"] in verdicts:
                verdict_ok += 1
            else:
                mismatches.append(
                    f"[{c['id']}] no claim with verdict '{c['expect_verdict_any']}' "
                    f"(got {sorted(verdicts)})"
                )

    def pct(n: int, d: int) -> float:
        return round(n / d, 3) if d else 1.0

    return {
        "cases": len(cases),
        "lang_accuracy": pct(lang_ok, len(cases)),
        "manip_recall": pct(manip_hit, manip_expected),
        "manip_false_positives": manip_false_positives,
        "opinion_accuracy": pct(opinion_ok, opinion_total),
        "verdict_hit_rate": pct(verdict_ok, verdict_total),
        "mismatches": mismatches,
    }


def _passes_gates(report: dict) -> bool:
    return (
        report["lang_accuracy"] >= GATES["lang_accuracy"]
        and report["manip_false_positives"] <= GATES["manip_false_positives"]
        and report["opinion_accuracy"] >= GATES["opinion_accuracy"]
    )


def main() -> None:
    report = run_eval()
    print("=" * 60)
    print(f"EVAL — {report['cases']} cases")
    print("-" * 60)
    for k in (
        "lang_accuracy",
        "manip_recall",
        "manip_false_positives",
        "opinion_accuracy",
        "verdict_hit_rate",
    ):
        print(f"  {k:24} {report[k]}")
    if report["mismatches"]:
        print("-" * 60)
        print("Mismatches / gaps:")
        for m in report["mismatches"]:
            print("  •", m)
    print("=" * 60)
    if _passes_gates(report):
        print("GATES: PASS")
        sys.exit(0)
    print("GATES: FAIL")
    sys.exit(1)


if __name__ == "__main__":
    main()
