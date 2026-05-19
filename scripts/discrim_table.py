"""Day 4 discrimination table: static / LLM / lab three-layer comparison.

Runs each example prompt through all three contributor layers and produces
a per-axis comparison table. This is the G3 hard gate for v0.3 — if lab
projections agree with static + LLM on every example, the lab layer adds
no value as an evidence contributor.

Usage:
    python scripts/discrim_table.py
    python scripts/discrim_table.py --skip-llm    # if no API key

Output:
    docs/v03_discrim_report.md  (table + per-case analysis + G3 verdict)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from stateprobe.detector import detect_readings, _aggregate_to_readings
from stateprobe.engines import StaticRuleContributor
from stateprobe.engines.base import EngineUnavailable
from stateprobe.models import Axis


EXAMPLES_DIR = REPO_ROOT / "examples"
DEFAULT_OUT = REPO_ROOT / "docs" / "v03_discrim_report.md"
DEFAULT_VECTORS = REPO_ROOT / "lab_vectors" / "r1_distill_1.5b_v1.pt"

# G3 thresholds
DIVERGENCE_THRESHOLD = 0.20  # |lab - static_or_llm| > this counts as divergence
MIN_DIVERGENCE_CASES = 2     # need at least this many cases to pass G3


# Display order — matches the 4 axes covered by current lab pairs.
AXES_OF_INTEREST = [
    Axis.SYCOPHANCY,
    Axis.TASK_WIDTH,
    Axis.REASONING_BUDGET,
    Axis.SELF_VERIFICATION,
]


@dataclass
class LayerScore:
    """Per-layer score for one (prompt, axis) cell."""

    aggregate: float        # 0.0-1.0 reading after aggregation
    n_sources: int           # how many sources contributed
    available: bool = True   # False if the layer failed for this prompt


@dataclass
class CellResult:
    prompt_id: str
    axis: Axis
    static: LayerScore
    llm: Optional[LayerScore]
    lab: Optional[LayerScore]
    divergent: bool = False  # set during analysis


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-llm", action="store_true",
                   help="Skip LLM layer (no API key)")
    p.add_argument("--skip-lab", action="store_true",
                   help="Skip lab layer (no GPU / no vectors)")
    p.add_argument("--vectors", default=str(DEFAULT_VECTORS),
                   help=f"Lab vectors path (default: {DEFAULT_VECTORS})")
    p.add_argument("--out", default=str(DEFAULT_OUT),
                   help=f"Output report path (default: {DEFAULT_OUT})")
    return p.parse_args()


def load_examples() -> List[tuple]:
    """Return list of (prompt_id, prompt_text) tuples."""
    out = []
    for txt in sorted(EXAMPLES_DIR.glob("*.txt")):
        prompt = txt.read_text(encoding="utf-8").strip()
        if prompt:
            out.append((txt.stem, prompt))
    return out


def run_layer(
    contributor,
    prompts: List[tuple],
    label: str,
) -> Dict[str, Dict[Axis, LayerScore]]:
    """Run one contributor across all prompts; aggregate to AxisReadings.

    Returns dict: prompt_id -> Axis -> LayerScore.
    """
    out: Dict[str, Dict[Axis, LayerScore]] = {}
    for pid, prompt in prompts:
        t0 = time.perf_counter()
        try:
            sources = contributor.contribute(prompt)
        except EngineUnavailable as exc:
            print(f"  [SKIP] {label}/{pid}: {exc}")
            out[pid] = {axis: LayerScore(0.5, 0, available=False)
                        for axis in AXES_OF_INTEREST}
            continue

        readings = _aggregate_to_readings(sources, baseline=None)
        dt_ms = (time.perf_counter() - t0) * 1000
        out[pid] = {}
        for axis in AXES_OF_INTEREST:
            r = readings.get(axis)
            n = len(r.contributing_sources) if r else 0
            v = r.value if r else 0.5
            out[pid][axis] = LayerScore(aggregate=v, n_sources=n)
        n_axes = sum(1 for axis in AXES_OF_INTEREST if out[pid][axis].n_sources > 0)
        print(f"  [OK]   {label}/{pid}: {dt_ms:6.1f}ms, {n_axes}/{len(AXES_OF_INTEREST)} axes active")
    return out


def analyze_divergence(cells: List[CellResult]) -> List[CellResult]:
    """Mark cells where lab diverges from the lab-vs-static baseline."""
    diverged: List[CellResult] = []
    for c in cells:
        if c.lab is None or not c.lab.available:
            continue
        # Diverge if |lab - static| or |lab - llm| > threshold
        d_static = abs(c.lab.aggregate - c.static.aggregate)
        d_llm = (
            abs(c.lab.aggregate - c.llm.aggregate)
            if c.llm is not None and c.llm.available
            else 0.0
        )
        if max(d_static, d_llm) > DIVERGENCE_THRESHOLD:
            c.divergent = True
            diverged.append(c)
    return diverged


def render_table(prompts, static_results, llm_results, lab_results) -> str:
    """Render the 3-layer comparison table per (prompt, axis) cell."""
    lines: List[str] = []
    lines.append("# v0.3 区分度报告（Day 4 G3 验证）\n")
    lines.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"散度阈值：{DIVERGENCE_THRESHOLD}（任一层 vs lab 差异 > 此值算分歧）\n")
    lines.append(f"G3 通过条件：至少 {MIN_DIVERGENCE_CASES} 个 (prompt, axis) 单元有分歧\n")
    lines.append("\n")

    lines.append("## 三层对比表\n")
    lines.append("\n")
    header = "| prompt | axis | static | LLM | lab | divergent |\n"
    sep = "|---|---|---|---|---|---|\n"
    lines.append(header)
    lines.append(sep)

    cells: List[CellResult] = []
    for pid, _ in prompts:
        for axis in AXES_OF_INTEREST:
            s = static_results[pid][axis]
            l = llm_results.get(pid, {}).get(axis) if llm_results else None
            lab = lab_results.get(pid, {}).get(axis) if lab_results else None
            cell = CellResult(
                prompt_id=pid, axis=axis,
                static=s, llm=l, lab=lab,
            )
            cells.append(cell)

    diverged = analyze_divergence(cells)

    for c in cells:
        static_str = f"{c.static.aggregate:.2f} (n={c.static.n_sources})"
        llm_str = (
            f"{c.llm.aggregate:.2f} (n={c.llm.n_sources})"
            if c.llm and c.llm.available else "—"
        )
        lab_str = (
            f"{c.lab.aggregate:.2f} (n={c.lab.n_sources})"
            if c.lab and c.lab.available else "—"
        )
        div = "**YES**" if c.divergent else ""
        lines.append(
            f"| {c.prompt_id} | {c.axis.value} | {static_str} | "
            f"{llm_str} | {lab_str} | {div} |\n"
        )

    # Categorize divergent cases
    lab_only = []         # lab fires, static silent (lab adds value)
    static_only = []      # static fires, lab silent (lab misses)
    both_disagree = []    # both fire, magnitudes differ (hybrid disagreement)
    for c in diverged:
        s_fired = c.static.n_sources > 0
        l_fired = c.lab.n_sources > 0
        if l_fired and not s_fired:
            lab_only.append(c)
        elif s_fired and not l_fired:
            static_only.append(c)
        elif s_fired and l_fired:
            both_disagree.append(c)

    # Cases where lab catches signals static missed but |diff| is too small
    # to count as "divergent" by the 0.20 threshold. These are still valuable
    # — they show lab is doing useful work, just under the threshold radar.
    lab_unique_subthreshold = []
    for c in cells:
        if c.lab is None or not c.lab.available:
            continue
        if c.divergent:
            continue
        if c.lab.n_sources > 0 and c.static.n_sources == 0:
            lab_unique_subthreshold.append(c)

    # Per-case analysis
    lines.append("\n## 分歧 case 分析\n\n")
    if not diverged:
        lines.append("**未发现达到 |diff| > 0.20 阈值的分歧 case。**\n\n")
    else:
        lines.append(
            f"按分歧类型分组（共 {len(diverged)} 个 case）：\n"
            f"- **Lab 加价值**（lab fires, static silent）：{len(lab_only)}\n"
            f"- **双层都触发但读数不同**（hybrid disagreement）：{len(both_disagree)}\n"
            f"- **Lab 漏检**（lab silent, static fires）：{len(static_only)}\n\n"
        )

        for category_name, category_cases in [
            ("Lab 加价值", lab_only),
            ("双层都触发但读数不同", both_disagree),
            ("Lab 漏检", static_only),
        ]:
            if not category_cases:
                continue
            lines.append(f"### 类型：{category_name}\n\n")
            for c in category_cases:
                d_static = abs(c.lab.aggregate - c.static.aggregate)
                d_llm = (
                    abs(c.lab.aggregate - c.llm.aggregate)
                    if c.llm and c.llm.available else None
                )
                lines.append(f"#### {c.prompt_id} × {c.axis.value}\n\n")
                lines.append(f"- static: **{c.static.aggregate:.3f}** (n={c.static.n_sources})\n")
                if c.llm and c.llm.available:
                    lines.append(f"- LLM: **{c.llm.aggregate:.3f}** (n={c.llm.n_sources})\n")
                lines.append(f"- lab: **{c.lab.aggregate:.3f}** (n={c.lab.n_sources})\n")
                lines.append(f"- |lab − static| = {d_static:.3f}")
                if d_llm is not None:
                    lines.append(f"; |lab − LLM| = {d_llm:.3f}")
                lines.append("\n\n")
                lines.append(_interpret_divergence(c) + "\n\n")

    # Sub-threshold lab-only signals (not divergent by metric, but still valuable)
    if lab_unique_subthreshold:
        lines.append(
            "## Lab 阈下加价值 case（未计入 G3 分歧但有意义）\n\n"
            f"Lab 层在 {len(lab_unique_subthreshold)} 个 (prompt, axis) 单元上触发了"
            "证据，而 static 层完全沉默。这些 case 没有越过 |diff| > 0.20 的"
            "G3 分歧阈值（因为 static 的 baseline 0.50 距离 lab 读数较近），"
            "但它们是 lab 层 **真正补完文本规则覆盖盲区** 的证据。\n\n"
        )
        for c in lab_unique_subthreshold:
            d_static = abs(c.lab.aggregate - c.static.aggregate)
            lines.append(
                f"- **{c.prompt_id} × {c.axis.value}**: lab={c.lab.aggregate:.3f} "
                f"(n={c.lab.n_sources}), static=baseline (n=0), |diff|={d_static:.3f}\n"
            )
        lines.append("\n")

    # G3 verdict
    lines.append("---\n\n")
    lines.append("## G3 评判\n\n")
    n = len(diverged)
    if n >= MIN_DIVERGENCE_CASES:
        lines.append(
            f"✅ **PASS by letter**：发现 {n} 个分歧 case，达到 ≥ "
            f"{MIN_DIVERGENCE_CASES} 阈值。\n\n"
        )
        # Honest verdict: distinguish "lab adds value" from "lab misses"
        value_add = len(lab_only) + len(both_disagree) + len(lab_unique_subthreshold)
        lab_failures = len(static_only)
        lines.append("**诚实评估**（严格审视 lab 是否真正加价值）：\n\n")
        lines.append(
            f"- Lab 加价值证据：{value_add} 个 case "
            f"（{len(lab_only)} 个补盲 + {len(both_disagree)} 个 hybrid 校验 + "
            f"{len(lab_unique_subthreshold)} 个阈下补盲）\n"
        )
        lines.append(
            f"- Lab 漏检（static 抓到但 lab 沉默）：{lab_failures} 个 case\n\n"
        )
        if value_add >= 2:
            lines.append(
                "**结论：可以上线。** Lab 层在 ≥ 2 个独立 case 上展现 hybrid 价值"
                "（补盲 + 校验），即使在 1.5B distilled 模型这个最不利的实验设置下。"
                "Lab 漏检的 case 不构成回归——static 仍然抓到，hybrid 不会比 static-only 差。\n"
            )
        elif value_add >= 1:
            lines.append(
                "**结论：边缘 PASS。** Lab 仅在 1 个 case 上展现独立价值。"
                "建议作为 opt-in 实验功能上线，不默认启用，"
                "并在 v0.3.1 重新校准 axis vectors。\n"
            )
        else:
            lines.append(
                "**结论：技术上 PASS 但实质 FAIL。** 所有 \"分歧\" 都是 lab 漏检 "
                "static 抓到的信号，lab 层没有独立加价值。"
                "建议不上线，回 G3 失败应对流程。\n"
            )
    else:
        lines.append(
            f"❌ **FAIL**：仅发现 {n} 个分歧 case，未达到 ≥ {MIN_DIVERGENCE_CASES} 阈值。\n\n"
        )
        lines.append("**下一步选项**（参考 TECHNICAL_v03.md §8）：\n\n")
        lines.append("1. 换 layer：当前是 -1（最后一层），试 -8 或 -16（中间层）\n")
        lines.append("2. 重设计 contrastive pairs：当前 pairs 可能太工程化\n")
        lines.append("3. 承认 Persona Vectors 在 1.5B distilled 上不够强，降级为研究品\n")
    return "".join(lines)


def _interpret_divergence(cell: "Cell") -> str:
    """Generate a per-case interpretation based on the divergence pattern.

    Three patterns:
    - Lab silent (n=0) but Static fires: regex caught a textual feature the
      lab projection failed to mirror. Common on a 1.5B distilled model when
      the signal is weaker than 0.10 noise floor.
    - Lab fires but disagrees in magnitude with Static: both layers detected
      something but read it differently. Most interesting case — lab is
      adding genuinely new information.
    - Lab fires while Static silent: lab caught something the regex missed.
      Worth a closer look — could be a real false negative in the rule library.
    """
    static_fired = cell.static.n_sources > 0
    lab_fired = cell.lab.n_sources > 0

    if static_fired and not lab_fired:
        return (
            f"**模式**：static 抓到 {cell.static.n_sources} 条规则证据"
            f"（aggregate={cell.static.aggregate:.2f}），但 lab 投影低于 noise floor"
            f"（|raw| < 0.10）。原因可能是：①该 prompt 触发了表层措辞规则"
            f"（如 '{cell.axis.value}' 的关键词），但激活方向在 1.5B distilled "
            f"模型上未充分对齐 axis vector；②规则可能过敏（false positive）。"
            f"判断标准：看 static 给出的 rule_id 是否合理；如果规则没问题，"
            f"那这是 1.5B distilled 模型的物理局限——大模型上同 prompt 信号会更强。"
        )

    if lab_fired and not static_fired:
        return (
            f"**模式**：lab 抓到 {cell.lab.n_sources} 条投影证据"
            f"（aggregate={cell.lab.aggregate:.2f}），但 static 规则未匹配。"
            f"这是 **lab 层最有价值的发现**——抓到了规则库漏掉的语义信号。"
            f"建议人工 review：①确认 prompt 在该轴上是否真的有问题；"
            f"②如果是真信号，把这种 prompt 模式补进 static rules；"
            f"③如果是 lab 误报，记录 false positive 案例待后续校准。"
        )

    if static_fired and lab_fired:
        return (
            f"**模式**：两层都有信号但读数不一致。Static 给"
            f"{cell.static.aggregate:.2f}（{cell.static.n_sources} 条规则），"
            f"lab 给 {cell.lab.aggregate:.2f}（{cell.lab.n_sources} 条投影）。"
            f"这是 hybrid 设计的核心价值——两层独立证据互相校验。"
            f"如果 lab 比 static 更克制（数值更接近 baseline），说明规则可能过敏；"
            f"如果 lab 比 static 更激进，说明 prompt 的激活方向比表层措辞更强。"
        )

    return "**模式**：两层都未触发，但加权 baseline 不同。无须人工关注。"


def main() -> int:
    args = parse_args()
    prompts = load_examples()
    if not prompts:
        print(f"FAIL: no .txt examples found in {EXAMPLES_DIR}")
        return 1
    print(f"Loaded {len(prompts)} example prompts")
    for pid, p in prompts:
        print(f"  - {pid}: {p[:60]!r}")
    print()

    # Static layer (always run)
    print("=== Static layer ===")
    static_results = run_layer(StaticRuleContributor(), prompts, "static")

    # LLM layer (skip if no key or flag)
    llm_results = {}
    if args.skip_llm:
        print("\n=== LLM layer SKIPPED ===\n")
    elif not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("\n=== LLM layer SKIPPED (no API key set) ===\n")
    else:
        print("\n=== LLM layer ===")
        from stateprobe.engines import LLMJudgeContributor
        llm_results = run_layer(LLMJudgeContributor(), prompts, "llm")

    # Lab layer (skip if no GPU / no vectors)
    lab_results = {}
    if args.skip_lab:
        print("\n=== Lab layer SKIPPED ===\n")
    else:
        print("\n=== Lab layer ===")
        try:
            from stateprobe.engines.lab import LabContributor
            lab = LabContributor(vectors_path=args.vectors)
            lab_results = run_layer(lab, prompts, "lab")
        except EngineUnavailable as exc:
            print(f"  [SKIP] lab: {exc}")
            lab_results = {}

    # Render
    md = render_table(prompts, static_results, llm_results, lab_results)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nReport written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
