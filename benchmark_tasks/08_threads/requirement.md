# Message Threads (Android v25.08.3 -> v25.08.4)

## User outcome

Users can open a thread from a timeline event, read its focused conversation, and participate without losing the room or reply context.

## Functional requirements

- Opening a thread creates a timeline scoped to the selected root event and shows the root with its replies.
- Tapping a reply target focuses the matching event when it is available; loading an out-of-window target must not corrupt the current timeline.
- Text, attachments, voice messages, locations, and polls sent from a thread remain associated with that thread.
- Reply mode accepts any remote event that is valid in the thread and preserves the selected target until send or explicit cancellation.
- Returning from nested media, location, poll, or debug screens restores the same thread and composer context.
- A failed send remains visible as a recoverable failure; dismissal clears only the failure UI, and retry uses the original content and thread relation.

## Invariants and non-goals

- Main-room and thread timelines must not leak focused events or composer state into one another.
- Existing non-thread message behavior remains unchanged.
- Thread notification splitting and permalink support are outside this version boundary.
