# Reading Lists ArkTS runtime design

- The canonical contract is `../../canonical/transitions.json`; case IDs, trace digests, given values, events, outcomes, and invariants are unchanged.
- The installable API 23 app owns one `Index` page and one `SavedPageOwner`. Evaluator wiring mounts that same owner, dispatches its production methods, and reads the owner's production store before and after each event.
- ArkData Preferences named `saved_surface` is cleared and seeded through the production store. The evaluator reopens it after the event and requires the reopened JSON to equal the owner persistence view.
- Evaluator-controlled leaves record redirect, Room-flow, and sync boundary effects. Missing upstream Android UI coverage is represented by runtime setup and checkpoints, not invented unit-test coverage.
- The scorer binds an arbitrary candidate directory through the public page-owner ABI, hashes candidate production sources and the HAP, and marks unavailable binding, device, episode, or persistence evidence as `not_scored`.
- Semantic verdicts use runtime state/effects plus independent invariant checks. Candidate role is metadata only; source text is never scored.
