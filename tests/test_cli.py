from __future__ import annotations

from click.testing import CliRunner

from stateprobe.cli import main


def test_eval_run_help_includes_file_options():
    runner = CliRunner()
    result = runner.invoke(main, ["eval", "run", "--help"])
    assert result.exit_code == 0
    assert "--original-file" in result.output
    assert "--rewritten-file" in result.output


def test_eval_run_requires_original_and_rewritten_prompt():
    runner = CliRunner()
    result = runner.invoke(main, ["eval", "run"])
    assert result.exit_code != 0
    assert "请提供原始 prompt" in result.output


def test_eval_run_requires_rewritten_prompt_when_original_given():
    runner = CliRunner()
    result = runner.invoke(main, ["eval", "run", "原始 prompt"])
    assert result.exit_code != 0
    assert "请提供改写 prompt" in result.output


def test_check_command_smoke():
    runner = CliRunner()
    result = runner.invoke(main, ["check", "你是资深专家，请全面分析这个项目"])
    assert result.exit_code == 0
    assert "StateProbe" in result.output
