# Explore Feed ArkTS runtime design

- The canonical contract is `../../canonical/transitions.json`; case IDs, trace digests, given values, events, outcomes, and invariants are unchanged.
- The installable API 23 app owns one `Index` page and one `ExplorePageOwner`. Evaluator wiring mounts that same owner, dispatches its production methods, and reads the owner's production store before and after each event.
- ArkData Preferences named `explore_feed` is cleared and seeded through the production store. The evaluator reopens it after the event and requires the reopened JSON to equal the owner persistence view.
- External service leaves are evaluator controlled and record only effects. They do not implement Explore behavior or choose results by case ID inside candidate production.
- The scorer binds an arbitrary candidate directory through the public page-owner ABI, hashes candidate production sources and the HAP, and marks unavailable binding, device, episode, or persistence evidence as `not_scored`.
- Semantic verdicts use runtime state/effects plus independent invariant checks. Candidate role is metadata only; source text is never scored.
