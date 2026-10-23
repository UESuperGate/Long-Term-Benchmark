# Personalized Home feed lifecycle

## Version boundary

Implement the Home feed capability introduced between `r/50586-r-2026-05-12` (`40876929c5a84e1a1f968b29184c245582c7ff9a`) and `r/50590-r-2026-05-28` (`0c4d8a2e33dda8dface830e7ac90d1e923fe7c6e`).

## User outcome

Readers can move from the former Explore experience to a Home feed with Community and For You views, choose and retain what drives their feed, browse in an available Wikipedia language, hide unwanted content, and recover cleanly from empty or failed loads.

## Functional requirements

- New and upgrading readers are guided into the Home experience without unrelated announcements interrupting the flow. A completed choice determines the initial Home view and persists across later visits.
- Home exposes Community and For You tabs. Switching tabs loads that tab when needed without discarding already available content in the other tab.
- Community presents date-grouped editorial modules and can request older content. For You derives recommendation groups from saved interests, reading activity, and saved articles.
- Readers can choose a feed language from their configured app languages. Changing it persists the choice and reloads the active tab for that language; an unavailable stored language falls back to a configured language.
- Readers can select and later edit interests. Finishing an interest update invalidates stale personalized content and refreshes For You.
- Readers can hide an individual card or a whole module. The removal is reflected immediately, module visibility persists, and the immediate undo action restores the removed item.
- Feed settings support independent Community and For You module visibility. If every module for a tab is hidden, that tab shows a purposeful empty state with a route back to module management.
- Pull-to-refresh resets and reloads the active tab. Community load-more requests the next logical day, while For You retains a stable daily result per language until an explicit invalidation or date change.

## Behavioral state transitions

- An unconfigured reader moves from onboarding to a persisted Community or For You choice, then enters the selected Home tab.
- An idle tab moves to loading and then to content or an appropriate empty state; a failed load moves to error and retry returns through loading without skipping the failed page.
- Visible content moves to hidden after a card or module action; immediate undo returns it to its prior visible position, while later recovery remains available through settings.
- Changing language moves the active tab from its current language through refresh to content, empty, or retryable error in the newly selected language.

## Failure and recovery

- An initial service failure produces an error state with retry. A later failure after some content is present preserves that content and exposes an inline retry.
- Retry must request the same logical Community day or For You batch that failed; failed work must not advance pagination.
- A successful retry clears the error and returns to content. A valid response with no usable content produces the appropriate empty state rather than a permanent loading state.
- Missing interests or reading history produces a For You empty state with actions to customize interests or return to Community.
- Hiding content is recoverable through the immediate undo action; module visibility remains recoverable from settings after that action expires.

## Invariants

- At most one initial load or load-more operation runs for a tab at a time.
- Hidden cards and modules do not reappear in subsequent loads until restored.
- Cached personalized content is scoped by date and language.
- Empty, loading, content, and error presentations are mutually coherent for each tab.
- External content and analytics services are leaf boundaries; application-owned state selection, persistence, filtering, retry, and recovery behavior must execute.

## Non-goals

Live Wikimedia availability, recommendation ranking quality, pixel-perfect card rendering, analytics delivery, and changes to article reading, history, saved-page, or notification behavior are outside this task.
