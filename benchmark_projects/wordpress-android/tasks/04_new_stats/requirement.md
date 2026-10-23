# Interactive and Resilient New Stats

## Version boundary

- Base: WordPress for Android `27.1` (`52d78ca3a60d3ae77fce80a304416eae65f68523`)
- Final: WordPress for Android `27.6` (`e6dbc793f2256380cd7ab3c9210aae0cdd07710b`)

## User outcome

Make New Stats useful for comparative exploration across metrics and time. Users can choose what the chart represents, inspect individual buckets, move through coherent date periods, revisit recently viewed data without unnecessary waiting, and understand whether unavailable content is recoverable, unsupported, or restricted by plan.

## Functional requirements

1. The chart offers the supported metrics for the current context. Selecting another metric updates the chart and related totals from already available period data without an avoidable reload, and the preference is retained when the user returns to a compatible period.
2. When a single-day hourly chart cannot represent the preferred metric, it falls back to a supported metric without discarding the preference. Explicitly choosing an unsupported metric shows an unavailable state; moving back to a compatible period restores normal metric use.
3. Tapping a chart bucket soft-selects it: the selected bucket becomes distinguishable and the visible summary reflects that bucket. Tapping it again clears the selection, tapping another bucket moves it, and invoking the available drill-down action commits navigation to the corresponding narrower period.
4. Future or otherwise non-actionable chart buckets do not create a selection. A committed period change, chart-shape change, reload, or refresh clears any stale soft selection.
5. Period choices distinguish rolling windows from calendar periods. Paging backward and forward preserves the selected period's meaning, including after state restoration, and forward navigation stops at the present boundary.
6. Calendar periods use a consistent whole-period window across chart and supporting lists. The current period may show future buckets as empty placeholders, but those buckets are not interactive.
7. Revisiting a recently viewed period can show cached content immediately. Entering the screen may refresh cached content in the background; a failed background refresh keeps the usable cached result, while a successful refresh replaces it.
8. Pull-to-refresh requests fresh data rather than presenting the old cached result as final. Data that began loading before that refresh must not later overwrite the refreshed state.
9. Offline or ordinary load failures expose a retry path. Retrying after connectivity or service recovery reloads the affected content and returns it to the normal loaded state.
10. Plan-restricted data is presented as a plan-gated state with an appropriate plan action, not as a generic permission failure or ordinary retry. Moving to an unrestricted metric or card recovers normal stats interaction.

## Required state transitions

- Loaded metric -> alternate metric -> hourly fallback or explicit unavailable state -> restored preferred metric on a compatible period.
- Unselected chart -> soft-selected bucket -> moved or cleared selection -> committed drill-down period.
- Chosen rolling or calendar period -> previous/next period -> restored state with the same period semantics.
- Fresh data -> cached revisit -> background refresh failure with cached data preserved -> successful refresh with replacement data.
- Loading or failed content -> retrying -> loaded content, and eligible restricted content -> plan-gated presentation -> unrestricted content.

## Failure and recovery

- A background refresh failure must not erase usable cached data or replace it with a full blocking error.
- A foreground load failure must stop loading and expose a retry that can recover after the underlying failure is resolved.
- Pull-to-refresh must establish a new refresh boundary so older in-flight results cannot repopulate stale state afterward.
- Plan-gated responses must remain distinguishable from transient failures; only transient failures use ordinary retry behavior.

## Invariants

- Metric choice, chart selection, period choice, and loaded data remain mutually coherent.
- Rolling and calendar periods do not silently change meaning while paging or restoring state.
- Cache reuse never crosses site, period, date-window, or request-variant boundaries.
- Failure recovery does not discard still-valid user choices unless the destination context cannot support them.
- The task is defined by observable behavior, not by internal cache structure, UI class names, analytics payloads, or exact view identifiers.

## Non-goals

- The Latest Post Summary and per-post detail feature that landed in the same release interval.
- Exact analytics instrumentation or event payload validation.
- A prescribed charting library, cache implementation, capacity, or application architecture.
