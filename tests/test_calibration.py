"""Calibration regressions for the StateProbe Skill decision layer.

These tests turn ``tests/fixtures/skill_cases.jsonl`` into hard
regressions:

- Every case with ``status == "agree"`` must keep matching the human
  oracle. If a refactor flips one of these to a different action /
  confidence, this test breaks loudly.
- Every case with ``status == "known_issue"`` records what StateProbe
  ships **today** under ``actual``. We assert the live decision still
  matches that documented behaviour, so a silent improvement *or*
  regression on a known issue forces a deliberate fixture update
  (and hopefully a "moved from known_issue to agree" PR).

The richer human-readable report lives in ``scripts/calibrate_skill.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from stateprobe.skill import preview_attention

FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "skill_cases.jsonl"
)


def _load_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    with FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"{FIXTURE_PATH}:{line_no}: invalid JSON: {exc}"
                ) from exc
    assert cases, f"no cases found in {FIXTURE_PATH}"
    return cases


def _run(case: Dict[str, Any]) -> Dict[str, Any]:
    preview = preview_attention(case["context"], case["planned_focus"])
    decision = preview.activation_decision
    return {
        "action": decision.action,
        "should_stop": decision.should_stop,
        "confidence": decision.confidence,
        "contamination_risks_empty": not preview.context_contamination_risks,
        "boundary_questions_empty": not preview.boundary_questions,
        "violated_empty": not any(
            g.kind == "over_focused" and g.severity == "high"
            for g in preview.missing_before_start
        ),
    }


def _diff(actual: Dict[str, Any], expected: Dict[str, Any]) -> List[str]:
    return [
        f"{key}={actual[key]!r} expected={value!r}"
        for key, value in expected.items()
        if actual.get(key) != value
    ]


_CASES = _load_cases()
_AGREE_CASES = [c for c in _CASES if c.get("status") == "agree"]
_KNOWN_ISSUE_CASES = [c for c in _CASES if c.get("status") == "known_issue"]


@pytest.mark.parametrize(
    "case",
    _AGREE_CASES,
    ids=[c["id"] for c in _AGREE_CASES],
)
def test_skill_calibration_agree_cases_match_oracle(
    case: Dict[str, Any],
) -> None:
    actual = _run(case)
    diffs = _diff(actual, case["oracle"])
    assert not diffs, (
        f"calibration mismatch for {case['id']} "
        f"({case.get('category', '')}): {diffs}"
    )


@pytest.mark.parametrize(
    "case",
    _KNOWN_ISSUE_CASES,
    ids=[c["id"] for c in _KNOWN_ISSUE_CASES],
)
def test_skill_calibration_known_issues_have_documented_behaviour(
    case: Dict[str, Any],
) -> None:
    documented = case.get("actual")
    assert documented, (
        f"known_issue {case['id']} must document its current 'actual' output "
        "so that any silent change forces a fixture update."
    )
    actual = _run(case)
    diffs = _diff(actual, documented)
    assert not diffs, (
        f"known_issue {case['id']} drifted from documented actual: {diffs}. "
        "If StateProbe now agrees with the oracle, move this case to "
        "status=agree and drop the 'actual' block."
    )
