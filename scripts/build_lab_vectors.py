"""One-shot builder for pre-computed axis direction vectors.

Run this once per machine / model to produce the .pt file that LabContributor
loads at runtime.

Usage:
    python scripts/build_lab_vectors.py
    python scripts/build_lab_vectors.py --layer -1 --out lab_vectors/r1_distill_1.5b_v1.pt

Output:
    lab_vectors/r1_distill_1.5b_v1.pt  (~ 10-50MB depending on hidden_dim)

This is the G2 gate in docs/archive/v0.3/ACCEPTANCE.md.

Exit codes:
    0  success
    2  optional lab dependencies (torch / transformers) missing
    3  CUDA not available (CPU is too slow for a one-shot build of all axes)
    4  model / tokenizer load failed (HF download blocked, no auth, etc.)
    5  axis-vector build failed (bug in pairs or probe code)
    6  no axis vectors built (all pair lists empty)
    7  round-trip integrity check failed
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from stateprobe.lab.cache import LabVectorStore
from stateprobe.lab.deepseek_pairs import DEEPSEEK_AXIS_PAIRS, DEFAULT_DEEPSEEK_MODEL
from stateprobe.lab.probe import (
    build_axis_vector,
    dependency_status,
    load_model_and_tokenizer,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--model",
        default=DEFAULT_DEEPSEEK_MODEL,
        help=f"HF model identifier (default: {DEFAULT_DEEPSEEK_MODEL})",
    )
    p.add_argument(
        "--layer",
        type=int,
        default=-1,
        help="Transformer layer index for hidden state extraction (default: -1 = last)",
    )
    p.add_argument(
        "--out",
        default="lab_vectors/r1_distill_1.5b_v1.pt",
        help="Output path for the pre-computed store",
    )
    p.add_argument(
        "--device",
        default=None,
        help="Force device (cuda / cpu). Default: auto-detect.",
    )
    return p.parse_args()


def _preflight(forced_device: str | None) -> str:
    """Verify lab deps + CUDA before spending time on a model download.

    Returns the device string to pass downstream. Exits the process with a
    distinct non-zero code on each failure class so users (and CI) can tell
    "no torch installed" from "no GPU" from "model load broke".
    """
    status = dependency_status()
    if not status.ready:
        missing = []
        if not status.torch_available:
            missing.append("torch")
        if not status.transformers_available:
            missing.append("transformers")
        print(
            f"FAIL: optional lab dependencies missing: {', '.join(missing)}.\n"
            f"FIX:  {status.install_hint}"
        )
        sys.exit(2)

    import torch  # safe now: dependency_status() confirmed it's importable.

    # Honor explicit --device cpu (advanced users / debugging only); otherwise
    # CUDA is required because building 4 axes × ~6 forward passes on CPU
    # easily takes 10+ minutes per axis on a 1.5B distilled model.
    if forced_device == "cpu":
        print("WARN: --device cpu is debug-only; expect 10+ min/axis on CPU.")
        return "cpu"

    if not torch.cuda.is_available():
        print(
            "FAIL: CUDA not available. Building all axes on CPU is impractical\n"
            "      (each forward pass takes ~10s vs ~50ms on GPU).\n"
            "FIX:  install a CUDA-enabled torch wheel:\n"
            "      pip install torch --index-url https://download.pytorch.org/whl/cu126\n"
            "      Or pass --device cpu to override (debug only)."
        )
        sys.exit(3)

    return forced_device or "cuda"


def main() -> int:
    args = parse_args()
    print(f"Building axis vectors for {args.model} at layer {args.layer}")
    print(f"Output: {args.out}")
    print()

    device = _preflight(args.device)

    t0 = time.perf_counter()
    try:
        model, tokenizer, resolved_device = load_model_and_tokenizer(
            model_name=args.model, device=device
        )
    except Exception as exc:
        print(
            f"\nFAIL: model load failed: {exc}\n"
            f"FIX:  - check the HF model id is correct ({args.model})\n"
            f"      - if behind a firewall, set HF_ENDPOINT=https://hf-mirror.com\n"
            f"      - or set STATEPROBE_LAB_MODEL_PATH to a local snapshot"
        )
        return 4
    load_dt = time.perf_counter() - t0
    print(f"Model loaded on {resolved_device} in {load_dt:.1f}s")
    print()

    axis_vectors = {}
    for axis, pairs in DEEPSEEK_AXIS_PAIRS.items():
        if not pairs:
            print(f"  [SKIP] {axis.value}: no contrastive pairs")
            continue
        t0 = time.perf_counter()
        try:
            av = build_axis_vector(
                axis=axis,
                pairs=pairs,
                model=model,
                tokenizer=tokenizer,
                layer=args.layer,
                device=resolved_device,
            )
        except Exception as exc:
            print(
                f"\nFAIL: axis-vector build crashed on {axis.value}: {exc}\n"
                f"FIX:  - check stateprobe/lab/deepseek_pairs.py for malformed pair data\n"
                f"      - re-run scripts/lab_smoke.py first to confirm probe.py works"
            )
            return 5
        dt = time.perf_counter() - t0
        norm = av.vector.float().norm().item()
        print(
            f"  [OK]   {axis.value:<20} pairs={len(pairs):>2}  "
            f"norm={norm:.4f}  time={dt:.2f}s"
        )
        axis_vectors[axis] = av

    if not axis_vectors:
        print("\nFAIL: No axis vectors built (all pair lists empty).")
        return 6

    store = LabVectorStore.from_axis_vectors(
        axis_vectors=axis_vectors, model_name=args.model
    )
    store.save(args.out)
    print()
    print(store.summary())
    print()
    out_size_mb = Path(args.out).stat().st_size / 1e6
    print(f"Saved: {args.out} ({out_size_mb:.1f} MB)")
    if out_size_mb > 100:
        print(f"WARN: file size {out_size_mb:.1f} MB exceeds G2 budget of 100 MB.")

    # Round-trip check
    reloaded = LabVectorStore.load(args.out)
    if set(reloaded.vectors.keys()) != set(store.vectors.keys()):
        print("FAIL: round-trip lost axes")
        return 7
    print("Round-trip check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
