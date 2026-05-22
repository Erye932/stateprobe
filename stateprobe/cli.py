"""Command-line interface for StateProbe."""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path
from typing import Optional

import io
import json
import os
import re
import warnings

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from stateprobe import __version__
from stateprobe.detector import diagnose
from stateprobe.html_report import write_report
from stateprobe.lab.deepseek_pairs import (
    DEFAULT_DEEPSEEK_MODEL,
    DEEPSEEK_AXIS_PAIRS,
)
from stateprobe.lab.probe import dependency_status
from stateprobe.lab.probe import (
    build_deepseek_vectors,
    load_model_and_tokenizer,
    project_prompt,
)
from stateprobe.eval.client import DEFAULT_EVAL_MODEL, DEFAULT_BASE_URL
from stateprobe.eval.scorer import BEHAVIOR_RUBRICS, run_eval
from stateprobe.models import Axis, Report
from stateprobe.rules import (
    DEFAULT_MODEL_BASELINE,
    DEFAULT_TARGET,
    MODEL_BASELINES,
    TARGET_PRESETS,
)


def _ensure_utf8_windows() -> None:
    """Force UTF-8 stdout/stderr on Windows to avoid GBK/CP936 encoding errors.

    Chinese Windows defaults to CP936 (GBK). Rich outputs UTF-8 box-drawing
    characters (▓░┃┌─┐ etc.) and Chinese text, which become garbled under GBK.

    This function:
    1. Sets the Windows console output code page to 65001 (UTF-8) via kernel32.
    2. Wraps sys.stdout/stderr with UTF-8 TextIOWrapper.

    Called both at module-level (for Console init) and per-command (safety net).
    Skips when stdout has no buffer (e.g. Click CliRunner in tests).
    """
    if sys.platform != "win32":
        return
    # Step 1: Set Windows console code page to UTF-8
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except (AttributeError, OSError):
        pass
    if not hasattr(sys.stdout, "buffer"):
        return
    # Step 2: Wrap stdout/stderr with UTF-8 encoding
    if getattr(sys.stdout, "encoding", "").lower().replace("-", "") == "utf8":
        return
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )
    except (AttributeError, ValueError):
        pass


# Apply UTF-8 fix BEFORE Console init so Rich sees UTF-8 stdout.
_ensure_utf8_windows()

console = Console(force_terminal=True)


# ---------------------------------------------------------------------------
# Contributor failure UX (yellow panels with context-aware hints)
#
# Every optional contributor (LLM judge, Lab activation projection, future
# embedding contributor) follows the same UX contract:
#   1. If the contributor cannot run (no API key, no GPU, no vectors,
#      malformed file, …) the CLI shows ONE yellow panel naming the layer
#      and giving an actionable next-step hint.
#   2. The remaining contributors still produce a report (graceful
#      degradation; exit code 0).
#
# Two paths produce the same panel UX:
#   A. Eager init failure  → CLI catches EngineUnavailable from constructor
#      (LabContributor with --lab-eager, LLM API-key pre-flight).
#   B. Lazy runtime failure → detect_readings() emits RuntimeWarning
#      (LLM 401 on first call, Lab lazy model-load failure). The CLI wraps
#      diagnose() in warnings.catch_warnings() and translates each captured
#      RuntimeWarning into the same panel.
#
# Both paths route through _render_contributor_warning() so the user can't
# tell which one fired — they just see "⚠ Lab unavailable" / "⚠ LLM
# unavailable" with the right hint.
# ---------------------------------------------------------------------------

def _hint_for_lab_unavailable(msg: str) -> str:
    """Return an actionable hint for a LabContributor failure message.

    Tested by test_check_lab_hint_matcher_routes_each_failure_class_correctly.
    """
    msg_lower = msg.lower()
    if "cuda" in msg_lower:
        return (
            "需要本地 NVIDIA GPU + CUDA。无 GPU 请省略 [bold]--lab-augment[/bold]，"
            "静态层 (+ 可选 LLM) 仍会出报告。"
        )
    if (
        "torch not installed" in msg_lower
        or "transformers" in msg_lower
        or "lab dependencies missing" in msg_lower
        or "stateprobe.lab.probe unavailable" in msg_lower
        or "stateprobe.lab.cache unavailable" in msg_lower
    ):
        return "缺少可选依赖。安装：[bold]pip install -e \".[lab]\"[/bold]"
    if (
        "not found" in msg_lower
        or "no vectors" in msg_lower
        or "no recognized axes" in msg_lower
        or "failed to load" in msg_lower
        or "schema_version" in msg_lower
    ):
        return (
            "缺 vectors 文件或文件损坏。先跑 "
            "[bold]python scripts/build_lab_vectors.py[/bold] 重新生成，"
            "或用 [bold]--lab-vectors[/bold] 指向已有文件。"
        )
    if "model load failed" in msg_lower:
        return (
            "模型加载失败。设环境变量 "
            "[bold]STATEPROBE_LAB_MODEL_PATH[/bold] 指向本地 snapshot，"
            "或先用 ModelScope/HF CLI 预下载。"
        )
    return (
        "省略 [bold]--lab-augment[/bold] 跑无 Lab 层；"
        "详细诊断见 [bold]docs/EXECUTION_v03.md[/bold]。"
    )


def _hint_for_llm_unavailable(msg: str) -> str:
    """Return an actionable hint for an LLMJudgeContributor failure message.

    Mirrors the Lab hint matcher so LLM failures get the same context-aware
    UX (instead of the previous raw RuntimeWarning stderr dump). Each branch
    is locked by test_check_llm_hint_matcher_routes_each_failure_class_correctly.
    """
    msg_lower = msg.lower()
    # Missing API key — matches both the Chinese "未找到 API key" raised by
    # chat_completion._get_api_key and the English "missing api key".
    if "未找到 api key" in msg_lower or "missing api key" in msg_lower:
        return (
            "设环境变量 [bold]DEEPSEEK_API_KEY[/bold] (或 [bold]OPENAI_API_KEY[/bold])，"
            "或用 [bold]--api-key[/bold] 传入。"
        )
    # Authentication failure (401 / 403 / "Authentication Fails")
    if (
        "401" in msg
        or "403" in msg
        or "authentication" in msg_lower
        or "unauthorized" in msg_lower
        or "invalid_request_error" in msg_lower
    ):
        return (
            "API key 无效或已过期。检查 [bold]DEEPSEEK_API_KEY[/bold] 是否正确，"
            "或在 https://platform.deepseek.com 重新申请。"
        )
    # Model not found
    if "404" in msg and "model" in msg_lower:
        return (
            "模型名不存在。用 [bold]--llm-model[/bold] 指定可用模型 "
            "(如 [bold]deepseek-chat[/bold]、[bold]deepseek-reasoner[/bold])。"
        )
    # Network / DNS / proxy
    if (
        "connection" in msg_lower
        or "timeout" in msg_lower
        or "timed out" in msg_lower
        or "unreachable" in msg_lower
        or "name or service" in msg_lower
        or "getaddrinfo" in msg_lower
    ):
        return (
            "API 不可达。检查网络/代理；或用 [bold]--llm-base-url[/bold] 切换 endpoint。"
        )
    # Rate limit
    if "429" in msg or "rate limit" in msg_lower:
        return "API 触发限流，稍后重试或升级配额。"
    # 5xx — server-side error (must come AFTER the 401/403/404 checks)
    if re.search(r"\b5\d\d\b", msg):
        return (
            "API 服务端错误。稍后重试；"
            "或用 [bold]--llm-base-url[/bold] 切换到备用 endpoint。"
        )
    # Malformed JSON from judge
    if "json" in msg_lower and ("解析失败" in msg or "未找到" in msg or "parse" in msg_lower):
        return (
            "LLM 判官返回了非法 JSON。换一个 [bold]--llm-model[/bold]，"
            "或省略 [bold]--llm-augment[/bold] 跑无 LLM 层。"
        )
    return (
        "省略 [bold]--llm-augment[/bold] 跑无 LLM 层；"
        "或检查 [bold]--llm-model[/bold] / [bold]--llm-base-url[/bold] / [bold]DEEPSEEK_API_KEY[/bold]。"
    )


def _render_contributor_warning(layer_name: str, msg: str, hint: str) -> None:
    """Render a yellow panel for a contributor unavailability.

    Used by both the eager-init try/except path (e.g. --lab-eager,
    LLM API-key pre-flight) and the lazy-runtime warnings.catch_warnings()
    path so users see a consistent message regardless of which contributor
    failed and at which lifecycle stage.
    """
    console.print(Panel(
        Text.from_markup(
            f"[yellow]{layer_name} 层不可用：[/yellow] {msg}\n"
            f"[dim]Hint: {hint}[/dim]"
        ),
        title=f"⚠ {layer_name} unavailable",
        border_style="yellow",
    ))


# Compiled once: parse the standard "Contributor '<name>' unavailable;
# dropping its evidence: <message>" string detect_readings() emits.
_CONTRIB_WARNING_RE = re.compile(
    r"Contributor '([^']+)' unavailable.*?dropping its evidence:\s*(.*)",
    re.DOTALL,
)


def _route_captured_warnings(caught: list) -> None:
    """Translate captured RuntimeWarnings from detect_readings() into panels.

    Non-RuntimeWarning entries are re-emitted so external warning consumers
    (pytest -W, library callers) keep seeing them. Stateprobe's own
    contributor-drop warnings get rendered as yellow panels matching the
    eager-init UX.
    """
    for w in caught:
        if not issubclass(w.category, RuntimeWarning):
            warnings.warn_explicit(
                str(w.message), w.category, w.filename, w.lineno,
            )
            continue
        match = _CONTRIB_WARNING_RE.search(str(w.message))
        if not match:
            warnings.warn_explicit(
                str(w.message), w.category, w.filename, w.lineno,
            )
            continue
        contrib_name = match.group(1)
        contrib_msg = match.group(2).strip()
        if contrib_name == "llm_judge":
            _render_contributor_warning(
                "LLM", contrib_msg, _hint_for_llm_unavailable(contrib_msg),
            )
        elif contrib_name == "lab":
            _render_contributor_warning(
                "Lab", contrib_msg, _hint_for_lab_unavailable(contrib_msg),
            )
        else:
            console.print(Panel(
                Text.from_markup(
                    f"[yellow]Contributor '{contrib_name}' 不可用：[/yellow] {contrib_msg}"
                ),
                title="⚠ Contributor unavailable",
                border_style="yellow",
            ))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_prompt(prompt_arg: Optional[str], file_path: Optional[str]) -> str:
    """Resolve prompt text from CLI args.

    Priority: --file > positional argument > stdin (if neither given and
    stdin is not a TTY).
    """
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    if prompt_arg:
        return prompt_arg.strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    raise click.UsageError(
        "请提供 prompt：作为参数、用 --file 读取，或通过 stdin 传入。"
    )


def _bar(value: float, width: int = 24, target: Optional[float] = None) -> Text:
    """Render a horizontal bar with a target marker. Returns rich Text."""
    filled = int(round(value * width))
    bar = Text()
    bar.append("▓" * filled, style="cyan")
    bar.append("░" * (width - filled), style="grey39")
    if target is not None:
        marker_pos = int(round(target * width))
        # Annotate target position by changing the char at that index in style.
        # Build a fresh Text with marker overlay.
        bar = Text()
        for i in range(width):
            if i == marker_pos:
                bar.append("┃", style="bold yellow")
            elif i < filled:
                bar.append("▓", style="cyan")
            else:
                bar.append("░", style="grey39")
    return bar


def _status_icon(delta: float) -> Text:
    if abs(delta) <= 0.15:
        return Text("✓", style="bold green")
    if delta < 0:
        return Text("↓ 过高", style="bold red")
    return Text("↑ 过低", style="bold red")


def _alignment_color(score: float) -> str:
    if score >= 0.80:
        return "bold green"
    if score >= 0.55:
        return "bold yellow"
    return "bold red"


# ---------------------------------------------------------------------------
# Terminal renderers
# ---------------------------------------------------------------------------

def render_terminal(report: Report) -> None:
    """Print the report nicely in the terminal."""
    # Header
    console.print()
    title = Text("StateProbe", style="bold magenta")
    title.append("  ·  ", style="grey50")
    title.append("Prompt 状态诊断", style="bold white")
    console.print(Panel(title, border_style="magenta", expand=False))

    # Prompt + target info
    prompt_preview = report.prompt
    if len(prompt_preview) > 280:
        prompt_preview = prompt_preview[:280] + "…"
    info = Text()
    info.append("Prompt:  ", style="grey50")
    info.append(prompt_preview + "\n", style="white")
    info.append("Target:  ", style="grey50")
    info.append(f"{report.target.label_zh}", style="bold cyan")
    info.append(f"  ({report.target.name})\n", style="grey50")
    info.append(report.target.description_zh, style="grey50")
    console.print(Panel(info, border_style="grey39", title="输入"))

    # Trivial prompt notice
    if report.is_trivial:
        console.print(Panel(
            "[bold yellow]提示词内容过少，无法有效诊断。[/bold yellow]\n"
            "以下读数仅反映模型默认行为（baseline），不是你的提示词效果。\n"
            "请输入一个有实际指令的 prompt 再试。",
            title="⚠ 空诊断",
            border_style="yellow",
        ))

    # Axis readings table
    table = Table(
        title="\n各轴读数（▓ = 当前激活，┃ = 目标坐标）",
        title_style="bold white",
        header_style="bold cyan",
        border_style="grey39",
        show_lines=False,
    )
    table.add_column("轴", style="white", no_wrap=True)
    table.add_column("读数条", no_wrap=True)
    table.add_column("当前", justify="right", style="cyan")
    table.add_column("目标", justify="right", style="yellow")
    table.add_column("状态", justify="left")

    for axis in Axis:
        reading = report.readings[axis]
        target_val = report.target.coordinates.get(axis, 0.5)
        delta = report.deltas[axis].delta
        table.add_row(
            axis.label_zh,
            _bar(reading.value, width=24, target=target_val),
            f"{reading.value * 100:.0f}%",
            f"{target_val * 100:.0f}%",
            _status_icon(delta),
        )
    console.print(table)

    # Alignment score — only meaningful when there's actual evidence from
    # the prompt. On trivial prompts the deltas are pure baseline-vs-target,
    # which says nothing about the user's prompt; showing a score would
    # mislead. The trivial banner upstream already explains why.
    if not report.is_trivial:
        align = report.alignment_score
        align_text = Text()
        align_text.append("对齐度: ", style="grey50")
        align_text.append(f"{align * 100:.0f}%", style=_alignment_color(align))
        if align >= 0.80:
            align_text.append("  (已对齐，无需改写)", style="green")
        elif align >= 0.55:
            align_text.append("  (部分对齐，建议改写)", style="yellow")
        else:
            align_text.append("  (严重偏离，强烈建议改写)", style="red")
        console.print(align_text)

    # Pollution sources
    sources = report.pollution_sources
    console.print()
    if not sources:
        console.print(Panel("未检测到显著污染源。", title="污染源", border_style="green"))
    else:
        sources_sorted = sorted(sources, key=lambda s: s.weight, reverse=True)
        ptable = Table(
            title=f"\n污染源（{len(sources)} 条，按权重降序）",
            title_style="bold white",
            header_style="bold red",
            border_style="grey39",
            show_lines=True,
        )
        ptable.add_column("轴", style="white")
        ptable.add_column("方向", justify="center")
        ptable.add_column("匹配文本", style="yellow")
        ptable.add_column("权重", justify="right", style="cyan")
        ptable.add_column("机制", style="grey70")
        for src in sources_sorted:
            arrow = Text("↓", style="green") if src.direction < 0 else Text("↑", style="red")
            ptable.add_row(
                src.axis.label_zh,
                arrow,
                f"「{src.matched_text}」",
                f"{src.weight:.2f}",
                src.explanation_zh,
            )
        console.print(ptable)

    # Baseline overlaps (meta-instruction warnings)
    if report.baseline_overlaps:
        console.print()
        bl = report.model_baseline
        bl_title = f"元指令重叠警告（模型: {bl.label_zh}）" if bl else "元指令重叠警告"
        ol_table = Table(
            title=f"\n{bl_title}",
            title_style="bold white",
            header_style="bold magenta",
            border_style="magenta",
            show_lines=True,
        )
        ol_table.add_column("轴", style="white")
        ol_table.add_column("模型基线", justify="center", style="yellow")
        ol_table.add_column("你的提示词", justify="center", style="cyan")
        ol_table.add_column("诊断", style="bright_red")
        for ov in report.baseline_overlaps:
            ol_table.add_row(
                ov.axis.label_zh,
                f"{ov.model_baseline:.0%}",
                f"{ov.user_pressure:.0%}",
                ov.warning_zh,
            )
        console.print(ol_table)

    # Structural warnings (length / redundancy / synonym stacking / filler)
    if report.structural_warnings:
        console.print()
        sw_table = Table(
            title="\n结构警告（V4 CSA 压缩相关）",
            title_style="bold white",
            header_style="bold yellow",
            border_style="yellow",
            show_lines=True,
        )
        sw_table.add_column("严重度", style="white", no_wrap=True)
        sw_table.add_column("类型", style="cyan", no_wrap=True)
        sw_table.add_column("诊断", style="white")
        sw_table.add_column("建议", style="bright_blue")
        _severity_styles = {
            "critical": ("[bold red]严重[/bold red]", "red"),
            "warning": ("[bold yellow]警告[/bold yellow]", "yellow"),
            "info": ("[dim]提示[/dim]", "dim"),
        }
        _kind_zh = {
            "length": "长度",
            "redundancy": "重复",
            "synonym_stacking": "同义词堆叠",
            "filler": "填充副词",
        }
        for w in report.structural_warnings:
            sev_label, _ = _severity_styles.get(w.severity, (w.severity, "white"))
            sw_table.add_row(
                sev_label,
                _kind_zh.get(w.kind, w.kind),
                w.message_zh,
                w.suggestion_zh or "",
            )
        console.print(sw_table)

    # Suggestions
    console.print()
    if not report.suggestions:
        if not report.is_trivial:
            console.print(
                Panel("✓ 已对齐目标坐标，无需改写。", title="改写建议", border_style="green")
            )
        # else: trivial banner upstream already told the user why there's
        # nothing to suggest. Don't double-message.
    else:
        for i, sug in enumerate(report.suggestions, 1):
            action_style = "green" if sug.action == "add" else "red"
            text = Text()
            text.append(f"[{sug.action.upper()}] ", style=f"bold {action_style}")
            text.append(f"{sug.axis.label_zh}  ", style="bold cyan")
            text.append("\n")
            text.append(f"  {sug.description_zh}", style="white")
            if sug.example_zh:
                text.append("\n")
                text.append(f"  示例: ", style="grey50")
                text.append(sug.example_zh, style="italic bright_blue")
            console.print(Panel(text, title=f"建议 {i}/{len(report.suggestions)}", border_style="blue"))

    console.print()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="stateprobe")
@click.pass_context
def main(ctx: click.Context) -> None:
    """StateProbe — Prompt 的状态 debugger。

    输入一段 prompt，诊断它激活了模型的哪些行为向量，
    给出污染源和改写建议。
    """
    _ensure_utf8_windows()
    if ctx.invoked_subcommand is None:
        _show_welcome()


def _show_welcome() -> None:
    """Welcome screen shown when stateprobe is invoked with no arguments.

    Replaces the default click help dump with a friendlier 3-option menu
    optimized for first-time users.
    """
    welcome = Panel(
        Text.from_markup(
            "[bold cyan]StateProbe[/bold cyan]  ·  Prompt 状态调试器\n\n"
            "第一次用？直接试这两个：\n\n"
            "  [bold green]stateprobe demo[/bold green]              "
            "[dim]# 30 秒看完整诊断效果[/dim]\n"
            "  [bold green]stateprobe ask[/bold green]               "
            "[dim]# 进入对话模式，粘贴 prompt 直接诊断[/dim]\n\n"
            "或者直接传 prompt：\n\n"
            "  [bold green]stateprobe check[/bold green] [yellow]\"你是资深专家请分析所有角度\"[/yellow]\n\n"
            "[dim]看全部命令：stateprobe --help[/dim]"
        ),
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(welcome)


@main.command()
def demo() -> None:
    """30 秒演示：用一个典型坏 prompt 跑完整诊断。

    不需要任何参数。读者装完直接 `stateprobe demo` 就能看到工具能力。
    """
    _ensure_utf8_windows()
    demo_prompt = "你是一位顶级 AI 专家，请彻底全面深入仔细完整地分析所有角度"
    console.print(Panel(
        Text.from_markup(
            f"[bold]演示 prompt:[/bold] [yellow]{demo_prompt}[/yellow]\n\n"
            f"[dim]这是一个典型的'看起来很好其实很糟'的 prompt：\n"
            f"  · 强人设触发专家腔\n"
            f"  · 同义词堆叠（彻底/全面/深入/仔细/完整）\n"
            f"  · 任务过宽（所有角度）\n"
            f"  · 无失败标准\n"
            f"接下来 StateProbe 会诊断 V4-Pro 上的实际行为压力 ↓[/dim]"
        ),
        title="\n[bold cyan]StateProbe Demo[/bold cyan]",
        border_style="cyan",
    ))
    console.print()
    report = diagnose(demo_prompt, target_name="calm_reasoning", model_name="v4-pro")
    render_terminal(report)
    console.print(Panel(
        Text.from_markup(
            "[bold green]✓ Demo 结束。[/bold green]\n\n"
            "想试你自己的 prompt？\n"
            "  [bold cyan]stateprobe ask[/bold cyan]                          "
            "[dim]# 对话模式，粘贴即诊断[/dim]\n"
            "  [bold cyan]stateprobe check[/bold cyan] [yellow]\"你的 prompt\"[/yellow]   "
            "[dim]# 单次诊断[/dim]\n\n"
            "[dim]切换模型基线：--model v4-pro / v4-flash / deepseek / generic\n"
            "切换目标状态：--target calm_reasoning / strict_execution / ...[/dim]"
        ),
        border_style="green",
    ))


@main.command()
@click.option(
    "-t", "--target", "target_name",
    type=click.Choice(list(TARGET_PRESETS), case_sensitive=False),
    default=DEFAULT_TARGET,
    show_default=True,
    help="初始目标状态预设。可在对话中用 :target <name> 切换。",
)
@click.option(
    "-m", "--model", "model_name",
    type=click.Choice(list(MODEL_BASELINES), case_sensitive=False),
    default=DEFAULT_MODEL_BASELINE,
    show_default=True,
    help="初始模型基线。可在对话中用 :model <name> 切换。",
)
def ask(target_name: str, model_name: str) -> None:
    """对话模式：粘贴 prompt 即诊断。最适合新手。

    支持的对话指令：
      :model v4-pro     切换模型基线
      :target strict_execution   切换目标
      :targets          列出所有目标
      :models           列出所有模型
      :clear            清屏
      :q  /  :quit      退出
    """
    _ensure_utf8_windows()
    console.print(Panel(
        Text.from_markup(
            "[bold cyan]StateProbe 对话模式[/bold cyan]\n\n"
            "粘贴你的 prompt（[yellow]空行结束输入并诊断[/yellow]）。\n"
            f"当前设定：[green]model={model_name}[/green]  [green]target={target_name}[/green]\n\n"
            "[dim]命令：:model <name>  ·  :target <name>  ·  :models  ·  :targets  ·  :q 退出[/dim]"
        ),
        border_style="cyan",
    ))
    console.print()

    current_model = model_name
    current_target = target_name

    while True:
        try:
            # Collect multi-line input until blank line
            console.print("[bold cyan]>[/bold cyan] ", end="")
            first_line = input().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]再见。[/dim]")
            return

        if not first_line:
            continue

        # Handle dialog commands
        if first_line.startswith(":"):
            cmd_parts = first_line[1:].split(None, 1)
            cmd = cmd_parts[0].lower() if cmd_parts else ""
            arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
            if cmd in ("q", "quit", "exit"):
                console.print("[dim]再见。[/dim]")
                return
            if cmd == "clear":
                console.clear()
                continue
            if cmd == "models":
                console.print("[bold]可用模型基线：[/bold]")
                for name in MODEL_BASELINES:
                    marker = " [green](当前)[/green]" if name == current_model else ""
                    console.print(f"  · {name}{marker}")
                continue
            if cmd == "targets":
                console.print("[bold]可用目标预设：[/bold]")
                for name in TARGET_PRESETS:
                    marker = " [green](当前)[/green]" if name == current_target else ""
                    console.print(f"  · {name}{marker}")
                continue
            if cmd == "model":
                if arg in MODEL_BASELINES:
                    current_model = arg
                    console.print(f"[green]✓ 模型切换为 {arg}[/green]")
                else:
                    console.print(f"[red]未知模型 {arg!r}。可用：{list(MODEL_BASELINES)}[/red]")
                continue
            if cmd == "target":
                if arg in TARGET_PRESETS:
                    current_target = arg
                    console.print(f"[green]✓ 目标切换为 {arg}[/green]")
                else:
                    console.print(f"[red]未知目标 {arg!r}。可用：{list(TARGET_PRESETS)}[/red]")
                continue
            console.print(f"[red]未知命令 :{cmd}[/red]")
            continue

        # Collect additional lines until blank
        lines = [first_line]
        while True:
            try:
                next_line = input()
            except (EOFError, KeyboardInterrupt):
                break
            if not next_line.strip():
                break
            lines.append(next_line)

        prompt = "\n".join(lines)
        console.print()
        report = diagnose(prompt, target_name=current_target, model_name=current_model)
        render_terminal(report)
        console.print()
        console.print("[dim]继续粘贴下一个 prompt，或 :q 退出[/dim]")
        console.print()


@main.command()
@click.argument("prompt", required=False)
@click.option(
    "-f", "--file", "file_path",
    type=click.Path(exists=True, dir_okay=False),
    help="从文件读取 prompt（替代直接传参）。",
)
@click.option(
    "-t", "--target", "target_name",
    type=click.Choice(list(TARGET_PRESETS), case_sensitive=False),
    default=DEFAULT_TARGET,
    show_default=True,
    help="目标状态预设。",
)
@click.option(
    "--html", "html_path",
    type=click.Path(dir_okay=False),
    help="生成 HTML 报告到指定路径。",
)
@click.option(
    "--open", "auto_open",
    is_flag=True,
    default=False,
    help="生成 HTML 后自动用浏览器打开。",
)
@click.option(
    "--no-terminal",
    is_flag=True,
    default=False,
    help="不在终端打印报告（只生成 HTML）。",
)
@click.option(
    "-m", "--model", "model_name",
    type=click.Choice(list(MODEL_BASELINES), case_sensitive=False),
    default=DEFAULT_MODEL_BASELINE,
    show_default=True,
    help="模型基线（元指令预设）。用于检测提示词与元指令的重叠。",
)
@click.option(
    "--llm-augment",
    "llm_augment",
    is_flag=True,
    default=False,
    help="启用 LLM 语义层。在静态规则之外叠加 LLM-as-Judge 的证据"
         "（v0.2 hybrid，需要 DEEPSEEK_API_KEY 或 --api-key）。"
         "缺 key 或 API 不可用时，会以黄色面板提示并降级到只跑静态层。",
)
@click.option(
    "--engine",
    "engine_name",
    type=click.Choice(["static", "llm"], case_sensitive=False),
    default=None,
    show_default=False,
    hidden=True,
    help="DEPRECATED：v0.2.0.dev0 旧参数。请改用 --llm-augment。"
         "--engine llm 等价于 --llm-augment（且静态层不再被丢弃）。",
)
@click.option(
    "--llm-model",
    "llm_model",
    default=DEFAULT_EVAL_MODEL,
    show_default=True,
    help="LLM 语义层使用的判断模型（仅 --llm-augment 时生效）。",
)
@click.option(
    "--llm-base-url",
    "llm_base_url",
    default=DEFAULT_BASE_URL,
    show_default=True,
    help="LLM 语义层 API base URL（仅 --llm-augment 时生效）。",
)
@click.option(
    "--api-key",
    "api_key",
    default=None,
    help="LLM 语义层 API key。未提供时从 DEEPSEEK_API_KEY / OPENAI_API_KEY 环境变量读取。",
)
@click.option(
    "--lab-augment",
    "lab_augment",
    is_flag=True,
    default=False,
    help="启用 lab 激活投影层（v0.3 hybrid 第三层）。需要本地 GPU + 预计算的 axis vectors。"
         "用 scripts/build_lab_vectors.py 一次性生成 vectors 文件。",
)
@click.option(
    "--lab-vectors",
    "lab_vectors",
    default=None,
    help="lab 层的 axis vectors 文件路径（默认 lab_vectors/r1_distill_1.5b_v1.pt）。",
)
@click.option(
    "--lab-model",
    "lab_model",
    default=None,
    help="覆盖 vectors 文件里记录的模型名（默认用 vectors 文件里的 model_name）。",
)
@click.option(
    "--lab-eager",
    "lab_eager",
    is_flag=True,
    default=False,
    help="Lab 层模型启动时就加载（默认 lazy）。主要用于 CI / pre-flight："
         "HF 下载或模型加载失败会立刻以黄色面板报出，"
         "而不是拖到第一条 prompt 才静默降级。仅在 --lab-augment 下生效。",
)
def check(
    prompt: Optional[str],
    file_path: Optional[str],
    target_name: str,
    html_path: Optional[str],
    auto_open: bool,
    no_terminal: bool,
    model_name: str,
    llm_augment: bool,
    engine_name: Optional[str],
    llm_model: str,
    llm_base_url: str,
    api_key: Optional[str],
    lab_augment: bool,
    lab_vectors: Optional[str],
    lab_model: Optional[str],
    lab_eager: bool,
) -> None:
    """诊断一段 prompt 的状态向量。

    示例:

      stateprobe check "你是资深专家，请全面分析这个项目"

      stateprobe check --file my_prompt.txt --target super_thinking_max --html report.html --open

      stateprobe check "think step by step" --model generic

      stateprobe check --llm-augment "你的 prompt"   # v0.2 hybrid：静态 + LLM 双层证据

      stateprobe check --lab-augment "你的 prompt"   # v0.3 hybrid：静态 + lab 激活投影双层
      stateprobe check --llm-augment --lab-augment "你的 prompt"   # 三层 hybrid
      stateprobe check --lab-augment --lab-eager "你的 prompt"   # CI/pre-flight：启动即加载模型
    """
    from stateprobe.engines import LLMJudgeContributor

    text = _read_prompt(prompt, file_path)

    # Backward-compat: `--engine llm` from v0.2.0.dev0 maps to --llm-augment.
    # `--engine static` is the default and a no-op.
    if engine_name and engine_name.lower() == "llm":
        llm_augment = True
        console.print(Panel(
            Text.from_markup(
                "[yellow]`--engine llm` 已弃用。请改用 [bold]--llm-augment[/bold]。[/yellow]\n"
                "[dim]新行为：静态规则始终运行，LLM 仅作为额外证据层叠加。\n"
                "旧行为（LLM 替换静态）会在 v0.4 移除。[/dim]"
            ),
            title="⚠ 弃用警告",
            border_style="yellow",
        ))

    llm_contributor = None
    if llm_augment:
        # Pre-flight: API key must be resolvable. Fail fast with a yellow
        # panel rather than letting the missing-key error surface deep
        # inside detect_readings() on first contribute() (raw RuntimeWarning
        # with 401 JSON dump in stderr — the old "looks unreliable" UX).
        # Closes P0-2 of the v0.3 UX audit and mirrors the Lab eager-init
        # pre-flight pattern.
        has_key = bool(api_key) or bool(
            os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
        )
        if not has_key:
            msg = "未找到 API key。"
            _render_contributor_warning(
                "LLM", msg, _hint_for_llm_unavailable("未找到 api key"),
            )
        else:
            llm_contributor = LLMJudgeContributor(
                model=llm_model,
                base_url=llm_base_url,
                api_key=api_key,
            )

    # --lab-eager only meaningful with --lab-augment. Warn so users don't
    # silently get the lazy fallback when they thought they enabled eager.
    if lab_eager and not lab_augment:
        console.print(Panel(
            Text.from_markup(
                "[yellow]--lab-eager 需要配合 --lab-augment 使用。[/yellow]\n"
                "[dim]本次调用被当作不带 --lab-augment 处理（Lab 层未启用）。[/dim]"
            ),
            title="⚠ --lab-eager ignored",
            border_style="yellow",
        ))

    lab_contributor = None
    if lab_augment:
        # Lazy import to keep stateprobe importable without torch.
        from stateprobe.engines.base import EngineUnavailable
        try:
            from stateprobe.engines.lab import (
                DEFAULT_VECTORS_PATH,
                LabContributor,
            )
            if lab_eager:
                # Eager mode: load the transformer model up front so HF
                # download / model-load failures surface here (yellow panel)
                # instead of inside detect_readings on first contribute()
                # (RuntimeWarning only).
                with console.status(
                    "[cyan]Lab 层预加载模型中... (首次 ~10-30s)[/cyan]",
                    spinner="dots",
                ):
                    lab_contributor = LabContributor(
                        vectors_path=lab_vectors or DEFAULT_VECTORS_PATH,
                        model_name=lab_model,
                        lazy=False,
                    )
            else:
                lab_contributor = LabContributor(
                    vectors_path=lab_vectors or DEFAULT_VECTORS_PATH,
                    model_name=lab_model,
                )
        except EngineUnavailable as exc:
            # Degrade gracefully: lab layer unavailable, static (+ optional
            # LLM) still produce a result. Hint matcher lives in module
            # scope so the lazy-runtime path (RuntimeWarning) and the
            # eager-init path (this try/except) route through the same
            # branches — single source of truth.
            msg = str(exc)
            _render_contributor_warning(
                "Lab", msg, _hint_for_lab_unavailable(msg),
            )
            lab_contributor = None
        except ImportError as exc:
            _render_contributor_warning(
                "Lab",
                f"Lab 层依赖未安装：{exc}",
                "[bold]pip install -e \".[lab]\"[/bold]",
            )
            lab_contributor = None

    # Wrap diagnose() in warnings.catch_warnings so any RuntimeWarning the
    # detector emits when an optional contributor raises EngineUnavailable
    # at first contribute() (e.g., LLM 401 lazy-call failure, lab lazy
    # model-load failure) gets translated into the same yellow panel UX
    # as eager-init failures. Closes P0-2 of the v0.3 UX audit — previously
    # users saw a raw RuntimeWarning + 401 JSON dump in stderr and assumed
    # the tool was broken.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        report = diagnose(
            text,
            target_name=target_name,
            model_name=model_name,
            llm_augment=llm_contributor,
            lab_augment=lab_contributor,
        )
    _route_captured_warnings(caught)

    if not no_terminal:
        render_terminal(report)

    if html_path:
        out = write_report(report, Path(html_path))
        console.print(
            f"[green]✓[/green] HTML 报告已写入: [bold cyan]{out.resolve()}[/bold cyan]"
        )
        if auto_open:
            webbrowser.open(out.resolve().as_uri())
    elif auto_open:
        # User wants browser but didn't specify path → use default reports/.
        default_out = Path.cwd() / "reports" / "stateprobe_report.html"
        out = write_report(report, default_out)
        console.print(
            f"[green]✓[/green] HTML 报告已写入: [bold cyan]{out.resolve()}[/bold cyan]"
        )
        webbrowser.open(out.resolve().as_uri())


@main.command()
def targets() -> None:
    """列出所有可用的目标预设。"""
    table = Table(
        title="可用目标预设",
        header_style="bold cyan",
        border_style="grey39",
    )
    table.add_column("name", style="bold yellow")
    table.add_column("中文标签", style="bold cyan")
    table.add_column("描述", style="grey70")
    for name, preset in TARGET_PRESETS.items():
        default_marker = "  (默认)" if name == DEFAULT_TARGET else ""
        table.add_row(
            f"{name}{default_marker}",
            preset.label_zh,
            preset.description_zh,
        )
    console.print(table)


@main.command()
def axes() -> None:
    """列出所有检测的行为轴。"""
    table = Table(
        title="StateProbe 检测的 8 个行为轴",
        header_style="bold cyan",
        border_style="grey39",
    )
    table.add_column("轴", style="bold cyan")
    table.add_column("0 = 低端", style="grey70")
    table.add_column("1 = 高端", style="grey70")
    for axis in Axis:
        table.add_row(
            axis.label_zh,
            axis.low_end_zh,
            axis.high_end_zh,
        )
    console.print(table)


@main.group()
def skill() -> None:
    """StateProbe Skill：Agent 注意力仪表盘。"""


def _render_skill_group(title: str, rows: list, style: str) -> None:
    if not rows:
        return
    table = Table(
        title=title,
        header_style="bold cyan",
        border_style=style,
        show_lines=True,
    )
    table.add_column("用户要求", style="white")
    table.add_column("覆盖度", justify="right", style="cyan")
    table.add_column("命中内容", style="grey70")
    for item in rows:
        matched = "、".join(item.matched_keywords[:8]) if item.matched_keywords else "-"
        table.add_row(
            item.requirement.text,
            f"{item.coverage:.2f}",
            matched,
        )
    console.print(table)


_ALIGNMENT_STYLE = {
    "aligned": "green",
    "partial": "yellow",
    "off_task": "grey50",
    "violation": "red",
}

_PRIORITY_STYLE = {
    "must": "cyan",
    "must_not": "red",
    "supporting": "grey70",
}

_INTERRUPT_STYLE = {
    "ok": "bold green",
    "watch": "bold yellow",
    "interrupt": "bold red",
}

_INTERRUPT_LABEL = {
    "ok": "OK · 输出可继续",
    "watch": "WATCH · 关注偏移",
    "interrupt": "INTERRUPT · 建议打断当前输出",
}

_SEVERITY_STYLE = {
    "high": "bold red",
    "medium": "bold yellow",
    "low": "grey70",
}

_RISK_BORDER = {
    "low": "green",
    "medium": "yellow",
    "high": "bright_red",
}


def _skill_bar(weight: float, width: int = 12) -> str:
    """Unicode block bar for Skill HUD weight visualization (0.0~1.0).

    与项目里 check 命令使用的 ``_bar(value, width, target=...)`` 不同：
    后者返回 rich Text 且需要 target 参数；这里只返回纯字符串，用于拼
    接进 intent / attention map 表格。
    """
    try:
        w = float(weight)
    except (TypeError, ValueError):
        w = 0.0
    w = max(0.0, min(1.0, w))
    filled = int(round(w * width))
    return "█" * filled + "░" * (width - filled)


def _render_attention_hud(hud) -> None:
    drift_style = {
        "low": "bold green",
        "medium": "bold yellow",
        "high": "bold red",
    }.get(hud.drift_level, "bold white")
    interrupt_style = _INTERRUPT_STYLE.get(hud.interrupt_level, "bold white")
    interrupt_label = _INTERRUPT_LABEL.get(
        hud.interrupt_level, hud.interrupt_level
    )

    summary = Text()
    summary.append("偏移程度：", style="grey70")
    summary.append(f"{hud.drift_level}", style=drift_style)
    summary.append(f"  ({hud.drift_score:.2f})\n", style="grey70")
    summary.append("Interrupt：", style="grey70")
    summary.append(f"{interrupt_label}\n", style=interrupt_style)
    summary.append("已体现：", style="grey70")
    summary.append(str(len(hud.reflected)), style="bold green")
    summary.append("  弱体现：", style="grey70")
    summary.append(str(len(hud.weak)), style="bold yellow")
    summary.append("  被忽略：", style="grey70")
    summary.append(str(len(hud.ignored)), style="bold red")
    summary.append("  被违反：", style="grey70")
    summary.append(str(len(hud.violated)), style="bold red")
    console.print(Panel(
        summary,
        title="StateProbe Skill · Agent Attention HUD",
        border_style="magenta",
    ))

    if hud.core_focus:
        focus = Text()
        for item in hud.core_focus:
            focus.append(f"- {item}\n", style="white")
        console.print(Panel(focus, title="核心关注", border_style="cyan"))

    # Phase 7 ①：用户意图地图
    if hud.user_intent_map:
        intent_table = Table(
            show_header=True, header_style="bold cyan", expand=True
        )
        intent_table.add_column("priority", width=10)
        intent_table.add_column("weight", width=20)
        intent_table.add_column("intent", overflow="fold")
        for sig in hud.user_intent_map:
            style = _PRIORITY_STYLE.get(sig.priority, "white")
            intent_table.add_row(
                Text(sig.priority, style=style),
                Text(
                    f"{_skill_bar(sig.weight)} {sig.weight:.2f}", style=style
                ),
                sig.label,
            )
        console.print(Panel(
            intent_table,
            title="① User Intent Map · 用户要什么",
            border_style="cyan",
        ))

    # Phase 7 ②：Agent 注意力地图
    if hud.agent_attention_map:
        att_table = Table(
            show_header=True, header_style="bold magenta", expand=True
        )
        att_table.add_column("alignment", width=12)
        att_table.add_column("weight", width=20)
        att_table.add_column("focus", overflow="fold")
        for sig in hud.agent_attention_map:
            style = _ALIGNMENT_STYLE.get(sig.alignment, "white")
            att_table.add_row(
                Text(sig.alignment, style=style),
                Text(
                    f"{_skill_bar(sig.weight)} {sig.weight:.2f}", style=style
                ),
                Text(sig.label, style=style),
            )
        console.print(Panel(
            att_table,
            title="② Agent Attention Map · agent 现在关注什么",
            border_style="magenta",
        ))

    # Phase 7 ③：意图与注意力之间的缺口
    if hud.attention_gaps:
        gap_table = Table(
            show_header=True, header_style="bold yellow", expand=True
        )
        gap_table.add_column("kind", width=14)
        gap_table.add_column("severity", width=10)
        gap_table.add_column("label", overflow="fold")
        gap_table.add_column("why", overflow="fold")
        for g in hud.attention_gaps:
            sev_style = _SEVERITY_STYLE.get(g.severity, "white")
            gap_table.add_row(
                g.kind,
                Text(g.severity, style=sev_style),
                g.label,
                g.why,
            )
        console.print(Panel(
            gap_table,
            title="③ Attention Gaps · 意图与注意力的缺口",
            border_style="yellow",
        ))

    # Phase 7 ④：输出走向预测
    if hud.output_trajectory is not None:
        traj = hud.output_trajectory
        risk_style = {
            "low": "bold green",
            "medium": "bold yellow",
            "high": "bold red",
        }.get(traj.risk, "bold white")
        traj_text = Text()
        traj_text.append("likely_direction：", style="grey70")
        traj_text.append(f"{traj.likely_direction}\n", style="white")
        traj_text.append("risk：", style="grey70")
        traj_text.append(f"{traj.risk}", style=risk_style)
        traj_text.append("    confidence：", style="grey70")
        traj_text.append(f"{traj.confidence}\n", style="bold white")
        if traj.why:
            traj_text.append("why：\n", style="grey70")
            for line in traj.why:
                traj_text.append(f"  - {line}\n", style="white")
        console.print(Panel(
            traj_text,
            title="④ Output Trajectory · 继续写下去会怎样",
            border_style=_RISK_BORDER.get(traj.risk, "grey50"),
        ))

    # Phase 7 ⑤：下一轮可执行的控制杆
    levers = hud.control_levers
    if levers and (
        levers.boost or levers.suppress or levers.stop_doing or levers.return_to
    ):
        lever_table = Table(
            show_header=True, header_style="bold white", expand=True
        )
        lever_table.add_column("boost (拉回)", style="green", overflow="fold")
        lever_table.add_column(
            "return_to (回到)", style="green", overflow="fold"
        )
        lever_table.add_column("suppress (压低)", style="red", overflow="fold")
        lever_table.add_column(
            "stop_doing (停止)", style="red", overflow="fold"
        )
        rows = max(
            len(levers.boost),
            len(levers.return_to),
            len(levers.suppress),
            len(levers.stop_doing),
        )
        for i in range(rows):
            lever_table.add_row(
                levers.boost[i] if i < len(levers.boost) else "",
                levers.return_to[i] if i < len(levers.return_to) else "",
                levers.suppress[i] if i < len(levers.suppress) else "",
                levers.stop_doing[i] if i < len(levers.stop_doing) else "",
            )
        console.print(Panel(
            lever_table,
            title="⑤ Control Levers · 下一轮可执行的注意力调节",
            border_style="bright_blue",
        ))

    _render_skill_group("已体现要求", hud.reflected, "green")
    _render_skill_group("被弱化要求", hud.weak, "yellow")
    _render_skill_group("被忽略要求", hud.ignored, "red")
    _render_skill_group("被违反要求", hud.violated, "red")

    if hud.next_turn_patch:
        patch = Text()
        for line in hud.next_turn_patch:
            patch.append(f"- {line}\n", style="white")
        console.print(Panel(patch, title="下一轮纠偏", border_style="yellow"))

    notes = Text()
    for note in hud.notes:
        notes.append(f"- {note}\n", style="grey70")
    console.print(Panel(notes, title="边界说明", border_style="grey39"))


def _render_attention_preview(preview, debug: bool = False) -> None:
    risk_style = {
        "low": "bold green",
        "medium": "bold yellow",
        "high": "bold red",
    }.get(preview.risk_level, "bold white")
    continue_style = "bold green" if preview.should_continue else "bold red"

    summary = Text()
    summary.append("Risk：", style="grey70")
    summary.append(f"{preview.risk_level}", style=risk_style)
    summary.append(f"  ({preview.risk_score:.2f})\n", style="grey70")
    summary.append("Should continue：", style="grey70")
    summary.append(str(preview.should_continue), style=continue_style)
    console.print(Panel(
        summary,
        title="StateProbe · 执行边界预览",
        border_style=_RISK_BORDER.get(preview.risk_level, "magenta"),
    ))

    decision = getattr(preview, "activation_decision", None)
    if decision:
        decision_style = "bold red" if decision.should_stop else "bold green"
        decision_text = Text()
        decision_text.append("Action：", style="grey70")
        decision_text.append(decision.action, style=decision_style)
        decision_text.append("\nStop before output：", style="grey70")
        decision_text.append(str(decision.should_stop), style=decision_style)
        decision_text.append("\nReason：", style="grey70")
        decision_text.append(decision.reason, style="white")
        decision_text.append("\nMessage：", style="grey70")
        decision_text.append(decision.message, style="white")
        if decision.blockers:
            decision_text.append("\nBlockers：", style="grey70")
            decision_text.append(", ".join(decision.blockers), style="yellow")
        console.print(Panel(
            decision_text,
            title="⓪ Activation Decision · Agent 下一步",
            border_style="red" if decision.should_stop else "green",
        ))

    boundary = getattr(preview, "boundary_decomposition", None)
    if boundary:
        boundary_table = Table(
            show_header=True, header_style="bold cyan", expand=True
        )
        boundary_table.add_column("must_show", style="green", overflow="fold")
        boundary_table.add_column("can_imply", style="yellow", overflow="fold")
        boundary_table.add_column(
            "must_not_show", style="red", overflow="fold"
        )
        rows = max(
            len(boundary.must_show),
            len(boundary.can_imply),
            len(boundary.must_not_show),
            1,
        )
        for i in range(rows):
            boundary_table.add_row(
                boundary.must_show[i].element
                if i < len(boundary.must_show) else "",
                boundary.can_imply[i].element
                if i < len(boundary.can_imply) else "",
                boundary.must_not_show[i].element
                if i < len(boundary.must_not_show) else "",
            )
        console.print(Panel(
            boundary_table,
            title="① Boundary Contract · 必须显示 / 可暗示 / 禁止显示",
            border_style="cyan",
        ))

    if getattr(preview, "literalization_risks", None):
        risk_table = Table(
            show_header=True, header_style="bold red", expand=True
        )
        risk_table.add_column("element", width=12)
        risk_table.add_column("literal result", overflow="fold")
        risk_table.add_column("risk", overflow="fold")
        for risk in preview.literalization_risks:
            sev_style = _SEVERITY_STYLE.get(risk.severity, "white")
            risk_table.add_row(
                Text(risk.element, style=sev_style),
                risk.literal_interpretation,
                risk.risk_description,
            )
        console.print(Panel(
            risk_table,
            title="② Literalization Risk · 可能被模型字面化的地方",
            border_style="red",
        ))

    if getattr(preview, "boundary_questions", None):
        q_text = Text()
        for q in preview.boundary_questions:
            q_text.append(f"{q.question}\n", style="bold white")
            for option in q.options:
                suffix = "（推荐）" if option.recommended else ""
                q_text.append(
                    f"  {option.label}. {option.description}{suffix}\n",
                    style="yellow" if option.recommended else "white",
                )
            q_text.append("\n")
        console.print(Panel(
            q_text,
            title="③ Boundary Questions · 生成前先确认",
            border_style="yellow",
        ))

    if getattr(preview, "context_contamination_risks", None):
        contamination_table = Table(
            show_header=True, header_style="bold red", expand=True
        )
        contamination_table.add_column("severity", width=10)
        contamination_table.add_column("old focus", overflow="fold")
        contamination_table.add_column("active focus", overflow="fold")
        contamination_table.add_column("why", overflow="fold")
        for risk in preview.context_contamination_risks:
            sev_style = _SEVERITY_STYLE.get(risk.severity, "white")
            contamination_table.add_row(
                Text(risk.severity, style=sev_style),
                risk.source_context,
                risk.active_context,
                risk.reason,
            )
        console.print(Panel(
            contamination_table,
            title="④ Context Contamination · 旧上下文残留风险",
            border_style="red",
        ))

    if debug and preview.user_intent_map:
        intent_table = Table(
            show_header=True, header_style="bold cyan", expand=True
        )
        intent_table.add_column("priority", width=10)
        intent_table.add_column("weight", width=20)
        intent_table.add_column("intent", overflow="fold")
        for sig in preview.user_intent_map:
            style = _PRIORITY_STYLE.get(sig.priority, "white")
            intent_table.add_row(
                Text(sig.priority, style=style),
                Text(
                    f"{_skill_bar(sig.weight)} {sig.weight:.2f}", style=style
                ),
                sig.label,
            )
        console.print(Panel(
            intent_table,
            title="⑤ User Intent Map · 用户要什么",
            border_style="cyan",
        ))

    if debug and preview.planned_attention_map:
        planned_table = Table(
            show_header=True, header_style="bold magenta", expand=True
        )
        planned_table.add_column("alignment", width=12)
        planned_table.add_column("weight", width=20)
        planned_table.add_column("planned focus", overflow="fold")
        for sig in preview.planned_attention_map:
            style = _ALIGNMENT_STYLE.get(sig.alignment, "white")
            planned_table.add_row(
                Text(sig.alignment, style=style),
                Text(
                    f"{_skill_bar(sig.weight)} {sig.weight:.2f}", style=style
                ),
                Text(sig.label, style=style),
            )
        console.print(Panel(
            planned_table,
            title="⑥ Planned Attention Map · 正文开始前准备关注什么",
            border_style="magenta",
        ))

    if debug and preview.missing_before_start:
        gap_table = Table(
            show_header=True, header_style="bold yellow", expand=True
        )
        gap_table.add_column("kind", width=14)
        gap_table.add_column("severity", width=10)
        gap_table.add_column("label", overflow="fold")
        gap_table.add_column("why", overflow="fold")
        for gap in preview.missing_before_start:
            sev_style = _SEVERITY_STYLE.get(gap.severity, "white")
            gap_table.add_row(
                gap.kind,
                Text(gap.severity, style=sev_style),
                gap.label,
                gap.why,
            )
        console.print(Panel(
            gap_table,
            title="⑦ Missing Before Start · 正文前已暴露的缺口",
            border_style="yellow",
        ))

    levers = preview.control_levers
    if debug and levers and (
        levers.boost or levers.suppress or levers.stop_doing or levers.return_to
    ):
        lever_table = Table(
            show_header=True, header_style="bold white", expand=True
        )
        lever_table.add_column("boost", style="green", overflow="fold")
        lever_table.add_column("return_to", style="green", overflow="fold")
        lever_table.add_column("suppress", style="red", overflow="fold")
        lever_table.add_column("stop_doing", style="red", overflow="fold")
        rows = max(
            len(levers.boost),
            len(levers.return_to),
            len(levers.suppress),
            len(levers.stop_doing),
        )
        for i in range(rows):
            lever_table.add_row(
                levers.boost[i] if i < len(levers.boost) else "",
                levers.return_to[i] if i < len(levers.return_to) else "",
                levers.suppress[i] if i < len(levers.suppress) else "",
                levers.stop_doing[i] if i < len(levers.stop_doing) else "",
            )
        console.print(Panel(
            lever_table,
            title="⑧ Control Levers · 正文开始前先调注意力",
            border_style="bright_blue",
        ))

    if preview.opening_patch:
        patch = Text()
        for line in preview.opening_patch:
            patch.append(f"- {line}\n", style="white")
        console.print(Panel(
            "\n".join(preview.opening_patch),
            title="⑨ Opening Patch · 建议正文开头先做什么",
            border_style="green",
        ))

    notes = Text()
    for note in preview.notes:
        notes.append(f"- {note}\n", style="grey70")
    console.print(Panel(notes, title="边界说明", border_style="grey39"))


def _resolve_skill_inputs(
    context_path: Optional[str],
    agent_output_path: Optional[str],
    context_text: Optional[str],
    agent_output_text: Optional[str],
    stdin_json: bool,
) -> tuple[str, str]:
    """从三种来源解析 (user_context, agent_output)：文件 / 直传文本 / stdin JSON。

    优先级：``--stdin-json`` > ``--*-text`` > ``--context/--output`` 文件路径。
    三种来源 *互斥*，便于 agent host 不落盘直接调用。
    """
    if stdin_json and (
        context_path or agent_output_path or context_text or agent_output_text
    ):
        raise click.UsageError(
            "--stdin-json 不能与 --context / --output / --context-text / "
            "--output-text 同时使用。"
        )

    if stdin_json:
        raw = sys.stdin.read()
        if not raw.strip():
            raise click.UsageError("--stdin-json 已启用但 stdin 为空。")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise click.UsageError(f"--stdin-json 解析失败：{exc}") from exc
        if not isinstance(payload, dict):
            raise click.UsageError(
                "--stdin-json 期望对象 {\"context\": ..., \"output\": ...}。"
            )
        ctx = payload.get("context")
        out = payload.get("output")
        if not isinstance(ctx, str) or not isinstance(out, str):
            raise click.UsageError(
                "--stdin-json 需要 context 和 output 两个字符串字段。"
            )
        return ctx.strip(), out.strip()

    if context_path and context_text:
        raise click.UsageError(
            "--context 与 --context-text 不能同时使用。"
        )
    if agent_output_path and agent_output_text:
        raise click.UsageError(
            "--output 与 --output-text 不能同时使用。"
        )

    if context_text is not None:
        user_context = context_text.strip()
    elif context_path:
        user_context = Path(context_path).read_text(encoding="utf-8").strip()
    else:
        raise click.UsageError(
            "缺少用户上下文：请提供 --context PATH 或 --context-text TEXT "
            "或 --stdin-json。"
        )

    if agent_output_text is not None:
        agent_output = agent_output_text.strip()
    elif agent_output_path:
        agent_output = (
            Path(agent_output_path).read_text(encoding="utf-8").strip()
        )
    else:
        raise click.UsageError(
            "缺少 agent 输出：请提供 --output PATH 或 --output-text TEXT "
            "或 --stdin-json。"
        )

    return user_context, agent_output


def _resolve_skill_preview_inputs(
    context_path: Optional[str],
    plan_path: Optional[str],
    context_text: Optional[str],
    plan_text: Optional[str],
    stdin_json: bool,
) -> tuple[str, str]:
    if stdin_json and (context_path or plan_path or context_text or plan_text):
        raise click.UsageError(
            "--stdin-json 不能与 --context / --plan / --context-text / "
            "--plan-text 同时使用。"
        )

    if stdin_json:
        raw = sys.stdin.read()
        if not raw.strip():
            raise click.UsageError("--stdin-json 已启用但 stdin 为空。")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise click.UsageError(f"--stdin-json 解析失败：{exc}") from exc
        if not isinstance(payload, dict):
            raise click.UsageError(
                "--stdin-json 期望对象 {\"context\": ..., \"plan\": ...}。"
            )
        ctx = payload.get("context")
        plan = payload.get("plan", payload.get("planned_focus"))
        if not isinstance(ctx, str) or not isinstance(plan, str):
            raise click.UsageError(
                "--stdin-json 需要 context 和 plan 两个字符串字段。"
            )
        return ctx.strip(), plan.strip()

    if context_path and context_text:
        raise click.UsageError(
            "--context 与 --context-text 不能同时使用。"
        )
    if plan_path and plan_text:
        raise click.UsageError("--plan 与 --plan-text 不能同时使用。")

    if context_text is not None:
        user_context = context_text.strip()
    elif context_path:
        user_context = Path(context_path).read_text(encoding="utf-8").strip()
    else:
        raise click.UsageError(
            "缺少用户上下文：请提供 --context PATH 或 --context-text TEXT "
            "或 --stdin-json。"
        )

    if plan_text is not None:
        planned_focus = plan_text.strip()
    elif plan_path:
        planned_focus = Path(plan_path).read_text(encoding="utf-8").strip()
    else:
        raise click.UsageError(
            "缺少 planned focus：请提供 --plan PATH 或 --plan-text TEXT "
            "或 --stdin-json。"
        )

    return user_context, planned_focus


@skill.command("preview")
@click.option(
    "--context",
    "context_path",
    required=False,
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="用户上下文文件。与 --context-text / --stdin-json 互斥。",
)
@click.option(
    "--plan",
    "plan_path",
    required=False,
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="agent 计划关注内容文件。与 --plan-text / --stdin-json 互斥。",
)
@click.option(
    "--context-text",
    "context_text",
    required=False,
    default=None,
    type=str,
    help="直接传入用户上下文文本。",
)
@click.option(
    "--plan-text",
    "plan_text",
    required=False,
    default=None,
    type=str,
    help="直接传入 agent 正文前计划关注内容。",
)
@click.option(
    "--stdin-json",
    "stdin_json",
    is_flag=True,
    default=False,
    help='从 stdin 读 JSON：{"context": "...", "plan": "..."}。',
)
@click.option(
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="输出机器可读 JSON。",
)
@click.option(
    "--debug",
    "debug",
    is_flag=True,
    default=False,
    help="显示底层 attention map / gap / control levers 技术面板。",
)
def skill_preview(
    context_path: Optional[str],
    plan_path: Optional[str],
    context_text: Optional[str],
    plan_text: Optional[str],
    stdin_json: bool,
    json_mode: bool,
    debug: bool,
) -> None:
    """正文开始前生成 Opening Attention Preview。"""
    from stateprobe.skill import preview_attention

    user_context, planned_focus = _resolve_skill_preview_inputs(
        context_path,
        plan_path,
        context_text,
        plan_text,
        stdin_json,
    )
    preview = preview_attention(user_context, planned_focus)

    if json_mode:
        click.echo(json.dumps(preview.to_dict(), ensure_ascii=False, indent=2))
        return

    _render_attention_preview(preview, debug=debug)


@skill.command("overlay")
@click.option(
    "--context",
    "context_path",
    required=False,
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="用户上下文文件。与 --context-text / --stdin-json 互斥。",
)
@click.option(
    "--output",
    "agent_output_path",
    required=False,
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="agent 已输出内容文件。与 --output-text / --stdin-json 互斥。",
)
@click.option(
    "--context-text",
    "context_text",
    required=False,
    default=None,
    type=str,
    help="直接传入用户上下文文本（agent host 友好，不需落盘）。",
)
@click.option(
    "--output-text",
    "agent_output_text",
    required=False,
    default=None,
    type=str,
    help="直接传入 agent 输出文本（agent host 友好，不需落盘）。",
)
@click.option(
    "--stdin-json",
    "stdin_json",
    is_flag=True,
    default=False,
    help='从 stdin 读 JSON：{"context": "...", "output": "..."}。',
)
@click.option(
    "--json",
    "json_mode",
    is_flag=True,
    default=False,
    help="输出机器可读 JSON。",
)
@click.option(
    "--control-patch",
    "control_patch",
    is_flag=True,
    default=False,
    help="只输出下一轮纠偏提示。",
)
def skill_overlay(
    context_path: Optional[str],
    agent_output_path: Optional[str],
    context_text: Optional[str],
    agent_output_text: Optional[str],
    stdin_json: bool,
    json_mode: bool,
    control_patch: bool,
) -> None:
    """生成 Agent 注意力仪表盘。

    输入来源三选一（互斥）：
    - 文件：``--context PATH --output PATH``
    - 直传文本：``--context-text TEXT --output-text TEXT``
    - stdin JSON：``--stdin-json``（读 ``{"context":"...","output":"..."}``）
    """
    from stateprobe.skill import analyze_attention

    user_context, agent_output = _resolve_skill_inputs(
        context_path,
        agent_output_path,
        context_text,
        agent_output_text,
        stdin_json,
    )
    hud = analyze_attention(user_context, agent_output)

    if json_mode:
        click.echo(json.dumps(hud.to_dict(), ensure_ascii=False, indent=2))
        return

    if control_patch:
        if not hud.next_turn_patch:
            click.echo("未发现明显需要纠偏的要求。")
            return
        for line in hud.next_turn_patch:
            click.echo(f"- {line}")
        return

    _render_attention_hud(hud)


@main.group()
def lab() -> None:
    """DeepSeek Lab：开源模型 hidden-state 向量实验。"""


@lab.command("status")
def lab_status() -> None:
    """检查 DeepSeek Lab 可选依赖是否安装。"""
    status = dependency_status()
    table = Table(
        title="DeepSeek Lab 状态",
        header_style="bold cyan",
        border_style="grey39",
    )
    table.add_column("项目", style="bold white")
    table.add_column("状态")
    table.add_column("说明", style="grey70")
    table.add_row(
        "默认模型",
        DEFAULT_DEEPSEEK_MODEL,
        "需要模型权重；只有运行 probe 时才会加载。",
    )
    table.add_row(
        "torch",
        "✓ 已安装" if status.torch_available else "✗ 未安装",
        "用于 forward pass 和向量计算。",
    )
    table.add_row(
        "transformers",
        "✓ 已安装" if status.transformers_available else "✗ 未安装",
        "用于加载 DeepSeek-R1-Distill-Qwen。",
    )
    table.add_row(
        "Lab ready",
        "✓ ready" if status.ready else "✗ not ready",
        Text("安装命令：" + status.install_hint),
    )
    console.print(table)


@lab.command("pairs")
def lab_pairs() -> None:
    """展示 DeepSeek Lab 内置的 contrastive prompt pairs。"""
    for axis, pairs in DEEPSEEK_AXIS_PAIRS.items():
        table = Table(
            title=f"{axis.label_zh} ({axis.value})",
            header_style="bold cyan",
            border_style="grey39",
            show_lines=True,
        )
        table.add_column("positive", style="green")
        table.add_column("negative", style="red")
        table.add_column("rationale", style="grey70")
        for pair in pairs:
            table.add_row(pair.positive, pair.negative, pair.rationale_zh)
        console.print(table)


@lab.command("explain")
def lab_explain() -> None:
    """解释真正的 DeepSeek hidden-state probe 怎么工作。"""
    text = Text()
    text.append("DeepSeek Lab 的目标：", style="bold cyan")
    text.append("用开源 DeepSeek-R1-Distill 模型的 hidden_states 真正构造行为方向。\n\n")
    text.append("流程：\n", style="bold white")
    text.append("1. 为每个轴准备 positive / negative prompt pairs。\n")
    text.append("2. 用 DeepSeek-R1-Distill-Qwen 跑 forward pass，取某层 last-token hidden state。\n")
    text.append("3. 计算 axis_vector = mean(positive) - mean(negative)。\n")
    text.append("4. 新 prompt 进来后，计算 activation 与 axis_vector 的 cosine projection。\n")
    text.append("5. 后续可做 activation steering：activation ± alpha * axis_vector。\n\n")
    text.append("注意：", style="bold yellow")
    text.append("这只支持开源权重模型；闭源 API 拿不到 hidden_states。")
    console.print(Panel(text, title="StateProbe DeepSeek Lab", border_style="cyan"))


@lab.command("probe")
@click.argument("prompt", required=False)
@click.option(
    "-f", "--file", "file_path",
    type=click.Path(exists=True, dir_okay=False),
    help="从文件读取 prompt。",
)
@click.option(
    "--model",
    "model_name",
    default=DEFAULT_DEEPSEEK_MODEL,
    show_default=True,
    help="Hugging Face 模型名或本地模型目录。",
)
@click.option(
    "--axis",
    "axis_names",
    multiple=True,
    type=click.Choice([axis.value for axis in DEEPSEEK_AXIS_PAIRS], case_sensitive=False),
    help="只测指定轴；可重复传入。",
)
@click.option(
    "--layer",
    default=-1,
    show_default=True,
    type=int,
    help="抽取 hidden_states 的层号。",
)
@click.option(
    "--device",
    default=None,
    help="cuda / cpu；不填则自动选择。",
)
@click.option(
    "--allow-download",
    is_flag=True,
    default=False,
    help="允许 transformers 从 Hugging Face 下载模型权重。",
)
def lab_probe(
    prompt: Optional[str],
    file_path: Optional[str],
    model_name: str,
    axis_names: tuple,
    layer: int,
    device: Optional[str],
    allow_download: bool,
) -> None:
    """用 DeepSeek-R1-Distill hidden_states 投影测量 prompt。"""
    text = _read_prompt(prompt, file_path)
    selected_axes = [
        Axis(name)
        for name in axis_names
    ] if axis_names else list(DEEPSEEK_AXIS_PAIRS.keys())

    if not allow_download:
        console.print(
            "[yellow]提示：默认只使用本地已有模型。若需要下载权重，加 --allow-download。[/yellow]"
        )

    try:
        with console.status("加载模型和 tokenizer...", spinner="dots"):
            model, tokenizer, resolved_device = load_model_and_tokenizer(
                model_name=model_name,
                device=device,
                local_files_only=not allow_download,
            )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    except OSError as exc:
        hint = (
            "未找到本地模型权重。请先下载模型，或加 --allow-download 允许下载。"
        )
        raise click.ClickException(f"{hint}\n原始错误：{exc}") from exc

    with console.status("构造 DeepSeek contrastive axis vectors...", spinner="dots"):
        axis_vectors = build_deepseek_vectors(
            model=model,
            tokenizer=tokenizer,
            axes=selected_axes,
            layer=layer,
            device=resolved_device,
        )

    with console.status("投影用户 prompt hidden state...", spinner="dots"):
        results = project_prompt(
            prompt=text,
            axis_vectors=axis_vectors,
            model=model,
            tokenizer=tokenizer,
            layer=layer,
            device=resolved_device,
        )

    table = Table(
        title=f"DeepSeek Lab Projection ({model_name}, layer={layer})",
        header_style="bold cyan",
        border_style="grey39",
    )
    table.add_column("轴", style="bold white")
    table.add_column("raw cosine", justify="right", style="cyan")
    table.add_column("0-1 score", justify="right", style="yellow")
    table.add_column("读数条")
    for axis, result in results.items():
        table.add_row(
            axis.label_zh,
            f"{result.raw_score:.4f}",
            f"{result.normalized_score:.2f}",
            _bar(result.normalized_score, width=24),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# eval — black-box behavioral evaluation via frontier APIs
# ---------------------------------------------------------------------------

@main.group()
def eval() -> None:
    """Black-box 行为评测：用 DeepSeek Pro / OpenAI API 验证改写效果。"""


@eval.command("rubrics")
def eval_rubrics() -> None:
    """展示 8 轴行为评分 rubric。"""
    table = Table(
        title="Black-box Eval Rubrics",
        header_style="bold cyan",
        border_style="grey39",
        show_lines=True,
    )
    table.add_column("轴", style="bold white")
    table.add_column("评分问题", style="grey70")
    table.add_column("0 端", style="green")
    table.add_column("1 端", style="red")
    for r in BEHAVIOR_RUBRICS:
        table.add_row(r.axis.label_zh, r.question_zh, r.low_label, r.high_label)
    console.print(table)


@eval.command("run")
@click.argument("original_prompt", required=False)
@click.argument("rewritten_prompt", required=False)
@click.option(
    "--original-file",
    "original_file",
    type=click.Path(exists=True, dir_okay=False),
    help="从文件读取原始 prompt。",
)
@click.option(
    "--rewritten-file",
    "rewritten_file",
    type=click.Path(exists=True, dir_okay=False),
    help="从文件读取改写 prompt。",
)
@click.option(
    "--system", "system_prompt",
    default=None,
    help="可选的 system prompt（两组都用同一个）。",
)
@click.option(
    "--model",
    default=DEFAULT_EVAL_MODEL,
    show_default=True,
    help="目标 LLM 模型名。",
)
@click.option(
    "--base-url",
    default=DEFAULT_BASE_URL,
    show_default=True,
    help="OpenAI 兼容 API base URL。",
)
@click.option(
    "--api-key",
    default=None,
    help="API key（也可通过 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量设置）。",
)
@click.option(
    "--judge-model",
    default=None,
    help="评分用的 judge 模型（默认与 --model 相同）。",
)
def eval_run(
    original_prompt: Optional[str],
    rewritten_prompt: Optional[str],
    original_file: Optional[str],
    rewritten_file: Optional[str],
    system_prompt: Optional[str],
    model: str,
    base_url: str,
    api_key: Optional[str],
    judge_model: Optional[str],
) -> None:
    """对比原始 prompt 和改写 prompt 在目标模型上的输出行为差异。

    示例:

      stateprobe eval run \\
        "你是资深专家，请全面分析这个项目" \\
        "判断这个项目本周是否值得继续投入。不要鼓励，敢说不行。"
    """
    original_text = (
        Path(original_file).read_text(encoding="utf-8").strip()
        if original_file
        else (original_prompt or "").strip()
    )
    rewritten_text = (
        Path(rewritten_file).read_text(encoding="utf-8").strip()
        if rewritten_file
        else (rewritten_prompt or "").strip()
    )
    if not original_text:
        raise click.UsageError("请提供原始 prompt：作为第一个参数或通过 --original-file。")
    if not rewritten_text:
        raise click.UsageError("请提供改写 prompt：作为第二个参数或通过 --rewritten-file。")

    try:
        with console.status("调用目标模型生成 Output A & B...", spinner="dots"):
            result = run_eval(
                original_prompt=original_text,
                rewritten_prompt=rewritten_text,
                system_prompt=system_prompt,
                model=model,
                base_url=base_url,
                api_key=api_key,
                judge_model=judge_model,
                judge_base_url=base_url,
                judge_api_key=api_key,
            )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    # Output A / B preview
    console.print()
    console.print(Panel(
        result.original_output[:600] + ("..." if len(result.original_output) > 600 else ""),
        title="Output A（原始 prompt）",
        border_style="red",
    ))
    console.print(Panel(
        result.rewritten_output[:600] + ("..." if len(result.rewritten_output) > 600 else ""),
        title="Output B（改写 prompt）",
        border_style="green",
    ))

    # Score table
    table = Table(
        title=f"\nBlack-box Eval ({result.model})",
        header_style="bold cyan",
        border_style="grey39",
    )
    table.add_column("轴", style="bold white")
    table.add_column("Output A", justify="right", style="red")
    table.add_column("Output B", justify="right", style="green")
    table.add_column("Δ", justify="right")
    table.add_column("方向")
    for axis in Axis:
        if axis not in result.axis_scores:
            continue
        s = result.axis_scores[axis]
        delta_val = s.delta
        if abs(delta_val) < 0.05:
            direction = Text("=", style="grey50")
        elif delta_val < 0:
            direction = Text("↓", style="green")
        else:
            direction = Text("↑", style="red")
        table.add_row(
            axis.label_zh,
            f"{s.score_original:.2f}",
            f"{s.score_rewritten:.2f}",
            f"{delta_val:+.2f}",
            direction,
        )
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# benchmark — DeepSeek behavior benchmark seed
# ---------------------------------------------------------------------------

@main.group()
def benchmark() -> None:
    """DeepSeek 行为 benchmark：验证和管理 prompt 行为案例库。"""


@benchmark.command("validate")
def benchmark_validate() -> None:
    """校验 benchmark cases.jsonl 的格式和完整性。"""
    import subprocess
    script = Path(__file__).resolve().parent.parent / "scripts" / "validate_benchmark.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(script.parent.parent),
        capture_output=True,
        text=True,
    )
    if result.stdout:
        console.print(result.stdout.rstrip())
    if result.stderr:
        console.print(result.stderr.rstrip(), style="red")
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
