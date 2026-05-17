"""Tests for the black-box eval scaffolding (no API calls)."""

from __future__ import annotations

from stateprobe.eval.client import DEFAULT_EVAL_MODEL, DEFAULT_BASE_URL
from stateprobe.eval.scorer import (
    BEHAVIOR_RUBRICS,
    BehaviorRubric,
    _build_judge_prompt,
    _parse_judge_json,
    AxisEvalScore,
)
from stateprobe.models import Axis


def test_default_eval_model_is_deepseek_chat():
    assert DEFAULT_EVAL_MODEL == "deepseek-chat"


def test_default_base_url_is_deepseek():
    assert "deepseek.com" in DEFAULT_BASE_URL


def test_rubrics_cover_all_8_axes():
    rubric_axes = {r.axis for r in BEHAVIOR_RUBRICS}
    assert rubric_axes == set(Axis)


def test_all_rubrics_have_non_empty_fields():
    for r in BEHAVIOR_RUBRICS:
        assert isinstance(r, BehaviorRubric)
        assert r.question_zh.strip()
        assert r.low_label.strip()
        assert r.high_label.strip()


def test_judge_prompt_contains_both_outputs():
    prompt = _build_judge_prompt(
        original_output="Output A content here",
        rewritten_output="Output B content here",
        rubrics=BEHAVIOR_RUBRICS,
    )
    assert "Output A" in prompt
    assert "Output B" in prompt
    assert "sycophancy" in prompt
    assert "scores_a" in prompt
    assert "scores_b" in prompt


def test_parse_judge_json_valid():
    raw = '{"scores_a": {"sycophancy": 0.7}, "scores_b": {"sycophancy": 0.3}}'
    parsed = _parse_judge_json(raw)
    assert parsed["scores_a"]["sycophancy"] == 0.7
    assert parsed["scores_b"]["sycophancy"] == 0.3


def test_parse_judge_json_with_surrounding_text():
    raw = 'Here is the result:\n{"scores_a": {"sycophancy": 0.5}, "scores_b": {"sycophancy": 0.2}}\nDone.'
    parsed = _parse_judge_json(raw)
    assert "scores_a" in parsed


def test_parse_judge_json_raises_on_invalid():
    import pytest
    with pytest.raises(ValueError):
        _parse_judge_json("no json here")


def test_axis_eval_score_delta():
    s = AxisEvalScore(axis=Axis.SYCOPHANCY, score_original=0.8, score_rewritten=0.3)
    assert s.delta == -0.5
    assert s.changed
    assert "0.80" in s.summary_zh
    assert "0.30" in s.summary_zh


def test_axis_eval_score_changed_threshold():
    s = AxisEvalScore(axis=Axis.SYCOPHANCY, score_original=0.50, score_rewritten=0.53)
    assert not s.changed
