# Saved articles and collections workflow

## Version boundary

Implement the collections-based Saved experience introduced between `r/50600-r-2026-07-28` (`8b7427f178b619aeb585fbcbb8a02e5ea0f0b68c`) and `r/50603-r-2026-08-25` (`12d1dd2bffea3db7ead5a69b2025bcbf287fe64d`).

## User outcome

Readers can see every saved article in one place, organize articles into named collections, search and manage each view independently, save or unsave from any article entry point, and recover from destructive actions, offline metadata lookup, account limitations, and sync interruptions.

## Functional requirements

- Saved provides All articles and Collections tabs. All articles shows each logical saved article once even when it belongs to several collections, while Collections shows user-created collections and excludes the default Saved collection.
- Switching tabs changes the visible rows, search scope, sort choices, menu actions, empty state, and onboarding content without losing the underlying saved data.
- Search is debounced and applies only to the active tab. All articles additionally supports filtering to articles that are only in the default Saved collection. Sorting persists independently for article and collection views.
- Collection and article data react to database changes without requiring a manual page rebuild. Offline availability and active download progress are reflected for visible articles.
- Readers can enter selection mode for the active tab, select one, many, or all visible rows, and run the actions valid for that row type. The default Saved collection remains protected from deletion.
- Opening Save for an article ensures it is saved, then presents its current collection membership. Readers can create a collection, add or remove the article from collections, or unsave it.
- Removing an article that belongs to user-created collections requires confirmation before all memberships are removed. Removing an article held only by the default Saved collection may complete directly.
- Collection and per-collection article limits block the requested addition, report the reason, and leave existing memberships unchanged.
- Pull-to-refresh initiates collection synchronization for an eligible signed-in account. The refreshing state ends when synchronization reports completion.
- Login, logout, shared-collection receipt, and sync preference changes update the visible onboarding, badge, and feedback state.

## Behavioral state transitions

- Saved opens in All articles; selecting Collections changes the row model and available actions, and selecting All articles returns to the deduplicated article view.
- An absent article moves to saved in the default collection, can then gain or lose named-collection memberships, and reaches unsaved only after the required confirmation when named memberships exist.
- Idle sync moves to refreshing; an ineligible account returns to idle with a login prompt, while an eligible account returns to idle after the sync completion event.
- Visible rows move into selection, then pending deletion, then either deleted or restored through undo without changing unrelated rows.

## Failure and recovery

- If redirect metadata cannot be resolved because the device is offline or the request fails, saving proceeds with the original article identity.
- A signed-out or temporary-account refresh prompts for login and immediately clears the refresh state. After login, a new refresh can initiate synchronization.
- Deleting collections or saved articles supports recovery through undo where offered. Cancelling an unsave confirmation leaves all memberships intact.
- Empty search results, an empty All articles view, and an empty Collections view are distinct from loading and expose context-appropriate recovery actions.
- When a requested collection no longer exists, the operation exits without mutating another collection.

## Invariants

- All articles deduplicates by wiki language and article identity while retaining the set of containing collections.
- Search, filter, and sort alter presentation only; they do not change membership.
- The default Saved collection is not shown as a user-created collection and cannot be deleted.
- Rows queued for deletion are not rendered as active memberships.
- External HTTP, sync, analytics, and file services are leaf boundaries; application-owned state reduction, persistence, selection, confirmation, limit handling, and recovery behavior must execute.

## Non-goals

Server-side sync implementation, import/export file formats, ranking of recommended collections, pixel-perfect Compose rendering, and unrelated article rendering are outside this task.
