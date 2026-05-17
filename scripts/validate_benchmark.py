#!/usr/bin/env python3
"""Validate benchmark cases against schema."""

import json
import sys
from pathlib import Path

BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "deepseek_behavior_seed"
SCHEMA_PATH = BENCHMARK_DIR / "schema.json"
CASES_PATH = BENCHMARK_DIR / "cases.jsonl"

VALID_AXES = {
    "sycophancy",
    "task_width",
    "success_criteria",
    "reasoning_budget",
    "identity_strength",
    "assertiveness",
    "self_verification",
    "info_flow",
}

REQUIRED_FIELDS = [
    "id",
    "axis",
    "failure_mode",
    "bad_prompt",
    "improved_prompt",
    "expected_behavior_change",
    "static_diagnosis_summary",
]

OPTIONAL_FIELDS = {
    "deepseek_output_before",
    "deepseek_output_after",
    "human_note",
    "tags",
}

ALL_FIELDS = set(REQUIRED_FIELDS) | OPTIONAL_FIELDS


def validate_case(case: dict, line_num: int) -> list[str]:
    """Return list of error strings for a single case."""
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in case:
            errors.append(f"line {line_num}: missing required field '{field}'")
        elif not isinstance(case[field], str) or not case[field].strip():
            errors.append(f"line {line_num}: field '{field}' must be a non-empty string")

    if "axis" in case and case["axis"] not in VALID_AXES:
        errors.append(f"line {line_num}: invalid axis '{case['axis']}', must be one of {sorted(VALID_AXES)}")

    if "id" in case:
        import re
        if not re.match(r"^[a-z0-9_]+$", case["id"]):
            errors.append(f"line {line_num}: id '{case['id']}' must be snake_case (a-z, 0-9, _)")

    if "tags" in case:
        if not isinstance(case["tags"], list) or not all(isinstance(t, str) for t in case["tags"]):
            errors.append(f"line {line_num}: 'tags' must be an array of strings")

    extra_fields = set(case.keys()) - ALL_FIELDS
    if extra_fields:
        errors.append(f"line {line_num}: unknown fields {sorted(extra_fields)}")

    return errors


def main() -> int:
    if not CASES_PATH.exists():
        print(f"ERROR: {CASES_PATH} not found")
        return 1

    if not SCHEMA_PATH.exists():
        print(f"ERROR: {SCHEMA_PATH} not found")
        return 1

    cases = []
    parse_errors = []
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append((i, json.loads(line)))
            except json.JSONDecodeError as e:
                parse_errors.append(f"line {i}: invalid JSON: {e}")

    if parse_errors:
        for e in parse_errors:
            print(f"ERROR: {e}")
        return 1

    all_errors = []
    seen_ids = set()
    axes_covered = set()

    for line_num, case in cases:
        errors = validate_case(case, line_num)
        all_errors.extend(errors)

        case_id = case.get("id", "")
        if case_id in seen_ids:
            all_errors.append(f"line {line_num}: duplicate id '{case_id}'")
        seen_ids.add(case_id)

        axis = case.get("axis", "")
        if axis in VALID_AXES:
            axes_covered.add(axis)

    if all_errors:
        print(f"Benchmark validation FAILED ({len(all_errors)} errors):\n")
        for e in all_errors:
            print(f"  {e}")
        return 1

    missing_axes = VALID_AXES - axes_covered
    print(f"Benchmark validation passed: {len(cases)} cases, {len(axes_covered)}/8 axes covered.")
    if missing_axes:
        print(f"  Missing axes: {sorted(missing_axes)}")
    else:
        print("  All 8 axes covered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
