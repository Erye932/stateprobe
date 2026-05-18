"""Test the rule library is structurally valid."""

from __future__ import annotations

import re

import pytest

from stateprobe.models import Axis
from stateprobe.rules import (
    ALL_RULES,
    DEFAULT_TARGET,
    TARGET_PRESETS,
    rule_by_id,
    rules_for_axis,
)


def test_all_rules_have_unique_ids():
    ids = [r.id for r in ALL_RULES]
    assert len(ids) == len(set(ids)), f"Duplicate rule ids: {ids}"


def test_all_rules_have_valid_axis():
    for rule in ALL_RULES:
        assert isinstance(rule.axis, Axis)


def test_all_rules_have_valid_direction():
    for rule in ALL_RULES:
        assert rule.direction in (-1, 1), f"Rule {rule.id}: invalid direction"


def test_all_rules_have_valid_weight():
    for rule in ALL_RULES:
        assert 0.0 <= rule.weight <= 1.0, f"Rule {rule.id}: weight out of range"


def test_all_rule_patterns_compile():
    """Every regex pattern in the library must compile."""
    for rule in ALL_RULES:
        for pattern in rule.patterns:
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                pytest.fail(f"Rule {rule.id}: pattern {pattern!r} fails to compile: {e}")


def test_all_rules_have_non_empty_explanation():
    for rule in ALL_RULES:
        assert rule.explanation_zh.strip(), f"Rule {rule.id}: empty explanation"
        assert rule.citation.strip(), f"Rule {rule.id}: empty citation"


def test_every_axis_has_at_least_two_rules():
    """Each axis needs at least 2 rules to be useful (typically one +1 and one -1)."""
    for axis in Axis:
        axis_rules = rules_for_axis(axis)
        assert len(axis_rules) >= 2, f"Axis {axis} has only {len(axis_rules)} rule(s)"


def test_rule_by_id_lookup():
    sample = ALL_RULES[0]
    assert rule_by_id(sample.id) is sample


def test_rule_by_id_raises_for_missing():
    with pytest.raises(KeyError):
        rule_by_id("nonexistent_rule_id_xyz")


def test_all_target_presets_cover_all_axes():
    """Every preset must specify a coordinate for every axis."""
    for name, preset in TARGET_PRESETS.items():
        for axis in Axis:
            assert axis in preset.coordinates, (
                f"Preset {name} missing coordinate for {axis}"
            )


def test_target_preset_coordinates_in_range():
    for name, preset in TARGET_PRESETS.items():
        for axis, val in preset.coordinates.items():
            assert 0.0 <= val <= 1.0, (
                f"Preset {name}: {axis} coordinate {val} out of range"
            )


def test_default_target_exists():
    assert DEFAULT_TARGET in TARGET_PRESETS


def test_five_target_presets_defined():
    """The MVP spec calls for exactly 5 target presets."""
    assert len(TARGET_PRESETS) == 5


# ---------------------------------------------------------------------------
# Regression: rule library precision
# ---------------------------------------------------------------------------

def test_tw_time_bounded_does_not_false_positive_on_casual_mentions():
    """v0.2 stress test caught: bare '今天'/'today' in a casual phrase
    (e.g. '今天天气怎么样') was matching tw_time_bounded and falsely
    narrowing TASK_WIDTH. The rule now requires a scope/deadline marker
    adjacent to the time word.
    """
    rule = rule_by_id("tw_time_bounded")
    casual_phrases = [
        "今天天气怎么样",
        "明天我要去哪里",
        "today is a sunny day",
        "this week has been busy",
        "下周打算休息",
    ]
    for phrase in casual_phrases:
        for pattern in rule.patterns:
            assert not re.search(pattern, phrase, re.IGNORECASE), (
                f"tw_time_bounded falsely matched {pattern!r} on casual "
                f"phrase {phrase!r}"
            )


def test_tw_time_bounded_still_fires_on_real_scope_markers():
    """The rule must still catch genuine scope-narrowing language."""
    rule = rule_by_id("tw_time_bounded")
    scope_phrases = [
        "今天内完成这个",
        "本周内交付",
        "明天前做完",
        "下一步行动",
        "by tomorrow",
        "next step",
    ]
    for phrase in scope_phrases:
        matched = any(
            re.search(pattern, phrase, re.IGNORECASE)
            for pattern in rule.patterns
        )
        assert matched, (
            f"tw_time_bounded should match scope phrase {phrase!r} but didn't"
        )
