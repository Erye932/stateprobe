# StateProbe Skill calibration

This page explains how StateProbe answers the question **"how often does
the Skill agree with a human?"** with a number instead of a slogan.

## Why this exists

StateProbe Skill is rule-based. Rule-based judges always have false
positives and false negatives. The defensible answer to "is it accurate
enough to use?" is not "trust us"; it is:

1. Maintain a small, hand-labelled fixture of representative cases.
2. Run the live decision against every case.
3. Report agreement rate, plus a transparent list of known
   miscalibrations.

The new `confidence` / `evidence` contract on `activation_decision`
already pushes responsibility back to the host (only `confidence=high`
hard-stops; everything else is `continue_with_warning`). Calibration
adds the second half: a measurable baseline that any change has to
preserve.

## Files

| File | Purpose |
| --- | --- |
| [`tests/fixtures/skill_cases.jsonl`](https://github.com/Erye932/stateprobe/blob/main/tests/fixtures/skill_cases.jsonl) | Hand-labelled cases. One JSON per line. |
| [`scripts/calibrate_skill.py`](https://github.com/Erye932/stateprobe/blob/main/scripts/calibrate_skill.py) | Runs every case, prints agreement rate + known issues. |
| [`tests/test_calibration.py`](https://github.com/Erye932/stateprobe/blob/main/tests/test_calibration.py) | Pytest regressions: agree cases must keep matching the oracle; known issues must keep matching their documented current behaviour. |

## Fixture schema

Each line is a JSON object:

```json
{
  "id": "HARD-001",
  "category": "hard_stop_misalignment",
  "description": "plan misses the real must AND lands on the forbidden direction",
  "context": "...",
  "planned_focus": "...",
  "oracle": {
    "action": "rewrite_planned_focus",
    "should_stop": true,
    "confidence": "high"
  },
  "status": "agree"
}
```

- `oracle` is the human-labelled correct answer.
- `status` is one of:
  - `agree` — current StateProbe behaviour matches the oracle. Locked
    by `test_skill_calibration_agree_cases_match_oracle`.
  - `known_issue` — current StateProbe behaviour does **not** match the
    oracle. The case must also include an `actual` block recording
    what StateProbe ships today, plus a `notes` field explaining where
    the fix lives. Locked by
    `test_skill_calibration_known_issues_have_documented_behaviour`.
- `check: "contamination_only"` / `"boundary_questions_only"` /
  `"violated_only"` narrow the comparison to a single signal. Use these
  for false-positive regressions where you only want to lock that
  *one* signal (e.g. "this email task must never trigger a visual
  boundary question"). The runner exposes
  `contamination_risks_empty`, `boundary_questions_empty`, and
  `violated_empty` for this purpose.

## Running locally

```bash
python scripts/calibrate_skill.py
```

Sample output (v0.3.x):

```
=== StateProbe Skill calibration ===
fixture: tests\fixtures\skill_cases.jsonl
total cases: 51
agree cases: 32  passing: 32
agreement rate (agree cases): 100.0%
known issues: 19
```

The known-issues list below the summary records oracle vs. actual
for every case StateProbe currently misjudges. Each one names the
layer where the fix would live (keyword extraction, antonym lexicon,
pivot markers, plan-substance detection, …) so the gap is
actionable, not just acknowledged.

The script never exits non-zero. It is a diagnostic. The pytest suite
is what blocks regressions.

## How to add a case

1. Pick a representative scenario StateProbe should handle.
2. Decide what a human would do (the oracle).
3. Run the case manually:

   ```bash
   echo '{"context": "...", "planned_focus": "..."}' \
     | stateprobe skill preview --stdin-json --json
   ```

4. If StateProbe matches the oracle → add as `status: "agree"`.
5. If StateProbe disagrees → add as `status: "known_issue"`, copy the
   live `action` / `should_stop` / `confidence` into `actual`, and
   write a one-line `notes` explaining where the fix would go.

## How to fix a known issue

1. Land the underlying fix.
2. Re-run the case. StateProbe should now match the oracle.
3. Move the fixture entry from `status: "known_issue"` to
   `status: "agree"`. Drop the `actual` block.
4. The known-issues test will fail loudly until the fixture is updated,
   which forces the move to be a deliberate PR rather than a silent
   improvement.

## What this is not

- **Not a replacement for an LLM judge.** StateProbe deliberately stays
  rule-based and zero-cost. Calibration is what makes the rule layer
  defensible.
- **Not a benchmark suite.** It is a small fixture meant to grow
  organically as users report cases. The current 51 cases are a
  starting point, not a proof of accuracy.
- **Not a confidence claim.** "100% on 32 agree cases" only means
  those 32 cases pass. The honest message is the 19-item
  *known issues* list and the path to fix each one.

## Future work

- **Host feedback channel.** Today, when an agent host disagrees with
  a StateProbe verdict, the only feedback path is filing a fixture
  case manually. A first-class "the host says StateProbe judged this
  wrong" channel would let mismatches flow back into
  `skill_cases.jsonl` without human transcription. Deliberately
  deferred until there is real user volume — the data is the point,
  and we need users before we need plumbing.
- **Antonym / paraphrase lexicon.** ISSUE-005, ISSUE-006, and
  ISSUE-020 all share one root cause: the matcher only looks at
  literal keyword overlap. A small concept lexicon would close all
  three at once.
- **Modifier-aware coverage.** ISSUE-001, ISSUE-009, ISSUE-016 share
  the "plan covers the head must but loses a soft modifier" pattern.
  Weighting modifier loss separately from concept loss would close
  them together.
- **Plan-substance detection.** ISSUE-012 and ISSUE-018: a plan that
  is just `"好的"` or just a clarifying question should hard-stop.
  Today it soft-warns.
