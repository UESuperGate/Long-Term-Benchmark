# Android runtime test design

The evaluator installs a real API37 app and instrumentation APK. It seeds production SharedPreferences, launches `BenchmarkActivity`, lets the production page owner establish reading days in SQLite, dispatches the canonical user event, reopens persistence, and retrieves a device-written runtime episode. Case keys and expected values remain evaluator-owned.

The base and final use the same entry surface. Base has ordinary application/deep-link behavior but no account-encouragement feature. Final adds eligibility, two-impression persistence, permanent dismissal, registration completion, account/deep-link/history gating, and corrupt-date fail-closed handling.
