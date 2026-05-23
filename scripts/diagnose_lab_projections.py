"""Diagnose actual raw projection magnitudes per (prompt, axis) cell.

Outputs a table of raw cosine values so we can decide:
- Whether MIN_LAB_CONFIDENCE = 0.15 is too strict for 1.5B distilled.
  (Day 4 outcome: yes — final value lowered to 0.10 and confidence is now
  sigmoid-mapped via `sigmoid(10 * (|raw| - 0.15))`. See lab.py comments
  + docs/archive/v0.3/TECHNICAL.md §6.4.)
- Whether the contrastive pairs need redesign.
- Whether layer -1 is the wrong layer to extract from.

Not part of acceptance gates — purely diagnostic. Re-run after any change to
the contrastive pairs or layer choice to re-verify the calibration.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

EXAMPLES_DIR = REPO_ROOT / "examples"
DEFAULT_VECTORS = REPO_ROOT / "lab_vectors" / "r1_distill_1.5b_v1.pt"


def main() -> int:
    from stateprobe.engines.lab import LabContributor
    from stateprobe.models import Axis

    examples = []
    for txt in sorted(EXAMPLES_DIR.glob("*.txt")):
        prompt = txt.read_text(encoding="utf-8").strip()
        if prompt:
            examples.append((txt.stem, prompt))

    print(f"Loading lab from {DEFAULT_VECTORS}")
    lab = LabContributor(vectors_path=str(DEFAULT_VECTORS))

    axes_present = sorted(lab.axes_available(), key=lambda a: a.value)
    header = f"{'prompt':<28}" + "".join(f"{a.value:>22}" for a in axes_present)
    print(header)
    print("-" * len(header))

    raw_table = {}
    for pid, prompt in examples:
        t0 = time.perf_counter()
        scores = lab.project_prompt(prompt)
        dt = (time.perf_counter() - t0) * 1000
        raw_table[pid] = scores
        cells = "".join(f"{scores.get(a, 0.0):>+22.4f}" for a in axes_present)
        print(f"{pid:<28}{cells}  [{dt:6.1f}ms]")

    print()
    print("=== Magnitude summary (|raw|) ===")
    for axis in axes_present:
        magnitudes = [abs(raw_table[pid].get(axis, 0.0)) for pid, _ in examples]
        max_m = max(magnitudes)
        avg_m = sum(magnitudes) / len(magnitudes)
        active_at_015 = sum(1 for m in magnitudes if m >= 0.15)
        active_at_010 = sum(1 for m in magnitudes if m >= 0.10)
        active_at_005 = sum(1 for m in magnitudes if m >= 0.05)
        print(
            f"  {axis.value:<20} "
            f"max={max_m:.3f}  avg={avg_m:.3f}  "
            f">=0.15: {active_at_015}/5  "
            f">=0.10: {active_at_010}/5  "
            f">=0.05: {active_at_005}/5"
        )

    print()
    print("=== Recommendation ===")
    all_max = max(
        abs(raw_table[pid].get(a, 0.0))
        for pid, _ in examples for a in axes_present
    )
    if all_max < 0.10:
        print(
            f"Max projection magnitude across all (prompt, axis) cells is {all_max:.3f}.\n"
            f"This is below 0.10 — Persona Vectors signal is very weak on 1.5B distilled.\n"
            f"Suggested next steps:\n"
            f"  1. Try layer -8 (mid-stack) instead of -1.\n"
            f"  2. Redesign contrastive pairs (current pairs may be too 'engineered').\n"
            f"  3. Lower MIN_LAB_CONFIDENCE to 0.03 — but signal-to-noise will be poor.\n"
        )
    elif all_max < 0.15:
        print(
            f"Max projection magnitude is {all_max:.3f} — below the 0.15 threshold.\n"
            f"Suggested next step: lower MIN_LAB_CONFIDENCE to 0.05 or 0.08.\n"
        )
    else:
        print(
            f"Max projection magnitude is {all_max:.3f} — signal is detectable.\n"
            f"Consider lowering MIN_LAB_CONFIDENCE if too few sources fire.\n"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
