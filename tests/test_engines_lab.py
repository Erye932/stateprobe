"""Tests for the v0.3 LabContributor (ADR_010).

These are unit tests with mocked model/tokenizer — no GPU or HF download
required. End-to-end testing with the real R1-Distill model is covered by
scripts/lab_smoke.py and the G3 discrimination report.

Covers:
- LabContributor implements EvidenceContributor protocol.
- Vectors file missing → EngineUnavailable.
- CUDA unavailable + allow_cpu=False → EngineUnavailable.
- contribute() returns Dict[Axis, List[PollutionSource]] with every axis key.
- Confidence gating: |raw_score| < min_confidence drops the source.
- Direction +/- preserved from sign of raw_score.
- Trivial prompt (empty/whitespace) returns empty sources without loading model.
- LabVectorStore round-trip preserves vectors exactly.
- diagnose(contributors=[lab]) integrates cleanly via the shared aggregator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from stateprobe.engines.base import EngineUnavailable, EvidenceContributor
from stateprobe.models import Axis, PollutionSource


# --------------------------------------------------------------------------
# Skip the entire file gracefully when torch isn't installed (CI / no-GPU env)
# --------------------------------------------------------------------------

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from stateprobe.engines.lab import (  # noqa: E402  (after importorskip)
    DEFAULT_VECTORS_PATH,
    LabContributor,
    MIN_LAB_CONFIDENCE,
    _weight_from_raw,
)
from stateprobe.lab.cache import LabVectorStore  # noqa: E402


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

HIDDEN_DIM = 16


def _make_store(
    tmp_path: Path,
    axes_and_vectors: Dict[Axis, "torch.Tensor"],
    model_name: str = "mock-model",
    layer: int = -1,
) -> Path:
    """Write a LabVectorStore .pt file with the provided per-axis vectors."""
    store = LabVectorStore(
        model_name=model_name,
        layer=layer,
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
        built_at=LabVectorStore.now_iso(),
        pair_counts={ax.value: 3 for ax in axes_and_vectors},
        vectors={ax.value: vec.cpu().float() for ax, vec in axes_and_vectors.items()},
    )
    path = tmp_path / "store.pt"
    store.save(str(path))
    return path


def _patch_lab_internals(
    monkeypatch,
    activations_per_prompt: Dict[str, "torch.Tensor"],
):
    """Replace the heavy model-load + extract_activation with deterministic stubs.

    `activations_per_prompt` maps a prompt string to the hidden state vector
    that extract_activation should return.
    """
    from stateprobe.engines import lab as lab_module
    from stateprobe.lab import probe as probe_module

    def fake_load_model_and_tokenizer(model_name=None, device=None, **kwargs):
        return ("FAKE_MODEL", "FAKE_TOKENIZER", "cpu")

    def fake_extract_activation(prompt, model, tokenizer, layer=-1, device=None):
        if prompt not in activations_per_prompt:
            raise AssertionError(
                f"test bug: no fake activation for prompt {prompt!r}"
            )
        return activations_per_prompt[prompt].clone()

    monkeypatch.setattr(
        lab_module, "_load_model", lambda self: None, raising=False
    )
    # Override LabContributor._load_model on instances by monkeypatching class.
    monkeypatch.setattr(
        LabContributor, "_load_model", lambda self: None
    )
    # Override the internal extraction via the probe module:
    monkeypatch.setattr(probe_module, "load_model_and_tokenizer", fake_load_model_and_tokenizer)
    monkeypatch.setattr(probe_module, "extract_activation", fake_extract_activation)


# --------------------------------------------------------------------------
# Vector store round-trip
# --------------------------------------------------------------------------

def test_lab_vector_store_round_trip(tmp_path):
    vec_a = torch.randn(HIDDEN_DIM)
    vec_b = torch.randn(HIDDEN_DIM)
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec_a, Axis.REASONING_BUDGET: vec_b})
    store = LabVectorStore.load(str(path))
    assert store.model_name == "mock-model"
    assert store.layer == -1
    assert torch.allclose(store.get(Axis.SYCOPHANCY), vec_a)
    assert torch.allclose(store.get(Axis.REASONING_BUDGET), vec_b)
    # Axes() returns only recognized Axis values
    assert Axis.SYCOPHANCY in store.axes()
    assert Axis.REASONING_BUDGET in store.axes()


def test_lab_vector_store_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        LabVectorStore.load(str(tmp_path / "does_not_exist.pt"))


# --------------------------------------------------------------------------
# LabContributor: protocol, init, errors
# --------------------------------------------------------------------------

def test_lab_contributor_implements_protocol(tmp_path, monkeypatch):
    vec = torch.randn(HIDDEN_DIM)
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})
    _patch_lab_internals(monkeypatch, activations_per_prompt={})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    assert isinstance(lab, EvidenceContributor)
    assert lab.name == "lab"


def test_lab_contributor_missing_vectors_raises_unavailable(tmp_path, monkeypatch):
    _patch_lab_internals(monkeypatch, activations_per_prompt={})
    with pytest.raises(EngineUnavailable, match="not found|missing"):
        LabContributor(vectors_path=str(tmp_path / "no.pt"))


def test_lab_contributor_no_cuda_raises_at_init_not_at_contribute(tmp_path, monkeypatch):
    """Regression: CUDA-unavailable must surface at __init__, not silently
    inside detect_readings on first contribute().

    Before v0.3 release this was only checked inside _load_model() (called
    lazily from contribute()); the EngineUnavailable would be silently
    swallowed by detect_readings, leaving --lab-augment as an invisible
    no-op. The fix moved the cheap env check into __init__.
    """
    import torch as _torch

    vec = torch.zeros(HIDDEN_DIM); vec[0] = 1.0
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})
    # Pretend CUDA is unavailable, even if it really is on this machine.
    monkeypatch.setattr(_torch.cuda, "is_available", lambda: False)
    with pytest.raises(EngineUnavailable, match="CUDA"):
        LabContributor(vectors_path=str(path), allow_cpu=False)


def test_lab_contributor_allow_cpu_bypasses_cuda_check(tmp_path, monkeypatch):
    """allow_cpu=True keeps tests runnable on no-GPU CI machines."""
    import torch as _torch

    vec = torch.zeros(HIDDEN_DIM); vec[0] = 1.0
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})
    monkeypatch.setattr(_torch.cuda, "is_available", lambda: False)
    # Must NOT raise — allow_cpu opt-in is the documented escape hatch.
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    assert lab.name == "lab"


def test_lab_contributor_missing_transformers_raises_at_init(tmp_path, monkeypatch):
    """Regression: missing transformers must surface at __init__ too, not
    silently inside the lazy _load_model() path.

    Same UX gap as no-CUDA — fixed by routing _check_runtime() through
    stateprobe.lab.probe.dependency_status() which already inspects both
    torch and transformers availability.
    """
    from stateprobe.lab import probe as probe_module
    from stateprobe.lab.probe import LabDependencyStatus

    vec = torch.zeros(HIDDEN_DIM); vec[0] = 1.0
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})

    # Pretend torch is fine but transformers is missing.
    monkeypatch.setattr(
        probe_module,
        "dependency_status",
        lambda: LabDependencyStatus(torch_available=True, transformers_available=False),
    )
    with pytest.raises(EngineUnavailable, match="transformers"):
        LabContributor(vectors_path=str(path), allow_cpu=True)


def test_lab_contributor_eager_surfaces_model_load_failure_at_init(tmp_path, monkeypatch):
    """The lazy=False (eager) construction path must surface model-load
    failures at __init__, not lazily on first contribute().

    Contract for the CLI's --lab-eager flag: HF download / model-load
    failure shows up as EngineUnavailable that the CLI's try/except can
    turn into a yellow panel, instead of leaking out as a RuntimeWarning
    inside detect_readings on the first diagnosis.

    Compare to the default lazy=True path: same failure must NOT raise
    at __init__ (the contributor stays constructable, fails only on
    contribute()).
    """
    vec = torch.zeros(HIDDEN_DIM); vec[0] = 1.0
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})

    def fake_load_model_failing(self):
        raise EngineUnavailable(
            "LabContributor: model load failed: simulated HF download timeout"
        )

    monkeypatch.setattr(LabContributor, "_load_model", fake_load_model_failing)

    # lazy=True (default): failure deferred — __init__ succeeds.
    lab_lazy = LabContributor(vectors_path=str(path), allow_cpu=True, lazy=True)
    assert lab_lazy.name == "lab"

    # lazy=False (eager): failure surfaces at __init__ with the model-load
    # message the CLI's hint matcher keys on.
    with pytest.raises(EngineUnavailable, match="model load failed"):
        LabContributor(vectors_path=str(path), allow_cpu=True, lazy=False)


def test_lab_contributor_empty_prompt_returns_empty_sources(tmp_path, monkeypatch):
    vec = torch.randn(HIDDEN_DIM)
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})
    _patch_lab_internals(monkeypatch, activations_per_prompt={})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    out = lab.contribute("")
    assert set(out.keys()) == set(Axis)
    assert all(v == [] for v in out.values())
    out2 = lab.contribute("   \n\t  ")
    assert all(v == [] for v in out2.values())


# --------------------------------------------------------------------------
# LabContributor: projection logic
# --------------------------------------------------------------------------

def test_lab_contributor_emits_source_when_aligned(tmp_path, monkeypatch):
    """Prompt activation aligned with axis vector → positive direction source."""
    axis_vec = torch.zeros(HIDDEN_DIM)
    axis_vec[0] = 1.0  # axis points along e_0
    activation = torch.zeros(HIDDEN_DIM)
    activation[0] = 1.0  # exactly aligned → cosine = 1.0
    activation[1] = 0.01  # tiny noise so vector isn't exactly unit
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: axis_vec})
    _patch_lab_internals(monkeypatch, activations_per_prompt={"aligned": activation})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    out = lab.contribute("aligned")
    assert len(out[Axis.SYCOPHANCY]) == 1
    src = out[Axis.SYCOPHANCY][0]
    assert isinstance(src, PollutionSource)
    assert src.axis is Axis.SYCOPHANCY
    assert src.direction == +1
    assert src.rule_id == "lab:sycophancy"
    assert src.confidence > 0.9  # near 1.0
    # Other axes have no vector → empty
    assert out[Axis.REASONING_BUDGET] == []


def test_lab_contributor_emits_negative_direction_when_opposed(tmp_path, monkeypatch):
    axis_vec = torch.zeros(HIDDEN_DIM)
    axis_vec[0] = 1.0
    activation = torch.zeros(HIDDEN_DIM)
    activation[0] = -1.0  # opposite direction → cosine = -1.0
    activation[1] = 0.01
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: axis_vec})
    _patch_lab_internals(monkeypatch, activations_per_prompt={"opposed": activation})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    out = lab.contribute("opposed")
    assert len(out[Axis.SYCOPHANCY]) == 1
    assert out[Axis.SYCOPHANCY][0].direction == -1


def test_lab_contributor_drops_low_confidence(tmp_path, monkeypatch):
    """A near-orthogonal activation should be silently dropped (below MIN_LAB_CONFIDENCE)."""
    axis_vec = torch.zeros(HIDDEN_DIM)
    axis_vec[0] = 1.0
    activation = torch.zeros(HIDDEN_DIM)
    activation[5] = 1.0  # orthogonal → cosine ≈ 0
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: axis_vec})
    _patch_lab_internals(monkeypatch, activations_per_prompt={"weak": activation})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    out = lab.contribute("weak")
    assert out[Axis.SYCOPHANCY] == []


def test_lab_contributor_projects_multiple_axes_in_one_pass(tmp_path, monkeypatch):
    """One activation → projections onto every axis vector in the store."""
    vec_a = torch.zeros(HIDDEN_DIM); vec_a[0] = 1.0
    vec_b = torch.zeros(HIDDEN_DIM); vec_b[3] = 1.0
    activation = torch.zeros(HIDDEN_DIM)
    activation[0] = 0.6   # somewhat aligned with vec_a
    activation[3] = -0.8  # opposed to vec_b
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec_a, Axis.REASONING_BUDGET: vec_b})
    _patch_lab_internals(monkeypatch, activations_per_prompt={"mixed": activation})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    out = lab.contribute("mixed")
    assert len(out[Axis.SYCOPHANCY]) == 1
    assert out[Axis.SYCOPHANCY][0].direction == +1
    assert len(out[Axis.REASONING_BUDGET]) == 1
    assert out[Axis.REASONING_BUDGET][0].direction == -1


def test_lab_contributor_returns_every_axis_as_key(tmp_path, monkeypatch):
    """Per EvidenceContributor protocol, every Axis must be a dict key."""
    vec = torch.zeros(HIDDEN_DIM); vec[0] = 1.0
    activation = torch.zeros(HIDDEN_DIM); activation[0] = 1.0; activation[1] = 0.01
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})
    _patch_lab_internals(monkeypatch, activations_per_prompt={"x": activation})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    out = lab.contribute("x")
    assert set(out.keys()) == set(Axis)


# --------------------------------------------------------------------------
# Weight mapping
# --------------------------------------------------------------------------

def test_weight_from_raw_monotone_and_bounded():
    assert _weight_from_raw(0.0) == pytest.approx(0.5)
    assert 0.5 < _weight_from_raw(0.25) < _weight_from_raw(0.5)
    assert _weight_from_raw(1.0) > 0.95
    assert _weight_from_raw(-1.0) == _weight_from_raw(1.0)  # symmetric on |raw|


# --------------------------------------------------------------------------
# Integration with diagnose() shared aggregator
# --------------------------------------------------------------------------

def test_lab_contributor_integrates_with_diagnose(tmp_path, monkeypatch):
    """diagnose(contributors=[lab]) produces a Report with lab-sourced readings."""
    from stateprobe.detector import diagnose

    vec = torch.zeros(HIDDEN_DIM); vec[0] = 1.0
    activation = torch.zeros(HIDDEN_DIM); activation[0] = 1.0; activation[1] = 0.01
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})
    _patch_lab_internals(monkeypatch, activations_per_prompt={"hello world": activation})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    report = diagnose("hello world", contributors=[lab])
    # The reading should have a lab-sourced PollutionSource
    sycophancy_reading = report.readings[Axis.SYCOPHANCY]
    lab_sources = [
        s for s in sycophancy_reading.contributing_sources
        if s.rule_id.startswith("lab:")
    ]
    assert len(lab_sources) >= 1


# --------------------------------------------------------------------------
# project_prompt helper (for `stateprobe lab-probe` subcommand)
# --------------------------------------------------------------------------

def test_lab_contributor_project_prompt_returns_raw_scores(tmp_path, monkeypatch):
    vec = torch.zeros(HIDDEN_DIM); vec[0] = 1.0
    activation = torch.zeros(HIDDEN_DIM); activation[0] = 0.7; activation[1] = 0.01
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})
    _patch_lab_internals(monkeypatch, activations_per_prompt={"x": activation})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    scores = lab.project_prompt("x")
    assert Axis.SYCOPHANCY in scores
    assert scores[Axis.SYCOPHANCY] > 0.5  # ~0.7 / 0.7 ≈ 1.0 actually


def test_lab_contributor_project_prompt_empty_returns_empty(tmp_path, monkeypatch):
    vec = torch.zeros(HIDDEN_DIM); vec[0] = 1.0
    path = _make_store(tmp_path, {Axis.SYCOPHANCY: vec})
    _patch_lab_internals(monkeypatch, activations_per_prompt={})
    lab = LabContributor(vectors_path=str(path), allow_cpu=True)
    assert lab.project_prompt("") == {}
    assert lab.project_prompt("   ") == {}
