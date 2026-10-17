# Identity Reset (Android v0.5.0 -> v0.5.1)

## User outcome

When normal recovery is unavailable, users can reset their own cryptographic identity through an explicit, authenticated, recoverable flow.

## Functional requirements

- Offer reset only from a recovery state where it is meaningful and explain the destructive consequence before starting.
- Confirmation creates one reset operation and routes to the required authentication step.
- Password or delegated reauthentication state is preserved while the reset operation is active.
- Valid authentication advances the same operation to completion; it must not start a second reset.
- Invalid credentials or SDK failure display recoverable errors and retain enough state to retry.
- Canceling at confirmation or authentication closes the active reset path without reporting success.
- Successful reset leaves the flow and refreshes recovery/verification state.

## Invariants and non-goals

- Cancel and failure never mark recovery as configured.
- Normal recovery-key verification and resetting another user's identity are outside this task.
