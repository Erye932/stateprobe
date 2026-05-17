#!/usr/bin/env python3
"""Run DeepSeek API on all benchmark cases and fill in before/after outputs.

Reads DEEPSEEK_API_KEY from environment variable (never hardcoded).
Writes results back to cases.jsonl with deepseek_output_before/after fields.
"""

import json
import os
import sys
import time
from pathlib import Path

BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "deepseek_behavior_seed"
CASES_PATH = BENCHMARK_DIR / "cases.jsonl"
OUTPUT_PATH = BENCHMARK_DIR / "cases.jsonl"

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_TOKENS = 1024
TEMPERATURE = 0.3  # low temperature for reproducibility


def call_deepseek(prompt: str) -> str:
    """Call DeepSeek chat API with a single user message."""
    import urllib.request
    import urllib.error

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
    }).encode("utf-8")

    req = urllib.request.Request(BASE_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API error {e.code}: {error_body}") from e


def main() -> int:
    if not API_KEY:
        print("ERROR: DEEPSEEK_API_KEY environment variable not set.")
        print("Set it with:")
        print('  [System.Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "sk-xxx", "User")')
        print("Then restart your terminal.")
        return 1

    cases = []
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    print(f"Loaded {len(cases)} cases. Model: {MODEL}")
    print(f"Temperature: {TEMPERATURE}, Max tokens: {MAX_TOKENS}")
    print("=" * 60)

    for i, case in enumerate(cases):
        case_id = case["id"]
        print(f"\n[{i+1}/{len(cases)}] {case_id} (axis: {case['axis']})")

        # Skip if already has output
        if case.get("deepseek_output_before") and case.get("deepseek_output_after"):
            print("  Already has outputs, skipping.")
            continue

        # Run bad prompt
        print("  Running bad_prompt...", end=" ", flush=True)
        try:
            before = call_deepseek(case["bad_prompt"])
            case["deepseek_output_before"] = before
            print(f"OK ({len(before)} chars)")
        except RuntimeError as e:
            print(f"FAILED: {e}")
            return 1

        time.sleep(1)  # rate limit courtesy

        # Run improved prompt
        print("  Running improved_prompt...", end=" ", flush=True)
        try:
            after = call_deepseek(case["improved_prompt"])
            case["deepseek_output_after"] = after
            print(f"OK ({len(after)} chars)")
        except RuntimeError as e:
            print(f"FAILED: {e}")
            return 1

        time.sleep(1)

    # Write back
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    print("\n" + "=" * 60)
    print(f"Done. {len(cases)} cases written to {OUTPUT_PATH}")
    print("\nNext: review outputs with")
    print("  python scripts/show_benchmark_results.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
