# Multi-Project Benchmark Registry

This directory contains benchmark batches whose Android source is not Element X.
Each project owns its task identifiers, source evidence, migrations, and result
manifests so that case counts and agent metrics cannot leak across projects.

```text
benchmark_projects/
  catalog.json
  <project>/
    catalog.json
    tasks/<task-id>/
    migrations/<task-id>/
    results/
```

The legacy Element X suite remains under `benchmark_tasks/` and `migrations/`.
New project catalogs are admitted only after their accepted tasks have immutable
Android refs and complete Android/ArkTS runtime calibration. Source conformance,
adapter readiness, and transport status are diagnostics rather than benchmark
metrics.

## Accepted Tasks

| Project | Task | Android boundary | Canonical cases |
|---|---|---|---:|
| Signal | Unified media keyboard | `v8.28.4` -> `v8.30.0` | 10 |
| Signal | Sticker management | `v7.40.2` -> `v7.43.1` | 10 |
| Signal | Responsive media editor | `v8.22.2` -> `v8.23.0` | 10 |
| Signal | Phone-numberless registration | `v8.26.4` -> `v8.28.0` | 10 |
| WordPress | Modern pages list | `26.8` -> `26.9` | 10 |
| WordPress | Unified support | `26.8` -> `26.9` | 10 |
| WordPress | Redesigned site picker | `24.6` -> `24.7` | 10 |
| WordPress | Interactive New Stats | `27.1` -> `27.6` | 10 |
| Wikipedia | Reading challenge | `r/50579-r-2026-04-14` -> `r/50585-r-2026-05-06` | 10 |
| Wikipedia | Hybrid search | `r/50566-r-2026-02-04` -> `r/50574-r-2026-03-20` | 10 |
| Wikipedia | Personalized Home feed | `r/50586-r-2026-05-12` -> `r/50590-r-2026-05-28` | 10 |
| Wikipedia | Saved articles and collections | `r/50600-r-2026-07-28` -> `r/50603-r-2026-08-25` | 10 |

Every task has a platform-neutral canonical transition contract and matched
Android/ArkTS runtime adapters. Calibration is base `0/10`, final `10/10` on
both platforms, with no unscored cases. Android scoring runs through installed
application owners on an API 37 emulator; ArkTS scoring launches EntryAbility
and the production ArkUI page owner on OpenHarmony API 23.

## Deep-Mining MiniMax-M3 Result

The latest OpenCode + MiniMax-M3 run is
[`deep_mining_minimax_m3_runtime_20261023`](results/deep_mining_minimax_m3_runtime_20261023/run-manifest.json).
It covers the six newly mined tasks above; all 24 base/final calibration cells
have the required `0/10` and `10/10` polarity, and all agent cases are scored.

| Platform | Code generation | Compile | Semantic testcases |
|---|---:|---:|---:|
| Android | 5/6 (83.33%) | 6/6 (100.00%) | 8/60 (13.33%) |
| ArkTS | 5/6 (83.33%) | 6/6 (100.00%) | 6/60 (10.00%) |
| Combined | 10/12 (83.33%) | 12/12 (100.00%) | 14/120 (11.67%) |

| Project | Code generation | Compile | Semantic testcases |
|---|---:|---:|---:|
| Signal | 4/4 | 4/4 | 12/40 |
| WordPress | 4/4 | 4/4 | 2/40 |
| Wikipedia | 2/4 | 4/4 | 0/40 |

The two Wikipedia ArkTS cells retain an `isolation_unverified` diagnostic due
to missing terminal subagent-session metadata. Their code-generation, compile,
and runtime semantic results are still recorded independently; the diagnostic
is not counted as a benchmark metric.

## Earlier MiniMax-M3 Result

The formal OpenCode + MiniMax-M3 run is
[`multi_project_minimax_m3_runtime_v2_20261022`](results/multi_project_minimax_m3_runtime_v2_20261022/run-manifest.json).

| Platform | Code generation | Compile | Semantic testcases |
|---|---:|---:|---:|
| Android | 3/6 (50.00%) | 6/6 (100.00%) | 28/60 (46.67%) |
| ArkTS | 6/6 (100.00%) | 6/6 (100.00%) | 24/60 (40.00%) |
| Combined | 9/12 (75.00%) | 12/12 (100.00%) | 52/120 (43.33%) |

Only these three columns are benchmark metrics. Hidden evaluator compilation,
adapter selection, device transport, and provider status remain diagnostics.
The retained result bundle includes the canonical-report validation, per-cell
reports, reconstructable platform patches, generated-file inventories, and
artifact hashes; it does not contain an API key.

