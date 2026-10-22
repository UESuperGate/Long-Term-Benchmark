# Task14 Original Device UI

Status: implementation and ten local tests ready for parent build/device
verification. No Task14 native import/render/click result is claimed. Task11
post-load success is a transport precedent, not Task14 evidence. No shared
adapter, shared platform, shared packager, production or canonical file changed.

## Parent Integration

For the task14 `--fixture bundle --native-ui` disposable workspace, immediately
after the existing bundle generator and before generated evaluator hashes:

```js
report.task14DeviceUI = require(path.join(root,
  'state_tests/runtime/arkts/native/Task14DeviceUi.install.cjs')).install(work);
```

Use `TASK14_ORIGINAL_MODULE_IMPORT=after-page-ready` for an explicitly opted-in
build, or pass `{ mode: 'after-page-ready' }` to this installer. Default is
`disabled`; it returns NS without starting/importing. Install only this Task14
companion for this candidate, not the task12 companion. No adapterFactory
registration is needed. The installer changes only generated `entry/src/test`:

- Adds suite configuration using manifest-derived bundle/module/ability/routes
  and original production OHM URLs. Copies six independent Task14 modules.
- Attaches `bridge.evaluateTask14UI(args)` for cases001/003/007 only and skips
  the stale pre-start `bridge.ui.navigate` for those cases.
- Changes the generated runtime adapter dispatch to
  `(bridge.evaluateTask14UI || module.exports.runCase)(args)`. The shared
  `tasks12_15.cjs`, factories, comparator and row persistence are untouched.
- Preserves `args.load` for source provenance only, without constructing or
  invoking its bundled exports. Actual state always comes from the original
  app class imported AFTER positive original-page evidence. All actual native
  observations use the existing observation recorder; trace receives before/
  event/after checkpoints. Per-case ID and digest are retained and checked.
- Hashes original production bytes before/after and generated module contents.
  Capture parent generatedEvaluator hashes after this installer.

If the parent prefers a shared adapter early branch later, the equivalent is
`return await native.evaluateTask14UI(args)` when that function is attached.
Do not add a CJS require for these files to the three embedded adapterFactories.
The generated branch already performs this dispatch; do not dispatch twice.

## Original Lifecycle

One fresh process/case. Register actual AbilityMonitor and ApplicationContext
ability lifecycle callbacks before starting the unchanged EntryAbility. Require
cold creation, foreground/top ability, actual WindowStage main-window identity,
matching getLastWindow ID, exact host identity, focused Driver bundle and exact
window geometry. Read the original route and inspector inside the UIContext's
scoped task. No numeric WindowType fallback, replacement page or router push.

Require actual Start-a-chat title/search and join entry before importing. For
final, the original Index imports the presenter, so entry case001 can bind after
the initial page loads and before its real click. For separate-page candidates,
003/007 first click the real entry, verify the actual form, then import the
presenter. A separate-page entry case001 is explicitly NS: importing before the
feature is loaded risks the known native fatal, while editing after entry could
overwrite canonical post-state. No test-module class fallback is accepted.

`Task14PageObserver` wraps the actual imported prototype with return/throw/
Promise identity preserved. It never constructs a presenter and never calls
methods/getters to obtain a receiver. State reads require original page calls;
the naturally invoked visibleAddressState projection is retained, not invoked
by the evaluator. Require one receiver and stable window throughout the event.

Controls combine real Driver presence/bounds/text/focus/enabled/clickability
with original scoped inspector visibility/opacity. Null/undefined queries are
empty, not positive. Inspector-only presence and absent opacity remain unknown.
The full inspector tree is stored once per frame, not duplicated under another
property; recorder/checkpoint summaries reference the frame label. No claim of
pixel occlusion detection is made.

## Canonical Scope

- 001: verify original start-chat and inactive search, bind original class,
  physically click join, observe actual form/address/state. Return through real
  Cancel/Dismiss for the existing create/people-action invariant. Never equate
  a search widget or Invite-friends button with a direct-message action.
- 003: real input of given address; wait for original internal invalid state,
  verify validationRequested=false and pre-Continue error suppression. Real
  Continue click, original callback, actual error visibility and navigator count.
- 007: bind ONLY the external DemoRoomAliasResolver/HttpRoomAliasResolver
  request boundary to a pending Promise. Input the given alias, then real
  Continue while pending establishes visible resolving, matching Android's
  rendered fixture. Check same-page resolver identity, alias and exactly one
  pending request. Reject that external response; production continuations
  mutate state. Observe real error/editor, actual navigation count and flow
  retention. Supplemental real retry input confirms editing, but does not alter
  the already captured canonical post-state. No presenter assignment/reset.

Other cases remain on their existing adapter. Missing actual navigator count in
an alternate API remains NS, never inferred from an unchanged route or pending
intent. Missing initial entry API is NS rather than a synthetic baseline fail.
Default unsupported mode and failed prerequisite checks cannot manufacture PASS.

## Audit

Immutable Android `v25.03.0^{commit}` resolves to
`18b9593c147141974c542b6c06a33e770f01886a`. Read with `git show` from
`_sources/element-x-android`:

- `features/createroom/impl/src/main/kotlin/io/element/android/features/createroom/impl/root/CreateRoomRootView.kt`:
  UserListView retains StartDM and CreateRoomActionButtonsList retains new-room
  and existing DM callbacks when search is inactive. The contract's retained
  actions are supported; it does not require simultaneous modal/root visibility.
- `features/createroom/impl/src/main/kotlin/io/element/android/features/createroom/impl/joinbyaddress/JoinRoomByAddressPresenter.kt`:
  visible state is Unknown before Continue unless RoomFound. Therefore 007's
  visible-resolving given requires real Continue setup; the local original
  Android rendered fixture does this in `resolving()` as well. We do not press
  Continue after the canonical failure to force error visibility.

Potential genuine migrated mismatch, not an assertion correction: final
`final_dev_nodes/14_join_room_by_address_final_25_03_0/entry/src/main/ets/pages/Index.ets`
has a Search-people input but no people list or DM action. The original base
Index has Alice/Bob/Charlie selection rows; the archived agent retains them.
The independent suite retains a false availability invariant if the actual
final start-chat tree lacks those known actions. A visible but non-clickable
person label is unsupported pending an actual ancestor action binding, not
counted as an available DM action. No contract weakening or production repair.

Local command:

```sh
node --test state_tests/runtime/arkts/native/Task14DeviceUi.test.cjs
```

Ten tests pass: original observer identity/return/throw restoration, real
transpiled final production plus explicit OS doubles for all three cases,
negative givens/error visibility, deferred import guard, immutable installation,
Stage ownership, real input dispatch, null query/opacity handling, and disabled
mode. These are evaluator/unit tests, not native results. Parent owns device
execution and the first Task14 build. Native ABI or inspector gaps remain NS.
