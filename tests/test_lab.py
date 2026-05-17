"""Tests for the experimental DeepSeek Lab scaffolding."""

from __future__ import annotations

from stateprobe.lab.deepseek_pairs import (
    DEFAULT_DEEPSEEK_MODEL,
    DEEPSEEK_AXIS_PAIRS,
    available_deepseek_axes,
    pairs_for_axis,
)
from stateprobe.lab.probe import dependency_status
from stateprobe.models import Axis


def test_default_deepseek_model_is_distill_qwen():
    assert DEFAULT_DEEPSEEK_MODEL == "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"


def test_deepseek_lab_has_reasoning_and_self_verification_pairs():
    assert Axis.REASONING_BUDGET in DEEPSEEK_AXIS_PAIRS
    assert Axis.SELF_VERIFICATION in DEEPSEEK_AXIS_PAIRS
    assert len(DEEPSEEK_AXIS_PAIRS[Axis.REASONING_BUDGET]) >= 2
    assert len(DEEPSEEK_AXIS_PAIRS[Axis.SELF_VERIFICATION]) >= 2


def test_all_deepseek_pairs_have_positive_negative_and_rationale():
    for axis, pairs in DEEPSEEK_AXIS_PAIRS.items():
        assert isinstance(axis, Axis)
        for pair in pairs:
            assert pair.axis is axis
            assert pair.positive.strip()
            assert pair.negative.strip()
            assert pair.rationale_zh.strip()
            assert pair.positive != pair.negative


def test_available_deepseek_axes_matches_pair_keys():
    assert set(available_deepseek_axes()) == set(DEEPSEEK_AXIS_PAIRS.keys())


def test_pairs_for_axis_returns_empty_for_unsupported_axis():
    assert pairs_for_axis(Axis.INFO_FLOW) == []


def test_dependency_status_is_safe_without_lab_extra():
    status = dependency_status()
    assert isinstance(status.torch_available, bool)
    assert isinstance(status.transformers_available, bool)
    assert isinstance(status.ready, bool)
    assert status.install_hint == 'pip install -e ".[lab]"'
