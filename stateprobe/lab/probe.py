"""Experimental hidden-state probe for open-weight DeepSeek-style models.

This module is optional. It only works when the `lab` extra is installed and
when model weights are available locally or can be downloaded from Hugging Face.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import math

from stateprobe.models import Axis
from stateprobe.lab.deepseek_pairs import (
    DEFAULT_DEEPSEEK_MODEL,
    ContrastivePair,
    DEEPSEEK_AXIS_PAIRS,
)


@dataclass(frozen=True)
class LabDependencyStatus:
    torch_available: bool
    transformers_available: bool

    @property
    def ready(self) -> bool:
        return self.torch_available and self.transformers_available

    @property
    def install_hint(self) -> str:
        return 'pip install -e ".[lab]"'


@dataclass
class AxisVector:
    axis: Axis
    layer: int
    vector: object
    positive_count: int
    negative_count: int


@dataclass
class ProjectionResult:
    axis: Axis
    raw_score: float
    normalized_score: float
    layer: int


def dependency_status() -> LabDependencyStatus:
    try:
        import torch  # noqa: F401
        torch_ok = True
    except ImportError:
        torch_ok = False

    try:
        import transformers  # noqa: F401
        transformers_ok = True
    except ImportError:
        transformers_ok = False

    return LabDependencyStatus(
        torch_available=torch_ok,
        transformers_available=transformers_ok,
    )


def require_lab_dependencies() -> None:
    status = dependency_status()
    if not status.ready:
        missing = []
        if not status.torch_available:
            missing.append("torch")
        if not status.transformers_available:
            missing.append("transformers")
        raise RuntimeError(
            "StateProbe Lab requires optional dependencies: "
            + ", ".join(missing)
            + f". Install with: {status.install_hint}"
        )


def _resolve_model_path(model_name: str) -> str:
    """Resolve the model identifier, honoring STATEPROBE_LAB_MODEL_PATH override.

    Use cases:
    - HF Hub access blocked / rate-limited → pre-download via ModelScope into
      a local directory and set STATEPROBE_LAB_MODEL_PATH to that directory.
    - Custom snapshots / fine-tunes → point to local fine-tuned weights.

    The override takes effect only if the env var is set AND points to an
    existing directory; otherwise the original `model_name` is returned and
    transformers will resolve it through HF Hub as usual.
    """
    import os
    override = os.environ.get("STATEPROBE_LAB_MODEL_PATH")
    if override and os.path.isdir(override):
        return override
    return model_name


def load_model_and_tokenizer(
    model_name: str = DEFAULT_DEEPSEEK_MODEL,
    device: Optional[str] = None,
    local_files_only: bool = False,
):
    require_lab_dependencies()
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # STATEPROBE_LAB_MODEL_PATH override (ModelScope-downloaded snapshot etc.)
    resolved = _resolve_model_path(model_name)

    tokenizer = AutoTokenizer.from_pretrained(
        resolved,
        trust_remote_code=True,
        local_files_only=local_files_only,
    )
    # `dtype=` replaces the deprecated `torch_dtype=` in transformers >= 5.0.
    # Fall back to torch_dtype for transformers 4.x compatibility.
    dtype = torch.float16 if device == "cuda" else torch.float32
    try:
        model = AutoModelForCausalLM.from_pretrained(
            resolved,
            trust_remote_code=True,
            dtype=dtype,
            local_files_only=local_files_only,
        )
    except TypeError:
        # transformers < 5.0 uses torch_dtype.
        model = AutoModelForCausalLM.from_pretrained(
            resolved,
            trust_remote_code=True,
            torch_dtype=dtype,
            local_files_only=local_files_only,
        )
    model.to(device)
    model.eval()
    return model, tokenizer, device


def extract_activation(
    prompt: str,
    model,
    tokenizer,
    layer: int = -1,
    device: Optional[str] = None,
):
    require_lab_dependencies()
    import torch

    if device is None:
        device = next(model.parameters()).device

    encoded = tokenizer(prompt, return_tensors="pt")
    encoded = {k: v.to(device) for k, v in encoded.items()}

    with torch.no_grad():
        outputs = model(
            **encoded,
            output_hidden_states=True,
            return_dict=True,
        )

    hidden = outputs.hidden_states[layer]
    return hidden[:, -1, :].detach().float().squeeze(0).cpu()


def build_axis_vector(
    axis: Axis,
    pairs: Iterable[ContrastivePair],
    model,
    tokenizer,
    layer: int = -1,
    device: Optional[str] = None,
) -> AxisVector:
    require_lab_dependencies()
    import torch

    positive_vectors = []
    negative_vectors = []

    for pair in pairs:
        positive_vectors.append(
            extract_activation(pair.positive, model, tokenizer, layer=layer, device=device)
        )
        negative_vectors.append(
            extract_activation(pair.negative, model, tokenizer, layer=layer, device=device)
        )

    if not positive_vectors or not negative_vectors:
        raise ValueError(f"No contrastive pairs provided for axis {axis.value}")

    pos_mean = torch.stack(positive_vectors).mean(dim=0)
    neg_mean = torch.stack(negative_vectors).mean(dim=0)
    vector = pos_mean - neg_mean

    return AxisVector(
        axis=axis,
        layer=layer,
        vector=vector,
        positive_count=len(positive_vectors),
        negative_count=len(negative_vectors),
    )


def cosine_projection(activation, axis_vector: AxisVector) -> ProjectionResult:
    require_lab_dependencies()
    import torch

    a = activation.float()
    b = axis_vector.vector.float()
    denom = torch.norm(a) * torch.norm(b)
    raw = 0.0 if denom.item() == 0.0 else torch.dot(a, b).item() / denom.item()
    normalized = 1.0 / (1.0 + math.exp(-4.0 * raw))
    return ProjectionResult(
        axis=axis_vector.axis,
        raw_score=raw,
        normalized_score=normalized,
        layer=axis_vector.layer,
    )


def build_deepseek_vectors(
    model,
    tokenizer,
    axes: Optional[List[Axis]] = None,
    layer: int = -1,
    device: Optional[str] = None,
) -> Dict[Axis, AxisVector]:
    selected_axes = axes or list(DEEPSEEK_AXIS_PAIRS.keys())
    vectors: Dict[Axis, AxisVector] = {}
    for axis in selected_axes:
        vectors[axis] = build_axis_vector(
            axis=axis,
            pairs=DEEPSEEK_AXIS_PAIRS[axis],
            model=model,
            tokenizer=tokenizer,
            layer=layer,
            device=device,
        )
    return vectors


def project_prompt(
    prompt: str,
    axis_vectors: Dict[Axis, AxisVector],
    model,
    tokenizer,
    layer: int = -1,
    device: Optional[str] = None,
) -> Dict[Axis, ProjectionResult]:
    activation = extract_activation(prompt, model, tokenizer, layer=layer, device=device)
    return {
        axis: cosine_projection(activation, vector)
        for axis, vector in axis_vectors.items()
    }
