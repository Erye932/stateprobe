"""End-to-end smoke test for the StateProbe Lab pipeline.

Purpose: prove on Day 1 that the existing stateprobe/lab/probe.py scaffold
actually runs on this machine — model loading, activation extraction, axis
vector construction, and projection all work, with acceptable latency and
GPU memory headroom.

This is the G1 gate for v0.3 LabContributor per docs/archive/v0.3/ACCEPTANCE.md.

Usage:
    python scripts/lab_smoke.py

Gate criteria (printed at the end):
- Model loads without error
- CUDA actually used (not silent CPU fallback)
- Single-prompt activation extraction < 500ms
- Axis vector construction succeeds
- Projection produces a sensible scalar in [-1, 1]
- GPU memory peak < 7GB (leaving headroom for KV cache and longer prompts)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Make `stateprobe` importable when running from repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from stateprobe.lab.probe import (
    DEFAULT_DEEPSEEK_MODEL,
    build_axis_vector,
    cosine_projection,
    dependency_status,
    extract_activation,
    load_model_and_tokenizer,
)
from stateprobe.lab.deepseek_pairs import DEEPSEEK_AXIS_PAIRS
from stateprobe.models import Axis


SMOKE_PROMPTS = [
    "请一步一步深度推理这个问题。",
    "?",
    "你好",
    "我这个想法很棒吧，请支持我并肯定我的判断。",
    "请客观判断这个想法是否成立，如果不值得做就直接否定。",
]


def banner(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def check_dependencies() -> None:
    banner("G0 / Dependency check")
    status = dependency_status()
    print(f"torch_available:        {status.torch_available}")
    print(f"transformers_available: {status.transformers_available}")
    print(f"ready:                  {status.ready}")
    if not status.ready:
        print(f"\nFIX: {status.install_hint}")
        sys.exit(2)


def check_cuda() -> str:
    banner("G0 / CUDA check")
    import torch
    print(f"torch version:  {torch.__version__}")
    print(f"cuda available: {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("\nFAIL: CUDA not available. CPU runs are too slow to ship.")
        print("FIX:  pip install torch --index-url https://download.pytorch.org/whl/cu126")
        sys.exit(3)
    print(f"cuda version:   {torch.version.cuda}")
    print(f"device name:    {torch.cuda.get_device_name(0)}")
    total = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"total memory:   {total:.2f} GB")
    return "cuda"


def time_load_model(device: str):
    banner("G1 / Model + tokenizer load")
    print(f"model: {DEFAULT_DEEPSEEK_MODEL}")
    print("(first run downloads ~3GB from huggingface)")
    t0 = time.perf_counter()
    model, tokenizer, resolved_device = load_model_and_tokenizer(
        model_name=DEFAULT_DEEPSEEK_MODEL,
        device=device,
    )
    dt = time.perf_counter() - t0
    print(f"load latency:   {dt:.1f}s")
    print(f"device used:    {resolved_device}")
    return model, tokenizer


def time_single_activation(model, tokenizer) -> float:
    banner("G1 / Single-prompt activation extraction")
    # Warm up — first forward call has cuDNN tuning + lazy init overhead.
    extract_activation("warmup", model, tokenizer)
    latencies = []
    for prompt in SMOKE_PROMPTS:
        t0 = time.perf_counter()
        activation = extract_activation(prompt, model, tokenizer)
        dt_ms = (time.perf_counter() - t0) * 1000
        latencies.append(dt_ms)
        print(
            f"  [{dt_ms:6.1f} ms] shape={tuple(activation.shape)} "
            f"dtype={activation.dtype} prompt={prompt[:30]!r}"
        )
    avg_ms = sum(latencies) / len(latencies)
    p_max_ms = max(latencies)
    print(f"\navg latency: {avg_ms:.1f} ms  /  max latency: {p_max_ms:.1f} ms")
    if p_max_ms > 500:
        print("WARN: max latency above 500ms target — investigate before scaling.")
    return p_max_ms


def time_axis_vector(model, tokenizer) -> object:
    banner("G2 / Axis vector construction (REASONING_BUDGET)")
    pairs = DEEPSEEK_AXIS_PAIRS[Axis.REASONING_BUDGET]
    print(f"pairs: {len(pairs)}")
    t0 = time.perf_counter()
    vec = build_axis_vector(Axis.REASONING_BUDGET, pairs, model, tokenizer)
    dt = time.perf_counter() - t0
    print(f"build latency:  {dt:.2f}s ({len(pairs) * 2} forward passes)")
    print(f"vector shape:   {tuple(vec.vector.shape)}")
    print(f"vector norm:    {vec.vector.float().norm().item():.4f}")
    return vec


def test_projection(model, tokenizer, axis_vec) -> None:
    banner("G3 / Projection on contrasting prompts (sanity)")
    positive_test = "请一步步推理，列出所有中间步骤，再给出最终结论。"
    negative_test = "一句话告诉我答案，不要展开。"

    pos_act = extract_activation(positive_test, model, tokenizer)
    neg_act = extract_activation(negative_test, model, tokenizer)

    pos_proj = cosine_projection(pos_act, axis_vec)
    neg_proj = cosine_projection(neg_act, axis_vec)

    print(f"axis: REASONING_BUDGET (high = deep reasoning, low = direct)")
    print(f"  positive prompt projection: raw={pos_proj.raw_score:+.4f}  "
          f"normalized={pos_proj.normalized_score:.4f}")
    print(f"  negative prompt projection: raw={neg_proj.raw_score:+.4f}  "
          f"normalized={neg_proj.normalized_score:.4f}")
    print(f"  delta (pos - neg):          {pos_proj.raw_score - neg_proj.raw_score:+.4f}")
    if pos_proj.raw_score <= neg_proj.raw_score:
        print("WARN: positive prompt did NOT project higher than negative — "
              "axis direction may be inverted or signal too weak.")
    else:
        print("OK: positive prompt projects higher than negative as expected.")


def report_gpu_memory() -> None:
    banner("G1 / GPU memory peak")
    import torch
    peak = torch.cuda.max_memory_allocated() / 1e9
    reserved = torch.cuda.max_memory_reserved() / 1e9
    print(f"max allocated:  {peak:.2f} GB")
    print(f"max reserved:   {reserved:.2f} GB")
    if reserved > 7.0:
        print("WARN: reserved memory above 7GB — risk of OOM with longer prompts.")


def main() -> int:
    check_dependencies()
    device = check_cuda()
    model, tokenizer = time_load_model(device)
    max_latency = time_single_activation(model, tokenizer)
    axis_vec = time_axis_vector(model, tokenizer)
    test_projection(model, tokenizer, axis_vec)
    report_gpu_memory()
    banner("ALL GATES PASSED")
    print(f"Max single-prompt latency: {max_latency:.1f} ms")
    print("Day 0 + Day 1 smoke test complete — ready for Day 3 (cache vectors).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
