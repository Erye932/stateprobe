"""LLM-as-Judge contributor (v0.2+).

Per ADR_009, this is one contributor among several in the hybrid evidence
pipeline. It does NOT compute axis readings; it emits PollutionSource items
that the detector aggregates alongside other contributors' evidence.

Compared to v0.2.0.dev0's `LLMJudgeEngine`:
- Returns Dict[Axis, List[PollutionSource]] instead of full readings.
- Asks the judge LLM for direction + strength + confidence + a short quote
  per axis, not just a single 0-1 score.
- Drops `_build_synthetic_source`. Low-confidence axes simply emit nothing,
  which lets the aggregator correctly mark trivial prompts as `is_trivial`.
- Confidence threshold: axes with confidence < 0.30 are silently dropped.

Failure modes:
- Missing API key → raise EngineUnavailable (the orchestrator drops the
  contributor silently; static rules still produce a result).
- Network / 5xx → raise EngineUnavailable.
- Malformed JSON → raise EngineError (the judge is broken; surface).
"""

from __future__ import annotations

import json
import re
from typing import Callable, Dict, List, Optional

from stateprobe.engines.base import (
    Engine,
    EngineError,
    EngineUnavailable,
    EvidenceContributor,
)
from stateprobe.eval.client import (
    DEFAULT_BASE_URL,
    DEFAULT_EVAL_MODEL,
    chat_completion,
    CompletionResult,
)
from stateprobe.models import (
    Axis,
    AxisReading,
    ModelBaseline,
    PollutionSource,
)


# Type alias: a callable that takes the same kwargs as chat_completion and
# returns a CompletionResult. Lets tests inject a fake without monkeypatching
# the urllib layer.
ChatCallable = Callable[..., CompletionResult]


_AXIS_DESCRIPTIONS_FOR_JUDGE: Dict[Axis, str] = {
    Axis.SYCOPHANCY: (
        "迎合度：用户的措辞是否在索取正面反馈、暗示想要赞同、"
        "或者用礼貌包装来抑制模型说'不'？0=完全敢说不行；1=强烈索取迎合。"
    ),
    Axis.TASK_WIDTH: (
        "任务宽度：任务范围是收敛在一个具体判断点，还是要求覆盖多方面、"
        "全面分析？0=单点判断；1=全面铺开。"
    ),
    Axis.SUCCESS_CRITERIA: (
        "验收清晰度：是否给出了明确的成功/失败标准、输出格式或验收边界？"
        "0=完全没有边界；1=失败标准非常明确。"
    ),
    Axis.REASONING_BUDGET: (
        "推理预算：用户是否要求模型展开深度推理、一步步思考、"
        "或者只想要直接结论？0=直接答；1=要求深度推理。"
    ),
    Axis.IDENTITY_STRENGTH: (
        "身份强度：用户是否给模型赋予了一个强身份/角色（专家、教授、CEO 等）？"
        "0=无角色赋予；1=强烈角色扮演要求。"
    ),
    Axis.ASSERTIVENESS: (
        "自信度：用户是否要求模型给出明确结论、敢下判断，"
        "还是允许使用'可能'、'也许'等模糊表达？0=允许犹豫；1=要求果断。"
    ),
    Axis.SELF_VERIFICATION: (
        "自我验证：用户是否要求模型自我质疑、检查反例、推翻假设？"
        "0=接受首次答案；1=要求反复自我验证。"
    ),
    Axis.INFO_FLOW: (
        "信息流向：用户是否希望模型主动反问澄清需求，还是直接给答案？"
        "0=直接给答案；1=主动提问。"
    ),
}


# Confidence below this threshold means "I observed nothing meaningful on
# this axis." Such observations contribute no source — the axis sits at
# baseline, and trivial prompts correctly stay trivial.
MIN_LLM_CONFIDENCE = 0.30


def _build_judge_prompt(prompt: str) -> str:
    """Build the user prompt sent to the judge LLM.

    Asks for direction (up/down/none) + strength + confidence + quote per
    axis. Refusing to express an opinion (low confidence) is explicitly
    encouraged — this lets trivial prompts produce empty observations.
    """
    axis_lines: List[str] = []
    for axis in Axis:
        axis_lines.append(f"- {axis.value}: {_AXIS_DESCRIPTIONS_FOR_JUDGE[axis]}")

    keys = ", ".join(f'"{a.value}"' for a in Axis)

    return f"""你是一个 LLM Prompt 行为分析专家。

下面给你一段用户写给 LLM 的 Prompt，请评估这段 Prompt 在以下 8 个行为轴上
**是否在某方向施加了可观察的压力**。

重要原则：
- 如果你在某个轴上**没看到明确的证据**，请把 confidence 标为 0（或省略该轴）。
  不要凑数、不要为了填满 8 个轴而强行打分。
- 只对你**真正能从 prompt 里指认出具体措辞**的轴给出非零 confidence。
- 一段空白、单字符、纯寒暄的 prompt 应该所有 8 个轴的 confidence 都是 0。

8 个行为轴：
{chr(10).join(axis_lines)}

每个有信号的轴给出：
- direction: "up"（prompt 把这个轴推高）或 "down"（推低）
- strength: 0.0~1.0，信号本身有多强（你引用的措辞有多强烈）
- confidence: 0.0~1.0，你对自己这个观察有多确信（< 0.3 表示几乎无信号，
  此时不要列出该轴）
- quote: 从 prompt 中复制的那段措辞（不超过 20 字），是它驱动了这个判断
- reason: 一句不超过 30 字的中文解释

严格只输出 JSON，不要任何额外文字、不要 markdown 代码块。

格式（轴 key 必须是这 8 个之一：{keys}）：
{{
  "observations": [
    {{
      "axis": "sycophancy",
      "direction": "up",
      "strength": 0.6,
      "confidence": 0.85,
      "quote": "多看到积极的一面",
      "reason": "明确索取正面反馈"
    }},
    ...只列出 confidence ≥ 0.3 的轴
  ]
}}

如果整段 prompt 没有任何可观察的轴压力（如空白、单字符、emoji、纯寒暄），
返回：
{{ "observations": [] }}

---
待评估的 Prompt：
{prompt}
"""


def _parse_judge_response(text: str) -> List[Dict]:
    """Parse the judge's JSON output. Returns a list of observation dicts.

    Each dict has: axis, direction, strength, confidence, quote, reason.
    Raises EngineError on malformed input — the judge is supposed to return
    strict JSON; if it doesn't, surfacing the error is better than silently
    falling back to defaults.
    """
    text = text.strip()
    # Strip markdown code fences the judge might add despite instructions.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        raise EngineError(
            f"LLM judge 返回中未找到 JSON: {text[:200]}"
        )

    try:
        payload = json.loads(json_match.group())
    except json.JSONDecodeError as exc:
        raise EngineError(f"LLM judge 返回的 JSON 解析失败: {exc}") from exc

    observations = payload.get("observations", [])
    if not isinstance(observations, list):
        raise EngineError(
            f"LLM judge 'observations' 字段不是数组: {observations!r}"
        )
    return observations


def _observation_to_source(obs: Dict) -> Optional[PollutionSource]:
    """Translate one LLM observation dict into a PollutionSource.

    Returns None if confidence is below the minimum threshold or the
    observation is missing required fields. This is the trivial-detection
    fix: low-confidence axes never produce a source, so total_sources stays
    accurately at 0 for prompts the judge couldn't read.
    """
    axis_id = obs.get("axis")
    if not axis_id:
        return None
    try:
        axis = Axis(axis_id)
    except ValueError:
        return None

    try:
        confidence = float(obs.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if confidence < MIN_LLM_CONFIDENCE:
        return None

    direction_raw = str(obs.get("direction", "")).lower().strip()
    if direction_raw == "up":
        direction = 1
    elif direction_raw == "down":
        direction = -1
    else:
        return None

    try:
        strength = float(obs.get("strength", 0.0))
    except (TypeError, ValueError):
        return None
    strength = max(0.0, min(1.0, strength))
    confidence = max(0.0, min(1.0, confidence))

    quote = str(obs.get("quote", "")).strip()[:60]
    reason = str(obs.get("reason", "")).strip()[:120]

    return PollutionSource(
        rule_id=f"llm:{axis.value}",
        axis=axis,
        direction=direction,
        weight=strength,
        matched_text=quote or reason or "(LLM 未给出具体证据)",
        explanation_zh=reason or f"LLM 判断该 prompt 在「{axis.label_zh}」上有压力",
        citation="LLM-as-Judge (v0.2)",
        confidence=confidence,
    )


class LLMJudgeContributor:
    """Ask a judge LLM for axis observations and emit them as evidence.

    Per ADR_009, this is a contributor — it returns sources, not readings.
    Low-confidence observations are discarded so trivial prompts produce
    no evidence and `is_trivial` works correctly.
    """

    name = "llm_judge"

    def __init__(
        self,
        model: str = DEFAULT_EVAL_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        chat_fn: Optional[ChatCallable] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        """
        Args:
            model: Judge model name (e.g., 'deepseek-chat').
            base_url: API base URL.
            api_key: Optional API key. If None, the underlying client picks
                it up from DEEPSEEK_API_KEY or OPENAI_API_KEY env vars.
            chat_fn: Optional injection point for testing. Defaults to the
                real chat_completion implementation.
            temperature: Lower = more deterministic judging.
            max_tokens: Cap on judge response length.
        """
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self._chat_fn: ChatCallable = chat_fn or chat_completion
        self.temperature = temperature
        self.max_tokens = max_tokens

    def contribute(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline] = None,
    ) -> Dict[Axis, List[PollutionSource]]:
        sources_by_axis: Dict[Axis, List[PollutionSource]] = {
            axis: [] for axis in Axis
        }
        if not prompt or not prompt.strip():
            return sources_by_axis

        judge_prompt = _build_judge_prompt(prompt)

        try:
            result = self._chat_fn(
                user_prompt=judge_prompt,
                model=self.model,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except RuntimeError as exc:
            # chat_completion raises RuntimeError for missing key + HTTP errors.
            # Both are recoverable: orchestrator drops this contributor.
            raise EngineUnavailable(f"LLM judge 不可用: {exc}") from exc

        observations = _parse_judge_response(result.response_text)
        for obs in observations:
            source = _observation_to_source(obs)
            if source is None:
                continue
            sources_by_axis[source.axis].append(source)
        return sources_by_axis


# ---------------------------------------------------------------------------
# Deprecated: v0.2.0.dev0 alias. Will be removed in v0.3.
# Wraps the new contributor + aggregator to keep the old read_axes shape.
# ---------------------------------------------------------------------------

class LLMJudgeEngine(Engine):
    """DEPRECATED: legacy v0.2.0.dev0 wrapper. Use LLMJudgeContributor.

    Returns full readings by running the contributor + the shared aggregator.
    Will be removed in v0.3.
    """

    name = "llm"

    def __init__(self, *args, **kwargs):
        self._contributor = LLMJudgeContributor(*args, **kwargs)

    def read_axes(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline] = None,
    ) -> Dict[Axis, AxisReading]:
        from stateprobe.detector import _aggregate_to_readings

        sources = self._contributor.contribute(prompt, baseline=baseline)
        return _aggregate_to_readings(sources, baseline=baseline)
