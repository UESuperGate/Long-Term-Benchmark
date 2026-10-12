# Android External Semantic Observer

The Android semantic observer is evaluator-owned. It runs after the candidate
has finished and after the candidate-integrity audit has passed.

The observer does not add code to the submitted worktree. `init.gradle` adds a
temporary, external source directory to one module's `test` source set. The
source directory is populated from evaluator-private probes derived from the
official final Element X tag. Gradle compiles those probes against the
candidate's production code.

Source isolation is enforced twice: on the Android `test` source set and on the
debug unit-test Kotlin/Java compiler tasks. Candidate-owned test classes and
fixtures therefore cannot be compiled into the observer run.

A probe can declare narrowly scoped `supportSources` when its official test
class depends on same-module test fixtures. The evaluator extracts those files
from the same final tag and injects them with the primary probe; candidate-owned
fixtures are never used as oracle code.

An observation is scoreable only when all of the following are true:

1. the candidate-integrity audit passes before probe injection;
2. the probe source is outside the candidate worktree;
3. the named JUnit test method executes (not merely compiles);
4. the JUnit XML reports that method as passed; and
5. the observation records the exact state-trace digest.

Missing probes, compilation errors, missing JUnit XML, skipped tests, and
observer protocol failures are `not_scored`. They are never converted into a
semantic testcase failure.

The old in-app `StateTestProbeProvider` is not valid semantic evidence for an
agent result because it is part of the agent-editable source tree.
