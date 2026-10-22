# Task11 ArkTS strict runtime evaluator

This evaluator binds the six active `11_room_upgrade_navigation` cases to the
original ArkUI page and production room feature module on an OpenHarmony API23
device. Each case runs in a cold process after a fresh install.

The evaluator controls only the external room-info response. Room mapping,
presenter state, ArkUI rendering, physical UI clicks, navigation and invariants
remain production behavior. Missing final controls are observed as semantic
failures from the common page-ready prefix; build, transport and device errors
remain `not_scored` and cannot satisfy base polarity.

The suite rejects changed case identities or trace digests, imports the role's
original feature module after the production page is ready, and records UI
inspector frames plus production runtime state before and after each event. It
does not inspect source text.

Run the host regression tests:

```sh
node --test state_tests/runtime/arkts/native/task11_strict/Task11Strict.test.cjs
```

Run a fresh device matrix:

```sh
node scripts/runtime_semantics/task11_arkts_strict_matrix.cjs \
  --output-dir /absolute/new/evidence/path \
  --serial 127.0.0.1:5555 \
  --roles base,final
```

The matrix has a 3600 second task timeout, waits for both shared device locks,
builds the application and ohosTest HAP for every case, and requires owned-app
cleanup before accepting a row.
