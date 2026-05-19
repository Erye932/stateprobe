# StateProbe v0.3 — Reproducibility Guide

**TL;DR** — StateProbe v0.3 ships a third evidence layer (`LabContributor`) that
projects prompt activations onto pre-built axis direction vectors on
DeepSeek-R1-Distill-Qwen-1.5B. This is the open-source equivalent of the
Persona Vectors method (Anthropic, [arXiv:2507.21509](https://arxiv.org/abs/2507.21509)).
This page lets you reproduce every number we publish in ~20 minutes on a
consumer GPU.

## What this layer does

For each behavior axis (sycophancy, task width, reasoning budget,
self-verification), we precompute a **direction vector** in the model's
1536-dim residual stream:

```
axis_vector  =  mean(positive_prompts.last_token_hidden) -
                mean(negative_prompts.last_token_hidden)
```

For a new prompt `p`, we compute:

```
raw_score   = cosine(p.last_token_hidden, axis_vector)
confidence  = sigmoid(10 * (|raw_score| - 0.15))
direction   = sign(raw_score)
```

This emits a `PollutionSource` into the same evidence pool as the static
regex layer and the LLM judge layer. The aggregator weights all three
sources by `direction × weight × confidence` and produces the final
per-axis reading.

## Hardware

| Component | Tested config | Notes |
|---|---|---|
| GPU | NVIDIA RTX 4060 Ti, 8GB | Any CUDA card with ≥4GB works |
| Driver | CUDA 12.6, torch 2.12+cu126 | Older CUDA toolkits compatible |
| Disk | 5GB free for model + cache | Model is 3.3GB, vectors are 27KB |
| RAM | 16GB+ recommended | Forward pass is single-prompt |

CPU fallback exists in code but is too slow to ship (≥10s per prompt). The
LabContributor will refuse to load on a CPU-only system.

## Step-by-step reproduction

### 1. Install

```bash
git clone https://github.com/Erye932/stateprobe
cd stateprobe
pip install -e ".[lab]"
```

This pulls `torch`, `transformers`, `accelerate`. **Do not** install with the
default CPU torch wheel — install the matching CUDA wheel separately if
your `pip install torch` selects CPU:

```bash
pip uninstall -y torch
pip install torch --index-url https://download.pytorch.org/whl/cu126
```

### 2. Pre-download the model weights

Hugging Face Hub rate-limits unauthenticated downloads aggressively. Two
reliable paths:

**Option A — ModelScope mirror (recommended in CN)**

```bash
pip install modelscope
python -c "from modelscope import snapshot_download; \
  snapshot_download('deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B')"

# Point StateProbe at the local snapshot. Note: ModelScope replaces dots
# with ___ on Windows, so the directory ends in 1___5B not 1.5B.
export STATEPROBE_LAB_MODEL_PATH=~/.cache/modelscope/hub/deepseek-ai/DeepSeek-R1-Distill-Qwen-1___5B
```

**Option B — Hugging Face Hub with token**

```bash
export HF_TOKEN=hf_xxxxxxx  # get one at huggingface.co/settings/tokens
huggingface-cli download deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B
```

### 3. Verify environment (G0 gate)

```bash
python -c "
import torch, transformers, accelerate
assert torch.cuda.is_available()
assert 'NVIDIA' in torch.cuda.get_device_name(0)
print(f'OK: {torch.cuda.get_device_name(0)} / torch {torch.__version__} / transformers {transformers.__version__}')
"
```

### 4. Smoke test (G1 gate, ~30s)

```bash
python scripts/lab_smoke.py
```

Expected output (RTX 4060 Ti):

```
ALL GATES PASSED
Max single-prompt latency: ~50ms
GPU memory peak: 3.57 GB
```

### 5. Build axis vectors (G2 gate, ~15s)

```bash
python scripts/build_lab_vectors.py
# → lab_vectors/r1_distill_1.5b_v1.pt  (27KB)
```

### 6. Run discrimination report (G3 gate, ~30s)

```bash
python scripts/discrim_table.py --skip-llm
# → docs/v03_discrim_report.md  (5 examples × 4 axes × 2-3 layers)
```

### 7. End-to-end CLI

```bash
# Two-layer hybrid (static + lab)
stateprobe check --lab-augment "假装你是世界顶级专家，请全面分析这个公司"

# Three-layer hybrid (static + LLM judge + lab)
stateprobe check --llm-augment --lab-augment --file examples/bad_sycophant.txt
```

### 8. Run all tests

```bash
pytest -q
# 122 passed (108 from v0.1/v0.2 + 14 new lab tests)

python scripts/acceptance_check.py     # 0 failures
python scripts/acceptance_v02_stress.py # all v0.2 backward-compat passes
```

## Performance baseline (RTX 4060 Ti, 8GB VRAM)

| Operation | Time | Notes |
|---|---|---|
| `import stateprobe` | ~0.2s | torch/transformers NOT loaded (lazy import) |
| Model load (first call) | ~10s | One-shot per CLI invocation |
| Single-prompt activation | 40–70ms | Forward pass + last-token extraction |
| `--lab-augment` overhead | ~10s + 50ms | Dominated by model load |
| `--lab-augment` GPU peak | 3.57 GB | Out of 8.59 GB available |
| Vectors file size | 27 KB | 4 axes × 1536 dims × float32 |

## Calibration notes

The LabContributor's confidence formula was empirically tuned on the
1.5B distilled model. Two observations:

1. **Signal magnitudes are smaller than in frontier models.** The original
   Persona Vectors paper (Claude scale) reports projections in the 0.3–0.6
   range; on R1-Distill-Qwen-1.5B we see a max of 0.28 across our test
   prompts. We compensate with a sigmoid confidence map centered at 0.15.

2. **Random baseline is `1/√1536 ≈ 0.025`.** Our threshold of `|raw| > 0.10`
   is a 4× signal-to-noise margin — strict enough to filter random chatter,
   loose enough to catch genuine signals on this model size.

See `stateprobe/engines/lab.py` lines 38–83 for the full calibration
narrative and the rationale for the sigmoid coefficient choice.

## What we deliberately do NOT claim

- **Reading hidden states of closed-source models.** The LabContributor only
  works on open-weight models. OpenAI/Claude/Gemini physically don't expose
  activations through their APIs. For closed models we still rely on the
  static + LLM judge layers.

- **Causal control of behavior.** LabContributor reads the activation, it
  does not steer it. Activation steering (adding `α × axis_vector` to the
  forward pass) is a v0.5 stretch goal, not v0.3.

- **Frontier-model accuracy.** A 1.5B distilled model is the smallest
  practical scale for this technique. Signal-to-noise is meaningfully
  weaker than what the Persona Vectors paper reports on Claude-scale
  models. We chose 1.5B because it runs on consumer hardware in seconds;
  v0.4 will explore MoE expert routing on V2-Lite scale (~16B) given cloud
  GPU budget.

## What's actually new vs Persona Vectors paper

| Aspect | Persona Vectors paper | StateProbe v0.3 |
|---|---|---|
| Model | Claude (closed) | DeepSeek-R1-Distill-Qwen-1.5B (open) |
| Reproducible | No (closed model) | Yes (run on consumer GPU) |
| Integration | Standalone analysis | Hybrid pipeline alongside regex + LLM judge |
| Axes | Various traits | 4 prompt-engineering axes (sycophancy, task width, reasoning budget, self-verification) |
| Pre-built cache | N/A | 27KB `lab_vectors/r1_distill_1.5b_v1.pt` |
| Graceful degradation | N/A | Falls back to static-only if no GPU/torch/vectors |

## Citation

If you use StateProbe in research, cite:

```bibtex
@software{stateprobe2026,
  title  = {StateProbe: A debugger for prompts and LLM behavior},
  author = {{StateProbe Contributors}},
  year   = {2026},
  url    = {https://github.com/Erye932/stateprobe}
}
```

And the underlying technique:

```bibtex
@article{persona-vectors-2025,
  title  = {Persona Vectors: Monitoring and Controlling Character Traits in Language Models},
  author = {Anthropic},
  journal= {arXiv preprint arXiv:2507.21509},
  year   = {2025}
}
```

## Issue reporting

Reproduction failures, please file at
[github.com/Erye932/stateprobe/issues](https://github.com/Erye932/stateprobe/issues)
with:

- Output of step 3 (G0 verify)
- Output of step 4 (`lab_smoke.py`)
- GPU model and driver version
- OS

We treat reproduction breakages as P0 bugs.
