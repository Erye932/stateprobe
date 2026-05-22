"""StateProbe Enterprise — Runtime Probe (placeholder only).

This package reserves the directory and import path for the future
enterprise Runtime Probe line. Nothing is implemented yet.

See `docs/ENTERPRISE_RUNTIME_PROBE.md` for direction, non-goals,
and the relationship to the Skill line and the existing Lab layer.

Any attempt to use the public Runtime Probe API at this stage raises
`NotImplementedError` on purpose, so accidental imports during early
prototyping fail loudly instead of silently shipping a half-built layer.
"""

from __future__ import annotations


__all__ = ["RuntimeProbe"]


class RuntimeProbe:
    """Placeholder for the future enterprise Runtime Probe.

    The real implementation is not in this release. This stub exists
    only to reserve the public name and to make any premature usage
    obvious during code review.
    """

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "StateProbe Enterprise Runtime Probe is not implemented yet. "
            "See docs/ENTERPRISE_RUNTIME_PROBE.md for the planned scope."
        )
