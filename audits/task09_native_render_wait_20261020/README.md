# Task09 Read-Only Render Readiness Repair

The v5 exact-candidate replay has 3 pass, 5 fail and 1 unscored raw rows. Its
formal result correctly remains unavailable. Case004 stopped before its first
Join dispatch: the actual repository had two loaded children with idle join
state and no join attempts, but the native control was not yet ready. No
canonical join/retry transition was observed in that run.

The before-version of `Task09Repository.js` is retained alongside this audit,
SHA-256 `a8d3560c582d113b5955b8376a3ce4f86ef2e5b9f3992bd778bf4f3d09fe0a03`.
The repair adds bounded, read-only acquisition of a present, visible and enabled
control before one original physical click. It never changes production state,
forces a disabled control, or retries an already dispatched click. An unresolved
control remains unavailable, not a semantic failure.

The original model patch, canonical assertions, v5 reports and raw device rows
are preserved. New calibration and exact-candidate execution must use a fresh
output version; old fixture hashes are not relabelled.

The v6 candidate subsequently completed 3 pass / 6 fail / 0 unscored, and the
main thread independently verified its retained native rows and 20 production
files before changing fixtures again. V6 calibration was incomplete: several
base placeholder reads had unknown visibility and final case004 acquired its
control before render readiness. Those failures remain unavailable; the valid
candidate trace alone is not a complete newly calibrated benchmark result.

The v7 repair shares the same read-only acquisition and exact pre-dispatch
retry helper between original base/final pages and the split candidate adapter.
The base records its final checkpoint only after the actual placeholder is
present and visibly rendered. No absent/disabled/visibility-unknown control is
forced, and no delivered action or failed semantic assertion is retried.
The v6 before-versions are retained as `Task09Suite.v6.before.js` (SHA-256
`f97c4183023b7b1eda00922fcd167786441bed8a422ad7889047ca3b3688d34f`)
and `Task09Repository.v6.before.js` (SHA-256
`1d3b8c6897b5bd5d298aaa216b996853344ebd3f8e1cca54d103458702682703`).

V7 re-established base 0/9 and final 9/9, both with no NS. Its candidate again
had 3 pass / 5 fail / 1 unscored: automatic production pagination completed while
the fixture was acquiring the manual Load more control. V8 accepts that setup
only with the original presenter's actual pagination-dispatch record for the
same selected space and its loading/completion state. A dedicated exception code
proves the manual click was never dispatched. Delivered-action errors and absent
original-pagination evidence still fail closed. No leave-state assertion changes.
`Task09Repository.v7.before.js` retains SHA-256
`ad6bbe0c3982b34fd0912b06d580ed9a1debcc5d9affbeb420fd26f40ac2b5d4`.
