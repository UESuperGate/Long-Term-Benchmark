# Unified media keyboard

## Version boundary

Implement the user-visible media keyboard behavior introduced between Signal Android v8.28.4 (`d0b314d2d7197c38737c6189d1f6c294e76e247e`) and v8.30.0 (`d8d36376f480eb4669efe8bfee94b2c196a9f7bd`).

## User outcome

Conversation participants can use one coherent keyboard surface for emoji, stickers, and GIFs. The keyboard exposes only media types supported by the host, remembers the user's preferred tab while temporary restrictions are active, supports GIF loading and retry, and asks for confirmation before a tapped sticker is sent.

## Functional requirements

- Initialize available tabs from the media repository in stable product order and select a reachable tab.
- Let the host temporarily restrict tabs without forgetting the user's preferred tab; lifting the restriction restores that preference when it remains available.
- Clear a media search query when the user switches tabs.
- Load the first GIF page and append later pages without replacing prior results.
- Represent an initial GIF failure as a recoverable state; retry starts a fresh first-page request and clears the failure after success.
- Tapping a sticker requests confirmation without recording usage or sending it.
- Canceling confirmation sends nothing. Confirming hides the overlay and dispatches the pending sticker exactly once.

## Invariants

- A restriction never exposes a tab the repository did not offer.
- A failed GIF request does not leave loading active or claim more pages are available.
- Pagination preserves previously loaded GIFs and uses their count as the next offset.
- No sticker use or send effect occurs before explicit confirmation.
- Dismissing an already hidden confirmation and sending with no pending sticker are no-ops.

## Failure and recovery

An initial GIF request may fail. The UI must expose a retryable failure state, and a later successful retry must replace it with the returned first page. Sticker confirmation cancellation is a normal recovery path that returns to the conversation without sending.

## Non-goals

Message transport, attachment upload, remote GIF/sticker service behavior, and unrelated conversation layout are outside this task. The ArkTS implementation is a migration target, not the capability being benchmarked.
