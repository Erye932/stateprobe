"""Lab activation-projection contributor (v0.3+).

Per ADR_009 and ADR_010, this contributor reads the hidden state of a
DeepSeek-family model and projects the activation onto pre-built axis
direction vectors (Persona Vectors method, Anthropic arXiv:2507.21509).

Compared to LLMJudgeContributor:
- No API call. Runs locally on GPU.
- Confidence is a sigmoid-calibrated mapping of cosine-projection magnitude
  (see _confidence_from_raw + docs/archive/v0.3/TECHNICAL.md §6.4 for the calibration
  rationale), not a self-reported number from an LLM.
- Initialization is expensive (loads transformer model, ~10-30s). The
  contributor is designed to be created once per process and reused.

Failure modes (all surface at construction time except model-load):
- vectors_path missing → EngineUnavailable (raised by _load_store in __init__).
- torch / transformers import error → EngineUnavailable (raised by
  _check_runtime in __init__, via stateprobe.lab.probe.dependency_status).
- CUDA unavailable → EngineUnavailable (raised by _check_runtime in __init__).
- HF download / model load error → EngineUnavailable (raised by _load_model on
  first contribute(), or eagerly when lazy=False).

The cheap environment checks (torch + transformers importable, CUDA presence)
run eagerly in __init__ so the CLI's existing try/except surfaces a yellow
warning panel immediately, instead of the contributor silently no-op-ing
inside detect_readings on first contribute(). The expensive transformer load
stays lazy so non-CUDA users importing the module pay nothing.

CI / pre-flight callers who want HF-download / model-load failure to *also*
surface at construction (rather than as a deferred RuntimeWarning inside
detect_readings) can pass lazy=False, which is what the CLI's --lab-eager
flag does. Default lazy=True preserves fast startup for the common case.

This module deliberately does NOT import torch / transformers at the top
level so importing stateprobe.engines.lab is cheap and never fails because
of missing optional dependencies. Heavy imports happen inside methods.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from stateprobe.engines.base import EngineUnavailable, EvidenceContributor
from stateprobe.models import Axis, ModelBaseline, PollutionSource


DEFAULT_VECTORS_PATH = "lab_vectors/r1_distill_1.5b_v1.pt"


# Sources with |raw_score| below this threshold are silently dropped.
# Rationale (see docs/archive/v0.3/TECHNICAL.md §6.4 for the calibration story):
# - For hidden_dim = 1536, two random unit vectors have expected cosine
#   |c| ~ 1/sqrt(1536) ≈ 0.025 (gaussian-ish around zero).
# - 0.10 ≈ 4× the random-vector noise floor — a robust signal-to-noise margin.
# - Empirically calibrated on R1-Distill-Qwen-1.5B with 5 example prompts:
#   the original 0.15 dropped meaningful signals (e.g., good_calm_reasoning
#   projects sycophancy at -0.227, but task_width signals topped out at 0.278
#   only on the strongest persona-laden prompt). 0.10 captures useful cases
#   like sycophancy (3/5 active) while still gating noise.
# - Larger frontier models would tolerate a higher threshold (Persona Vectors
#   paper used Claude-scale models). On distilled 1.5B we accept slightly
#   noisier sources in exchange for non-trivial coverage.
MIN_LAB_CONFIDENCE = 0.10


def _weight_from_raw(raw: float) -> float:
    """Map cosine raw_score (-1, +1) to weight in roughly [0.5, 1.0].

    Uses sigmoid(4 * |raw|): a |raw| of 0.25 yields ~0.73, 0.5 yields ~0.88,
    matching the intuition that magnitude reflects pressure strength.
    """
    abs_raw = abs(raw)
    return 1.0 / (1.0 + math.exp(-4.0 * abs_raw))


def _confidence_from_raw(raw: float) -> float:
    """Map cosine raw_score to a [0, 1] confidence the aggregator can accept.

    The aggregator filters out sources with confidence < MIN_AGGREGATE_CONFIDENCE
    (0.30) — a raw |cosine| of 0.10 in a 1536-dim space is a meaningful signal
    (4× the random noise floor), but its naive |raw| = 0.10 would be dropped.

    Sigmoid centered at the "weak signal" threshold (0.15):
    - |raw| = 0.05  →  confidence ≈ 0.27  (noise-ish, may be dropped)
    - |raw| = 0.10  →  confidence ≈ 0.38  (passes aggregator)
    - |raw| = 0.15  →  confidence ≈ 0.50
    - |raw| = 0.25  →  confidence ≈ 0.73
    - |raw| = 0.40  →  confidence ≈ 0.92

    This decouples LabContributor's signal-to-noise judgement from the
    aggregator's threshold — the contributor reports its real confidence,
    the aggregator uses its own gate.
    """
    abs_raw = abs(raw)
    return 1.0 / (1.0 + math.exp(-10.0 * (abs_raw - 0.15)))


class LabContributor:
    """Project prompt activation onto pre-built axis vectors and emit evidence.

    The model is loaded lazily on first ``contribute()`` call (or eagerly if
    ``lazy=False``). Subsequent calls reuse the loaded model.

    Per the EvidenceContributor protocol, ``contribute()`` returns
    Dict[Axis, List[PollutionSource]] where every Axis key is present (may
    map to empty list).
    """

    name = "lab"

    def __init__(
        self,
        vectors_path: str = DEFAULT_VECTORS_PATH,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        lazy: bool = True,
        min_confidence: float = MIN_LAB_CONFIDENCE,
        allow_cpu: bool = False,
    ):
        """
        Args:
            vectors_path:    Pre-computed axis vectors file. Build with
                             scripts/build_lab_vectors.py.
            model_name:      HF model identifier. Default uses store metadata
                             so the model matches the vectors.
            device:          "cuda" / "cpu" / None (auto-detect).
            lazy:            If True (default), model is loaded on first
                             contribute() call.
            min_confidence:  Sources with |raw_score| below this are dropped.
            allow_cpu:       Permit CPU fallback (tests only — production is
                             too slow on CPU).

        Raises:
            EngineUnavailable: vectors file missing, store schema mismatch,
                               torch not installed, or CUDA unavailable
                               when allow_cpu=False. All these surface at
                               construction time so the CLI can show a clear
                               warning instead of the contributor silently
                               no-op-ing during detect_readings.
        """
        self.vectors_path = vectors_path
        self.model_name = model_name
        self.device = device
        self.min_confidence = min_confidence
        self.allow_cpu = allow_cpu

        # Heavy resources (loaded on demand):
        self._store: Any = None
        self._model: Any = None
        self._tokenizer: Any = None
        self._resolved_device: Optional[str] = None
        self._axis_vectors: Dict[Axis, Any] = {}

        # Validate the vectors file exists and can be parsed (lightweight).
        # This catches the most common "forgot to run build" failure early.
        self._load_store()

        # Cheap environment check (torch importable + CUDA available unless
        # allow_cpu). Runs eagerly so the CLI's try/except sees the failure
        # at construction time instead of the contributor silently dropping
        # in detect_readings on the first contribute() call.
        self._check_runtime()

        if not lazy:
            self._load_model()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_store(self) -> None:
        """Load the pre-computed axis vectors. No torch model load yet."""
        # Lazy: only fail at first use, not at import.
        try:
            from stateprobe.lab.cache import LabVectorStore
        except ImportError as exc:
            raise EngineUnavailable(
                f"LabContributor: stateprobe.lab.cache unavailable: {exc}"
            ) from exc

        try:
            store = LabVectorStore.load(self.vectors_path)
        except FileNotFoundError as exc:
            raise EngineUnavailable(str(exc)) from exc
        except Exception as exc:
            raise EngineUnavailable(
                f"LabContributor: failed to load {self.vectors_path}: {exc}"
            ) from exc

        if not store.vectors:
            raise EngineUnavailable(
                f"LabContributor: store at {self.vectors_path} contains no vectors"
            )

        # Build per-Axis lookup for fast contribute() calls.
        axis_vectors: Dict[Axis, Any] = {}
        for axis_value, tensor in store.vectors.items():
            try:
                axis = Axis(axis_value)
            except ValueError:
                # Unknown axis (older stateprobe vs newer store, or typo).
                # Skip silently; the contributor still works for known axes.
                continue
            axis_vectors[axis] = tensor

        if not axis_vectors:
            raise EngineUnavailable(
                f"LabContributor: store has no recognized axes "
                f"(found: {list(store.vectors.keys())})"
            )

        self._store = store
        self._axis_vectors = axis_vectors

        # Pick model name from store if not explicitly overridden.
        if self.model_name is None:
            self.model_name = store.model_name

    def _check_runtime(self) -> None:
        """Cheap environment check: lab deps importable + CUDA available.

        Called eagerly from __init__ so the CLI surfaces these failures via
        its existing try/except instead of detect_readings silently dropping
        the contributor on the first contribute() call.

        Covers torch AND transformers (via stateprobe.lab.probe.dependency_status)
        so missing transformers also surfaces eagerly, not lazily inside
        _load_model().

        Does NOT load the transformer model — that stays lazy in _load_model().
        """
        try:
            from stateprobe.lab.probe import dependency_status
        except ImportError as exc:
            # stateprobe.lab.probe itself failing to import means a deeper
            # packaging problem; treat as unavailable rather than crashing.
            raise EngineUnavailable(
                f"LabContributor: stateprobe.lab.probe unavailable: {exc}. "
                f"Install: pip install -e \".[lab]\""
            ) from exc

        status = dependency_status()
        if not status.ready:
            missing = []
            if not status.torch_available:
                missing.append("torch")
            if not status.transformers_available:
                missing.append("transformers")
            raise EngineUnavailable(
                f"LabContributor: optional lab dependencies missing: "
                f"{', '.join(missing)}. Install: {status.install_hint}"
            )

        # torch is now guaranteed importable — safe to inspect CUDA state.
        import torch
        if not self.allow_cpu and not torch.cuda.is_available():
            raise EngineUnavailable(
                "LabContributor: CUDA not available. Lab 层需要 GPU; "
                "CPU is too slow for production use. Omit --lab-augment to "
                "run static (+ optional LLM) layers only, or pass "
                "allow_cpu=True for tests."
            )

    def _load_model(self) -> None:
        """Lazy-load the transformer model on first contribute() call.

        torch + CUDA availability are already verified by _check_runtime()
        at construction time; this method only handles the expensive load.
        """
        if self._model is not None:
            return

        try:
            from stateprobe.lab.probe import load_model_and_tokenizer
        except ImportError as exc:
            raise EngineUnavailable(
                f"LabContributor: stateprobe.lab.probe unavailable: {exc}"
            ) from exc

        try:
            model, tokenizer, resolved_device = load_model_and_tokenizer(
                model_name=self.model_name,
                device=self.device,
            )
        except Exception as exc:
            raise EngineUnavailable(
                f"LabContributor: model load failed: {exc}. "
                f"Hint: set STATEPROBE_LAB_MODEL_PATH to a local snapshot if "
                f"the HF download is blocked."
            ) from exc

        self._model = model
        self._tokenizer = tokenizer
        self._resolved_device = resolved_device

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _extract_activation(self, prompt: str) -> Any:
        """Forward pass; return last-token hidden state at the store's layer."""
        from stateprobe.lab.probe import extract_activation

        return extract_activation(
            prompt=prompt,
            model=self._model,
            tokenizer=self._tokenizer,
            layer=self._store.layer,
            device=self._resolved_device,
        )

    def _project(self, activation: Any, axis_vector: Any) -> float:
        """Cosine projection of activation onto axis_vector. Returns raw_score."""
        import torch

        a = activation.float()
        b = axis_vector.float()
        denom = torch.norm(a).item() * torch.norm(b).item()
        if denom == 0.0:
            return 0.0
        return float(torch.dot(a, b).item() / denom)

    # ------------------------------------------------------------------
    # EvidenceContributor protocol
    # ------------------------------------------------------------------

    def contribute(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline] = None,
    ) -> Dict[Axis, List[PollutionSource]]:
        sources_by_axis: Dict[Axis, List[PollutionSource]] = {
            axis: [] for axis in Axis
        }
        if not prompt or not prompt.strip():
            return sources_by_axis

        # Lazy-load on first call.
        self._load_model()

        # One forward pass to get the activation once; project onto every axis.
        activation = self._extract_activation(prompt)

        for axis, axis_vec in self._axis_vectors.items():
            raw_score = self._project(activation, axis_vec)
            abs_raw = abs(raw_score)
            if abs_raw < self.min_confidence:
                continue

            direction = 1 if raw_score > 0 else -1
            weight = _weight_from_raw(raw_score)
            confidence = _confidence_from_raw(raw_score)

            sources_by_axis[axis].append(
                PollutionSource(
                    rule_id=f"lab:{axis.value}",
                    axis=axis,
                    direction=direction,
                    weight=weight,
                    matched_text=f"activation projection raw={raw_score:+.4f}",
                    explanation_zh=(
                        f"在 {self.model_name} 第 {self._store.layer} 层 residual "
                        f"stream 上，prompt 激活与「{axis.label_zh}」方向 cosine "
                        f"投影 = {raw_score:+.3f}（{'推高' if direction > 0 else '推低'}）"
                    ),
                    citation=(
                        f"Persona Vectors (arXiv:2507.21509) on "
                        f"{self.model_name}; vectors built {self._store.built_at}"
                    ),
                    confidence=confidence,
                )
            )

        return sources_by_axis

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    def axes_available(self) -> List[Axis]:
        """Return the axes for which this contributor has vectors."""
        return list(self._axis_vectors.keys())

    def project_prompt(self, prompt: str) -> Dict[Axis, float]:
        """Return raw cosine score per axis. Used by lab-probe subcommand."""
        self._load_model()
        if not prompt or not prompt.strip():
            return {}
        activation = self._extract_activation(prompt)
        return {
            axis: self._project(activation, vec)
            for axis, vec in self._axis_vectors.items()
        }

    def __repr__(self) -> str:
        return (
            f"LabContributor(model={self.model_name!r}, "
            f"axes={len(self._axis_vectors)}, "
            f"loaded={self._model is not None})"
        )
