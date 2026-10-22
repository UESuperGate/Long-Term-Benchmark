package runtime.task17.connected

import android.Manifest
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import com.bumble.appyx.core.children.nodeOrNull
import com.bumble.appyx.core.composable.Children
import com.bumble.appyx.core.integration.NodeHost
import com.bumble.appyx.core.integrationpoint.NodeActivity
import com.bumble.appyx.core.modality.BuildContext
import com.bumble.appyx.core.node.Node
import com.bumble.appyx.core.node.ParentNode
import com.bumble.appyx.navmodel.backstack.BackStack
import com.bumble.appyx.navmodel.backstack.activeElement
import io.element.android.appnav.LoggedInFlowNode
import io.element.android.compound.theme.ElementTheme
import io.element.android.features.messages.impl.MessagesState
import io.element.android.features.messages.impl.timeline.FocusRequestState
import io.element.android.features.messages.impl.timeline.model.TimelineItem
import io.element.android.features.messages.impl.timeline.model.event.TimelineItemTextBasedContent
import io.element.android.libraries.architecture.NodeFactoriesBindings
import io.element.android.libraries.di.DaggerComponentOwner
import io.element.android.libraries.designsystem.utils.snackbar.LocalSnackbarDispatcher
import io.element.android.x.di.AppBindings
import io.element.android.libraries.matrix.api.core.toRoomIdOrAlias
import io.element.android.libraries.ui.strings.CommonStrings
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.test.*
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.util.UUID

class Task17Activity : NodeActivity() {
    override fun onCreate(savedInstanceState: android.os.Bundle?) {
        setTheme(io.element.android.x.R.style.Theme_ElementX)
        super.onCreate(savedInstanceState)
    }
    fun productionIntegrationPoint() = appyxIntegrationPoint
}

/** No detached presenter composition, callback rewiring, or manually constructed banner state. */
@RunWith(RobolectricTestRunner::class)
@Config(application = Task17Application::class, sdk = [34], qualifiers = "en-rUS-w411dp-h891dp-mdpi")
@LooperMode(LooperMode.Mode.PAUSED)
@OptIn(ExperimentalCoroutinesApi::class, ExperimentalTestApi::class)
class Task17ConnectedFlowTest {
    private val scheduler = TestCoroutineScheduler()
    private val dispatcher = StandardTestDispatcher(scheduler)
    @get:Rule val compose = createEmptyComposeRule()

    private class Host(context: BuildContext, override val daggerComponent: NodeFactoriesBindings,
        private val backstack: BackStack<String> = BackStack("session", savedStateMap = null),
        val construct: (BuildContext) -> LoggedInFlowNode,
    ) : ParentNode<String>(navModel = backstack, buildContext = context, plugins = emptyList()), DaggerComponentOwner {
        var loggedIn: LoggedInFlowNode? = null
        override fun resolve(navTarget: String, buildContext: BuildContext): Node = construct(buildContext).also { loggedIn = it }
        @Composable override fun View(modifier: Modifier) {
            val attachedChildren by children.collectAsState()
            if (attachedChildren.isNotEmpty()) Children(navModel = backstack, modifier = modifier)
        }
    }

    private fun nodes(node: Node): List<Node> = listOf(node) +
        (if (node is ParentNode<*>) node.children.value.mapNotNull { it.value.nodeOrNull }.flatMap(::nodes) else emptyList())
    private fun nodeTree(node: Node, parent: Node? = null): List<Map<String, Any?>> = listOf(mapOf(
        "nodeId" to System.identityHashCode(node), "parentId" to parent?.let(System::identityHashCode),
        "class" to node.javaClass.name, "lifecycle" to node.lifecycle.currentState.name)) +
        (if (node is ParentNode<*>) node.children.value.mapNotNull { it.value.nodeOrNull }.flatMap { nodeTree(it, node) } else emptyList())
    private fun read(instance: Any, property: String): Any? {
        val getter = "get" + property.replaceFirstChar { it.uppercase() }
        instance.javaClass.methods.singleOrNull { it.name == getter && it.parameterCount == 0 }?.let { return it.invoke(instance) }
        var type: Class<*>? = instance.javaClass
        while (type != null) {
            val field = type.declaredFields.singleOrNull { it.name == property }
            if (field != null) { field.isAccessible = true; return field.get(instance) }
            type = type.superclass
        }
        return null
    }

    private fun runOriginalConnectedEpisode(key: String) {
        val contract = JSONObject(File(checkNotNull(System.getProperty("task17.contract"))).readText())
        val cases = contract.getJSONArray("cases")
        val spec = (0 until cases.length()).map { cases.getJSONObject(it) }.single { it.getString("key") == key }
        val episode = UUID.randomUUID().toString()
        val frames = mutableListOf<Map<String, Any?>>()
        val actions = mutableListOf<Map<String, Any?>>()
        val errors = mutableListOf<String>()
        val appyxSyncReceipts = mutableListOf<Map<String, Any?>>()
        val appyxSyncedNodes = mutableSetOf<Int>()
        var sequence = 0
        val scope = CoroutineScope(SupervisorJob() + dispatcher + CoroutineExceptionHandler { _, e -> errors += e.stackTraceToString() })
        val sdk = Task17SdkInputs(episode, scope)
        sdk.allowPinUnpin = key != "unpin_permission_denied"
        if (key == "empty_success") sdk.emptyServerCollection()
        val context = RuntimeEnvironment.getApplication() as Task17Application
        Shadows.shadowOf(context).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
        val bindings = Task17ProductionBindings(context, sdk)
        val readback = Task17RenderedReadback()
        var host: Host? = null
        var activity: org.robolectric.android.controller.ActivityController<Task17Activity>? = null
        var error: String? = null
        var timelineParent: Int? = null
        var featureUnavailable = false
        val productionRoomInfo = java.util.Collections.synchronizedMap(
            java.util.IdentityHashMap<io.element.android.libraries.matrix.api.room.MatrixRoom,
                io.element.android.libraries.matrix.api.room.MatrixRoomInfo>())
        val observedRooms = java.util.Collections.newSetFromMap(
            java.util.IdentityHashMap<io.element.android.libraries.matrix.api.room.MatrixRoom, Boolean>())
        fun tree() = compose.onAllNodes(isRoot(), useUnmergedTree = true).printToString(maxDepth = Int.MAX_VALUE)
        fun syncAppyx(node: Node) {
            if (node !is ParentNode<*>) return
            val managerField = ParentNode::class.java.getDeclaredField("childNodeCreationManager").apply { isAccessible = true }
            val manager = managerField.get(node)
            val keepModeField = manager.javaClass.getDeclaredField("keepMode").apply { isAccessible = true }
            val keepMode = keepModeField.get(manager).toString()
            val screen = node.navModel.screenState.value
            val onScreen = screen.onScreen.mapTo(linkedSetOf()) { it.key }
            val offScreen = screen.offScreen.mapTo(linkedSetOf()) { it.key }
            val kept = if (keepMode == "KEEP") onScreen + offScreen else onScreen
            val suspended = if (keepMode == "SUSPEND") offScreen else emptySet()
            val all = kept + suspended
            val update = manager.javaClass.declaredMethods.single { it.name == "updateChildren" && it.parameterCount == 3 }
                .apply { isAccessible = true }
            update.invoke(manager, all, kept, suspended)
            node.updateLifecycleState(node.lifecycle.currentState)
            val nodeId = System.identityHashCode(node)
            if (appyxSyncedNodes.add(nodeId)) appyxSyncReceipts += mapOf(
                "nodeId" to nodeId, "nodeClass" to node.javaClass.name,
                "managerClass" to manager.javaClass.name, "method" to update.name,
                "keepMode" to keepMode, "navKeyCount" to all.size)
            node.children.value.mapNotNull { it.value.nodeOrNull }.forEach(::syncAppyx)
        }
        fun pump(ms: Long = 16) {
            scheduler.runCurrent()
            scheduler.advanceTimeBy(ms)
            scheduler.runCurrent()
            Shadows.shadowOf(android.os.Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(ms))
            compose.runOnUiThread { host?.let(::syncAppyx) }
            compose.mainClock.advanceTimeBy(ms)
            compose.waitForIdle()
            check(errors.isEmpty()) { errors.joinToString("\n") }
        }
        fun until(reason: String, predicate: () -> Boolean) {
            val stop = System.nanoTime() + 10_000_000_000L
            while (!predicate() && System.nanoTime() < stop) pump()
            check(predicate()) { "Original runtime boundary unavailable: $reason" }
        }
        fun currentNode(): Node {
            val suffix = when (readback.renderedSurface()) {
                "room_timeline" -> ".MessagesNode"
                "pinned_messages" -> ".PinnedMessagesListNode"
                else -> error("No unique currently rendered messages/list surface")
            }
            return nodes(checkNotNull(host)).filter { it.javaClass.name.endsWith(suffix) }
                .filter { it.lifecycle.currentState.name == "RESUMED" }.singleOrNull()
                ?: error("No unique actual resumed owner for rendered surface $suffix")
        }
        fun label(id: Int) = context.getString(id)
        fun visibleText(text: String): Boolean {
            val matches = compose.onAllNodesWithText(text, useUnmergedTree = true).fetchSemanticsNodes()
            check(matches.size <= 1) { "Ambiguous original text control: $text" }
            if (matches.isEmpty()) return false
            return runCatching { compose.onNodeWithText(text, useUnmergedTree = true).assertIsDisplayed() }.isSuccess
        }
        fun visibleEventBody(body: String): Boolean {
            val matcher = hasTestTag("message_bubble") and
                hasAnyDescendant(hasText(body) or hasContentDescription(body))
            val matches = compose.onAllNodes(matcher, useUnmergedTree = true).fetchSemanticsNodes()
            check(matches.size <= 1) { "Ambiguous rendered message body: $body" }
            return matches.size == 1 && runCatching {
                compose.onNode(matcher, useUnmergedTree = true).assertIsDisplayed()
            }.isSuccess
        }
        fun pinnedStateEvents(): List<TimelineItem.Event> {
            val state = readback.pinned()
            return (read(state, "timelineItems") as? List<*>).orEmpty().filterIsInstance<TimelineItem.Event>()
        }
        fun pinnedStateEventIds(): List<String> = pinnedStateEvents().mapNotNull { it.eventId?.value }
        fun renderedPinnedEvents(): List<Map<String, String?>> = pinnedStateEvents().mapNotNull { event ->
            val body = (event.content as? TimelineItemTextBasedContent)?.body ?: return@mapNotNull null
            if (!visibleEventBody(body)) return@mapNotNull null
            mapOf("eventId" to event.eventId?.value, "body" to body)
        }
        fun renderedPinnedEventIds(): List<String> = renderedPinnedEvents().mapNotNull { it["eventId"] }
        fun click(text: String, phase: String = "event") {
            val matcher = hasClickAction() and (hasText(text) or hasAnyDescendant(hasText(text)))
            val control = compose.onNode(matcher, useUnmergedTree = true).assertIsDisplayed().assertIsEnabled()
            val snapshot = tree()
            actions += mapOf("sequence" to ++sequence, "episode" to episode,
                "activityId" to System.identityHashCode(checkNotNull(activity).get()), "phase" to phase,
                "dispatch" to "compose_original_control", "eligible" to true, "selectorText" to text,
                "semanticsNodeId" to control.fetchSemanticsNode().id, "semanticsBefore" to snapshot)
            control.performClick()
            pump()
        }
        fun dismissBlockingEnvironmentDialog() {
            val nodes = compose.onAllNodesWithTag("dialog-positive", useUnmergedTree = true).fetchSemanticsNodes()
            if (nodes.isEmpty()) return
            check(nodes.size == 1) { "Ambiguous environment dialog positive action" }
            val control = compose.onNodeWithTag("dialog-positive", useUnmergedTree = true)
                .assertIsDisplayed().assertIsEnabled()
            actions += mapOf("sequence" to ++sequence, "episode" to episode,
                "activityId" to System.identityHashCode(checkNotNull(activity).get()), "phase" to "environment_setup",
                "dispatch" to "compose_original_control", "eligible" to true, "selectorTag" to "dialog-positive",
                "semanticsNodeId" to control.fetchSemanticsNode().id, "semanticsBefore" to tree(),
                "operation" to "dismiss_blocking_notification_transport_error")
            control.performClick()
            pump()
        }
        fun openActions(phase: String) {
            val bubble = compose.onNode(hasTestTag("message_bubble") and
                hasAnyDescendant(hasText("Alpha") or hasContentDescription("Alpha")), useUnmergedTree = true)
                .assertIsDisplayed().assertIsEnabled()
            actions += mapOf("sequence" to ++sequence, "episode" to episode,
                "activityId" to System.identityHashCode(checkNotNull(activity).get()), "phase" to phase,
                "dispatch" to "compose_original_control", "eligible" to true,
                "semanticsNodeId" to bubble.fetchSemanticsNode().id, "semanticsBefore" to tree(), "operation" to "longClick")
            bubble.performTouchInput { longClick() }
            pump(400)
        }
        fun resumedNode(className: String): Node = nodes(checkNotNull(host))
            .filter { it.javaClass.name == className && it.lifecycle.currentState.name == "RESUMED" }
            .singleOrNull() ?: error("No unique resumed original node: $className")
        fun pinnedProvider(owner: Node): Any? {
            val presenter = checkNotNull(read(owner, "presenter")) { "Node-owned original presenter unreadable" }
            return read(presenter, "timelineProvider") ?:
                read(presenter, "pinnedMessagesBannerPresenter")?.let { read(it, "pinnedEventsTimelineProvider") }
        }
        fun checkpointUnavailable(name: String, owner: Node, screen: String, missingControl: String) {
            val presenter = checkNotNull(read(owner, "presenter")) { "Node-owned original presenter unreadable" }
            val sdkRoom = checkNotNull(read(owner, "room") ?: read(presenter, "room"))
            check(sdkRoom is io.element.android.libraries.matrix.impl.room.RustMatrixRoom &&
                read(sdkRoom, "innerRoom") === sdk.innerRoom) { "Unavailable-feature page bypasses original RustMatrixRoom bridge" }
            if (observedRooms.add(sdkRoom)) scope.launch {
                sdkRoom.roomInfoFlow.collect { productionRoomInfo[sdkRoom] = it }
            }
            until("original Rust room-info mapper observation") { productionRoomInfo.containsKey(sdkRoom) }
            val parent = nodes(checkNotNull(host)).filterIsInstance<LoggedInFlowNode>().single()
            val actualTree = nodeTree(checkNotNull(host))
            val target = parent.backstack.activeElement
            frames += mapOf(
                "name" to name, "sequence" to ++sequence, "episode" to episode,
                "activityId" to System.identityHashCode(checkNotNull(activity).get()), "semanticsTree" to tree(),
                "nodes" to actualTree, "timelineParentNodeId" to timelineParent,
                "owner" to mapOf("nodeId" to System.identityHashCode(owner), "nodeClass" to owner.javaClass.name,
                    "presenterId" to System.identityHashCode(presenter), "roomId" to System.identityHashCode(sdkRoom),
                    "readback" to "actual_mounted_node_fields", "featureAvailable" to false),
                "parentRoute" to mapOf("nodeId" to System.identityHashCode(parent), "target" to target.toString()),
                "state" to mapOf("screen" to screen, "featureAvailable" to false,
                    "missingControl" to missingControl, "missingControlDisplayed" to visibleText(missingControl),
                    "productionPinnedEventIds" to checkNotNull(productionRoomInfo[sdkRoom]).pinnedEventIds.map { it.value }),
                "sdkCalls" to sdk.calls.toList(),
                "bridgeEvidence" to mapOf("sdkNamespace" to "org.matrix.rustcomponents.sdk",
                    "roomClass" to sdkRoom.javaClass.name, "roomId" to System.identityHashCode(sdkRoom),
                    "leafRoomId" to read(sdkRoom, "innerRoom")?.let(System::identityHashCode)),
                "productionComponents" to bindings.componentEvidence() + mapOf(
                    "roomId" to System.identityHashCode(sdkRoom),
                    "actualRootClientId" to read(parent, "matrixClient")?.let(System::identityHashCode)))
        }
        fun probeMissingControl(text: String) {
            val matcher = hasText(text) or hasAnyDescendant(hasText(text))
            check(compose.onAllNodes(matcher, useUnmergedTree = true).fetchSemanticsNodes().isEmpty()) {
                "Unavailable-feature probe found the canonical control: $text"
            }
            actions += mapOf("sequence" to ++sequence, "episode" to episode,
                "activityId" to System.identityHashCode(checkNotNull(activity).get()), "phase" to "event",
                "dispatch" to "missing_original_control_probe", "eligible" to false,
                "selectorText" to text, "semanticsBefore" to tree())
        }
        fun checkpoint(name: String) {
            val owner = currentNode()
            val presenter = checkNotNull(read(owner, "presenter")) { "Node-owned original presenter unreadable" }
            val state = if (owner.javaClass.name.endsWith(".MessagesNode")) readback.messages() else readback.pinned()
            val provider = checkNotNull(read(presenter, "timelineProvider") ?:
                read(presenter, "pinnedMessagesBannerPresenter")?.let { read(it, "pinnedEventsTimelineProvider") }) {
                "Actual page presenter-to-pinned-provider dependency unavailable"
            }
            val sdkRoom = checkNotNull(read(presenter, "room"))
            check(sdkRoom is io.element.android.libraries.matrix.impl.room.RustMatrixRoom &&
                read(sdkRoom, "innerRoom") === sdk.innerRoom) { "Page presenter bypasses original RustMatrixRoom bridge" }
            if (observedRooms.add(sdkRoom)) scope.launch {
                sdkRoom.roomInfoFlow.collect { productionRoomInfo[sdkRoom] = it }
            }
            until("original Rust room-info mapper observation") { productionRoomInfo.containsKey(sdkRoom) }
            val parent = nodes(checkNotNull(host)).filterIsInstance<LoggedInFlowNode>().single()
            val target = parent.backstack.activeElement
            val actualTree = nodeTree(checkNotNull(host))
            val ancestors = mutableListOf<Node>(owner)
            var parentId = actualTree.single { it["nodeId"] == System.identityHashCode(owner) }["parentId"]
            while (parentId != null) {
                ancestors += nodes(checkNotNull(host)).single { System.identityHashCode(it) == parentId }
                parentId = actualTree.single { it["nodeId"] == parentId }["parentId"]
            }
            val loadedOwner = ancestors.single { it.javaClass.name == "io.element.android.appnav.room.joined.JoinedRoomLoadedFlowNode" }
            val roomComponent = (loadedOwner as DaggerComponentOwner).daggerComponent
            val actualFlow = ancestors.first { it.javaClass.name == "io.element.android.features.messages.impl.MessagesFlowNode" }
            val callbackReadback = ancestors.mapNotNull { node ->
                (read(node, "callbacks") as? List<*>)?.let { callbacks -> mapOf(
                    "nodeId" to System.identityHashCode(node), "nodeClass" to node.javaClass.name,
                    "callbacks" to callbacks.map { callback ->
                        checkNotNull(callback)
                        mapOf("instanceId" to System.identityHashCode(callback), "class" to callback.javaClass.name,
                            "enclosingClass" to callback.javaClass.enclosingClass?.name,
                            "outerNodes" to callback.javaClass.declaredFields.mapNotNull { field ->
                                if (!Node::class.java.isAssignableFrom(field.type)) null else {
                                    field.isAccessible = true
                                    (field.get(callback) as? Node)?.let { outer -> mapOf("field" to field.name,
                                        "nodeId" to System.identityHashCode(outer), "nodeClass" to outer.javaClass.name) }
                                }
                            })
                    }) }
            }
            val items = if (state is MessagesState) state.timelineState.timelineItems else read(state, "timelineItems") as? List<*>
            val ids = items.orEmpty().filterIsInstance<TimelineItem.Event>().mapNotNull { it.eventId?.value }
            val stateFacts = mutableMapOf<String, Any?>("stateClass" to state.javaClass.name,
                "stateId" to System.identityHashCode(state), "loadedEventIds" to ids,
                "sdkPinnedEventIds" to sdk.serverPinnedEventIds,
                "productionPinnedEventIds" to checkNotNull(productionRoomInfo[sdkRoom]).pinnedEventIds.map { it.value },
                "sdkCacheEventIds" to sdk.sdkCacheEventIds,
                "screen" to if (state is MessagesState) "room_timeline" else "pinned_messages")
            if (state is MessagesState) {
                val focus = state.timelineState.focusRequestState
                stateFacts["focus"] = mapOf("eventId" to state.timelineState.focusedEventId?.value,
                    "rendered" to ((focus as? FocusRequestState.Success)?.rendered == true),
                    "targetControlDisplayed" to (state.timelineState.focusedEventId?.value == "\$a" && visibleText("Alpha")))
            } else {
                val actionListState = read(state, "actionListState")
                val target = actionListState?.let { read(it, "target") }
                stateFacts["selectedEventId"] = (target?.let { read(it, "event") } as? TimelineItem.Event)?.eventId?.value
                stateFacts["canPinUnpin"] = read(state, "userEventPermissions")?.let { read(it, "canPinUnpin") }
                stateFacts["listState"] = state.javaClass.simpleName.lowercase()
                stateFacts["loadedPinnedMessagesCount"] = read(state, "loadedPinnedMessagesCount")
                    ?: if (state.javaClass.simpleName == "Empty") 0 else null
                stateFacts["errorVisible"] = visibleText(label(CommonStrings.error_failed_loading_messages))
                stateFacts["emptyStateVisible"] = visibleText(label(CommonStrings.screen_pinned_timeline_empty_state_headline))
                stateFacts["actionsVisible"] = listOf("view_in_timeline" to CommonStrings.action_view_in_timeline,
                    "unpin" to CommonStrings.action_unpin).filter { visibleText(label(it.second)) }.map { it.first }
                val renderedEvents = renderedPinnedEvents()
                stateFacts["renderedEventIds"] = renderedEvents.mapNotNull { it["eventId"] }
                stateFacts["renderedEvents"] = renderedEvents
                stateFacts["displayedBodies"] = renderedEvents.mapNotNull { it["body"] }
                val snackbar = read(presenter, "snackbarDispatcher")
                stateFacts["snackbarDispatcherId"] = snackbar?.let(System::identityHashCode)
                stateFacts["snackbarMessageResIds"] = (snackbar?.let { read(it, "snackBarMessageQueue") } as? Collection<*>)
                    ?.map { it?.let { message -> read(message, "messageResId") } }
                stateFacts["errorSnackbarResId"] = CommonStrings.common_error
            }
            val objects = listOfNotNull(presenter, read(presenter, "pinnedMessagesBannerPresenter"),
                read(presenter, "timelinePresenter"), provider)
            val providerState = (read(provider, "timelineStateFlow") as? kotlinx.coroutines.flow.StateFlow<*>)?.value
            val pinnedTimeline = providerState?.let { read(it, "data") }
            val providerFailure = providerState?.let { read(it, "error") } as? Throwable
            val bridge = mapOf("roomClass" to sdkRoom.javaClass.name,
                "roomId" to System.identityHashCode(sdkRoom), "leafRoomId" to read(sdkRoom, "innerRoom")?.let(System::identityHashCode),
                "providerStateClass" to providerState?.javaClass?.name,
                "providerFailure" to providerFailure?.let { failure -> mapOf(
                    "class" to failure.javaClass.name, "message" to failure.message,
                    "stack" to failure.stackTrace.take(12).map(StackTraceElement::toString)) },
                "pinnedTimelineClass" to pinnedTimeline?.javaClass?.name,
                "pinnedTimelineId" to pinnedTimeline?.let(System::identityHashCode),
                "pinnedTimelineRoomId" to pinnedTimeline?.let { read(it, "matrixRoom") }?.let(System::identityHashCode),
                "leafPinnedTimelineId" to pinnedTimeline?.let { read(it, "inner") }?.let(System::identityHashCode),
                "expectedLeafPinnedTimelineId" to System.identityHashCode(sdk.pinned.timeline),
                "postprocessorMode" to pinnedTimeline?.let { read(it, "roomBeginningPostProcessor") }?.let { read(it, "mode") }?.toString(),
                "sdkNamespace" to "org.matrix.rustcomponents.sdk")
            val dependencyReadback = objects.map { instance -> mapOf(
                "class" to instance.javaClass.name, "instanceId" to System.identityHashCode(instance),
                "readback" to "original_instance_fields_no_constructor_replay",
                "dependencies" to listOf("navigator", "room", "timelineProvider", "pinnedMessagesBannerPresenter",
                    "pinnedEventsTimelineProvider", "timelinePresenter").mapNotNull { field ->
                    read(instance, field)?.let { value -> mapOf("name" to field,
                        "instanceId" to System.identityHashCode(value), "class" to value.javaClass.name) }
                }) }
            frames += mapOf("name" to name, "sequence" to ++sequence, "episode" to episode,
                "activityId" to System.identityHashCode(checkNotNull(activity).get()), "semanticsTree" to tree(),
                "nodes" to actualTree, "timelineParentNodeId" to timelineParent,
                "owner" to mapOf("nodeId" to System.identityHashCode(owner), "nodeClass" to owner.javaClass.name,
                    "presenterId" to System.identityHashCode(presenter), "pagePresenterId" to System.identityHashCode(read(owner, "presenter")),
                    "providerId" to System.identityHashCode(provider), "roomId" to System.identityHashCode(sdkRoom),
                    "readback" to "actual_composition_parameter",
                    "renderFunction" to if (state is MessagesState) "MessagesView" else "PinnedMessagesListView"),
                "parentRoute" to mapOf("nodeId" to System.identityHashCode(parent), "target" to target.toString(),
                    "focusedEventId" to ((target as? LoggedInFlowNode.NavTarget.Room)?.initialElement?.let { read(it, "focusedEventId") }
                        ?.let { if (it is String) it else read(it, "value") ?: it.toString() })),
                "state" to stateFacts, "sdkCalls" to sdk.calls.toList(),
                "dependencyReadback" to dependencyReadback, "callbackReadback" to callbackReadback, "bridgeEvidence" to bridge,
                "productionComponents" to bindings.componentEvidence() + mapOf(
                    "roomId" to System.identityHashCode(sdkRoom),
                    "loadedRoomOwnerId" to System.identityHashCode(loadedOwner),
                    "roomComponentId" to System.identityHashCode(roomComponent), "roomComponentClass" to roomComponent.javaClass.name,
                    "actualRootClientId" to read(parent, "matrixClient")?.let(System::identityHashCode),
                    "actualRoomInputId" to read(loadedOwner, "inputs")?.let { read(it, "room") }?.let(System::identityHashCode),
                    "actualFlowProviderId" to read(actualFlow, "pinnedEventsTimelineProvider")?.let(System::identityHashCode)))
        }
        fun enterList(phase: String) {
            // Real header -> real room-details row -> production MessagesEntryPoint.PinnedMessages.
            click("Pinned runtime", phase)
            val pinnedRow = label(CommonStrings.screen_room_details_pinned_events_row_title)
            until("displayed room-details pinned row") { visibleText(pinnedRow) }
            click(pinnedRow, phase)
            until("rendered list node") { runCatching {
                readback.renderedSurface() == "pinned_messages" && currentNode().javaClass.name.endsWith(".PinnedMessagesListNode")
            }.getOrDefault(false) }
        }
        try {
            runBlocking { bindings.configureExistingInputs() }
            activity = Robolectric.buildActivity(Task17Activity::class.java).setup().visible().windowFocusChanged(true)
            val actual = activity.get()
            compose.mainClock.autoAdvance = false
            compose.runOnUiThread {
                actual.setContent {
                    readback.Observe { ElementTheme(darkTheme = false) {
                        CompositionLocalProvider(LocalSnackbarDispatcher provides (bindings.app as AppBindings).snackbarDispatcher()) {
                        NodeHost(integrationPoint = actual.productionIntegrationPoint(), modifier = Modifier.fillMaxSize()) { build ->
                            Host(build, bindings.session) { child ->
                                bindings.rootFactory().create(child, emptyList()) as LoggedInFlowNode
                            }.also { host = it }
                        }
                        }
                    } }
                }
            }
            until("original logged-in owner") { host?.loggedIn != null }
            scope.launch { checkNotNull(host?.loggedIn).attachRoom(sdk.roomId.toRoomIdOrAlias()) }
            until("rendered original room timeline") { runCatching {
                readback.renderedSurface() == "room_timeline" && currentNode().javaClass.name.endsWith(".MessagesNode")
            }.getOrDefault(false) }
            dismissBlockingEnvironmentDialog()
            timelineParent = System.identityHashCode(currentNode())
            val initialOwner = currentNode()
            if (pinnedProvider(initialOwner) == null) {
                featureUnavailable = true
                val pinnedRow = label(CommonStrings.screen_room_details_pinned_events_row_title)
                checkpointUnavailable("common_room_timeline", initialOwner, "room_timeline", pinnedRow)
                click("Pinned runtime", "prefix")
                until("rendered original room details") { runCatching {
                    resumedNode("io.element.android.features.roomdetails.impl.RoomDetailsNode")
                    true
                }.getOrDefault(false) }
                val details = resumedNode("io.element.android.features.roomdetails.impl.RoomDetailsNode")
                checkpointUnavailable("before", details, "room_details", pinnedRow)
                probeMissingControl(pinnedRow)
                checkpointUnavailable("after", details, "room_details", pinnedRow)
            } else {
                checkpoint("common_room_timeline")
                if (key == "open_loading") {
                    checkpoint("before")
                    enterList("event")
                    checkpoint("after")
                } else if (key in setOf("load_failure", "empty_success", "filled_list")) {
                    enterList("prefix")
                    checkpoint("before")
                    actions += mapOf("sequence" to ++sequence, "episode" to episode, "phase" to "event",
                        "dispatch" to "external_sdk_completion", "boundary" to "org.matrix.rustcomponents.sdk", "operation" to "pinnedTimelineComplete")
                    sdk.completeOpen(failure = key == "load_failure")
                    until("settled rendered pinned completion") {
                        val state = readback.pinned()
                        when (key) {
                            "load_failure" -> state.javaClass.simpleName == "Failed" &&
                                visibleText(label(CommonStrings.error_failed_loading_messages))
                            "empty_success" -> state.javaClass.simpleName == "Empty"
                            else -> state.javaClass.simpleName == "Filled" &&
                                pinnedStateEventIds() == sdk.serverPinnedEventIds &&
                                renderedPinnedEventIds() == sdk.serverPinnedEventIds
                        }
                    }
                    checkpoint("after")
                } else {
                    sdk.completeOpen()
                    pump(400)
                    enterList("prefix")
                    until("settled rendered populated pinned list") {
                        readback.pinned().javaClass.simpleName == "Filled" &&
                            pinnedStateEventIds() == sdk.serverPinnedEventIds &&
                            renderedPinnedEventIds() == sdk.serverPinnedEventIds
                    }
                    if (key in setOf("unpin_permission_denied", "unpin_permission_allowed")) {
                        checkpoint("before")
                        openActions("event")
                        checkpoint("after")
                    } else {
                        openActions("prefix")
                        checkpoint("before")
                        if (key == "view_in_timeline") {
                            click(label(CommonStrings.action_view_in_timeline))
                            until("original parent replaced room and focused rendered target") {
                                runCatching {
                                    currentNode().javaClass.name.endsWith(".MessagesNode") &&
                                        (readback.messages().timelineState.focusRequestState as? FocusRequestState.Success)?.rendered == true
                                }.getOrDefault(false)
                            }
                            checkpoint("after")
                        } else {
                            check(key in setOf("unpin_success", "unpin_failure_recovery")) { "Unreviewed canonical event: $key" }
                            sdk.failUnpin = key == "unpin_failure_recovery"
                            click(label(CommonStrings.action_unpin))
                            until("actual held SDK unpin request") { sdk.hasPendingUnpin() }
                            checkpoint("pending")
                            sdk.completeUnpin()
                            if (key == "unpin_success") {
                                until("rendered successful unpin completion") {
                                    pinnedStateEventIds() == sdk.serverPinnedEventIds &&
                                        renderedPinnedEventIds() == sdk.serverPinnedEventIds
                                }
                            } else {
                                pump(400)
                            }
                            checkpoint("after")
                            if (key == "unpin_failure_recovery") {
                                openActions("invariant")
                                click(label(CommonStrings.action_unpin), "invariant")
                                until("actual eligible retry SDK request") { sdk.hasPendingUnpin() }
                                checkpoint("retry_pending")
                                sdk.completeUnpin()
                                pump(400)
                                checkpoint("retry")
                            }
                        }
                    }
                }
            }
        } catch (failure: Throwable) { error = failure.stackTraceToString() }
        finally {
            val beforeCleanup = host?.let(::nodeTree)
            runCatching { activity?.pause()?.stop()?.destroy() }.onFailure { errors += it.stackTraceToString() }
            runCatching { bindings.cancelOwnedScopes() }.onFailure { errors += it.stackTraceToString() }
            runCatching { sdk.assertComplete() }.onFailure { errors += it.stackTraceToString() }
            runCatching { context.removeEvaluatorProvider() }.onFailure { errors += it.stackTraceToString() }
            scope.cancel()
            val raw = mapOf("protocol" to "task17.android.connected-roomflow.v3", "taskId" to contract.getString("taskId"),
                "caseId" to spec.getString("caseId"), "traceDigest" to spec.getString("traceDigest"),
                "role" to checkNotNull(System.getProperty("task17.role")), "episode" to episode,
                "activityId" to activity?.get()?.let(System::identityHashCode),
                "canonicalAssertions" to mapOf("expected" to spec.getJSONObject("expected"), "invariants" to spec.getJSONArray("invariants")),
                "frames" to frames, "actions" to actions, "sdkCalls" to sdk.calls,
                "featureUnavailable" to featureUnavailable,
                "productionComponents" to bindings.componentEvidence(),
                "appyxSyncReceipts" to appyxSyncReceipts,
                "leafSdkAudit" to sdk.audit.receipts.toList(),
                "sdkBoundaryVersion" to "org.matrix.rustcomponents.sdk-only.v1",
                "asyncErrors" to errors, "bindingErrors" to listOfNotNull(error), "nodeTreeBeforeCleanup" to beforeCleanup,
                "runtimeExecuted" to true, "semanticScore" to "not_admitted", "cleanupAttempted" to true)
            val output = File(checkNotNull(System.getProperty("task17.evidence.dir")), key + ".native.json")
            output.parentFile.mkdirs()
            check(!output.exists()) { "Refusing old evidence" }
            output.writeText(JSONObject(raw).toString(2) + "\n")
        }
        check(error == null) { checkNotNull(error) }
        check(errors.isEmpty()) { errors.joinToString("\n") }
    }

    @Test fun original_connected_episode() =
        runOriginalConnectedEpisode(checkNotNull(System.getProperty("task17.case")))

    @Test fun original_connected_case_001_open_loading() = runOriginalConnectedEpisode("open_loading")
    @Test fun original_connected_case_002_load_failure() = runOriginalConnectedEpisode("load_failure")
    @Test fun original_connected_case_003_empty_success() = runOriginalConnectedEpisode("empty_success")
    @Test fun original_connected_case_004_filled_list() = runOriginalConnectedEpisode("filled_list")
    @Test fun original_connected_case_005_unpin_permission_denied() = runOriginalConnectedEpisode("unpin_permission_denied")
    @Test fun original_connected_case_006_unpin_permission_allowed() = runOriginalConnectedEpisode("unpin_permission_allowed")
    @Test fun original_connected_case_007_view_in_timeline() = runOriginalConnectedEpisode("view_in_timeline")
    @Test fun original_connected_case_008_unpin_success() = runOriginalConnectedEpisode("unpin_success")
    @Test fun original_connected_case_009_unpin_failure_recovery() = runOriginalConnectedEpisode("unpin_failure_recovery")
}
