# Pinned Messages (Android v0.5.1 -> v0.5.3)

## User outcome

Users can open a room's pinned-message collection, browse it, jump to a message, and unpin items when permitted.

## Functional requirements

- Opening the pinned collection creates a timeline scoped to pinned events and loads its initial page.
- Represent loading, empty, filled, and failed states distinctly; a load failure is not an empty collection.
- Additional pages can load without duplicating existing items or losing item actions.
- Selecting an item returns to the room timeline and focuses that event when possible.
- The room banner reflects whether pinned messages exist and opens the list.
- Pin/unpin actions are shown only when current permissions allow them.
- Successful unpin removes the item through the underlying state update; failure keeps it visible and offers recoverable feedback.
- Redacted or unavailable pinned events remain handled without crashing the list.

## Invariants and non-goals

- The server remains authoritative for pin ordering and permissions.
- Pin expiration and manual reordering are outside this task.
