"""Command-line interface for StateProbe."""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path
from typing import Optional

import io
import os

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
         "（v0.2 hybrid，需要 DEEPSEEK_API_KEY）。两层证据合并后再聚合。",
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
) -> None:
    """诊断一段 prompt 的状态向量。

    示例:

      stateprobe check "你是资深专家，请全面分析这个项目"

      stateprobe check --file my_prompt.txt --target super_thinking_max --html report.html --open

      stateprobe check "think step by step" --model generic

      stateprobe check --llm-augment "你的 prompt"   # v0.2 hybrid：静态 + LLM 双层证据
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
                "旧行为（LLM 替换静态）会在 v0.3 移除。[/dim]"
            ),
            title="⚠ 弃用警告",
            border_style="yellow",
        ))

    augment_contributor = None
    if llm_augment:
        augment_contributor = LLMJudgeContributor(
            model=llm_model,
            base_url=llm_base_url,
            api_key=api_key,
        )

    # Note: EngineUnavailable from the LLM contributor is now caught silently
    # inside detect_readings — static evidence still produces a result.
    # No fallback panel needed because the user always gets output.
    report = diagnose(
        text,
        target_name=target_name,
        model_name=model_name,
        llm_augment=augment_contributor,
    )

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
