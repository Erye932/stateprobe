"""Tests for the v0.2 hybrid evidence pipeline (ADR_009).

Covers:
- StaticRuleContributor.contribute returns lists of PollutionSource per axis.
- LLMJudgeContributor parses the new observations format, gates by confidence.
- diagnose() default == static-only (backward-compat with v0.1).
- diagnose(llm_augment=...) merges both contributors' evidence.
- Trivial prompts correctly marked (no synthetic sources from low-conf LLM).
- EngineUnavailable from llm_augment is dropped (graceful degradation) and
  emits a RuntimeWarning (v0.3+ visibility); static still runs.
- Deprecated StaticEngine / LLMJudgeEngine aliases still produce readings.
"""

from __future__ import annotations

import json

import pytest

from stateprobe.detector import diagnose, detect_readings
from stateprobe.engines import (
    EngineError,
    EngineUnavailable,
    EvidenceContributor,
    LLMJudgeContributor,
    LLMJudgeEngine,
    StaticEngine,
    StaticRuleContributor,
)
from stateprobe.engines.llm_judge import (
    MIN_LLM_CONFIDENCE,
    _observation_to_source,
    _parse_judge_response,
)
from stateprobe.eval.client import CompletionResult, ChatMessage
from stateprobe.models import Axis


# ---------------------------------------------------------------------------
# Helpers — build fake judge JSON in the new "observations" format
# ---------------------------------------------------------------------------

def _obs(axis: Axis, direction: str, strength: float, confidence: float,
         quote: str = "test quote", reason: str = "test reason") -> dict:
    return {
        "axis": axis.value,
        "direction": direction,
        "strength": strength,
        "confidence": confidence,
        "quote": quote,
        "reason": reason,
    }


def _obs_json(*observations: dict) -> str:
    return json.dumps({"observations": list(observations)})


def _all_axes_strong_obs(direction: str = "up", confidence: float = 0.9) -> str:
    """Build a judge response with one strong observation per axis."""
    return _obs_json(*[
        _obs(a, direction=direction, strength=0.7, confidence=confidence)
        for a in Axis
    ])


def _make_fake_chat(response_text: str):
    def fake_chat(**kwargs):
        return CompletionResult(
            model=kwargs.get("model", "fake"),
            prompt_messages=[ChatMessage(role="user", content="...")],
            response_text=response_text,
            usage={},
        )
    return fake_chat


def _make_failing_chat(exc: Exception):
    def fake_chat(**kwargs):
        raise exc
    return fake_chat


# ---------------------------------------------------------------------------
# StaticRuleContributor
# ---------------------------------------------------------------------------

def test_static_contributor_returns_sources_per_axis():
    contrib = StaticRuleContributor()
    sources_by_axis = contrib.contribute("你是资深专家，请全面分析这个项目")
    assert set(sources_by_axis.keys()) == set(Axis)
    # At least one axis should have detected pressure
    assert any(len(srcs) > 0 for srcs in sources_by_axis.values())


def test_static_contributor_empty_prompt_returns_empty_lists():
    contrib = StaticRuleContributor()
    sources_by_axis = contrib.contribute("")
    assert set(sources_by_axis.keys()) == set(Axis)
    for srcs in sources_by_axis.values():
        assert srcs == []


def test_static_contributor_all_sources_have_full_confidence():
    contrib = StaticRuleContributor()
    sources_by_axis = contrib.contribute("你是资深专家，请全面分析这个项目")
    for srcs in sources_by_axis.values():
        for src in srcs:
            # Regex matches are deterministic → confidence always 1.0
            assert src.confidence == 1.0


def test_static_contributor_satisfies_protocol():
    assert isinstance(StaticRuleContributor(), EvidenceContributor)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def test_parse_strict_observations_json():
    raw = _obs_json(_obs(Axis.SYCOPHANCY, "up", 0.7, 0.9, quote="多讲优点"))
    observations = _parse_judge_response(raw)
    assert len(observations) == 1
    assert observations[0]["axis"] == "sycophancy"


def test_parse_handles_markdown_code_fence():
    raw = "```json\n" + _obs_json(_obs(Axis.SYCOPHANCY, "up", 0.5, 0.8)) + "\n```"
    observations = _parse_judge_response(raw)
    assert len(observations) == 1


def test_parse_handles_surrounding_prose():
    raw = ("Here is my analysis:\n"
           + _obs_json(_obs(Axis.SYCOPHANCY, "up", 0.5, 0.8))
           + "\nDone.")
    observations = _parse_judge_response(raw)
    assert len(observations) == 1


def test_parse_empty_observations_list():
    raw = _obs_json()
    observations = _parse_judge_response(raw)
    assert observations == []


def test_parse_raises_on_invalid_json():
    with pytest.raises(EngineError):
        _parse_judge_response("not json at all")


def test_parse_raises_when_observations_not_list():
    raw = json.dumps({"observations": "not a list"})
    with pytest.raises(EngineError):
        _parse_judge_response(raw)


# ---------------------------------------------------------------------------
# _observation_to_source — confidence gating + direction/strength parsing
# ---------------------------------------------------------------------------

def test_observation_below_confidence_threshold_dropped():
    # confidence below MIN_LLM_CONFIDENCE → no source emitted
    obs = _obs(Axis.SYCOPHANCY, "up", 0.7, confidence=MIN_LLM_CONFIDENCE - 0.01)
    assert _observation_to_source(obs) is None


def test_observation_at_confidence_threshold_kept():
    obs = _obs(Axis.SYCOPHANCY, "up", 0.7, confidence=MIN_LLM_CONFIDENCE)
    src = _observation_to_source(obs)
    assert src is not None
    assert src.confidence == MIN_LLM_CONFIDENCE


def test_observation_up_direction_becomes_positive():
    obs = _obs(Axis.SYCOPHANCY, "up", 0.7, 0.9, quote="多讲优点")
    src = _observation_to_source(obs)
    assert src.direction == 1
    assert src.weight == 0.7
    assert src.matched_text == "多讲优点"
    assert src.rule_id == "llm:sycophancy"


def test_observation_down_direction_becomes_negative():
    obs = _obs(Axis.SYCOPHANCY, "down", 0.5, 0.9, quote="敢说不行")
    src = _observation_to_source(obs)
    assert src.direction == -1


def test_observation_invalid_direction_dropped():
    obs = {**_obs(Axis.SYCOPHANCY, "up", 0.7, 0.9), "direction": "sideways"}
    assert _observation_to_source(obs) is None


def test_observation_unknown_axis_dropped():
    obs = {"axis": "made_up_axis", "direction": "up", "strength": 0.7,
           "confidence": 0.9, "quote": "", "reason": ""}
    assert _observation_to_source(obs) is None


def test_observation_strength_clamped_to_unit_range():
    obs = _obs(Axis.SYCOPHANCY, "up", strength=1.5, confidence=0.9)
    src = _observation_to_source(obs)
    assert src.weight == 1.0


# ---------------------------------------------------------------------------
# LLMJudgeContributor
# ---------------------------------------------------------------------------

def test_llm_contributor_emits_sources_for_high_confidence_observations():
    contrib = LLMJudgeContributor(
        api_key="fake-key",
        chat_fn=_make_fake_chat(_all_axes_strong_obs(confidence=0.9)),
    )
    sources_by_axis = contrib.contribute("一段需要 LLM 判断的微妙 prompt")
    assert set(sources_by_axis.keys()) == set(Axis)
    # Every axis gets exactly one strong source.
    for axis, srcs in sources_by_axis.items():
        assert len(srcs) == 1
        assert srcs[0].rule_id == f"llm:{axis.value}"
        assert srcs[0].confidence == 0.9


def test_llm_contributor_filters_low_confidence_observations():
    # Every axis below threshold → no sources emitted at all.
    contrib = LLMJudgeContributor(
        api_key="fake",
        chat_fn=_make_fake_chat(_all_axes_strong_obs(
            confidence=MIN_LLM_CONFIDENCE - 0.01
        )),
    )
    sources_by_axis = contrib.contribute("test")
    for srcs in sources_by_axis.values():
        assert srcs == []


def test_llm_contributor_empty_prompt_no_api_call():
    def must_not_be_called(**kwargs):
        raise AssertionError("chat_fn should not be called for empty prompt")

    contrib = LLMJudgeContributor(api_key="fake", chat_fn=must_not_be_called)
    sources_by_axis = contrib.contribute("   ")
    for srcs in sources_by_axis.values():
        assert srcs == []


def test_llm_contributor_raises_unavailable_on_runtime_error():
    contrib = LLMJudgeContributor(
        chat_fn=_make_failing_chat(RuntimeError("no api key")),
    )
    with pytest.raises(EngineUnavailable):
        contrib.contribute("test prompt")


def test_llm_contributor_propagates_engine_error_on_bad_json():
    contrib = LLMJudgeContributor(
        api_key="fake",
        chat_fn=_make_fake_chat("garbage that is not json"),
    )
    with pytest.raises(EngineError):
        contrib.contribute("test")


def test_llm_contributor_name():
    assert LLMJudgeContributor.name == "llm_judge"


def test_llm_contributor_satisfies_protocol():
    assert isinstance(
        LLMJudgeContributor(api_key="fake", chat_fn=_make_fake_chat(_obs_json())),
        EvidenceContributor,
    )


# ---------------------------------------------------------------------------
# diagnose() — hybrid composition
# ---------------------------------------------------------------------------

def test_diagnose_default_is_static_only():
    """Calling diagnose() with no extra args must behave exactly like v0.1."""
    report = diagnose("你是资深专家，请全面分析这个项目")
    assert not report.is_trivial
    assert len(report.pollution_sources) > 0
    # No LLM sources should appear.
    for src in report.pollution_sources:
        assert not src.rule_id.startswith("llm:")


def test_diagnose_with_llm_augment_merges_evidence():
    """llm_augment runs in addition to static, not instead of."""
    llm = LLMJudgeContributor(
        api_key="fake",
        chat_fn=_make_fake_chat(_obs_json(
            _obs(Axis.SYCOPHANCY, "up", 0.6, 0.9, quote="多讲优点")
        )),
    )
    report = diagnose(
        "你是资深专家，请全面分析这个项目",
        llm_augment=llm,
        model_name=None,
    )
    static_sources = [s for s in report.pollution_sources
                      if not s.rule_id.startswith("llm:")]
    llm_sources = [s for s in report.pollution_sources
                   if s.rule_id.startswith("llm:")]
    assert len(static_sources) > 0, "static layer should still run"
    assert len(llm_sources) == 1, "llm layer should add one observation"


def test_diagnose_llm_only_trivial_when_low_confidence():
    """Regression for v0.2.0.dev0 bug: trivial prompts must stay trivial
    even when the LLM contributor runs, as long as confidence is low."""
    llm = LLMJudgeContributor(
        api_key="fake",
        chat_fn=_make_fake_chat(_all_axes_strong_obs(
            confidence=MIN_LLM_CONFIDENCE - 0.01
        )),
    )
    # Prompt has no static rule matches AND LLM returns only low-confidence.
    report = diagnose(
        "你好",
        llm_augment=llm,
        model_name=None,
    )
    assert report.is_trivial
    assert report.suggestions == []
    assert report.baseline_overlaps == []


def test_diagnose_silent_fallback_when_llm_unavailable():
    """LLM contributor raising EngineUnavailable must not break diagnosis.
    Static contributor's evidence should still produce a normal report."""
    llm = LLMJudgeContributor(
        chat_fn=_make_failing_chat(RuntimeError("api 5xx")),
    )
    report = diagnose(
        "你是资深专家，请全面分析这个项目",
        llm_augment=llm,
    )
    # Static evidence still landed.
    assert not report.is_trivial
    static_sources = [s for s in report.pollution_sources
                      if not s.rule_id.startswith("llm:")]
    assert len(static_sources) > 0


def test_diagnose_emits_warning_when_contributor_drops(recwarn):
    """v0.3: silent drops must emit a RuntimeWarning so library callers see
    them. The contributor is still dropped (graceful degradation contract)
    but the warning makes the failure observable to programmatic callers,
    closing the silent-drop UX gap the CLI also fixed via its yellow panel.
    """
    import warnings as _warnings

    llm = LLMJudgeContributor(
        chat_fn=_make_failing_chat(RuntimeError("api 5xx")),
    )
    with _warnings.catch_warnings(record=True) as caught:
        _warnings.simplefilter("always")
        report = diagnose(
            "你是资深专家，请全面分析这个项目",
            llm_augment=llm,
        )

    # Report still produced (graceful degradation preserved).
    assert not report.is_trivial
    # Warning emitted naming the dropped contributor + reason.
    runtime_warnings = [w for w in caught
                        if issubclass(w.category, RuntimeWarning)]
    assert any("llm_judge" in str(w.message) and "unavailable" in str(w.message)
               for w in runtime_warnings), (
        f"Expected RuntimeWarning naming the dropped contributor; got: "
        f"{[str(w.message) for w in runtime_warnings]}"
    )


def test_diagnose_explicit_contributors_overrides_defaults():
    """Passing contributors= bypasses the default [static] composition."""
    # Empty contributor list → no evidence at all → trivial report.
    report = diagnose(
        "你是资深专家，请全面分析这个项目",
        contributors=[],
        model_name=None,
    )
    assert report.is_trivial
    assert report.pollution_sources == []


# ---------------------------------------------------------------------------
# Deprecated v0.2.0.dev0 aliases — still functional but emit deprecation
# warnings (not asserted here; just that the API still works).
# ---------------------------------------------------------------------------

def test_deprecated_static_engine_still_produces_readings():
    engine = StaticEngine()
    readings = engine.read_axes("你是资深专家，请全面分析")
    assert set(readings.keys()) == set(Axis)
    assert any(r.contributing_sources for r in readings.values())


def test_deprecated_llm_engine_still_produces_readings():
    engine = LLMJudgeEngine(
        api_key="fake",
        chat_fn=_make_fake_chat(_all_axes_strong_obs(confidence=0.9)),
    )
    readings = engine.read_axes("test")
    assert set(readings.keys()) == set(Axis)
    # All axes had high-confidence sources → all should be above baseline.
    for r in readings.values():
        assert r.value > 0.5


def test_deprecated_diagnose_engine_param_still_works():
    """Passing engine= (deprecated) should still produce a sensible report."""
    engine = StaticEngine()
    report = diagnose("你是资深专家，请全面分析", engine=engine)
    assert not report.is_trivial


# ---------------------------------------------------------------------------
# Aggregator confidence weighting — sanity checks
# ---------------------------------------------------------------------------

def test_aggregator_filters_below_min_confidence():
    """detect_readings() should pass through high-conf sources only."""
    from stateprobe.models import PollutionSource

    class _FakeContrib:
        name = "fake"

        def contribute(self, prompt, baseline=None):
            return {
                Axis.SYCOPHANCY: [
                    PollutionSource(
                        rule_id="fake:high", axis=Axis.SYCOPHANCY,
                        direction=1, weight=0.8,
                        matched_text="x", explanation_zh="x", citation="x",
                        confidence=0.9,
                    ),
                    PollutionSource(
                        rule_id="fake:low", axis=Axis.SYCOPHANCY,
                        direction=1, weight=0.8,
                        matched_text="y", explanation_zh="y", citation="y",
                        confidence=0.1,
                    ),
                ],
                **{a: [] for a in Axis if a is not Axis.SYCOPHANCY},
            }

    readings = detect_readings("test", contributors=[_FakeContrib()])
    sources = readings[Axis.SYCOPHANCY].contributing_sources
    rule_ids = {s.rule_id for s in sources}
    assert "fake:high" in rule_ids
    assert "fake:low" not in rule_ids
