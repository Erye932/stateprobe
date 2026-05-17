#!/usr/bin/env python3
"""Show benchmark case results side by side."""

import json
import sys
from pathlib import Path

CASES_PATH = Path(__file__).resolve().parent.parent / "benchmarks" / "deepseek_behavior_seed" / "cases.jsonl"


def truncate(text: str, limit: int = 300) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def main() -> int:
    cases = []
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    for case in cases:
        before = case.get("deepseek_output_before", "")
        after = case.get("deepseek_output_after", "")
        print("=" * 70)
        print(f"CASE: {case['id']}  |  AXIS: {case['axis']}")
        print(f"FAILURE: {case['failure_mode']}")
        print("-" * 70)
        print(f"BAD PROMPT ({len(case['bad_prompt'])} chars):")
        print(f"  {case['bad_prompt'][:200]}")
        print(f"\nDEEPSEEK OUTPUT BEFORE ({len(before)} chars):")
        print(f"  {truncate(before)}")
        print(f"\nIMPROVED PROMPT ({len(case['improved_prompt'])} chars):")
        print(f"  {case['improved_prompt'][:200]}")
        print(f"\nDEEPSEEK OUTPUT AFTER ({len(after)} chars):")
        print(f"  {truncate(after)}")
        ratio = len(before) / max(len(after), 1)
        print(f"\n  RATIO: {ratio:.1f}x shorter  |  BEFORE: {len(before)} chars → AFTER: {len(after)} chars")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
