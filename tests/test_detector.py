"""Test the detection engine on representative prompts."""

from __future__ import annotations

import pytest

from stateprobe.detector import detect_readings, diagnose
from stateprobe.models import Axis


# ---------------------------------------------------------------------------
# Boundary / sanity tests
# ---------------------------------------------------------------------------

def test_empty_prompt_yields_neutral_readings():
    readings = detect_readings("")
    for axis in Axis:
        assert readings[axis].value == pytest.approx(0.5)
        assert readings[axis].contributing_sources == []


def test_whitespace_only_prompt_yields_neutral_readings():
    readings = detect_readings("   \n  \t  ")
    for axis in Axis:
        assert readings[axis].value == pytest.approx(0.5)


def test_readings_are_in_unit_interval():
    """No matter how toxic the prompt, every reading stays in [0, 1]."""
    extreme_prompt = (
        "你是世界顶级的资深首席专家大师，请扮演投资顾问，"
        "全面、详尽、深入地分析所有方面，越多越好，"
        "麻烦你鼓励一下我，给出优点和缺点和优势和劣势。"
    )
    readings = detect_readings(extreme_prompt)
    for axis in Axis:
        assert 0.0 <= readings[axis].value <= 1.0


# ---------------------------------------------------------------------------
# Behavioral tests — bad prompts should activate expected axes
# ---------------------------------------------------------------------------

def test_vague_expert_activates_identity_and_width():
    prompt = "你是一位资深的产品经理专家，请全面分析这个项目的各个方面。"
    readings = detect_readings(prompt)
    assert readings[Axis.IDENTITY_STRENGTH].value > 0.6, (
        "「资深...专家」应明显激活身份强度轴"
    )
    assert readings[Axis.TASK_WIDTH].value > 0.6, (
        "「全面...各个方面」应明显激活任务宽度轴"
    )


def test_sycophant_prompt_activates_sycophancy():
    prompt = "你觉得这个怎么样？麻烦你鼓励一下我，请给出全面的优缺点。"
    readings = detect_readings(prompt)
    assert readings[Axis.SYCOPHANCY].value > 0.7, (
        "迎合诱导词组合应明显激活迎合度"
    )


def test_role_play_activates_identity():
    prompt = "假装你是首席投资分析师大师，扮演一位资深财务顾问。"
    readings = detect_readings(prompt)
    assert readings[Axis.IDENTITY_STRENGTH].value > 0.7, (
        "扮演 + 角色堆叠应激活身份强度"
    )


def test_brief_request_lowers_reasoning_budget():
    prompt = "用一句话快速直接告诉我答案。"
    readings = detect_readings(prompt)
    assert readings[Axis.REASONING_BUDGET].value < 0.4


# ---------------------------------------------------------------------------
# Behavioral tests — good prompts should be near target
# ---------------------------------------------------------------------------

def test_calm_reasoning_prompt_lowers_sycophancy():
    prompt = (
        "判断这个项目本周是否值得继续投入。"
        "不要鼓励，敢说不行。失败标准：不能指导今天取舍 = 失败。"
        "输出：结论 + 最大风险 + 3 个证据。"
    )
    readings = detect_readings(prompt)
    assert readings[Axis.SYCOPHANCY].value < 0.4, (
        "反迎合 permission 应降低迎合度"
    )
    assert readings[Axis.SUCCESS_CRITERIA].value > 0.6, (
        "「失败标准」应提高验收清晰度"
    )
    assert readings[Axis.TASK_WIDTH].value < 0.4, (
        "「是否」+「本周」应收窄任务宽度"
    )


def test_super_thinking_max_activates_self_verification():
    prompt = (
        "请一步一步推理。给出初步结论后，假设你是错的，"
        "论证反方观点。至少列出一个反例并解释为什么不成立。"
    )
    readings = detect_readings(prompt)
    assert readings[Axis.REASONING_BUDGET].value > 0.6
    assert readings[Axis.SELF_VERIFICATION].value > 0.6


# ---------------------------------------------------------------------------
# End-to-end: diagnose() returns a full Report
# ---------------------------------------------------------------------------

def test_diagnose_returns_full_report():
    prompt = "你是资深产品经理专家，请全面分析项目。"
    report = diagnose(prompt, target_name="calm_reasoning")
    assert report.prompt == prompt
    assert report.target.name == "calm_reasoning"
    assert set(report.readings.keys()) == set(Axis)
    assert set(report.deltas.keys()) == set(Axis)
    # This prompt is misaligned with calm_reasoning, so we expect suggestions.
    assert len(report.suggestions) > 0


def test_diagnose_aligned_prompt_yields_high_alignment():
    prompt = (
        "判断这个项目本周是否值得继续投入。不要鼓励，敢说不行。"
        "失败标准：不能指导今天取舍 = 失败。"
        "输出：结论 + 最大风险 + 3 个证据。"
    )
    report = diagnose(prompt, target_name="calm_reasoning")
    # Not perfect, but should be meaningfully more aligned than a bad prompt.
    bad_report = diagnose(
        "你是资深专家，请全面分析各个方面，越详细越好。",
        target_name="calm_reasoning",
    )
    assert report.alignment_score > bad_report.alignment_score


def test_diagnose_invalid_target_raises():
    with pytest.raises(KeyError):
        diagnose("test prompt", target_name="nonexistent_target")
