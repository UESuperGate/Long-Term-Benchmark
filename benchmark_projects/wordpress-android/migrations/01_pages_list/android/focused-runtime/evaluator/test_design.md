# Android focused runtime test design

The evaluator compiles the selected standalone project and captures the `PagesPage -> PagesViewModel -> PagesStore` production instance. Controlled doubles implement only `PagesServiceLeaf`; the page/controller/store and their request mapping, hierarchy, action eligibility, mutation, rollback, and media-resolution bodies remain real.

Each canonical case must record a before frame, the dispatched public page event, held external-leaf requests where asynchronous ordering matters, an after frame, and one independently evaluated row per invariant. The adapter must compare those observations with `canonical/transitions.json`; it may never inspect source text or select a production outcome by case ID.

The completed adapter launches the application-owned `PagesRuntimeOwnerActivity`, dispatches every event through its production ViewModel and repository graph, and observes rows, tabs, menus, mutation rollback, and trash state from that same owner. API 37 calibration is fully scored at base `0/10` and final `10/10`; retained reports include before/event/after frames, controlled-leaf calls, invariant rows, and APK hashes. A random-directory no-change control remains mandatory before publishing an agent score.
