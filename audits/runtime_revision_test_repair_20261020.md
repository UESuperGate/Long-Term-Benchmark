# Bounded Historical Audit Test Repair

Date: 2026-10-20 (Asia/Shanghai).

## Scope

Read-only evidence inspection and Python audit/test repair. No application build,
device execution, contract/binding edit, production edit, score edit, scoring
validator edit, central dispatch edit, or readiness edit was performed.

Files changed in this repair:

- `scripts/audit_runtime_contract_revision.py`
- `scripts/test_runtime_contract_revision.py`
- `scripts/test_runtime_contract_revision3.py`
- `scripts/audit_task12_version_boundary.py`
- `scripts/test_task12_version_boundary.py`
- `scripts/test_runtime_transition_matrix.py`
- This independent audit note.

## Findings And Repairs

### Revision 2 And Revision 3

The revision-2 audit compared current Task10 revision-4 bytes with the revision-2
transformation. It now verifies the hash-bound revision-2 archive, manifest
changes, historical aggregate transformation, and retained revision-2 snapshot
under revision-3/before. Current Task10 must separately equal the audited
`revision_4_task10_v2/after` contract and binding. Returned revision-2 hashes
remain historical; the current revision-4 hash is never relabelled revision 2.

The revision-3 staging manifest's `activeCanonicalModified: false` describes the
staging operation, not a claim that active files can never be promoted later.
The test preserves the immutable manifest/artifact verification and explicitly
checks the approved current snapshots: Task10 revision 4, Task12 revision 3,
and the retained before-versions for Tasks15/18.

### Task12 Standalone Application Build Evidence

The former check required HAPs already removed during disk cleanup. Replacement
evidence is retained under:

`experiment_results/runtime_transition_20261020/formal_task12_13_runtime_20261020/task12-arkts-final-copy-v4.strict-evidence/`

For each of `base` and `final`, use
`runtime.arkts-evidence/application-build/application-build.json`, its hash-bound
log, the wrapper's `applicationBuild` identity, and the role's `cleanup.json`.
The generic builder labels reports `role=agent`; the actual calibrated pole is
verified by `label=task12-base/task12-final`, exact source root, wrapper role,
and source byte/hash inventory. Both records prove standalone `assembleHap`,
exit 0, unchanged production, and `BUILD SUCCESSFUL`. OhosTest packaging is
explicitly rejected as an application build substitute.

Application-build report SHA-256:

- base: `8dac9f0497375775ee41752b3c9866ac9e380deb836b3a284b5ec3cde1fa59f4`
- final: `27fb384c820191bd2393526523120cd97d76bcad405e7a161194e40c9c9262ed`

Removed HAP SHA-256 / bytes, cross-checked against cleanup:

- base: `45e50128841bf9587321c9efc88e8428032bea75c8a175dd85d61ee1dd9bb7ad` / 143747
- final: `6b929495ce06f880f3abc636585c28502b5cdb025d9fa68880f905ba87cafd9d` / 188698

The audit fails closed on a missing source inventory, mismatched report/log or
wrapper, runtime packaging substitution, or a cleanup flag without the exact
artifact hash. No HAP was regenerated and no benchmark compile score changed.

### Task14 Historical Entry Evidence

The 2026-10-19 single-case report binds earlier versions of
`StartChatEntryTest.kt`, `run.py`, and `adapter.json`. Their current bytes differ.
The historical positive-validation test is withdrawn; the replacement test
requires `not_scored` with `Artifact hash mismatch`. The original report bytes
and every original artifact hash remain unchanged.

Historical report:
`experiment_results/runtime_transition_20261019/android_followup_14/baseline_entry/base.json`

SHA-256: `3fe980beac551b7231988471607a8d565d3802cef6fbce1b0d9b1cad04a349d5`.

Replacement runtime evidence:
`experiment_results/runtime_transition_20261020/task14_android/base-entry-all-attempt2.json`

SHA-256: `87f280b912934c593302d3a35cd70251c3c2ecee5551a037273ef03e8fd9fec3`.

The test checks this replacement's persisted evaluator/log artifacts, immutable
upstream production bytes, all nine independent base failures and positive
controls through the existing independent Task14 verifier. A mutation claiming
that the missing transition executed is rejected. This is existing runtime
evidence revalidation, not a new execution or score.

## Remaining Real Gaps

- Active Task10 binding matches the approved after-version, but case
  `mq_state_008_block_when_all_oversized` has binding digest
  `7183f1873871b248e7778ca490faa58a8ee156768721fe32794399cb6bdc65a2`
  while the active contract has
  `415aa5d083075c72f83a0e7cc572ab2d8b6b4483c592ef742ac4666809cfeda4`.
  `active_binding_gaps()` reports it as
  `active_binding_mismatch_unpublishable`; historical audit success does not
  certify this current binding or authorize score publication.
- Aggregate `state_tests/canonical/new_tasks_cross_platform_contract.json` case
  rows differ from task-local canonical contracts for Tasks10, 12, 13, and 16.
  This repair does not regenerate or promote those data. The historical
  revision-2 aggregate verification no longer claims to certify today's
  aggregate parity.
- Task12 boundary audit still reports Android full application build pending.
  Retained ArkTS base/final standalone build evidence is verified, but it does
  not supply an Android compile result or restore deleted agent application
  build reports elsewhere in the evidence tree.
- The old Task14 single-case artifact chain is unavailable against today's
  mutable probe paths. It remains withdrawn/NS; the newer nine-case evidence
  has its own provenance and is not substituted into the old report.

## Validation

Initial reproduction: 58 tests, 3 failures and 2 errors.

Command:

```bash
PYTHONPATH=scripts python3 -m unittest \
  scripts.test_runtime_contract_revision \
  scripts.test_runtime_contract_revision3 \
  scripts.test_task10_contract_revision4 \
  scripts.test_task12_version_boundary \
  scripts.test_task13_contract_revision5 \
  scripts.test_task16_contract_revision5 \
  scripts.test_runtime_transition_matrix
```

After repair: 64 tests pass. Tests verify historical revision identity,
standalone application build provenance after binary cleanup, rejection of
artifact-hash/runtime-packaging mutations, explicit old-evidence withdrawal,
and replacement runtime evidence. Existing semantic validators remain intact.
