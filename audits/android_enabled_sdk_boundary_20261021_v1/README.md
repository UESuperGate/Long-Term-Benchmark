# Enabled Android SDK Boundary Review

`audit.json` freezes the read-only review of Tasks 10, 11, 12, 13 and 15.
It records immutable base/final commits, changed paths/symbols and blob hashes,
canonical case IDs/digests with precise affected effects, fixture hashes,
retained raw/log hashes, executed-class evidence and available classpath records.
No source bodies, archives, provider configuration, binaries or large reports
are duplicated. Historical execution classpaths are not fresh binary verification.

## Findings

- 10: new Rust limit bridge bypassed by app MatrixClient doubles. New processing
  and encoder handoff also bypassed; actual production cleanup remains observed.
- 11: real new predecessor mapper executed, but the app JoinedRoom fixture injects
  its mapped input above RustBaseRoom.predecessorRoom. Navigation/UI observations
  remain scoped observations, not proof of the missing SDK acquisition chain.
- 12: new capability/report bridges bypassed by MatrixClient/JoinedRoom proxies.
  Real form/entry/ordering assertions remain distinguished from SDK effects.
- 13: new user-verification request bookkeeping and identity mapping bypassed.
  Unchanged service API doubles are not automatically invalidated.
- 15: capability/auth retry/delegate recovery/session deletion bridge bypassed.
  App request counts are not SDK request counts; form/confirmation UI is separate.

Task11 WYSIWYG remains 2.38.3 on both immutable refs. Its SDK-owned plain-text
switch invokes the original renderer and rejects unsupported links/mentions.
Keep that boundary and the actual mapper test; do not equate them with an
app-owned feature implementation being replaced.

## Availability And Limits

Immutable base source exposes existing wrappers, not the newly used SDK APIs.
The tracked trees contain no SDK jar/AAR/UDL; the current candidate preparer does
not add an SDK API inventory. This is a discoverability gap, not proof that the
SDK lacks the methods, and not a new full-history baseline attestation.

Task10 old raw JSON paths are absent; retained small runtime/compiler logs and
normalized reports were inspected without fabricating missing raw. Task11's
configured temporary navigation file is absent; its annotation-only configured
hash was reproduced in memory from the current fixture, without writing a copy.
Raw fixture bindings for 12/13/15 matched current source hashes at review time.

This is coordinator technical review, not new human approval, score publication,
or readiness withdrawal. Main owns readiness/public guards. No contract, original
score/model report, model timing, SDK/cache, or production source was edited.

## Repair Queue

Task11 is first: actual immutable-version RustBaseRoom -> SDK Room leaf -> real
mapper -> original TimelinePresenter/page/navigation. No app PredecessorRoom
injection. Preserve mapper006/WYSIWYG. Source-parameterized preparation only;
MC owns the heavy queue and no JVM/device/model is launched here.

Task10's new SDK/codec-leaf diagnostic fixture drafts are paused, uncompiled and
unscored. They are not integrated into formal scoring and supply no new pass.
