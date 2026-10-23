# Android runtime design

The API 37 instrumentation episode strongly links one `HybridSearchPageActionPrefix`. Setup and event calls use that surviving application-owned page owner, which owns the production `SearchResultsViewModel`. Enable and retry are executed only in the event phase; the evaluator never calls the view model directly.

The owner exposes rendered mode, phase, sections, notices, retry availability, and result titles from production state. Controlled HTTP leaves retain raw operation, channel-status, and attempt logs; feedback and standard-search effects are recorded only at their external leaf interfaces. SharedPreferences is committed synchronously and reopened at observation boundaries.

The base owner has the same ABI but only the pre-feature standard-search behavior. There is no source/method-presence verdict or detached presenter. Formal calibration requires API 37 base 0/10 and final 10/10 with zero unscored cases. Raw device episodes are retained beside each scored report.

The visible scaffold only declares an empty `src/main/java` candidate root; it never copies, replaces, or removes production sources. Hidden assembly follows the candidate's declared `main` Kotlin roots and copies only compiled production `.kt`/`.java` inputs, excluding evaluator, leaf, and test roots. The untouched clean-room base must therefore compile through both stages and fail semantically at 0/10 with zero unscored cases.
