# Runtime failure audit: tasks 08-10

Audited 2026-10-19. Android evidence was read from `_sources/element-x-android` using `git show <commit>:<path>`, not the working checkout. Android tests below were inspected, not executed. Runtime probes used the parent `productionLoader`/`evaluateCase` against original final `.ets` files. Only this note was added; production, contracts, and adapters were not changed in this audit.

| Task / Android final ref | Immutable commit | Finding |
| --- | --- | --- |
| 08 / v25.08.4 | `5048d05e4f912585cd6100b1cbf505eac29d409f` | Migrated reply-target restriction is wrong; adapter also needs to distinguish fixture rejection from send-event failure. |
| 09 / v25.10.0 | `a2ad98c2c6606e4d27f7f53edffd7443b3e91ce3` | Unconditional post-open `childrenState=loading` is not established by Android; contract needs an explicit pending-load boundary. |
| 10 / v25.08.3 | `4c67edf0582ea30b34f5469a6bb84e5617cea76e` | Android explicitly exposes initial loading; migrated synchronous opening collapses that observable phase. No accidental await caused this failure. |

For source paths below, `M` means `features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/`; `S` means `features/space/impl/src/main/kotlin/io/element/android/features/space/impl/`; `R` means `libraries/matrix/impl/src/main/kotlin/io/element/android/libraries/matrix/impl/`. Line numbers refer to the corresponding immutable commit above.

## 08: remote reply

Canonical: `benchmark_tasks/08_threads/transitions.json`, `th_state_005_reply_remote_event` / `reply_remote_event`. Given thread `$root`, reply target `$remote`, text `reply`; event `send_reply`; expected a reply effect retaining both IDs and resetting composer mode.

Android evidence:

- `M/MessagesPresenter.kt:484-499`, `handleActionReply`: requires a remote event ID, calls the current timeline's `loadReplyDetails`, and installs `MessageComposerMode.Reply`. It does not require membership in the visible event list.
- `R/timeline/RustTimeline.kt:562-576`, `loadReplyDetails`: explicitly falls back to `inner.loadReplyDetails(eventId.value)` when the event is absent from `_timelineItems`. `replyMessage` at lines 318-332 forwards the requested event ID to `inner.sendReply`.
- `M/messagecomposer/MessageComposerPresenter.kt:422-469`, `sendMessage`: captures reply mode, resets the composer, and dispatches `replyMessage(repliedToEventId = eventId)` on the current timeline. `M/threads/ThreadedMessagesNode.kt:100-112` supplies that composer with a controller created from `CreateTimelineParams.Threaded(threadRootEventId)`.

Migrated final: `final_dev_nodes/08_threads_final_25_08_4/entry/src/main/ets/features/ThreadFeature.ets:92-95`, `ThreadPresenter.setReplyTarget`, silently rejects IDs not in `threadEvents`. The adapter calls this setter with `$remote`; its **before-event** checkpoint already contains `replyTargetId=null`. `sendMessage` then legitimately emits a normal thread message with gateway arguments `["reply", "$root", ""]`.

Recommendation: fix the migrated selector to resolve/accept valid remote targets independently of visible-window membership, preserving the thread relation. Keep the canonical remote-reply semantics; make remote-detail lookup and send success explicit fixture assumptions. Separately validate the adapter's given state: this run demonstrates a selection/setup defect, not a send regression from an established reply mode. If no production API can establish the given target, report that setup as unsupported; cover remote-target selection as its own transition. Android forwarding does not imply every nonexistent/inaccessible remote ID must succeed.

## 09: Space opening

Canonical: `benchmark_tasks/09_spaces_lifecycle/transitions.json`, `sp_state_001_open_space` / `open_space`. Given joined `!space`, no selection; event opens `!space`; expected Space surface, selected ID, and `childrenState=loading`. No pending request or pagination emission is specified.

Android evidence:

- `S/SpaceFlowNode.kt:54-57`, initialization: binds `spaceService.spaceRoomList(inputs.roomId)`. `S/root/SpacePresenter.kt:56-63`, `present`: starts with empty children, launches pagination, then collects child updates.
- `S/root/SpaceState.kt:19-28` exposes children, current Space, and `hasMoreToLoad`; there is no `childrenState`. `SpacePresenter.present:72-79` maps pagination `Loading` to `hasMoreToLoad=true`, not a separate child-loading field.
- `R/spaces/RustSpaceRoomList.kt:37-42,48-70,74-77`: pagination initially is `Idle(false)` and later follows SDK emissions; `paginate` awaits the inner provider. Opening alone does not guarantee a particular loading emission at the observation boundary.
- `features/home/impl/src/main/kotlin/io/element/android/features/home/impl/spaces/HomeSpacesPresenter.kt:36-45` keeps `CurrentSpace.Root`; selection is not a field mutated in this presenter. The canonical selected ID can describe flow navigation, but should not be attributed to that home state.

Migrated final: `final_dev_nodes/09_spaces_lifecycle_final_25_10_0/entry/src/main/ets/features/SpacesFeature.ets:93-104`, `openSpace`, sets loading, installs fixed children, and sets success before returning. The adapter snapshots immediately after this call, before its separate retention-invariant `loadMore` probe. The captured `success` is real.

Recommendation: repair the contract/projection before using this failure to demand a production change. Separate opening/navigation from loading; define a cold child source with a held request or explicit SDK `Loading` emission, and identify the observation boundary and canonical projection. The migrated fixed-child implementation cannot represent that pending fixture and would need an asynchronous child-source dependency. Do not merely force post-open loading, nor change the expected value universally to success.

## 10: attachment preview loading

Canonical: `benchmark_tasks/10_media_upload_quality/transitions.json`, `mq_state_001_async_loading` / `async_loading`. Given video with unknown upload limit and metadata; event opens preview; expected both loading states, usable preview, and idle send state.

Android evidence:

- `M/attachments/video/DefaultMediaOptimizationSelectorPresenter.kt:62-80`, `present`: `maxUploadSize` and `videoSizeEstimations` use `produceState` with initial `AsyncData.Loading`; estimation waits for a successful limit. Metadata extraction and success occur later at lines 87-117.
- `features/messages/impl/src/test/kotlin/io/element/android/features/messages/impl/attachments/video/DefaultMediaOptimizationSelectorPresenterTest.kt:45-71`, `present - initial state`: explicitly asserts both loading values in the first emission and success after recomposition, even with immediately successful fake dependencies.
- `M/attachments/preview/AttachmentsPreviewPresenter.kt:74-91,188-201` independently initializes idle send state, creates the text editor, and handles cancellation. Lines 97-113 allow background preprocessing when the quality-selector feature is disabled; an idle-while-pending fixture should specify the feature as enabled.

Migrated final: `final_dev_nodes/10_media_upload_quality_final_25_08_3/entry/src/main/ets/features/MediaQualityFeature.ets:105-123,130-137`, `openPreview`/`calculateVideoEstimations`, synchronously fetches a numeric limit and estimates a hard-coded 60-second video. Loading assignments exist internally, but the first state available after opening is already success.

Recommendation: preserve Android's initial loading semantics. Migrate to asynchronous limit/metadata completion with an observable initial state, and explicitly hold those completions in the canonical fixture. The current synchronous adapter supplies a concrete 35,000,000-byte gateway result for a null/unknown limit and has no unresolved-metadata input; record this fixture limitation rather than treating the score alone as proof of all async behavior. Never pass a Promise to the numeric gateway or return an internal loading assignment as a public post-open state. The reentrant caption/cancel probe is only domain reentrancy evidence, not proof of user interaction during a pending native operation.

## Loading-boundary verification

Read-only probes queued a microtask before each production opening, then inspected state immediately and after `await Promise.resolve()`:

| Probe | Microtask ran? | Observed |
| --- | --- | --- |
| Space: immediate `openSpace` return | false | `childrenState=success` |
| Space: after microtask | true | `childrenState=success` |
| Media: inside external `getMaxUploadSize` call | false | limit and estimation `loading` |
| Media: immediate `openPreview` return | false | limit and estimation `success` |
| Media: after microtask | true | limit and estimation `success` |

In `tasks08_11.cjs`, Space snapshots immediately after `p.openSpace`; media's `async_loading` branch executes `open(); observed = snapshot()` without awaiting `finish()`. Its callback-capable binding holds metadata/limit delivery. `await adapter(ctx)` happens after snapshots are copied and cannot advance their contents. Thus neither failure is caused by awaiting an already-resolved opening. Both expose synchronous migration boundaries; only task 10 has direct Android evidence for the canonical initial loading assertion. These probes do not execute Android coroutines, native ArkUI rendering, or device services.
