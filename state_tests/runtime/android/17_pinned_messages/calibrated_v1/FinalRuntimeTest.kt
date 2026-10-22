package runtime

import android.content.Context
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateOf
import io.element.android.features.messages.impl.UserEventPermissions
import io.element.android.features.messages.impl.actionlist.*
import io.element.android.features.messages.impl.actionlist.model.TimelineItemAction
import io.element.android.features.messages.impl.actionlist.model.TimelineItemActionPostProcessor
import io.element.android.features.messages.impl.pinned.DefaultIsPinnedMessagesFeatureEnabled
import io.element.android.features.messages.impl.pinned.PinnedEventsTimelineProvider
import io.element.android.features.messages.impl.pinned.list.*
import io.element.android.features.messages.impl.timeline.factories.TimelineItemsFactory
import io.element.android.features.messages.impl.timeline.model.TimelineItem
import io.element.android.features.networkmonitor.api.NetworkMonitor
import io.element.android.features.networkmonitor.api.NetworkStatus
import io.element.android.libraries.architecture.AsyncData
import io.element.android.libraries.core.coroutine.CoroutineDispatchers
import io.element.android.libraries.designsystem.utils.snackbar.SnackbarDispatcher
import io.element.android.libraries.featureflag.api.FeatureFlagService
import io.element.android.libraries.matrix.api.MatrixClient
import io.element.android.libraries.matrix.api.core.*
import io.element.android.libraries.matrix.api.room.*
import io.element.android.libraries.matrix.api.timeline.*
import io.element.android.libraries.matrix.api.timeline.item.TimelineItemDebugInfo
import io.element.android.libraries.matrix.api.timeline.item.event.*
import io.element.android.libraries.preferences.api.store.AppPreferencesStore
import kotlinx.collections.immutable.persistentListOf
import kotlinx.collections.immutable.persistentMapOf
import kotlinx.collections.immutable.toPersistentList
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import runtime.foundation.EvidenceRobolectricRunner
import java.io.File
import java.lang.reflect.Proxy
import kotlin.coroutines.Continuation
import kotlin.coroutines.intrinsics.COROUTINE_SUSPENDED

@RunWith(EvidenceRobolectricRunner::class)
@Config(sdk = [36])
@OptIn(ExperimentalCoroutinesApi::class)
class FinalRuntimeTest {
    private data class Scenario(
        val driver: CompositionDriver<PinnedMessagesListState>,
        val scope: TestScope,
        val sdkItems: MutableStateFlow<List<MatrixTimelineItem>>,
        val calls: MutableList<Map<String, Any?>>,
        val navigations: MutableList<String>,
        val snackbar: SnackbarDispatcher,
        val setUnpinFailure: (Boolean) -> Unit,
    ) : AutoCloseable {
        override fun close() = driver.close()
    }

    private fun port(type: Class<*>, calls: MutableList<Map<String, Any?>>, block: (String, Array<out Any?>) -> Any?): Any =
        Proxy.newProxyInstance(type.classLoader, arrayOf(type)) { proxy, method, args ->
            when (method.name) {
                "equals" -> proxy === args?.firstOrNull()
                "hashCode" -> System.identityHashCode(proxy)
                "toString" -> "ControlledBoundary:${type.simpleName}"
                else -> {
                    val actual = args ?: emptyArray()
                    calls += mapOf(
                        "port" to type.name,
                        "method" to method.name.substringBefore('-'),
                        "args" to actual.filterNot { it is Continuation<*> }.map { it.toString() },
                    )
                    block(method.name.substringBefore('-'), actual)
                }
            }
        }

    private fun construct(
        type: Class<*>,
        context: Context,
        dispatchers: CoroutineDispatchers,
        calls: MutableList<Map<String, Any?>>,
    ): Any {
        if (type == Context::class.java) return context
        if (type == CoroutineDispatchers::class.java) return dispatchers
        if (type == MatrixClient::class.java) {
            return port(type, calls) { name, _ ->
                when (name) {
                    "getSessionId" -> "@runtime:example.org"
                    else -> error("Unexpected MatrixClient.$name")
                }
            }
        }
        if (type.isInterface) return port(type, calls) { name, _ -> error("Unexpected ${type.name}.$name") }
        check(type.name.startsWith("io.element.android.")) { "Unreviewed constructor ${type.name}" }
        val constructors = type.constructors.filterNot { it.isSynthetic }
        val constructor = constructors.singleOrNull { it.getAnnotation(javax.inject.Inject::class.java) != null }
            ?: constructors.single()
        return constructor.newInstance(*constructor.parameterTypes.map { construct(it, context, dispatchers, calls) }.toTypedArray())
    }

    private fun event(id: String, body: String): MatrixTimelineItem.Event {
        val eventId = EventId(id)
        return MatrixTimelineItem.Event(
            uniqueId = UniqueId("unique-$id"),
            event = EventTimelineItem(
                eventId = eventId,
                transactionId = null,
                isEditable = false,
                canBeRepliedTo = false,
                isLocal = false,
                isOwn = false,
                isRemote = true,
                localSendState = null,
                reactions = persistentListOf(),
                receipts = persistentListOf(),
                sender = UserId("@sender:example.org"),
                senderProfile = ProfileTimelineDetails.Ready(body, false, null),
                timestamp = if (id == "\$a") 1L else 2L,
                content = UnknownContent,
                debugInfo = TimelineItemDebugInfo("runtime-$body", null, null),
                origin = null,
                messageShield = null,
            ),
        )
    }

    private fun failureValue(error: Throwable): Any? {
        val boxed: Any = Result.failure<Boolean>(error)
        val unbox = boxed.javaClass.declaredMethods.single { it.name == "unbox-impl" }
        unbox.isAccessible = true
        return unbox.invoke(boxed)
    }

    private fun TestScope.scenario(
        initial: List<MatrixTimelineItem> = listOf(event("\$b", "Beta"), event("\$a", "Alpha")),
        canPinUnpin: Boolean = true,
        heldOpen: Boolean = false,
        openFailure: Boolean = false,
    ): Scenario {
        val calls = mutableListOf<Map<String, Any?>>()
        val sdkItems = MutableStateFlow(initial)
        var failUnpin = false
        var held: Continuation<Any?>? = null
        val timeline = port(Timeline::class.java, calls) { name, args ->
            when (name) {
                "getTimelineItems" -> sdkItems
                "unpinEvent" -> {
                    val id = when (val raw = args.first()) {
                        is EventId -> raw
                        is String -> EventId(raw)
                        else -> error("Unexpected unpin event-id ABI: ${raw?.javaClass}")
                    }
                    if (failUnpin) failureValue(IllegalStateException("controlled unpin failure"))
                    else {
                        sdkItems.value = sdkItems.value.filterNot { (it as? MatrixTimelineItem.Event)?.eventId == id }
                        true
                    }
                }
                "close" -> Unit
                else -> error("Unexpected Timeline.$name")
            }
        } as Timeline
        val info = MutableStateFlow(
            MatrixRoomInfo(
                id = RoomId("!runtime:example.org"), name = "Pinned runtime", rawName = "Pinned runtime",
                topic = null, avatarUrl = null, isPublic = false, isDirect = false, isSpace = false,
                isTombstoned = false, isFavorite = false, canonicalAlias = null, alternativeAliases = persistentListOf(),
                currentUserMembership = CurrentUserMembership.JOINED, inviter = null, activeMembersCount = 3,
                invitedMembersCount = 0, joinedMembersCount = 3, userPowerLevels = persistentMapOf(),
                highlightCount = 0, notificationCount = 0, userDefinedNotificationMode = null,
                hasRoomCall = false, activeRoomCallParticipants = persistentListOf(), heroes = persistentListOf(),
                pinnedEventIds = initial.mapNotNull { (it as? MatrixTimelineItem.Event)?.eventId }.toPersistentList(),
            )
        )
        val members = MutableStateFlow<MatrixRoomMembersState>(MatrixRoomMembersState.Unknown)
        val sync = MutableStateFlow(0L)
        val room = port(MatrixRoom::class.java, calls) { name, args ->
            when (name) {
                "pinnedEventsTimeline" -> when {
                    heldOpen -> {
                        @Suppress("UNCHECKED_CAST")
                        held = args.last() as Continuation<Any?>
                        COROUTINE_SUSPENDED
                    }
                    openFailure -> failureValue(IllegalStateException("controlled open failure"))
                    else -> timeline
                }
                "getRoomInfoFlow" -> info
                "getMembersStateFlow" -> members
                "getSyncUpdateFlow" -> sync
                "getDisplayName" -> "Pinned runtime"
                "getActiveMemberCount" -> 3L
                "isDirect", "getIsDirect" -> false
                "canUserRedactOwn", "canUserRedactOther" -> false
                "canUserPinUnpin" -> canPinUnpin
                "getSessionId" -> "@runtime:example.org"
                "getRoomId" -> "!runtime:example.org"
                else -> error("Unexpected MatrixRoom.$name")
            }
        } as MatrixRoom
        val flags = port(FeatureFlagService::class.java, calls) { name, _ ->
            when (name) {
                "isFeatureEnabledFlow" -> MutableStateFlow(true)
                "isFeatureEnabled" -> true
                else -> error("Unexpected FeatureFlagService.$name")
            }
        } as FeatureFlagService
        val network = object : NetworkMonitor { override val connectivity = MutableStateFlow(NetworkStatus.Online) }
        val context = RuntimeEnvironment.getApplication() as Context
        val dispatchers = CoroutineDispatchers(StandardTestDispatcher(testScheduler), StandardTestDispatcher(testScheduler), StandardTestDispatcher(testScheduler))
        val factory = construct(TimelineItemsFactory::class.java, context, dispatchers, calls) as TimelineItemsFactory
        val preferences = port(AppPreferencesStore::class.java, calls) { name, _ ->
            when (name) {
                "isDeveloperModeEnabledFlow" -> flowOf(false)
                else -> error("Unexpected AppPreferencesStore.$name")
            }
        } as AppPreferencesStore
        val enabled = DefaultIsPinnedMessagesFeatureEnabled(flags)
        val actionFactory = object : ActionListPresenter.Factory {
            override fun create(postProcessor: TimelineItemActionPostProcessor): ActionListPresenter =
                DefaultActionListPresenter(postProcessor, preferences, enabled, room)
        }
        val navigations = mutableListOf<String>()
        val navigator = object : PinnedMessagesListNavigator {
            override fun onViewInTimelineClick(eventId: EventId) { navigations += eventId.value }
            override fun onShowEventDebugInfoClick(eventId: EventId?, debugInfo: TimelineItemDebugInfo) = error("Unexpected debug navigation")
            override fun onForwardEventClick(eventId: EventId) = error("Unexpected forward navigation")
        }
        val provider = PinnedEventsTimelineProvider(room, network, flags)
        provider.launchIn(backgroundScope)
        val snackbar = SnackbarDispatcher()
        val presenter = PinnedMessagesListPresenter(navigator, room, factory, provider, snackbar, actionFactory)
        val driver = CompositionDriver(this) { presenter.present() }
        if (heldOpen) {
            driver.flush()
            checkNotNull(held)
        } else {
            driver.advance(400)
        }
        return Scenario(driver, this, sdkItems, calls, navigations, snackbar, { failUnpin = it })
    }

    private fun PinnedMessagesListState.Filled.ids(): List<String> =
        timelineItems.filterIsInstance<TimelineItem.Event>().mapNotNull { it.eventId?.value }

    private fun PinnedMessagesListState.Filled.actionsForFirst(driver: CompositionDriver<PinnedMessagesListState>): List<TimelineItemAction> {
        actionListState.eventSink(ActionListEvents.ComputeForMessage(timelineItems.filterIsInstance<TimelineItem.Event>().first(), userEventPermissions))
        driver.flush()
        return ((driver.state as PinnedMessagesListState.Filled).actionListState.target as ActionListState.Target.Success).actions
    }

    @Test fun open_loading() = runTest {
        scenario(heldOpen = true).use { s ->
            assertSame(PinnedMessagesListState.Loading, s.driver.state)
            val openCalls = s.calls.count { it["port"].toString().endsWith("MatrixRoom") && it["method"] == "pinnedEventsTimeline" }
            Evidence.record("common_start", "screen" to "room_timeline", "pinnedList" to "closed", "parent" to "room_timeline")
            Evidence.record("post_event", "screen" to "pinned_messages", "listState" to "loading", "openPinnedTimelineCalls" to openCalls)
            Evidence.observe("screen" to "pinned_messages", "listState" to "loading", "effects" to listOf("open_pinned_timeline"))
            Evidence.invariant("the room timeline remains the navigation parent", openCalls == 1, mapOf("parent" to "room_timeline", "child" to "pinned_messages"))
        }
    }

    @Test fun load_failure() = runTest {
        scenario(openFailure = true).use { s ->
            assertSame(PinnedMessagesListState.Failed, s.driver.state)
            Evidence.record("canonical_given", "listState" to "loading", "pinnedTimelineResult" to "failure")
            Evidence.record("post_event", "actualState" to "failed")
            Evidence.observe("listState" to "failed", "emptyStateVisible" to false, "errorVisible" to true)
            Evidence.invariant("a load failure is never rendered as an empty collection", s.driver.state === PinnedMessagesListState.Failed, s.driver.state.toString())
        }
    }

    @Test fun empty_success() = runTest {
        scenario(initial = emptyList()).use { s ->
            assertSame(PinnedMessagesListState.Empty, s.driver.state)
            Evidence.record("canonical_given", "listState" to "loading", "pinnedTimelineItems" to emptyList<String>())
            Evidence.record("post_event", "actualState" to "empty")
            Evidence.observe("listState" to "empty", "loadedPinnedMessagesCount" to 0, "failureVisible" to false)
            Evidence.invariant("the empty state is a successful load", s.driver.state === PinnedMessagesListState.Empty, s.driver.state.toString())
        }
    }

    @Test fun filled_list() = runTest {
        scenario().use { s ->
            val state = s.driver.state as PinnedMessagesListState.Filled
            assertEquals(listOf("\$a", "\$b"), state.ids())
            Evidence.record("canonical_given", "pinnedTimelineItems" to listOf(mapOf("eventId" to "\$a", "body" to "Alpha"), mapOf("eventId" to "\$b", "body" to "Beta")))
            Evidence.record("post_event", "actualIds" to state.ids(), "actualCount" to state.loadedPinnedMessagesCount)
            Evidence.observe("listState" to "filled", "visibleEventIds" to state.ids(), "loadedPinnedMessagesCount" to state.loadedPinnedMessagesCount)
            Evidence.invariant("event identity and server order are preserved", state.ids() == listOf("\$a", "\$b"), state.ids())
        }
    }

    @Test fun unpin_permission_denied() = runTest {
        scenario(canPinUnpin = false).use { s ->
            val actions = (s.driver.state as PinnedMessagesListState.Filled).actionsForFirst(s.driver)
            val names = actions.map { it.javaClass.simpleName.removeSuffix("\$").replace("ViewInTimeline", "view_in_timeline").replace("Unpin", "unpin") }
            assertEquals(listOf("view_in_timeline"), names)
            Evidence.record("common_start", "listState" to "filled", "canPinUnpin" to false, "eventId" to "\$a")
            Evidence.record("post_event", "actions" to names, "ids" to (s.driver.state as PinnedMessagesListState.Filled).ids())
            Evidence.observe("actionsVisible" to listOf("view_in_timeline"), "actionsHidden" to listOf("unpin"))
            Evidence.invariant("opening the action menu does not mutate the pinned list", (s.driver.state as PinnedMessagesListState.Filled).ids() == listOf("\$a", "\$b"), names)
        }
    }

    @Test fun unpin_permission_allowed() = runTest {
        scenario(canPinUnpin = true).use { s ->
            val actions = (s.driver.state as PinnedMessagesListState.Filled).actionsForFirst(s.driver)
            val names = actions.map { if (it == TimelineItemAction.ViewInTimeline) "view_in_timeline" else if (it == TimelineItemAction.Unpin) "unpin" else it.toString() }
            assertEquals(listOf("view_in_timeline", "unpin"), names)
            Evidence.record("common_start", "listState" to "filled", "canPinUnpin" to true, "eventId" to "\$a")
            Evidence.record("post_event", "actions" to names)
            Evidence.observe("actionsVisible" to names)
            Evidence.invariant("server permissions remain authoritative", names == listOf("view_in_timeline", "unpin"), names)
        }
    }

    @Test fun view_in_timeline() = runTest {
        scenario().use { s ->
            val state = s.driver.state as PinnedMessagesListState.Filled
            val target = state.timelineItems.filterIsInstance<TimelineItem.Event>().first()
            state.eventSink(PinnedMessagesListEvents.HandleAction(TimelineItemAction.ViewInTimeline, target))
            s.driver.flush()
            assertEquals(listOf("\$a"), s.navigations)
            Evidence.record("common_start", "screen" to "pinned_messages", "eventId" to "\$a", "visibleEventIds" to state.ids())
            Evidence.record("post_event", "screen" to "room_timeline", "focusedEventId" to s.navigations.single(), "visibleEventIds" to (s.driver.state as PinnedMessagesListState.Filled).ids())
            Evidence.observe("screen" to "room_timeline", "focusedEventId" to "\$a", "effects" to listOf("navigate_to_event"))
            Evidence.invariant("the pinned event remains pinned", (s.driver.state as PinnedMessagesListState.Filled).ids().contains("\$a"), s.navigations)
        }
    }

    @Test fun unpin_success() = runTest {
        scenario().use { s ->
            val state = s.driver.state as PinnedMessagesListState.Filled
            val target = state.timelineItems.filterIsInstance<TimelineItem.Event>().first()
            state.eventSink(PinnedMessagesListEvents.HandleAction(TimelineItemAction.Unpin, target))
            s.driver.advance(400)
            val after = s.driver.state as PinnedMessagesListState.Filled
            val unpinCalls = s.calls.filter { it["port"].toString().endsWith("Timeline") && it["method"] == "unpinEvent" }
            assertEquals(listOf("\$b"), after.ids())
            assertEquals(1, unpinCalls.size)
            Evidence.record("common_start", "visibleEventIds" to listOf("\$a", "\$b"), "canPinUnpin" to true)
            Evidence.record("post_event", "visibleEventIds" to after.ids(), "unpinCalls" to unpinCalls, "sdkEventIds" to s.sdkItems.value.mapNotNull { (it as? MatrixTimelineItem.Event)?.eventId?.value })
            Evidence.observe("visibleEventIds" to after.ids(), "effects" to listOf("unpin_event", "persist_pinned_state"), "errorVisible" to false)
            Evidence.invariant("unrelated pinned events remain in server order", after.ids() == listOf("\$b"), after.ids())
        }
    }

    @Test fun unpin_failure_recovery() = runTest {
        scenario().use { s ->
            s.setUnpinFailure(true)
            val state = s.driver.state as PinnedMessagesListState.Filled
            val target = state.timelineItems.filterIsInstance<TimelineItem.Event>().first()
            state.eventSink(PinnedMessagesListEvents.HandleAction(TimelineItemAction.Unpin, target))
            s.driver.flush()
            val firstIds = (s.driver.state as PinnedMessagesListState.Filled).ids()
            val message = withTimeout(1000) { s.snackbar.snackbarMessage.first { it != null } }
            state.eventSink(PinnedMessagesListEvents.HandleAction(TimelineItemAction.Unpin, target))
            s.driver.flush()
            val calls = s.calls.count { it["port"].toString().endsWith("Timeline") && it["method"] == "unpinEvent" }
            assertEquals(listOf("\$a", "\$b"), firstIds)
            assertEquals(2, calls)
            Evidence.record("common_start", "visibleEventIds" to listOf("\$a", "\$b"), "canPinUnpin" to true)
            Evidence.record("post_event", "visibleEventIds" to firstIds, "snackbarMessage" to message.toString(), "retryUnpinCalls" to calls)
            Evidence.observe("visibleEventIds" to firstIds, "effects" to listOf("show_error"), "retryEnabled" to true)
            Evidence.invariant("a failed unpin never removes the item optimistically", firstIds == listOf("\$a", "\$b"), mapOf("retryCalls" to calls))
        }
    }
}
