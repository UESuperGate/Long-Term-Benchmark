# OpenCode + MiniMax-M3 Evaluation

Use model ID `minimax-token-plan/MiniMax-M3` and endpoint `https://api.minimaxi.com/v1`. Configure credentials outside the benchmark checkout. Redact any provider config copied into an artifact.

The candidate workspace contains only:

- a clean copy of the Android base;
- the public requirement;
- a redacted/public transition description without expected private selectors;
- project-local build tools and dependency metadata.

Allow file reads, edits, search, project-local Git inspection, Gradle, and subagents. Deny network search, external directories, evaluator directories, final projects, and hidden bindings. Subagent work is part of the same 3600-second task budget.

Capture one overall run interval and one interval per top-level task. Do not sum subagent durations. Build failures may be returned to the agent for repair, but semantic case failures must remain hidden until the run is complete.

Published metrics:

1. Code generation rate: tasks with at least one valid production source change / valid tasks.
2. Compile pass rate: compiling agent candidates / valid tasks.
3. Semantic testcase pass rate: passed canonical cases / scored canonical cases.

Provider errors, timeout, adapter failure, transport failure, integrity failure, and unscored cases are diagnostics and validity annotations, not substitute benchmark metrics.
