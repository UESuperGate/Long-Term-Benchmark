# User Verification (Android v25.03.1 -> v25.03.2)

## User outcome

Users can verify another Matrix user with an interactive challenge and can see when that user's identity has changed and requires attention.

## Functional requirements

- Start verification from a user or member profile only when verification is available.
- Represent request creation, remote acceptance, challenge receipt, local accept or decline, completion, cancellation, and failure as distinct states.
- Challenge data remains stable while the user compares it; accepting or declining sends exactly one response.
- Local cancellation and remote cancellation end the active request and offer a clean reset or exit path.
- Unexpected request or SDK failure becomes a recoverable canceled/failed state rather than a false success.
- Identity-change violations appear consistently in relevant timeline, room-member, room-detail, and user-profile surfaces.
- Successful verification clears the corresponding warning; cancellation or failure does not mark the user trusted.

## Invariants and non-goals

- Existing self-session verification continues to work.
- Identity reset, recovery setup, and cryptographic challenge generation are outside this task.
