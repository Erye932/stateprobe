"""Lock the contract between CHANGELOG.md and the release workflow.

``release.yml`` extracts the body of a single version section from
CHANGELOG.md to use as the GitHub Release notes. If the CHANGELOG format
ever drifts (e.g. someone changes ``## 0.5.0 - …`` to ``# v0.5.0``), the
release would silently ship with empty notes. These tests ensure that
``scripts/extract_changelog_section.py`` keeps working on the format the
repo actually uses, and that obvious bad inputs fail loudly.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "extract_changelog_section.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "extract_changelog_section", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract_changelog_section = _load_module()


def test_extracts_current_version_from_repo_changelog():
    """The version named in pyproject.toml must resolve against CHANGELOG.md.

    This is the actual contract the release workflow relies on: when a tag
    matches the package version, the workflow must be able to find the
    matching CHANGELOG section.
    """

    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version_line = next(
        line for line in pyproject.splitlines() if line.startswith("version")
    )
    version = version_line.split("=", 1)[1].strip().strip('"').strip("'")

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    body = extract_changelog_section.extract(changelog, version)

    assert body is not None, (
        f"CHANGELOG.md is missing a '## {version}' section. release.yml "
        f"would ship a release with empty notes."
    )
    assert body.strip(), "extracted section is whitespace-only"


def test_strips_v_prefix_from_tag():
    text = "## 0.4.0 - 2026-05-24 - Title\n\nbody line\n"
    assert extract_changelog_section.extract(text, "v0.4.0") == "body line"


def test_does_not_leak_heading_line_into_body():
    """Regression for the bug where the regex captured the rest of the
    heading (the date and title) into the release-notes body.
    """

    text = "## 0.4.0 - 2026-05-24 - Long title\n\nfirst real line\n"
    body = extract_changelog_section.extract(text, "0.4.0")
    assert body is not None
    assert "Long title" not in body
    assert "2026-05-24" not in body
    assert body.startswith("first real line")


def test_section_ends_at_next_version_heading():
    text = (
        "## 0.4.0 - X\n\nlatest body\n\n"
        "## 0.3.1 - Y\n\nolder body\n"
    )
    body = extract_changelog_section.extract(text, "0.4.0")
    assert body == "latest body"


def test_returns_none_for_missing_version():
    text = "## 0.4.0 - X\n\nbody\n"
    assert extract_changelog_section.extract(text, "9.9.9") is None


def test_does_not_match_version_prefix_collision():
    """``## 0.4.0`` must not match a request for ``0.4`` (which is not
    actually a heading in the repo) and must not match a longer version
    like ``0.4.10`` if the repo ever ships one.
    """

    text = "## 0.4.10 - newer\n\nbody10\n\n## 0.4.0 - older\n\nbody00\n"
    assert extract_changelog_section.extract(text, "0.4.0") == "body00"
    assert extract_changelog_section.extract(text, "0.4.10") == "body10"
    assert extract_changelog_section.extract(text, "0.4") is None


def test_cli_exits_nonzero_on_missing_section(tmp_path, capsys):
    """The CLI must signal failure when a version is missing so the
    workflow step fails loudly instead of uploading empty notes.
    """

    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## 0.4.0 - X\n\nbody\n", encoding="utf-8")

    rc = extract_changelog_section.main(["9.9.9", str(changelog)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "9.9.9" in captured.err


def test_cli_exits_nonzero_on_missing_changelog(tmp_path, capsys):
    rc = extract_changelog_section.main(["0.4.0", str(tmp_path / "nope.md")])
    assert rc == 2
    captured = capsys.readouterr()
    assert "not found" in captured.err
