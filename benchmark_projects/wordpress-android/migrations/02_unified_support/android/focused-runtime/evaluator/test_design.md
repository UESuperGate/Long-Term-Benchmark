# Android focused runtime test design

The evaluator compiles the selected standalone project and captures the `UnifiedSupportPage -> UnifiedSupportViewModel -> UnifiedSupportRepository -> UnifiedSupportStore` production instance. Controlled doubles implement only network availability, WordPress support service responses, encrypted-log upload, and temporary-file I/O. Optimistic updates, request mapping, rollback, list replacement, reply form ownership, conversation switching, and cleanup stay in production.

Every canonical case must include before/event/pending/settled frames as applicable, exact service-leaf arguments, original application-owned body invocation evidence, and one observed check per invariant. The adapter may never read source text or feed canonical expected values into production.

The completed adapter launches the application-owned `SupportRuntimeOwnerActivity`, retains the production ViewModel across a real `Activity.recreate()`, and observes detail affordances from the API 37 accessibility tree. Held completions, ordered leaf effects, cleanup, optimistic rollback, and owner replacement are recorded in the runtime episodes. Calibration is fully scored at base `0/10` and final `10/10`; a random-directory no-change control remains mandatory before publishing an agent score.
