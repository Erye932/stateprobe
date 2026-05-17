"""Experimental DeepSeek-aligned hidden-state probing utilities."""

from stateprobe.lab.deepseek_pairs import DEEPSEEK_AXIS_PAIRS, DEFAULT_DEEPSEEK_MODEL
from stateprobe.lab.probe import dependency_status

__all__ = [
    "DEEPSEEK_AXIS_PAIRS",
    "DEFAULT_DEEPSEEK_MODEL",
    "dependency_status",
]
