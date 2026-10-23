# Concurrent hybrid lexical and semantic search

## Version boundary

Implement the hybrid search capability between `r/50566-r-2026-02-04` (`6a085362ecf74ff69a3abf689038ba2882976c07`) and `r/50574-r-2026-03-20` (`2c086856d4840f854fb9fb456ae3b4db055f1183`). The release tags have a documented branch divergence; the target feature commit `af457ff7ae17cf2acdd14da991abe76e032fc28f` is absent from the base side and contained by the final side.

## User outcome

Eligible readers can opt into hybrid search and receive lexical and semantic results from one query. The page remains useful when one source fails, explains empty source groups, supports retry after complete failure, records semantic feedback, and allows opt-out back to standard search.

## Functional requirements

- Gate hybrid search by experiment assignment, persisted opt-in, and supported language.
- On a non-empty eligible query, enter loading and start lexical and semantic HTTP requests concurrently.
- The lexical application body performs prefix search first and fills remaining capacity with full-text results, removing duplicate lexical titles.
- The semantic application body maps semantic responses into semantic result cards and preserves section/snippet information.
- Merge successful source results without discarding a surviving source when the other fails. Both failures produce an error with a reachable retry action.
- Render lexical and semantic groups in the experiment-defined order and expose an empty-source notice when only one group has results.
- Retry re-executes both source requests through the same production view model.
- Rating a semantic result executes the page-owned feedback mapping with query, one-based position, target title, and positive/negative choice.
- Opting out persists the preference, leaves hybrid mode, and returns the current query to standard search.

## External boundaries

Lexical and semantic HTTP transports are controlled external leaves. The application-owned concurrency, prefix/full-text fallback, mapping, deduplication, merge, page state, retry, opt-out, and feedback body must execute unmocked.

## Failure and recovery

One failed source falls back to the other source. Two failed sources enter an error state. Retry after the leaves recover must reach a success state without recreating a disposed page.

## Non-goals

Live HTTP availability, ranking quality, unrelated standard-search pagination, and pixel-perfect Compose rendering are outside this task.
