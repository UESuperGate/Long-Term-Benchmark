# Join Room By Address (Android v25.02.0 -> v25.03.0)

## User outcome

Users can enter a Matrix room address, resolve it, inspect the matching room, and continue through the normal join flow.

## Functional requirements

- Accept room addresses in the supported Matrix alias form and distinguish untouched, invalid, resolving, not-found, and found states.
- Editing the field clears stale validation and prevents a response for an older address from replacing the current result.
- Continue on invalid input reveals validation without making a resolution request.
- Continue while a valid address is resolving waits for that result and advances automatically only if the same address resolves.
- A found room is passed to the existing preview/join flow using its resolved room identity.
- Not-found and network-resolution failure remain on the form with retryable feedback and preserve the typed address.
- Dismiss exits without joining or changing room membership.

## Invariants and non-goals

- Alias syntax and resolution are authoritative; guessed room identities are not allowed.
- Public room-directory search and alias creation are outside this task.
