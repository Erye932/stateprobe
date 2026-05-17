"""Tests for structural diagnostics (length / redundancy / synonym / filler)."""

from __future__ import annotations

from stateprobe.detector import diagnose
from stateprobe.structural import detect_structural_issues


# ---------------------------------------------------------------------------
# Length warnings
# ---------------------------------------------------------------------------

def test_short_prompt_no_length_warning():
    warnings = detect_structural_issues("用 Python 写一个二分查找")
    length_warnings = [w for w in warnings if w.kind == "length"]
    assert length_warnings == []


def test_long_prompt_info_threshold():
    prompt = "X" * 3000
    warnings = detect_structural_issues(prompt)
    length_warnings = [w for w in warnings if w.kind == "length"]
    assert len(length_warnings) == 1
    assert length_warnings[0].severity == "info"


def test_very_long_prompt_warning_threshold():
    prompt = "X" * 15000
    warnings = detect_structural_issues(prompt)
    length_warnings = [w for w in warnings if w.kind == "length"]
    assert len(length_warnings) == 1
    assert length_warnings[0].severity == "warning"


def test_critical_long_prompt():
    prompt = "X" * 60000
    warnings = detect_structural_issues(prompt)
    length_warnings = [w for w in warnings if w.kind == "length"]
    assert len(length_warnings) == 1
    assert length_warnings[0].severity == "critical"
    assert "60,000" in length_warnings[0].message_zh


# ---------------------------------------------------------------------------
# Character repetition
# ---------------------------------------------------------------------------

def test_no_repetition_clean():
    warnings = detect_structural_issues("请帮我写代码")
    redundancy = [w for w in warnings if w.kind == "redundancy"]
    assert redundancy == []


def test_repeated_chinese_chars_caught():
    warnings = detect_structural_issues("请请请请帮我")
    redundancy = [w for w in warnings if w.kind == "redundancy"]
    assert len(redundancy) >= 1
    assert "请请请请" in redundancy[0].matched_text


def test_repeated_english_chars_caught():
    warnings = detect_structural_issues("pleasse helllllp me")
    redundancy = [w for w in warnings if w.kind == "redundancy"]
    assert len(redundancy) >= 1


def test_double_char_not_triggered():
    # 双字重复（如"看看"、"想想"）是合法的中文，不应触发
    warnings = detect_structural_issues("帮我看看这段代码")
    redundancy = [w for w in warnings if w.kind == "redundancy"]
    assert redundancy == []


# ---------------------------------------------------------------------------
# Synonym stacking
# ---------------------------------------------------------------------------

def test_thoroughness_stacking_caught():
    warnings = detect_structural_issues("请彻底全面深入仔细完整地分析")
    stacking = [w for w in warnings if w.kind == "synonym_stacking"]
    assert len(stacking) >= 1
    assert "thoroughness" in stacking[0].message_zh


def test_two_synonyms_not_enough():
    # 2 个同义词不算堆叠
    warnings = detect_structural_issues("请仔细认真分析")
    stacking = [w for w in warnings if w.kind == "synonym_stacking"]
    assert stacking == []


def test_analysis_verb_stacking():
    warnings = detect_structural_issues("请分析、评估、考察、研究这个问题")
    stacking = [w for w in warnings if w.kind == "synonym_stacking"]
    assert len(stacking) >= 1
    assert "analysis_verbs" in stacking[0].message_zh


# ---------------------------------------------------------------------------
# Filler intensifiers
# ---------------------------------------------------------------------------

def test_filler_caught():
    warnings = detect_structural_issues("请你一定要仔细写")
    filler = [w for w in warnings if w.kind == "filler"]
    assert len(filler) >= 1


def test_no_filler_clean():
    warnings = detect_structural_issues("请帮我写代码")
    filler = [w for w in warnings if w.kind == "filler"]
    assert filler == []


# ---------------------------------------------------------------------------
# Integration with diagnose()
# ---------------------------------------------------------------------------

def test_diagnose_includes_structural_warnings():
    r = diagnose("请彻底全面深入仔细完整分析", model_name="v4-pro")
    assert len(r.structural_warnings) >= 1
    kinds = [w.kind for w in r.structural_warnings]
    assert "synonym_stacking" in kinds


def test_diagnose_empty_prompt_no_structural():
    r = diagnose("", model_name="v4-pro")
    assert r.structural_warnings == []


def test_warnings_sorted_by_severity():
    prompt = "X" * 60000 + "请请请请仔细仔细认真认真分析"
    warnings = detect_structural_issues(prompt)
    if len(warnings) >= 2:
        severity_rank = {"critical": 0, "warning": 1, "info": 2}
        for i in range(len(warnings) - 1):
            assert severity_rank[warnings[i].severity] <= severity_rank[warnings[i + 1].severity]


# ---------------------------------------------------------------------------
# V4 baselines
# ---------------------------------------------------------------------------

def test_v4_pro_baseline_exists():
    from stateprobe.rules import get_model_baseline, MODEL_BASELINES
    assert "v4-pro" in MODEL_BASELINES
    bl = get_model_baseline("v4-pro")
    assert bl.name == "v4-pro"


def test_v4_flash_baseline_exists():
    from stateprobe.rules import get_model_baseline, MODEL_BASELINES
    assert "v4-flash" in MODEL_BASELINES


def test_v4_pro_higher_reasoning_than_deepseek():
    from stateprobe.rules import get_model_baseline
    from stateprobe.models import Axis
    pro = get_model_baseline("v4-pro")
    legacy = get_model_baseline("deepseek")
    assert pro.axis_baselines[Axis.REASONING_BUDGET] >= legacy.axis_baselines[Axis.REASONING_BUDGET]


def test_v4_flash_lower_reasoning_than_pro():
    from stateprobe.rules import get_model_baseline
    from stateprobe.models import Axis
    flash = get_model_baseline("v4-flash")
    pro = get_model_baseline("v4-pro")
    assert flash.axis_baselines[Axis.REASONING_BUDGET] < pro.axis_baselines[Axis.REASONING_BUDGET]


def test_v4_pro_alignment_for_short_prompt():
    r = diagnose("用Python写二分查找", model_name="v4-pro")
    # Should have valid alignment score
    assert 0.0 <= r.alignment_score <= 1.0


def test_v4_flash_differs_from_v4_pro():
    """Same prompt on Flash vs Pro should give different alignment."""
    prompt = "你是资深专家请仔细分析所有角度"
    r_pro = diagnose(prompt, model_name="v4-pro")
    r_flash = diagnose(prompt, model_name="v4-flash")
    assert r_pro.alignment_score != r_flash.alignment_score
