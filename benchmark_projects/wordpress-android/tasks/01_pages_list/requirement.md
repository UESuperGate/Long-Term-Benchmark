# Modern pages list lifecycle and actions

## Version boundary

Implement the pages-list capability introduced between WordPress Android 26.8 (`20d41cdcd693e381a8c823ec2c93fc39efc9cf0c`) and 26.9 (`510f1cddc186a486ffa9559018578a644d303d96`). The official tags are release-branch snapshots rather than a locally provable ancestor chain; the 26.8 tree has been directly verified not to contain the target pages-list package or routing symbols.

## User outcome

Eligible users can opt into a modern pages screen that exposes Published, Drafts, Scheduled, and Trashed pages, remains useful across loading and network failures, and supports the everyday find, organize, create, and page-action workflows expected from the existing Pages entry point.

## Functional requirements

- Open the modern pages screen through the normal Pages entry and load pages through the application-owned pages service path. Published and draft-like tabs are title-ascending, Scheduled is date-ascending, and each request uses a page size of 20.
- Preserve loaded rows during a refresh failure, show a retry affordance for recoverable failures, and replace the stale state after a successful retry.
- Enter search mode immediately. Queries shorter than three characters keep the result area empty and do not dispatch a search. Queries of at least three characters dispatch once after a 250 ms debounce and search across all page statuses. Closing search immediately restores the active tab.
- Offer an Everyone/Me author filter only for eligible multi-author sites. Persist the selection and reload with the signed-in author identifier when Me is selected.
- Render the Published tab as a depth-first hierarchy. Promote missing-parent pages to roots, cap visual indentation at three levels, and keep other tabs and search results flat.
- Expose actions according to page status and eligibility. A homepage cannot be moved to draft, moved to trash, or set as homepage again; a trashed page exposes only restore-to-draft and permanent delete.
- Require confirmation before destructive or status-changing actions. A successful trash operation updates the list through the production store and shows success feedback. A failed operation preserves the page and can be retried without recreating the screen.
- Resolve and render featured-image thumbnails without removing the page row while media is loading or unavailable.

## Failure and recovery

Network and service failures must be represented as state, not as an empty success. Existing data remains visible on refresh failures. Retry executes the same application-owned request or mutation body against a controlled external leaf. Search teardown cancels stale work so late failures cannot overwrite a newer query or tab state.

## Invariants

- Requests and mutations always target pages, never posts.
- Search and filter changes close obsolete collections before opening replacements.
- A failed destructive action never removes or changes the page locally.
- Page identity, unrelated tabs, and unaffected preferences remain unchanged.
- Evaluator adapters may control only the external service/media leaves; they must execute the application-owned page, view-model, store, mapping, and mutation bodies.

## Non-goals

The task does not change the editor, reproduce live WordPress.com services, require a specific implementation class name, or score pixel-level rendering. The ArkTS project is a functional migration target and is not itself the capability under test.
