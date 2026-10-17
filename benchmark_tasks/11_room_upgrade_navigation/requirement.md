# Room Upgrade Navigation (Android v25.06.2 -> v25.06.3)

## User outcome

Users can recognize that a room was replaced after a version upgrade and navigate safely between the old and replacement rooms.

## Functional requirements

- Map predecessor and successor metadata from room state into stable application state.
- A replaced room is visibly marked in the room list and room timeline and is treated as read-only.
- The old room shows a successor action that opens the replacement room.
- The replacement room shows its predecessor at the beginning of the timeline and opens the old room when selected.
- Preserve the predecessor's last event id in timeline metadata while navigation opens the predecessor room safely.
- Missing reasons, temporarily unavailable metadata, or navigation failure must not hide existing room history or re-enable composing in a tombstoned room.

## Invariants and non-goals

- Upgrade metadata must not alter unrelated membership or encryption state.
- This task renders and navigates upgrade relationships; it does not perform the server-side upgrade itself.
