"""Persistence for pre-computed axis vectors.

LabVectorStore packs the axis vectors built by build_axis_vector() along
with metadata needed for reproducibility and version checking. Vectors are
serialized as a torch state dict on disk.

The cache is built once via scripts/build_lab_vectors.py and loaded at
runtime by LabContributor. This avoids re-running the contrastive prompts
through the model every time a user invokes `stateprobe check`.

Schema versioning: future revisions (e.g., v0.4 with MoE routing) bump
SCHEMA_VERSION; older stores can still load if back-compat code paths exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from stateprobe.models import Axis


SCHEMA_VERSION = 1


@dataclass
class LabVectorStore:
    """Serializable container for pre-computed axis direction vectors.

    Attributes:
        schema_version: Bumped when the on-disk format changes.
        model_name: HF identifier of the model used to build vectors.
        layer: Which transformer layer's hidden state was used (-1 = last).
        torch_version: torch.__version__ at build time (compatibility check).
        transformers_version: transformers.__version__ at build time.
        built_at: ISO8601 timestamp.
        pair_counts: axis_value -> number of contrastive pairs averaged.
        vectors: axis_value -> torch.Tensor of shape (hidden_dim,).
    """

    model_name: str
    layer: int
    torch_version: str
    transformers_version: str
    built_at: str
    pair_counts: Dict[str, int] = field(default_factory=dict)
    vectors: Dict[str, object] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def now_iso(cls) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"

    @classmethod
    def from_axis_vectors(
        cls,
        axis_vectors: Dict[Axis, "object"],
        model_name: str,
    ) -> "LabVectorStore":
        """Build a store from a dict of AxisVector objects (as returned by
        build_deepseek_vectors())."""
        # Lazy imports so the module loads without torch / transformers.
        import torch
        import transformers

        if not axis_vectors:
            raise ValueError("Cannot build LabVectorStore from empty axis_vectors")

        layers = {av.layer for av in axis_vectors.values()}
        if len(layers) != 1:
            raise ValueError(
                f"All axis vectors must use the same layer; got {layers}"
            )
        layer = next(iter(layers))

        vectors: Dict[str, object] = {}
        pair_counts: Dict[str, int] = {}
        for axis, av in axis_vectors.items():
            vectors[axis.value] = av.vector.detach().cpu().float()
            pair_counts[axis.value] = av.positive_count

        return cls(
            model_name=model_name,
            layer=layer,
            torch_version=torch.__version__,
            transformers_version=transformers.__version__,
            built_at=cls.now_iso(),
            pair_counts=pair_counts,
            vectors=vectors,
        )

    def save(self, path: str) -> None:
        """Write the store to disk as a torch state dict."""
        import torch

        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.schema_version,
            "model_name": self.model_name,
            "layer": self.layer,
            "torch_version": self.torch_version,
            "transformers_version": self.transformers_version,
            "built_at": self.built_at,
            "pair_counts": self.pair_counts,
            "vectors": self.vectors,
        }
        torch.save(payload, str(path_obj))

    @classmethod
    def load(cls, path: str) -> "LabVectorStore":
        """Load a store from disk. Raises FileNotFoundError if path missing."""
        import torch

        path_obj = Path(path)
        if not path_obj.is_file():
            raise FileNotFoundError(
                f"LabVectorStore file not found: {path}. "
                f"Build with: python scripts/build_lab_vectors.py"
            )
        payload = torch.load(str(path_obj), map_location="cpu", weights_only=False)
        version = payload.get("schema_version", 0)
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"LabVectorStore at {path} has schema_version={version} "
                f"newer than supported {SCHEMA_VERSION}. Upgrade stateprobe."
            )
        return cls(
            model_name=payload["model_name"],
            layer=payload["layer"],
            torch_version=payload["torch_version"],
            transformers_version=payload["transformers_version"],
            built_at=payload["built_at"],
            pair_counts=payload.get("pair_counts", {}),
            vectors=payload.get("vectors", {}),
            schema_version=version,
        )

    def get(self, axis: Axis) -> Optional[object]:
        """Return the torch.Tensor for axis, or None if not in this store."""
        return self.vectors.get(axis.value)

    def axes(self):
        """Return the set of Axis values present in this store."""
        out = set()
        for v in self.vectors.keys():
            try:
                out.add(Axis(v))
            except ValueError:
                continue
        return out

    def summary(self) -> str:
        lines = [
            f"LabVectorStore (schema v{self.schema_version})",
            f"  model:        {self.model_name}",
            f"  layer:        {self.layer}",
            f"  built_at:     {self.built_at}",
            f"  torch:        {self.torch_version}",
            f"  transformers: {self.transformers_version}",
            f"  axes ({len(self.vectors)}):",
        ]
        for axis_value, vec in self.vectors.items():
            shape = tuple(vec.shape) if hasattr(vec, "shape") else "?"
            pairs = self.pair_counts.get(axis_value, "?")
            lines.append(f"    - {axis_value:<20} shape={shape} pairs={pairs}")
        return "\n".join(lines)
