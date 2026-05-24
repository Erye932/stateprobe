"""StateProbe Skill calibration runner.

Reads ``tests/fixtures/skill_cases.jsonl`` and runs ``preview_attention``
against every case, comparing the live decision to the human-labelled
oracle. Prints a baseline report so the project can answer "how often
does StateProbe agree with a human?" with a real number instead of a
slogan.

Usage::

    python scripts/calibrate_skill.py

The script exits 0 even when there are mismatches — calibration is a
diagnostic, not a gate. The pytest suite is what blocks regressions.

Cases with ``status == "agree"`` are expected to match. Cases with
``status == "known_issue"`` are tracked separately; they record the
*actual* output we ship today plus the *oracle* answer a human would
give. Calibration counts both as data points and surfaces:

- agreement rate over the agree cases
- list of known issues (so reviewers can see "where StateProbe is
  honestly wrong today")
- any silent drift on known issues (when actual output no longer
  matches the documented actual — needs review)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "skill_cases.jsonl"

sys.path.insert(0, str(REPO_ROOT))

from stateprobe.skill import preview_attention  # noqa: E402


def load_cases(path: Path) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:  # pragma: no cover
                raise SystemExit(
                    f"{path}:{line_no}: invalid JSON: {exc}"
                ) from exc
    return cases


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    preview = preview_attention(case["context"], case["planned_focus"])
    decision = preview.activation_decision
    return {
        "action": decision.action,
        "should_stop": decision.should_stop,
        "confidence": decision.confidence,
        "contamination_risks_empty": not preview.context_contamination_risks,
        "_preview": preview,
    }


def compare(
    actual: Dict[str, Any], expected: Dict[str, Any], check: str
) -> Tuple[bool, List[str]]:
    diffs: List[str] = []
    if check == "contamination_only":
        if actual["contamination_risks_empty"] != expected.get(
            "contamination_risks_empty", True
        ):
            diffs.append(
                "contamination_risks_empty="
                f"{actual['contamination_risks_empty']} "
                f"expected={expected.get('contamination_risks_empty', True)}"
            )
        return not diffs, diffs

    for key in ("action", "should_stop", "confidence"):
        if key not in expected:
            continue
        if actual[key] != expected[key]:
            diffs.append(f"{key}={actual[key]!r} expected={expected[key]!r}")
    return not diffs, diffs


def fmt_section(title: str) -> str:
    return f"\n=== {title} ===\n"


def main() -> int:
    cases = load_cases(FIXTURE_PATH)
    if not cases:
        print(f"no cases in {FIXTURE_PATH}", file=sys.stderr)
        return 1

    agree_total = 0
    agree_pass = 0
    agree_fail: List[Tuple[Dict[str, Any], List[str]]] = []
    known_issues: List[Dict[str, Any]] = []
    silent_drift: List[Tuple[Dict[str, Any], List[str]]] = []

    for case in cases:
        check = case.get("check", "decision")
        actual = run_case(case)

        if case.get("status") == "agree":
            agree_total += 1
            ok, diffs = compare(actual, case["oracle"], check)
            if ok:
                agree_pass += 1
            else:
                agree_fail.append((case, diffs))
            continue

        if case.get("status") == "known_issue":
            known_issues.append(case)
            documented_actual = case.get("actual")
            if documented_actual:
                ok, diffs = compare(actual, documented_actual, check)
                if not ok:
                    silent_drift.append((case, diffs))
            continue

    print(fmt_section("StateProbe Skill calibration"))
    print(f"fixture: {FIXTURE_PATH.relative_to(REPO_ROOT)}")
    print(f"total cases: {len(cases)}")
    print(f"agree cases: {agree_total}  passing: {agree_pass}")
    if agree_total:
        rate = agree_pass / agree_total * 100
        print(f"agreement rate (agree cases): {rate:.1f}%")
    print(f"known issues: {len(known_issues)}")

    if agree_fail:
        print(fmt_section("agreement failures (regressions)"))
        for case, diffs in agree_fail:
            print(f"- {case['id']}  ({case.get('category', '')})")
            print(f"  {case.get('description', '').strip()}")
            for diff in diffs:
                print(f"    {diff}")

    if known_issues:
        print(fmt_section("known issues (oracle != current behaviour)"))
        for case in known_issues:
            actual_doc = case.get("actual", {})
            oracle = case.get("oracle", {})
            print(f"- {case['id']}  ({case.get('category', '')})")
            print(f"  oracle  : {oracle}")
            print(f"  actual  : {actual_doc}")
            if case.get("notes"):
                print(f"  notes   : {case['notes']}")

    if silent_drift:
        print(fmt_section("silent drift on known issues (review)"))
        for case, diffs in silent_drift:
            print(f"- {case['id']}: {', '.join(diffs)}")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
