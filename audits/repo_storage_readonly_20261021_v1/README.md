# Repository Experiment Storage Investigation

Read-only measurements of `experiment_results`, `eval_runs`, and
`state_tests/runtime` on2026-10-21. No model/build/device work, cache deletion,
source deletion, snapshot removal or evidence repackaging was performed in
this investigation. This file is the investigation output only.

## Measured Categories

Files were inspected with lstat; symlinks were not followed. For category
totals below, dependency/vendor directories `.dependencies`, `node_modules`,
`.git`, `.gradle`, `.hvigor`, `.native` were excluded. Already compressed
extensions include gzip/zip/tgz/xz/zst/7z/jar. Allocated bytes use
`st_blocks * 512`; neither allocation slack nor an archive's existing size is
claimed as safely reclaimable bytes.

| Root | Logical bytes | Allocated bytes | Files | Raw JSON/JSONL/log bytes | Already compressed bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| experiment_results | 3,945,392,763 | 4,188,618,752 | 90,457 | 3,095,050,529 | 445,500,882 |
| eval_runs | 264,933,345 | 282,980,352 | 6,384 | 235,814,567 | 70,187 |
| state_tests/runtime | 65,319,714 | 67,940,352 | 1,080 | 59,129,299 | 719,275 |

These are separate from initial `du` totals that included dependencies.
Free space changed during investigation from5.064GiB to5.006GiB and finally
5.5307GiB. No ownership of concurrent external writes or cleanup is inferred.

## Largest Named Groups

These measurements precede the final totals slightly; concurrent writers mean
they are not an atomic snapshot. They are occupied bytes, NOT cleanup approval
or net recoverable estimates.

| Experiment group | Logical bytes | Already compressed bytes | Classification |
| --- | ---: | ---: | --- |
| runtime_transition_20261020/formal_task12_13_runtime_20261020 | 285,019,762 | 12,964,159 | mixed historical controls, sources and raw; not all eligible |
| runtime_transition_20261020/task13_page_owner_port_v1 | 262,262,818 | 9,362,758 | current/accepted13 evidence mixed with historical diagnostics; preserve |
| runtime_transition_20261020/task11_arkts_strict | 246,048,221 | 3,613,698 | valid11 provenance may depend on paths; preserve |
| runtime_transition_20261020/task09_minimax_semantic_repair_v8 | 239,436,110 | 21,888,103 | protected09 accepted evidence; preserve |
| runtime_transition_20261020/formal_agent_scorer_audit | 185,485,230 | 1,825,203 | mixed historical raw and retained rejection reports |
| runtime_transition_20261021/task11_android_real_sdk_leaf_first_compile_v3 | 183,949,222 | 137,707,797 | current PT11 owner; preserve |
| runtime_transition_20261019/device-calibration | 172,856,904 | 0 | old runtime evidence, not source copies |

The largest individual file observed was
`runtime_transition_20261021/task11_android_real_sdk_leaf_first_compile_v3/attempt1/original-control.failed.tar.gz`
(75,792,384 bytes). It is already compressed and current-owner evidence,
not75MB of available savings.

## Duplicate And Build Candidates

SHA256 grouping of same-size, uncompressed regular files >=1MiB across the
three roots found30 exact-content duplicate groups. Removing all but one
copy would have a theoretical logical-byte upper bound of140,255,389 bytes
(133.76MiB), BEFORE eligibility checks and archive costs. It includes protected
Task09 and valid11/other control paths, so it is NOT a safe deletion list.
Files below1MiB were not included in that bound; it is not an all-file global
deduplication claim. Small-file allocation overhead is not evidence duplication.

Eight exact old generated `task12_prefix/*.artifacts/resources.jar` paths have
46,587,565 bytes total. Their paired original reports contain
`cleanup.temporaryCompilerOutput=removed` and `cleanup.buildLock=released`.
However, inspection of `android-final-v5.artifacts/resources.jar` found:
1,957 ZIP entries, all compression method8 (Deflate),5,508,579 compressed member
bytes,17,249,816 expanded bytes,5,825,249 total jar bytes. Therefore44.4MiB is
NOT an honest gzip/tar net-reclamation estimate. No low-yield repackaging or
hash-only deletion of these potentially provenance-referenced binaries was
performed.

Name-based snapshot grouping did not reveal a >=1GiB source-copy directory.
The largest such preliminary match was the old generated
`eval_runs/opencode_glm53_3600_20261009_combined/verification_reports/snapshot_state_dynamic_strict`
(16,073,034 logical bytes). Some name matches are UI/runtime state snapshots,
not copies of application source; naming alone does not authorize cleanup.

## Safe-Recovery Limit

No >=1GiB safe rebuildable/source-duplicate candidate was established. A
conservative metadata-only filter for >=1MiB old19/20day raw JSON/log outside
Task09, task11_arkts, task13_page_owner and formal_tasks10_11 found
557.9643MiB BEFORE terminal-proof, unique-evidence, active-owner and current
rejection-report checks. That is an unreviewed upper bound, not an executable
whitelist, and still below1GiB. Excluding valid ArkTS paths further reduces it.

The bulk of occupied space is raw runtime evidence with repeated serialized
state/provenance, not reconstructable build output or large duplicated source
trees. Reaching1GiB requires identifying additional completed historical raw
evidence sets and retaining exact-byte archives with restoration indices;
this cannot honestly be presented as clearing1GiB of duplicate source copies.
Existing protected/valid controls and unique evidence have not been removed.
All earlier storage archives and restore indexes remain intact.
