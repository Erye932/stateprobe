from __future__ import annotations

import pytest
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


# ---------------------------------------------------------------------------
# --lab-augment graceful-degradation regression tests (v0.3 silent-drop fix)
# ---------------------------------------------------------------------------

def test_check_lab_augment_missing_vectors_shows_panel_and_continues(tmp_path):
    """Missing vectors file must produce a yellow panel with vectors-specific
    hint, NOT a stack trace, and the report must still render (exit 0).

    Regression for the v0.3 perfectionist review: --lab-augment used to
    silently no-op when any sub-component was unavailable. The CLI now
    surfaces a context-aware warning and keeps the static (+ optional LLM)
    layers running.
    """
    runner = CliRunner()
    bogus = tmp_path / "no_such_vectors.pt"
    result = runner.invoke(main, [
        "check",
        "你是资深专家，请全面分析这个项目",
        "--lab-augment",
        "--lab-vectors", str(bogus),
    ])
    # Exit code must be 0 — graceful degradation, not a crash.
    assert result.exit_code == 0, (
        f"--lab-augment with missing vectors must degrade gracefully, "
        f"got exit_code={result.exit_code}\n--- stdout ---\n{result.output}"
    )
    # Yellow panel header is shown.
    assert "Lab unavailable" in result.output or "Lab 层不可用" in result.output
    # Vectors-specific hint is shown (not the generic / CUDA / model hint).
    assert "build_lab_vectors" in result.output or "lab-vectors" in result.output
    # Static layer still produced a report.
    assert "StateProbe" in result.output


def test_check_lab_augment_missing_vectors_does_not_mention_cuda_hint(tmp_path):
    """Hint must be context-specific — vectors-missing must NOT show CUDA hint."""
    runner = CliRunner()
    bogus = tmp_path / "no_such_vectors.pt"
    result = runner.invoke(main, [
        "check",
        "你是资深专家",
        "--lab-augment",
        "--lab-vectors", str(bogus),
    ])
    assert result.exit_code == 0
    # CUDA hint must not appear when the failure is a missing vectors file.
    assert "需要本地 NVIDIA GPU" not in result.output
    assert "省略 --lab-augment 跑无 Lab 层" not in result.output


# ---------------------------------------------------------------------------
# --lab-eager regression tests (closes the last silent-drop case for HF
# model-download failures inside the lazy _load_model() path).
# ---------------------------------------------------------------------------

def test_check_lab_eager_without_lab_augment_shows_ignored_warning():
    """--lab-eager standalone must show an 'ignored' yellow panel and still
    render the report. Catches typos / misuse where users forget to pair it
    with --lab-augment."""
    runner = CliRunner()
    result = runner.invoke(main, [
        "check",
        "你是资深专家，请全面分析这个项目",
        "--lab-eager",  # no --lab-augment
    ])
    assert result.exit_code == 0
    # Ignored warning shown.
    assert "--lab-eager" in result.output
    assert "ignored" in result.output or "未启用" in result.output
    # Static report still rendered.
    assert "StateProbe" in result.output


@pytest.mark.parametrize(
    "exc_message,expected_hint_keyword,forbidden_hint_keyword",
    [
        # CUDA branch
        (
            "LabContributor: CUDA not available. Lab 层需要 GPU; ...",
            "需要本地 NVIDIA GPU",
            "build_lab_vectors",
        ),
        # Deps branch — torch/transformers missing (new "lab dependencies missing" phrasing from Round 5)
        (
            "LabContributor: optional lab dependencies missing: torch. Install: pip install -e \".[lab]\"",
            "缺少可选依赖",
            "需要本地 NVIDIA GPU",
        ),
        # Deps branch — stateprobe.lab.probe packaging failure
        (
            "LabContributor: stateprobe.lab.probe unavailable: bad install",
            "缺少可选依赖",
            "build_lab_vectors",
        ),
        # Deps branch — stateprobe.lab.cache packaging failure (P0-4 fix)
        (
            "LabContributor: stateprobe.lab.cache unavailable: bad install",
            "缺少可选依赖",
            "build_lab_vectors",
        ),
        # Vectors branch — file not found
        (
            "LabVectorStore file not found: /no/such/path.pt. Build with: python scripts/build_lab_vectors.py",
            "build_lab_vectors",
            "需要本地 NVIDIA GPU",
        ),
        # Vectors branch — corrupt file (P0-4 fix: previously fell through to default hint)
        (
            "LabContributor: failed to load /tmp/x.pt: bad pickle",
            "build_lab_vectors",
            "缺少可选依赖",
        ),
        # Vectors branch — schema too new (P0-4 fix: previously fell through to default hint)
        (
            "LabVectorStore: refusing to load schema_version=99 (max supported: 1)",
            "build_lab_vectors",
            "缺少可选依赖",
        ),
        # Model-load branch
        (
            "LabContributor: model load failed: HF download timeout",
            "STATEPROBE_LAB_MODEL_PATH",
            "build_lab_vectors",
        ),
    ],
)
def test_check_lab_hint_matcher_routes_each_failure_class_correctly(
    monkeypatch, exc_message, expected_hint_keyword, forbidden_hint_keyword,
):
    """Lock the contract between LabContributor's EngineUnavailable messages
    and the CLI's context-aware hint matcher.

    Each row is a representative real-world exception text → the keyword
    expected in the rendered hint, plus a keyword that MUST NOT appear
    (catches accidental fall-through to the wrong branch).

    Regression for P0-4: the matcher used to silently fall through to the
    generic default hint for `failed to load`, `schema_version`, and
    `stateprobe.lab.cache unavailable` failures, misleading users about
    the fix.
    """
    from stateprobe.engines import lab as lab_module
    from stateprobe.engines.base import EngineUnavailable

    def fake_init(self, *args, **kwargs):
        raise EngineUnavailable(exc_message)

    monkeypatch.setattr(lab_module.LabContributor, "__init__", fake_init)

    runner = CliRunner()
    result = runner.invoke(main, [
        "check",
        "你是资深专家",
        "--lab-augment",
    ])
    assert result.exit_code == 0
    assert expected_hint_keyword in result.output, (
        f"hint matcher missed:\n  message: {exc_message}\n"
        f"  expected '{expected_hint_keyword}' in output\n"
        f"  --- output ---\n{result.output}"
    )
    assert forbidden_hint_keyword not in result.output, (
        f"hint matcher fell through wrong branch:\n  message: {exc_message}\n"
        f"  forbidden '{forbidden_hint_keyword}' was in output\n"
        f"  --- output ---\n{result.output}"
    )


def test_check_lab_augment_eager_surfaces_model_load_in_yellow_panel(monkeypatch):
    """--lab-augment --lab-eager: a model-load failure must surface as a
    yellow panel with the model-load hint, not as a deferred RuntimeWarning
    inside detect_readings on first contribute().

    This is the contract that justifies the --lab-eager flag's existence:
    closing the last silent-drop case (HF model download) for CI / pre-flight
    use.
    """
    from stateprobe.engines import lab as lab_module
    from stateprobe.engines.base import EngineUnavailable

    # Replace LabContributor.__init__ to simulate model-load failure when
    # the CLI passes lazy=False (i.e., --lab-eager). We don't need to spin up
    # real torch / CUDA / vectors for this path.
    def fake_init(self, *args, lazy=True, **kwargs):
        if not lazy:
            raise EngineUnavailable(
                "LabContributor: model load failed: simulated HF download timeout"
            )
        # Lazy-path stub: keep the contributor inert in case a future test
        # exercises it. Not exercised here.
        self.name = "lab"

    monkeypatch.setattr(lab_module.LabContributor, "__init__", fake_init)

    runner = CliRunner()
    result = runner.invoke(main, [
        "check",
        "你是资深专家，请全面分析这个项目",
        "--lab-augment",
        "--lab-eager",
    ])
    # Must degrade gracefully: report still renders.
    assert result.exit_code == 0, (
        f"--lab-eager + model-load failure must degrade gracefully, got "
        f"exit_code={result.exit_code}\n--- stdout ---\n{result.output}"
    )
    # Yellow panel header.
    assert "Lab unavailable" in result.output or "Lab 层不可用" in result.output
    # Model-load specific hint (NOT the CUDA / vectors / deps hint).
    assert (
        "STATEPROBE_LAB_MODEL_PATH" in result.output
        or "模型加载失败" in result.output
    )
    # Vectors-missing hint must NOT appear (would be wrong context).
    assert "build_lab_vectors" not in result.output
    # Static layer still produced a report.
    assert "StateProbe" in result.output
