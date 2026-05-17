# StateProbe Open Source Project Plan

This plan turns StateProbe from a working MVP into a credible open-source project for developers, prompt engineers, and AI technical readers.

## Project positioning

Recommended tagline:

> A debugger for prompts and LLM behavior.

Longer positioning:

> StateProbe helps developers see whether a prompt is likely to make an LLM actually answer, or drift into rambling, sycophancy, role-play, overthinking, or vague expert analysis.

## Target audience

Primary:

- Developers building LLM features
- Open-source users evaluating prompt tools
- Prompt engineers who need explainable debugging

Secondary:

- AI interpretability readers
- Evaluation and reliability engineers
- Researchers interested in activation vectors and behavioral states

## Release tracks

### Track 1: Packaging and first impression

Goal: make a GitHub visitor understand the project in 30 seconds.

Deliverables:

- Strong README first screen
- One high-impact demo
- Clear install and run commands
- Docs entry points for architecture, evidence, FAQ, and roadmap

### Track 2: Repository completeness

Goal: make the project feel like a serious open-source repo.

Deliverables:

- Confirm `LICENSE`
- Confirm `.gitignore`
- Update placeholder GitHub URLs in `pyproject.toml`
- Add or refine release checklist
- Add contribution guidelines when public launch is near

### Track 3: Evidence and credibility

Goal: prevent the project from looking like a vague prompt heuristic.

Deliverables:

- Explain Static Mode as proxy evidence
- Explain Black-box Eval as behavioral evidence
- Explain DeepSeek Lab as local activation evidence
- Add confidence labels in a future version

### Track 4: Accuracy benchmark

Goal: prove where StateProbe is reliable and where it fails.

Deliverables:

- Small labeled benchmark
- Per-axis precision and recall
- False-positive and false-negative examples
- Calibration report for confidence labels

### Track 5: Local activation roadmap

Goal: make the DeepSeek Lab more than a demo.

Deliverables:

- More contrastive pairs per axis
- Save/load axis vectors
- More reproducible layer and model metadata
- Clear experimental warnings

### Track 6: Developer workflow

Goal: make StateProbe useful in real LLM app development.

Deliverables:

- `stateprobe check` for prompt files
- HTML reports for PR review
- Optional CI examples
- Future VS Code / Cursor plugin

## GitHub launch checklist

Before public launch:

- README first screen is clear
- Demo commands run locally
- Tests pass
- No API keys or generated reports committed
- `pyproject.toml` URL is updated
- Release checklist is reviewed
- Known limitations are visible
- FAQ answers the “is this just regex?” question

## V0.2 suggested scope

V0.2 should focus on trust and usability, not feature sprawl.

Recommended V0.2:

- Evidence/confidence fields in reports
- Standalone answer-quality check design
- Small benchmark scaffold
- Better DeepSeek Lab vector persistence
- HTML report with clearer evidence sections

## What not to prioritize yet

Avoid these until the core story is trusted:

- Web app
- Account system
- Marketplace integrations
- Large-scale auto-labeling
- Activation steering claims
- Overstated “we can read any AI’s mind” messaging

## Success criteria

The project is ready for a serious GitHub launch when a developer can answer:

1. What does it do?
2. Why would I use it before promptfoo or LangSmith?
3. What evidence does it rely on?
4. What can it not claim?
5. Can I run a demo in under two minutes?

If those five answers are obvious from the README, StateProbe is packaged well enough to publish.
