from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def check(self, condition: bool, label: str, detail: str = "") -> None:
        if condition:
            print(f"PASS {label}")
        else:
            message = f"FAIL {label}"
            if detail:
                message += f" — {detail}"
            print(message)
            self.failures.append(message)

    def warn(self, condition: bool, label: str, detail: str = "") -> None:
        if condition:
            print(f"PASS {label}")
        else:
            message = f"WARN {label}"
            if detail:
                message += f" — {detail}"
            print(message)
            self.warnings.append(message)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def run_command(args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.returncode, completed.stdout.strip()


def check_required_files(result: Result) -> None:
    required = [
        ".gitattributes",
        "README.md",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CITATION.cff",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "pyproject.toml",
        ".github/workflows/ci.yml",
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/bug_report.md",
        ".github/ISSUE_TEMPLATE/feature_request.md",
        ".github/ISSUE_TEMPLATE/rule_request.md",
        "docs/PROJECT_BRIEF.md",
        "docs/PROJECT_PLAN.md",
        "docs/OPERATING_RULES.md",
        "docs/DEMO_WALKTHROUGH.md",
        "docs/ARCHITECTURE.md",
        "docs/EVIDENCE_MODEL.md",
        "docs/DEEPSEEK_ROADMAP.md",
        "docs/FAQ.md",
        "docs/QUALITY_BAR.md",
        "docs/OPEN_SOURCE_PLAN.md",
        "docs/CONTRIBUTOR_VISIBILITY_PLAN.md",
        "docs/PUBLISHING.md",
        "docs/RELEASE_CHECKLIST.md",
        "demos/README.md",
        "demos/smart_but_not_answering/bad_prompt.txt",
        "demos/smart_but_not_answering/good_prompt.txt",
        "demos/smart_but_not_answering/README.md",
        "stateprobe/cli.py",
        "stateprobe/detector.py",
        "stateprobe/lab/probe.py",
        "stateprobe/eval/scorer.py",
    ]
    for path in required:
        result.check(exists(path), f"required file exists: {path}")


def check_readme(result: Result) -> None:
    text = read("README.md")
    required_phrases = [
        "A debugger for prompts and LLM behavior",
        "30 秒 Demo",
        "smart_but_not_answering",
        "Static Mode",
        "Black-box Eval",
        "DeepSeek Lab",
        "docs/PROJECT_PLAN.md",
        "docs/OPERATING_RULES.md",
        "docs/ARCHITECTURE.md",
        "docs/EVIDENCE_MODEL.md",
        "docs/DEEPSEEK_ROADMAP.md",
        "docs/FAQ.md",
        "docs/QUALITY_BAR.md",
        "docs/OPEN_SOURCE_PLAN.md",
        "docs/CONTRIBUTOR_VISIBILITY_PLAN.md",
        "docs/PUBLISHING.md",
        "CODE_OF_CONDUCT.md",
        "CITATION.cff",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
    ]
    for phrase in required_phrases:
        result.check(phrase in text, f"README contains: {phrase}")
    first_screen = "\n".join(text.splitlines()[:80])
    result.check("actually answer" in first_screen or "没有回答核心问题" in first_screen, "README first screen states the core pain")
    result.check("不声称读取闭源模型 hidden states" in text, "README states static mode boundary")


def check_docs(result: Result) -> None:
    evidence = read("docs/EVIDENCE_MODEL.md")
    faq = read("docs/FAQ.md")
    open_source = read("docs/OPEN_SOURCE_PLAN.md")
    project_plan = read("docs/PROJECT_PLAN.md")
    operating_rules = read("docs/OPERATING_RULES.md")
    quality = read("docs/QUALITY_BAR.md")
    deepseek_roadmap = read("docs/DEEPSEEK_ROADMAP.md")
    visibility = read("docs/CONTRIBUTOR_VISIBILITY_PLAN.md")
    result.check("Static rule evidence" in evidence, "evidence model explains static evidence")
    result.check("Black-box behavior evidence" in evidence, "evidence model explains black-box evidence")
    result.check("Local activation evidence" in evidence, "evidence model explains local activation evidence")
    result.check("just a bunch of regex" in faq, "FAQ answers regex objection")
    result.check("Does StateProbe read real activations?" in faq, "FAQ answers activation objection")
    result.check("Is StateProbe only for DeepSeek-R1?" in faq, "FAQ answers DeepSeek-only objection")
    result.check("North star" in project_plan, "project plan defines north star")
    result.check("Version roadmap" in project_plan, "project plan defines version roadmap")
    result.check("First 30 days" in project_plan, "project plan defines first 30 days")
    result.check("Visibility-first, engineering-grounded" in operating_rules, "operating rules state core rule")
    result.check("Mandatory AI execution rule" in operating_rules, "operating rules define AI execution rule")
    result.check("five gates" in operating_rules, "operating rules define the five gates")
    result.check("GitHub launch checklist" in open_source, "open-source plan includes launch checklist")
    result.check("10k-star reference bar" in quality, "quality bar includes high-star benchmark")
    result.check("DeepSeek-first, not DeepSeek-only" in deepseek_roadmap, "DeepSeek roadmap states project focus")
    result.check("future DeepSeek models" in deepseek_roadmap, "DeepSeek roadmap covers future model migration")
    result.check("90-day strategy" in visibility, "visibility plan has 90-day strategy")
    result.check("DeepSeek behavior benchmark seed" in visibility, "visibility plan prioritizes benchmark seed")
    contributing = read("CONTRIBUTING.md")
    changelog = read("CHANGELOG.md")
    security = read("SECURITY.md")
    publishing = read("docs/PUBLISHING.md")
    code_of_conduct = read("CODE_OF_CONDUCT.md")
    citation = read("CITATION.cff")
    result.check("python scripts/acceptance_check.py" in contributing, "contributing guide requires acceptance check")
    result.check("https://github.com/Erye932/stateprobe.git" in contributing, "contributing guide uses real GitHub clone URL")
    result.check("Evidence discipline" in contributing, "contributing guide preserves evidence boundary")
    result.check("0.1.0 - Unreleased" in changelog, "changelog has unreleased version section")
    result.check("default `stateprobe check` command does not call external APIs" in security, "security policy states local-first default")
    result.check("revoke it immediately" in publishing, "publishing guide covers leaked token response")
    result.check("Expected behavior" in code_of_conduct, "code of conduct defines expected behavior")
    result.check("repository-code: \"https://github.com/Erye932/stateprobe\"" in citation, "citation file points to GitHub repository")


def check_demos(result: Result) -> None:
    bad = read("demos/smart_but_not_answering/bad_prompt.txt")
    good = read("demos/smart_but_not_answering/good_prompt.txt")
    index = read("demos/README.md")
    walkthrough = read("docs/DEMO_WALKTHROUGH.md")
    result.check("顶级 AI 产品和开源增长专家" in bad, "Demo 0 bad prompt has expert-role trap")
    result.check("不要鼓励我" in good, "Demo 0 good prompt has anti-sycophancy instruction")
    result.check("验收标准" in good, "Demo 0 good prompt has acceptance criteria")
    result.check("smart_but_not_answering" in index, "demo index links Demo 0")
    result.check("Demo 0" in walkthrough, "walkthrough includes Demo 0")


def check_security_and_packaging(result: Result) -> None:
    gitignore = read(".gitignore") if exists(".gitignore") else ""
    result.check(".env" in gitignore, ".gitignore excludes .env")
    result.check("*.key" in gitignore, ".gitignore excludes key files")
    secret_patterns = [
        re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
        re.compile(r"gho_[A-Za-z0-9_]{20,}"),
        re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"(?i)(api[_-]?key|secret|token)\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]"),
    ]
    ignored_dirs = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", "dist", "build"}
    text_suffixes = {".md", ".py", ".toml", ".yml", ".yaml", ".txt"}
    leaks = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(content) for pattern in secret_patterns):
            leaks.append(str(path.relative_to(ROOT)))
    result.check(
        not leaks,
        "no obvious hardcoded API or GitHub tokens in repository text files",
        ", ".join(leaks[:10]),
    )
    pyproject = read("pyproject.toml")
    result.warn(
        "https://github.com/yourname/stateprobe" not in pyproject,
        "GitHub URL placeholder replaced",
        "current placeholder is acceptable before repo exists but blocks public launch",
    )


def check_cli_and_tests(result: Result) -> None:
    code, output = run_command([sys.executable, "-m", "pytest", "tests", "-q"])
    result.check(code == 0, "unit tests pass", output[-1000:])
    code, output = run_command([sys.executable, "-m", "stateprobe.cli", "--help"])
    result.check(code == 0 and "StateProbe" in output, "CLI help works", output[-1000:])
    code, output = run_command([sys.executable, "-m", "stateprobe.cli", "check", "--help"])
    result.check(code == 0 and "--file" in output, "check help works", output[-1000:])
    code, output = run_command(
        [
            sys.executable,
            "-m",
            "stateprobe.cli",
            "check",
            "--file",
            "demos/smart_but_not_answering/bad_prompt.txt",
            "--no-terminal",
        ]
    )
    result.check(code == 0, "Demo 0 check command runs", output[-1000:])


def main() -> int:
    result = Result()
    print("StateProbe acceptance check")
    print("=" * 32)
    check_required_files(result)
    check_readme(result)
    check_docs(result)
    check_demos(result)
    check_security_and_packaging(result)
    check_cli_and_tests(result)
    print("=" * 32)
    print(f"failures: {len(result.failures)}")
    print(f"warnings: {len(result.warnings)}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    if result.failures:
        print("Failures:")
        for failure in result.failures:
            print(f"- {failure}")
        return 1
    print("Acceptance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
