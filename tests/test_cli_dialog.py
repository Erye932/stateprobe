"""Tests for new CLI entry points: welcome, demo, ask."""
from click.testing import CliRunner
from stateprobe.cli import main


def test_no_args_shows_welcome_not_help():
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "StateProbe" in result.output
    assert "stateprobe demo" in result.output
    assert "stateprobe ask" in result.output
    # Should NOT show the click default help dump
    assert "Commands:" not in result.output or "Options:" not in result.output


def test_demo_runs_full_diagnostic():
    runner = CliRunner()
    result = runner.invoke(main, ["demo"])
    assert result.exit_code == 0
    assert "StateProbe Demo" in result.output
    assert "Demo 结束" in result.output


def test_ask_quits_on_q():
    runner = CliRunner()
    result = runner.invoke(main, ["ask"], input=":q\n")
    assert result.exit_code == 0
    assert "对话模式" in result.output
    assert "再见" in result.output


def test_ask_diagnoses_prompt():
    runner = CliRunner()
    result = runner.invoke(main, ["ask"], input="用 Python 写二分查找\n\n:q\n")
    assert result.exit_code == 0
    assert "Prompt 状态诊断" in result.output


def test_ask_model_switch():
    runner = CliRunner()
    result = runner.invoke(main, ["ask"], input=":model v4-pro\n:q\n")
    assert result.exit_code == 0
    assert "v4-pro" in result.output


def test_ask_unknown_command_handled():
    runner = CliRunner()
    result = runner.invoke(main, ["ask"], input=":nosuchcmd\n:q\n")
    assert result.exit_code == 0
    assert "未知命令" in result.output
