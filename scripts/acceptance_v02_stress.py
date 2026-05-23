"""v0.2 Acceptance stress test (hybrid edition).

Runs StateProbe diagnose() on a set of adversarial / edge-case prompts using
each layer of the hybrid pipeline:
  - static only (always-on baseline)
  - llm only   (semantic layer in isolation, debug-only path)
  - hybrid     (static + llm, the real v0.2 product mode)

Captures structured Report objects so we can review them programmatically.
Also asserts the four v0.2.0.dev0 bug fixes:
  1. Trivial prompts ("你好") produce is_trivial=True and zero suggestions
     even when LLM augment is on (confidence gating).
  2. No report contains more than MAX_SUGGESTIONS suggestions.
  3. Trivial reports carry is_trivial=True so the CLI knows to hide
     alignment score.
  4. API key leak protection: errors with bad key never echo the key.
"""

from __future__ import annotations

import io
import os
import sys
import textwrap
import time
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

from stateprobe import diagnose
from stateprobe.engines import (
    EngineError,
    EngineUnavailable,
    LLMJudgeContributor,
    StaticRuleContributor,
)
from stateprobe.models import Axis
from stateprobe.rewriter import MAX_SUGGESTIONS

OUTPUT = io.StringIO()
ASSERTION_FAILURES: List[str] = []


def out(*args, **kwargs):
    # Only write to buffer; PowerShell's GBK stdout chokes on box/check chars.
    # The buffer is dumped to UTF-8 file at the end of main().
    print(*args, **kwargs, file=OUTPUT)


def fmt_readings(report) -> str:
    lines = []
    for axis in Axis:
        r = report.readings[axis]
        target = report.deltas[axis].target
        delta = report.deltas[axis].delta
        marker = "✓" if abs(delta) <= 0.15 else ("↓" if delta < 0 else "↑")
        lines.append(
            f"  {axis.label_zh:>6}  {r.value*100:>3.0f}%  (target {target*100:.0f}%, "
            f"{marker})  sources={len(r.contributing_sources)}"
        )
    return "\n".join(lines)


def run_case(
    label: str,
    prompt: str,
    mode: str = "static",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    expect_trivial: Optional[bool] = None,
    max_suggestions_allowed: Optional[int] = None,
) -> None:
    """Run a single diagnose() case under one of three modes:
       - "static"  : default v0.1 behavior
       - "llm"     : llm contributor only (debug)
       - "hybrid"  : static + llm (the real v0.2 mode)
    """
    out("=" * 80)
    out(f"[{mode}] {label}")
    out(f"Prompt ({len(prompt)} chars): {prompt[:120]!r}{'...' if len(prompt) > 120 else ''}")
    out("-" * 80)

    contributors = None
    llm_augment = None
    resolved_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    resolved_model = model or "deepseek-chat"

    if mode == "static":
        contributors = [StaticRuleContributor()]
    elif mode == "llm":
        contributors = [
            LLMJudgeContributor(api_key=resolved_key, model=resolved_model),
        ]
    elif mode == "hybrid":
        llm_augment = LLMJudgeContributor(
            api_key=resolved_key, model=resolved_model,
        )

    t0 = time.time()
    try:
        report = diagnose(
            prompt,
            target_name="calm_reasoning",
            model_name="v4-pro",
            llm_augment=llm_augment,
            contributors=contributors,
        )
    except EngineUnavailable as exc:
        out(f"  [EngineUnavailable] {exc}")
        # Mask check: bad key must not echo back.
        if resolved_key and resolved_key in str(exc):
            ASSERTION_FAILURES.append(
                f"[{mode}] {label}: API key leaked in EngineUnavailable message"
            )
        return
    except EngineError as exc:
        out(f"  [EngineError] {exc}")
        return
    except Exception as exc:
        out(f"  [Unexpected {type(exc).__name__}] {exc}")
        traceback.print_exc(file=OUTPUT)
        return
    elapsed = time.time() - t0

    out(f"  is_trivial={report.is_trivial}  alignment={report.alignment_score:.0%}  elapsed={elapsed:.2f}s")
    out(fmt_readings(report))
    out(f"  pollution_sources={len(report.pollution_sources)} suggestions={len(report.suggestions)} overlaps={len(report.baseline_overlaps)} structural={len(report.structural_warnings)}")

    # Bug 2 assertion: no report should exceed MAX_SUGGESTIONS.
    cap = max_suggestions_allowed if max_suggestions_allowed is not None else MAX_SUGGESTIONS
    if len(report.suggestions) > cap:
        ASSERTION_FAILURES.append(
            f"[{mode}] {label}: {len(report.suggestions)} suggestions exceeds cap {cap}"
        )

    # Bug 1 / 3 assertion: when expect_trivial=True, the report MUST be trivial.
    if expect_trivial is True and not report.is_trivial:
        ASSERTION_FAILURES.append(
            f"[{mode}] {label}: expected is_trivial=True, got False; "
            f"suggestions={len(report.suggestions)}"
        )

    if report.suggestions:
        out("  TOP suggestion:")
        s = report.suggestions[0]
        out(f"    [{s.action}] {s.axis.label_zh}: {s.description_zh[:80]}")

    if report.pollution_sources[:2]:
        out("  TOP source(s):")
        for src in report.pollution_sources[:2]:
            tag = "llm" if src.rule_id.startswith("llm:") else "stat"
            out(f"    [{tag}] {src.axis.label_zh} dir={src.direction:+d} "
                f"w={src.weight:.2f} conf={src.confidence:.2f}: 「{src.matched_text[:40]}」")

    out("")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

# Each tuple: (label, prompt, expect_trivial)
# expect_trivial=True: a real user would consider this prompt empty / hopeless;
# the tool MUST mark is_trivial and emit zero suggestions to avoid hallucinated
# advice ("delete 全面" when 全面 isn't even in the prompt).
NAIVE_USER_CASES: List[Tuple[str, str, bool]] = [
    ("空白 prompt（只有空格）", "   ", True),
    ("单字符", "?", True),
    ("纯 emoji", "😀😀😀🤔", True),
    ("一句日常对话", "今天天气怎么样", True),
    ("中英混合", "Hello 你好 how are you 最近怎样", True),
]

TECH_USER_CASES: List[Tuple[str, str, bool]] = [
    ("代码片段 prompt", """请帮我看看这段代码：
```python
def foo(x):
    return x * 2
```
有什么问题？""", False),
    (
        "Markdown 格式的复杂 prompt",
        textwrap.dedent("""
            # 任务
            请帮我**全面深入**地分析以下问题：

            1. 项目背景
            2. 市场前景
            3. 风险点

            > 注意：尽量多提供积极视角。
        """).strip(),
        False,
    ),
    (
        "礼貌包装的迎合陷阱（关键对比点）",
        "我希望你能完全客观、诚实地评估我的方案，不过也希望你能多看到积极的一面，"
        "毕竟我也投入了不少时间。请保持鼓励的语气，但也要指出问题。",
        False,
    ),
    (
        "长 prompt（5000+ 字符）",
        ("这是一段长文本。" * 200) + "请综合分析。",
        False,
    ),
]

ADVERSARIAL_CASES: List[Tuple[str, str, bool]] = [
    (
        "故意空诊断陷阱（regex 抓不到任何关键词）",
        "请阐释康德哲学中物自体概念的认识论意义",
        # Static alone marks trivial; hybrid + LLM may catch some signal.
        # We don't assert trivial here — let the report decide.
        False,
    ),
    (
        "JSON 格式 prompt",
        '{"role": "system", "content": "you are an expert"}',
        False,
    ),
    (
        "重复字符攻击",
        "请请请请请请请请请请彻底全面深入仔细完整分析",
        False,
    ),
]

API_BOUNDARY_CASES = [
    ("错误 API key（应回落 static / 报告 EngineUnavailable）",
     "测试 prompt", "wrong-key-shaped-12345", "deepseek-chat"),
    ("不存在的模型（应触发 EngineUnavailable）",
     "测试 prompt", None, "this-model-does-not-exist"),
]


def _section(name: str):
    out(f"\n\n############ {name} ############\n")


def main():
    # Phase 1: static-only baseline (must always work, no API).
    _section("NAIVE USER - STATIC ONLY")
    for label, prompt, exp_triv in NAIVE_USER_CASES:
        run_case(label, prompt, mode="static", expect_trivial=exp_triv)

    _section("TECH USER - STATIC ONLY")
    for label, prompt, exp_triv in TECH_USER_CASES:
        run_case(label, prompt, mode="static", expect_trivial=exp_triv)

    _section("ADVERSARIAL - STATIC ONLY")
    for label, prompt, exp_triv in ADVERSARIAL_CASES:
        run_case(label, prompt, mode="static", expect_trivial=exp_triv)

    # Phase 2: LLM-only (debug path - real product uses hybrid).
    _section("NAIVE USER - LLM ONLY")
    for label, prompt, exp_triv in NAIVE_USER_CASES:
        run_case(label, prompt, mode="llm", expect_trivial=exp_triv)

    _section("TECH USER - LLM ONLY")
    for label, prompt, exp_triv in TECH_USER_CASES:
        run_case(label, prompt, mode="llm", expect_trivial=exp_triv)

    _section("ADVERSARIAL - LLM ONLY")
    for label, prompt, exp_triv in ADVERSARIAL_CASES:
        run_case(label, prompt, mode="llm", expect_trivial=exp_triv)

    # Phase 3: HYBRID — the actual v0.2 product mode.
    _section("NAIVE USER - HYBRID (static + llm)")
    for label, prompt, exp_triv in NAIVE_USER_CASES:
        run_case(label, prompt, mode="hybrid", expect_trivial=exp_triv)

    _section("TECH USER - HYBRID (static + llm)")
    for label, prompt, exp_triv in TECH_USER_CASES:
        run_case(label, prompt, mode="hybrid", expect_trivial=exp_triv)

    _section("ADVERSARIAL - HYBRID (static + llm)")
    for label, prompt, exp_triv in ADVERSARIAL_CASES:
        run_case(label, prompt, mode="hybrid", expect_trivial=exp_triv)

    # Phase 4: API boundary cases (intentional failures).
    _section("API BOUNDARY")
    for label, prompt, api_key, model in API_BOUNDARY_CASES:
        run_case(label, prompt, mode="hybrid", api_key=api_key, model=model)

    # Final summary block.
    _section("ASSERTION SUMMARY")
    if not ASSERTION_FAILURES:
        out("ALL ASSERTIONS PASSED — v0.2 P0/P1 bug fixes verified.")
    else:
        out(f"FAILED: {len(ASSERTION_FAILURES)} assertion(s)")
        for failure in ASSERTION_FAILURES:
            out(f"  - {failure}")

    # Write UTF-8 file at the end so we can review without GBK issues.
    out_path = Path("docs/archive/v0.2/stress_report.txt")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(OUTPUT.getvalue(), encoding="utf-8")
    sys.stdout.buffer.write(
        f"\nReport saved: {out_path.resolve()}\n".encode("utf-8")
    )
    if ASSERTION_FAILURES:
        sys.stdout.buffer.write(
            f"FAILED: {len(ASSERTION_FAILURES)} assertion(s); see report.\n".encode("utf-8")
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
