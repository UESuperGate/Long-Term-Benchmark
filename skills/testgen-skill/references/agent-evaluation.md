# OpenCode + MiniMax-M3 Evaluation

Use model ID `minimax-token-plan/MiniMax-M3` and endpoint `https://api.minimaxi.com/v1`. Configure credentials outside the benchmark checkout. Redact any provider config copied into an artifact.

The candidate workspace contains only:

- a clean copy of the Android base;
- the public requirement;
- a redacted/public transition description without expected private selectors;
- project-local build tools and dependency metadata.

Allow file reads, edits, search, project-local Git inspection, Gradle, and subagents. Deny network search, external directories, evaluator directories, final projects, and hidden bindings. Subagent work is part of the same 3600-second task budget.

Before model execution, archive the complete clean-room baseline and public inputs with their commit/tree and SHA-256. Keep a compressed immutable source snapshot when the baseline is a migrated working tree. A patch and later copy of base do not independently attest unread, unchanged input files. Label any later recovery honestly rather than presenting it as an original-time snapshot.

Git archives attest committed blobs, not necessarily the working tree read by the
agent or compiler: LFS/clean filters may hide different raw bytes, and tar modes
may differ from filesystem modes. Keep a direct raw snapshot with file types,
bytes, exact POSIX modes and literal contained link targets, then verify both the
archive and unchanged working tree before execution. Record excluded inputs and
historical capture gaps explicitly; do not hydrate or rewrite them to claim parity.

Use one build argv for the public instruction, permission allowlist and actual
post-agent build. Do not silently change cache flags, init scripts, ABI or modules.
If a public candidate-local init is needed, seal its bytes/mode before the model,
deny agent edits and verify it again before and after build execution. Missing or
changed protected inputs invalidate the run; a global-file fallback is not parity.

Capture one overall run interval and one interval per top-level task. Do not sum subagent durations. Build failures may be returned to the agent for repair, but semantic case failures must remain hidden until the run is complete.

For Gradle workers, verify actual process closure with the pinned distribution;
`--no-daemon` can still create a single-use JVM outside the wrapper's session.
Use a version-verified startup strategy and actual JVM/group evidence before
crediting bounded execution or cleanup. Do not stop unrelated global daemons.
Bootstrap init scripts can run again for included builds: accept only identical
same-execution startup and acknowledgement records, without rewriting the first
proof; a new nonce, JVM identity or changed acknowledgement remains invalid.

Keep review provenance literal: an evaluator or coordinating agent's technical
review is not human authorization. A retrospective command-locality analysis does
not change the original frozen isolation-policy result. Preserve that result and
label any later analysis separately; never fabricate approval records to promote
a run's validity or publication eligibility.

When correcting a versioned contract, compare the actual public input files and requirement given to each archived agent, not only private expected values. If public inputs changed, replaying the old patch is evaluator regression evidence, not a comparable model result for the revised task. Preserve completed-read evidence and input hashes, label that confound, and run a fresh isolated one-shot candidate after recalibration. Never repair the archived candidate against revealed semantic failures. Private-only corrections still require a contract/specification audit before interpreting the rescore.

Published metrics:

1. Code generation rate: tasks with at least one valid production source change / valid tasks.
2. Compile pass rate: compiling agent candidates / valid tasks.
3. Semantic testcase pass rate: passed canonical cases / scored canonical cases.

Provider errors, timeout, adapter failure, transport failure, integrity failure, and unscored cases are diagnostics and validity annotations, not substitute benchmark metrics.

The application compile metric comes only from the agent runner's standalone candidate build. Evaluator packaging and test compilation are recorded separately as `runtimeCompile`. Environment, transport, or `runtimeCompile` failure leaves application compile unchanged, marks affected semantic cases `not_scored`, and blocks publication.

The published evidence bundle includes the run manifest, calibration and rescore summaries, normalized reports, and a binary-safe patch for every scored candidate. Verify that base plus patch reconstructs the scored candidate, including newly created files. Large local logs may stay outside Git, but publish their SHA-256 and byte length so each retained score remains bound to an immutable local archive. Record path, byte length, and SHA-256 for generated APK/HAP/HAR/APP/ABC/SO files, then delete those binaries and verify the retained evidence tree is binary-free.

Before removing a scorer's temporary tree, preserve the complete original native
result, execution/build receipts and referenced logs, not just their hashes or a
normalized summary. An independent verifier must compare scored state and
invariants to the original emitted bytes after candidate cleanup. Retain explicit
hash-preserving path mappings; do not rewrite old receipts to look current.
Lossless compressed JSON with verified restoration is suitable for large payloads.
Missing raw evidence makes a retained result incomplete, not reconstructable from
its reported verdict. Binary build artifacts and raw semantic evidence have
different retention requirements.
