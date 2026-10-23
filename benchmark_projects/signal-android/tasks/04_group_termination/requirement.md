# Initial group termination lifecycle

## Version boundary

Implement the group-termination behavior introduced between Signal Android v8.4.1 (`c7ec3ab837b3c149d5579840317b1dc6cd4629f3`) and v8.5.0 (`068eaff8010365353410914fbcf1bed79e69d6bb`). The original v8.4.0 candidate was normalized to v8.4.1 because v8.4.1 is the newest ancestor tag that still lacks the behavior.

## User outcome

An administrator of an active modern group can permanently end the group through an explicit destructive flow. Members who learn of the termination converge on a durable terminal state, see that the group ended, and can no longer use the primary conversation composer.

## Functional requirements

- Offer the end-group action only when the group is active, uses the modern group model, and the current user is an administrator. Do not offer it to non-admins, inactive groups, or legacy groups.
- Require two explicit confirmations before submitting termination. Canceling either confirmation leaves the group unchanged.
- While termination is being submitted, show an in-progress state. A successful submission advances the group revision, marks the group terminated, records the terminating member when known, and emits the normal group-update history entry.
- Apply a valid remote termination update to local group state just as a locally initiated termination is applied. Stop active typing state for the group and retain the terminator identity when the update identifies one.
- When the terminator is unknown, preserve the terminal state and present generic termination messaging rather than inventing an actor.
- A conversation that becomes terminated while open displays a termination notice for a termination initiated elsewhere, replaces the primary input with a terminated-state banner, and reflects the terminal state in conversation settings.
- Preserve the terminated flag through database migration, backup export, and backup import.
- Treat an already terminated group as stable: a forced refresh is a no-op, and later peer group changes do not advance or mutate the group.
- If a pending join discovers that the service has terminated the group, mark the local group terminated. Direct attempts to inspect or join a terminated group return a terminal-group error rather than a generic network failure.

## Invariants

- Only an eligible administrator can initiate termination from settings.
- No remote mutation or local terminal state is produced before the second confirmation.
- Termination is irreversible within this task; no state transition returns a terminated group to active.
- Duplicate discovery of an already terminated group is idempotent.
- Unknown terminator identity never blocks applying the terminal state.
- Canceling or failing termination leaves the group active and available for a later retry.

## Failure and recovery

If the termination request fails because of a group-change, busy-state, permission, or network error, dismiss the progress state and offer retry or cancel. Retry resubmits the termination attempt; cancel returns to the unchanged active group. A failed attempt must not display the group as terminated.

## Non-goals

Legacy-group termination and reopening a terminated group are outside this task. Also outside this v8.5.0 boundary are later hardening changes that suppress every secondary send or interaction path and later storage-service restoration behavior that synthesizes a termination event. The ArkTS implementation is a migration target, not the benchmarked capability.

## Review status

This candidate is `needs_review`: the official v8.5.0 release text does not mention group termination, and four follow-up commits that complete additional lockout and restoration behavior are not contained in v8.5.0. The requirement above is intentionally limited to behavior proven inside the stated final commit.
