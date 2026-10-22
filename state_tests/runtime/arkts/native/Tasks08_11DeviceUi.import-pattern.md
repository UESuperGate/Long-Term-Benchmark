# Original App Variable Import Pattern

For parent relay to tasks12/18. This is a task11-verified sequence, not evidence
that another candidate or device supports it. No shared implementation is
installed by this note. Default off; pre-start import is prohibited.

1. Register actual lifecycle monitors, then cold-start the unchanged original
   EntryAbility. Require original Stage main-window ownership, matching host
   identity, focused Driver window, route, full tree and real page anchor.
2. Only after original page readiness, use the manifest-derived ORIGINAL app
   module URL with standard JS variable dynamic import, not a test relative
   import or `entry_test@entry` record. Example transport pattern:

```js
const importOriginal = url => import(url);
const url = '@bundle:' + bundleName + '/' + originalModuleName +
  '/ets/features/' + originalFeatureName;
const namespace = await importOriginal(url);
const Presenter = namespace[actualExportName];
const descriptors = Object.getOwnPropertyDescriptors(Presenter.prototype);
const observer = installPassThroughObserver(Presenter);
```

The names above are integration placeholders, not supplied helper APIs.
Validate URL/export against the candidate, and audit compiled OHM records and
generated evaluator hashes. Record URL, exports, before/after descriptors and
actually changed wrapper names. Do not instantiate a presenter or call a
getter/business method to manufacture a receiver.

3. Through a real original UI control, perform an allowed setup action that
   naturally invokes the instrumented class. Require an observed receiver,
   original callback calls and agreement with actual rendered state. Import
   completion alone does not establish module identity. Preserve exact return
   values, Promise identity, exceptions and state mutation behavior.
4. Run the task's own canonical given checks, event and invariants afterward.
   Setup/callback delivery is not a navigation success or a semantic verdict.
   Restore wrappers during disposal; one fresh process per canonical case.

Task11 evidence and limitations are in `Tasks08_11DeviceUi.audit.md`.
The earlier pre-start attempt fatally resolved `entry.hsp`. Post-load success
is consistent with the ABC filename cache being populated, but cache residency
is not directly observable and cross-HAP support in general is NOT proved.
JS try/catch cannot contain native SIGABRT; keep any new task experiment bounded
and explicit opt-in. Never fall back to duplicated test-side production classes
as though they were the original page receiver.
