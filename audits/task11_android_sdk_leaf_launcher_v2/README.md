# Task11 SDK Leaf Queued Launcher V2

Status: supervisor prepared; **actual Kotlin compile/runtime NOT RUN**.
Await the coordinator's next small-slice window after Task12. This document
does not claim that a slot was granted or reserve/hold any real build lock.
Task10 remains paused/unscored. No new model budget or semantic result exists.

## Reviewed Process Protocol

Launcher: `scripts/runtime_semantics/task11_android_sdk_leaf_launcher_v2.py`.
It calls `tasks16_17_native_controller_v3._supervise` unchanged, reusing its
`task15_deadline_v4.OverallDeadline`; no new timer implementation is introduced.
The inherited controller's generic seal names its own native controller schema
and implementation files. It is only a process-supervision diagnostic here,
NOT a Task11 native admission/publication receipt. Task11's separate request,
worker result and diagnostic explicitly bind the Task11 implementation and carry
`semanticPromotionEligible: false` and `semanticScore: null`.

One original <=3600s parent clock covers source binding/export, evaluator
preparation, both lock waits, dependency/resource compilation, javac/kotlinc,
JUnit, evidence hashing/writes, finalization and owned temporary cleanup.
The child receives remaining seconds plus the bounded epoch deadline, not a
transported Python monotonic timestamp. There is no stage budget reset.

The parent creates one worker with `start_new_session=True`. All Git/Maven/aapt/
javac/kotlinc/JUnit children inherit that PGID. Worker instrumentation refuses
nested sessions/groups, preexec hooks and shell commands, records actual PID/
PGID launches, and removes direct-child `subprocess.run` timeouts: only the
original parent supervisor terminates the owned group. Each launch checks the
8GiB floor. Global full-build/probe lock and Android runtime `.build.lock` are
taken inside the worker, with the same remaining deadline. No app Gradle/Rust
build, model call, installation or dependency download is introduced.

Temporary compiler/source inputs are restricted to `owned-work`. Shared runtime
finalizers' directory removals are deferred, not executed by the worker. The
unchanged supervisor confirms the group is gone before hashing and removing its
own work. If group ownership is unsafe, inputs are retained. At hard expiration
the prebuilt atomic revocation is installed first, then only an unreaped owned
group may be signaled, followed by nonblocking reap. No late hashing, recursive
cleanup, new deadline, or foreign input deletion is attempted.

## Execution After Explicit Resource Release Only

Use one fresh output directory and a supplied standalone candidate. Do not call
the historical v1 `--execute-prepared`: it remains byte-preserved evidence, not
the v2 supervisor. Do not pre-run candidate preparation outside this command.

```sh
python3 -B -m scripts.runtime_semantics.task11_android_sdk_leaf_launcher_v2 \
  --source /absolute/standalone/task11-candidate \
  --output /absolute/fresh/task11-sdk-leaf-first-compile-v2 \
  --resource-clear-reviewed --timeout 3600
```

The flag records technical queue release, not human approval of semantics. It
must not be used until the coordinator grants the window. Failed compile or
runtime is retained diagnostic/NS, never a missing-class semantic failure.
CLI exit0 requires both actual slice compilation and runtime to report passed;
even then no canonical score or complete-cell claim is authorized.

Retained artifacts include `request.json`, `worker-launch.json`,
`actual-process-launches.json`, `actual-compilation.json` (compiler/source/
classpath hashes and produced class hashes before cleanup), `runtime.raw.json`,
`runtime.raw.log`, original rendered evidence, source/configuration bindings,
the derived evaluator plan, and `task11-diagnostic.json`. Early/hard failure may
leave an incomplete set; `controller-admission.json` remains pending/revoked,
with no guessed runtime evidence. Original production, canonical assertions,
mapper006, WYSIWYG and v1 preparation/fixtures are unchanged.

## Verification Already Performed

```sh
python3 -B -m unittest scripts.test_task11_android_sdk_leaf_launcher_v2 -v
python3 -B -m unittest scripts.test_tasks16_17_native_controller_v3 -v
python3 -B scripts/test_task11_android_sdk_leaf_preparation.py -v
```

12 launcher tests, 25 reused-supervisor regressions, 14 original preparation
tests passed. Short real Python workers/descendants test inherited PGID,
bounded lock wait, parent timeout, deferred cleanup, hash/finalizer/cleanup
interruptions and immutable foreign inputs. The runtime function is explicitly
mocked in the synthetic preparation test; no JVM/device/model was invoked.
These are process/preparation tests, not Kotlin compilation evidence.

Next: actual first compile in the released slot, retain compiler diagnostics,
repair evaluator wiring only if needed, then all six canonical rows with fresh
base/final/same-agent controls and exact-candidate replay. Main still owns
public/readiness changes. Offline success must not bypass this sequence.
