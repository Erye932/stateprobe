# examples/

**Internal test fixtures.** These short prompt files back the acceptance
check, the lab vector build, and a few unit tests. They are not curated
for users.

For user-facing prompt demos with bad / good pairs and runnable commands,
see [`demos/`](../demos/).

## What's here

| File | Used by |
|---|---|
| `bad_heavy_persona.txt` | acceptance check, discrim table |
| `bad_sycophant.txt` | acceptance check, discrim table |
| `bad_vague_expert.txt` | discrim table |
| `good_calm_reasoning.txt` | discrim table (baseline) |
| `good_super_thinking_max.txt` | discrim table (baseline) |
| `skill_attention_context.txt` | skill HUD context demo |
| `skill_attention_output.txt` | skill HUD output demo |

Treat these as fixtures — keep them short, deterministic, and stable across
versions so the acceptance check stays reproducible.
