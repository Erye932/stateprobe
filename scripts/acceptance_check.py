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
        encoding="utf-8",
        errors="replace",
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
        "docs/governance/PROJECT_BRIEF.md",
        "docs/DEMO_WALKTHROUGH.md",
        "docs/ARCHITECTURE.md",
        "docs/EVIDENCE_MODEL.md",
        "docs/DEEPSEEK_ROADMAP.md",
        "docs/FAQ.md",
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
        "benchmarks/deepseek_behavior_seed/schema.json",
        "benchmarks/deepseek_behavior_seed/cases.jsonl",
        "benchmarks/deepseek_behavior_seed/README.md",
        "scripts/validate_benchmark.py",
    ]
    for path in required:
        result.check(exists(path), f"required file exists: {path}")


def check_readme(result: Result) -> None:
    """Validate the bilingual README pair.

    The repo ships two top-level READMEs since the launch repackaging:
    - `README.md` — English primary, high-star convention, A2 hero
      ("The attention layer for LLM agents.")
    - `README.zh-CN.md` — Chinese mirror with the full China-specific install
      flow, PowerShell encoding fix, and richer narrative

    Each file owns a different set of phrase checks. Shared structural
    invariants (docs/* links, badges, contributor pointers) are validated
    against the English primary; Chinese-specific narrative phrases (the
    legacy `30 秒 demo` / `smart_but_not_answering` references, the
    boundary statement in Chinese) are validated against the mirror.
    """
    en_text = read("README.md")
    zh_text = read("README.zh-CN.md")

    # English primary: hero + high-star structural invariants
    en_required = [
        # A2 hero locked at launch repackaging
        "The attention layer for LLM agents.",
        # Boundary statement (English + Chinese mixed callout in EN README)
        "OpenAI/Claude 物理上读不到",
        # Sibling link to mirror
        "README.zh-CN.md",
        # Architecture pillars
        "Static Mode",
        "Black-box Eval",
        "DeepSeek Lab",
        # Demo path — EN README still links to the legacy demo by directory
        "smart_but_not_answering",
        # Doc links (must remain wired up after rewrite)
        "docs/ARCHITECTURE.md",
        "docs/EVIDENCE_MODEL.md",
        "docs/DEEPSEEK_ROADMAP.md",
        "docs/FAQ.md",
        "docs/PUBLISHING.md",
        "CODE_OF_CONDUCT.md",
        "CITATION.cff",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
    ]
    for phrase in en_required:
        result.check(phrase in en_text, f"README.md contains: {phrase}")

    en_first_screen = "\n".join(en_text.splitlines()[:40])
    result.check(
        "agents drift" in en_first_screen
        or "actually answer" in en_first_screen,
        "README.md first screen states the core pain",
    )
    # Boundary in English README
    en_boundary_phrases = [
        "cannot expose hidden states",
        "OpenAI/Claude 物理上读不到",
        "open-source models",
    ]
    result.check(
        any(p in en_text for p in en_boundary_phrases),
        "README.md states closed-source-internals boundary",
    )

    # Chinese mirror: comprehensive Chinese narrative + China install flow
    zh_required = [
        "LLM agent 的注意力控制层",
        "30 秒 demo",
        "PowerShell",
        "DeepSeek-first, not DeepSeek-only",
        # Doc links must also exist in zh-CN (China-first readers land here)
        "docs/SKILL_ATTENTION_HUD.md",
        "docs/MCP_SERVER.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
    ]
    for phrase in zh_required:
        result.check(phrase in zh_text, f"README.zh-CN.md contains: {phrase}")

    zh_boundary_phrases = [
        "闭源 API 拿不到 hidden states",
        "闭源 API",
        "Claude",
    ]
    result.check(
        any(p in zh_text for p in zh_boundary_phrases),
        "README.zh-CN.md states closed-source-internals boundary",
    )


def check_docs(result: Result) -> None:
    evidence = read("docs/EVIDENCE_MODEL.md")
    faq = read("docs/FAQ.md")
    deepseek_roadmap = read("docs/DEEPSEEK_ROADMAP.md")
    result.check("Static rule evidence" in evidence, "evidence model explains static evidence")
    result.check("Black-box behavior evidence" in evidence, "evidence model explains black-box evidence")
    result.check("Local activation evidence" in evidence, "evidence model explains local activation evidence")
    result.check("just a bunch of regex" in faq, "FAQ answers regex objection")
    result.check("Does StateProbe read real activations?" in faq, "FAQ answers activation objection")
    result.check("Is StateProbe only for DeepSeek-R1?" in faq, "FAQ answers DeepSeek-only objection")
    result.check("DeepSeek-first, not DeepSeek-only" in deepseek_roadmap, "DeepSeek roadmap states project focus")
    result.check("future DeepSeek models" in deepseek_roadmap, "DeepSeek roadmap covers future model migration")
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
    code, output = run_command([sys.executable, "scripts/validate_benchmark.py"])
    result.check(code == 0 and "validation passed" in output, "benchmark validate passes", output[-1000:])


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
