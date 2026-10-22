# Task17 ArkTS MiniMax-M3 Agent Audit

## Benchmark Result

The retained run used OpenCode 2.0.20 with
`minimax-token-plan/MiniMax-M3`. The API key was read from local secret
configuration and is not stored in repository evidence.

| Metric | Result |
| --- | --- |
| code generation | passed; 14 production files in the reconstructable patch |
| application compile | passed; standalone unsigned HAP built successfully |
| semantic testcases | 2/9 passed, 7/9 failed |
| end-to-end task interval | 3274.255 seconds |

The end-to-end interval is measured once from the agent task start at
2026-10-22 08:59:31 +08:00 through the last formal device case at
2026-10-22 09:54:05.255 +08:00. It includes the agent and any subagent work,
patch archival, independent application compile, evaluator validation, base and
final calibration, and agent semantic execution. Subagents are not timed or
summed separately.

## Runtime Calibration

All 27 rows used a fresh API 23 install, the installed candidate Ability and
ArkUI page owner, physical UiTest actions, and an evaluator-owned Matrix room
leaf. No row used a source observer or detached presenter.

| Role | Application compile | Semantic result | Unscored |
| --- | --- | --- | --- |
| base | passed | 0/9 passed, 9/9 failed | 0 |
| final | passed | 9/9 passed, 0/9 failed | 0 |
| agent | passed | 2/9 passed, 7/9 failed | 0 |

The final migration's missing retry control was repaired before calibration and
is separately version-audited in
`audits/task17_arkts_unpin_retry_migration_fix_20261022/README.md`. The contract,
assertions, and agent patch were unchanged.

## Agent Failure Root Cause

The agent passes the initial loading transition and explicit load failure. On a
synchronous successful timeline emission, `PinnedMessagesList.open()` changes
its internal state from loading to empty/filled but does not notify the page.
The real page therefore remains visibly loading. Cases 003-009 cannot expose
the loaded rows or their view/unpin actions and fail their original state and
effect assertions. The failures are semantic observations, not compile,
adapter, transport, SDK, or storage errors.

The generated implementation also retains a pagination risk after unpinning:
its offset is not reconciled with the removed item, so a later page can skip a
pin. The current seven failures occur earlier at the missing page notification;
this secondary issue was not used to manufacture an additional score.

## Evidence

- Local raw agent run: `eval_runs/task17_arkts_minimax_m3_runtime_20261022_v1/`
- Published reconstructable patch: `audits/task17_arkts_agent_minimax_m3_20261022/agent.patch`
- Candidate patch SHA-256:
  `3b1fbe5eaeb2ad4da7d128a5684ca8efa3ff452f911b77729d57be20492da276`
- Patch reconstruction: verified
- Independent HAP SHA-256:
  `acebbe63e9830993c2923da41ca71a139289a01fa62ccd24e6d37e3658d9a5a1`
- Published formal matrix:
  `audits/task17_arkts_agent_minimax_m3_20261022/matrix.json`
- Formal matrix SHA-256:
  `660c0a3325c8a7d487a07633fdcbd8c623dfed5cfb2ef95d1a3665bfe2e9a8b9`
- Published role summaries: `base.json`, `final.json`, and `agent.json` in the
  same audit directory
- Published binary cleanup receipt: `binary-cleanup.json` in the same audit
  directory
- Independent verifier:
  `scripts/runtime_semantics/task17_arkts_owner_verify.py`
- Owner-bound central handler: `task17_arkts_owner_agent_v3`

The matrix completed in 475.631 seconds for all three roles; its agent-only
device/build phase took 187.520 seconds. These phase durations are retained for
debugging and are not substituted for the end-to-end task interval above.

## Isolation Diagnostic

The original runner correctly stopped publication when OpenCode reused a
background reviewer child and that child had not reached a terminal session
state. The audit is therefore retained as `isolation_unverified`, not rewritten
as passed. Its two debug codes are `session_not_terminal` and
`reused_child_session`.

The exported child contains 11 read calls, all inside the candidate directory,
with no observed write, shell, network, or outside-candidate access. The patch
is reconstructable and the application compile and owner-bound semantic matrix
were independently rerun from that patch. This supports the three benchmark
metrics above while preserving the fail-closed isolation diagnostic as a
separate caveat.
