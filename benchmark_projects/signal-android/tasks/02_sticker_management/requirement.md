# Sticker management

## Version boundary

Implement the sticker-management behavior introduced between Signal Android v7.40.2 (`556bcda58ae65abbba75bf899a43666ba6d9d427`) and v7.43.1 (`23669c3c372284d42db486a218d9f29bef247abf`).

## User outcome

Users can browse available and installed sticker packs in separate tabs, install packs with visible progress, reorder installed packs, and safely remove one or several selected packs.

## Functional requirements

- Classify repository records into installed, official available, and other available groups while preserving repository order.
- Installing a pack progresses through in-progress and completed states, invokes the real application repository body, and shows a completion confirmation.
- Keep a just-installed pack visible in its completed state briefly, then clear the transient download status so repository classification can settle.
- Reordering changes the visible installed-pack order immediately; dropping persists exactly that order.
- Selecting an installed pack enters multi-select mode. Select-all toggles between every installed pack and none.
- A multi-delete request with a non-empty selection opens a count-bearing confirmation without uninstalling anything.
- Canceling deletion clears the prompt and preserves selection. Confirming deletion invokes the repository once for the selected set, removes those IDs from selection, and reports the number removed.

## Invariants

- A pack cannot appear in both installed and available groups.
- Installing one pack does not reorder unrelated packs.
- Installation still executes the application-owned repository body; database/download/linked-device services may be controlled only at their leaf interfaces.
- Reordering never changes pack identity or membership.
- No uninstall effect occurs before confirmation in multi-select mode.
- Canceling deletion preserves both installed packs and the user's current selection.

## Failure and recovery

Deletion cancellation is an explicit recovery path: the confirmation closes with no database or linked-device effect, and the selection remains available for a later action.

## Non-goals

Sticker authoring, sticker search, download transport internals, and unrelated chat features are outside this task. The ArkTS implementation is a migration target, not the benchmarked capability.
