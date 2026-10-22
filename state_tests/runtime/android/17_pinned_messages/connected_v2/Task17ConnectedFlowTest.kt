package runtime.task17.connected

import android.Manifest
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import com.bumble.appyx.core.children.nodeOrNull
import com.bumble.appyx.core.integration.NodeHost
import com.bumble.appyx.core.integrationpoint.ActivityIntegrationPoint
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
import io.element.android.libraries.architecture.BackstackView
import io.element.android.libraries.architecture.BaseFlowNode
import io.element.android.libraries.architecture.NodeFactoriesBindings
import io.element.android.libraries.di.DaggerComponentOwner
import io.element.android.libraries.matrix.api.core.toRoomIdOrAlias
import io.element.android.libraries.ui.strings.CommonStrings
import kotlinx.coroutines.*
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
import kotlin.reflect.full.createType

/** No detached presenter composition, callback rewiring, or manually constructed banner state. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "en-rUS-w411dp-h891dp-mdpi")
@LooperMode(LooperMode.Mode.PAUSED)
@OptIn(ExperimentalCoroutinesApi::class, ExperimentalTestApi::class)
class Task17ConnectedFlowTest {
    private val scheduler = TestCoroutineScheduler()
    private val dispatcher = StandardTestDispatcher(scheduler)
    @get:Rule val compose = createEmptyComposeRule(effectContext = dispatcher)

    private class Host(context: BuildContext, override val daggerComponent: NodeFactoriesBindings,
        val construct: (BuildContext) -> LoggedInFlowNode,
    ) : BaseFlowNode<String>(BackStack("session", savedStateMap = null), buildContext = context,
        plugins = emptyList()), DaggerComponentOwner {
        var loggedIn: LoggedInFlowNode? = null
        override fun resolve(navTarget: String, buildContext: BuildContext): Node = construct(buildContext).also { loggedIn = it }
        @Composable override fun View(modifier: Modifier) { BackstackView(modifier = modifier) }
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

    @Test fun original_connected_episode() {
        val key = checkNotNull(System.getProperty("task17.case"))
        val contract = JSONObject(File(checkNotNull(System.getProperty("task17.contract"))).readText())
        val cases = contract.getJSONArray("cases")
        val spec = (0 until cases.length()).map { cases.getJSONObject(it) }.single { it.getString("key") == key }
        val episode = UUID.randomUUID().toString()
        val frames = mutableListOf<Map<String, Any?>>()
        val actions = mutableListOf<Map<String, Any?>>()
        val errors = mutableListOf<String>()
        var sequence = 0
        val scope = CoroutineScope(SupervisorJob() + dispatcher + CoroutineExceptionHandler { _, e -> errors += e.stackTraceToString() })
        Dispatchers.setMain(dispatcher)
        val sdk = Task17SdkInputs(episode, scope)
        sdk.allowPinUnpin = key != "unpin_permission_denied"
        if (key == "empty_success") sdk.emptyServerCollection()
        val context = RuntimeEnvironment.getApplication()
        Shadows.shadowOf(context).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
        val bindings = Task17ProductionBindings(context, scope, sdk)
        val readback = Task17RenderedReadback()
        var host: Host? = null
        var activity: org.robolectric.android.controller.ActivityController<ComponentActivity>? = null
        var error: String? = null
        var timelineParent: Int? = null
        fun tree() = compose.onAllNodes(isRoot(), useUnmergedTree = true).printToString(maxDepth = Int.MAX_VALUE)
        fun pump(ms: Long = 16) {
            scheduler.runCurrent()
            scheduler.advanceTimeBy(ms)
            scheduler.runCurrent()
            Shadows.shadowOf(android.os.Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(ms))
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
            val actual = nodes(checkNotNull(host)).filter {
                it.javaClass.name.endsWith(".MessagesNode") || it.javaClass.name.endsWith(".PinnedMessagesListNode")
            }
            return actual.filter { it.lifecycle.currentState.name == "RESUMED" }.singleOrNull()
                ?: error("No unique actual resumed messages/list page owner")
        }
        fun label(id: Int) = context.getString(id)
        fun visibleText(text: String): Boolean {
            val matches = compose.onAllNodesWithText(text, useUnmergedTree = true).fetchSemanticsNodes()
            check(matches.size <= 1) { "Ambiguous original text control: $text" }
            if (matches.isEmpty()) return false
            return runCatching { compose.onNodeWithText(text, useUnmergedTree = true).assertIsDisplayed() }.isSuccess
        }
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
        fun checkpoint(name: String) {
            val owner = currentNode()
            val presenter = checkNotNull(read(owner, "presenter")) { "Node-owned original presenter unreadable" }
            val state = if (owner.javaClass.name.endsWith(".MessagesNode")) readback.messages() else readback.pinned()
            val provider = checkNotNull(read(presenter, "timelineProvider") ?:
                read(presenter, "pinnedMessagesBannerPresenter")?.let { read(it, "pinnedEventsTimelineProvider") }) {
                "Actual page presenter-to-pinned-provider dependency unavailable"
            }
            val sdkRoom = checkNotNull(read(presenter, "room"))
            check(sdkRoom === sdk.room) { "Page presenter disconnected from actual SDK room" }
            val parent = nodes(checkNotNull(host)).filterIsInstance<LoggedInFlowNode>().single()
            val target = parent.backstack.activeElement
            val items = if (state is MessagesState) state.timelineState.timelineItems else read(state, "timelineItems") as? List<*>
            val ids = items.orEmpty().filterIsInstance<TimelineItem.Event>().mapNotNull { it.eventId?.value }
            val stateFacts = mutableMapOf<String, Any?>("stateClass" to state.javaClass.name,
                "stateId" to System.identityHashCode(state), "loadedEventIds" to ids,
                "sdkPinnedEventIds" to sdk.info.value.pinnedEventIds.map { it.value })
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
                stateFacts["errorVisible"] = visibleText(label(CommonStrings.error_failed_loading_messages))
                stateFacts["emptyStateVisible"] = visibleText(label(CommonStrings.screen_pinned_timeline_empty_state_headline))
                stateFacts["actionsVisible"] = listOf("view_in_timeline" to CommonStrings.action_view_in_timeline,
                    "unpin" to CommonStrings.action_unpin).filter { visibleText(label(it.second)) }.map { it.first }
                stateFacts["renderedEventIds"] = readback.renderedEventIds("PinnedMessagesListView")
                stateFacts["displayedBodies"] = listOf("Alpha", "Beta").filter(::visibleText)
                val snackbar = read(presenter, "snackbarDispatcher")
                stateFacts["snackbarDispatcherId"] = snackbar?.let(System::identityHashCode)
                stateFacts["snackbarMessageResIds"] = (snackbar?.let { read(it, "snackBarMessageQueue") } as? Collection<*>)
                    ?.map { it?.let { message -> read(message, "messageResId") } }
            }
            frames += mapOf("name" to name, "sequence" to ++sequence, "episode" to episode,
                "activityId" to System.identityHashCode(checkNotNull(activity).get()), "semanticsTree" to tree(),
                "nodes" to nodeTree(checkNotNull(host)), "timelineParentNodeId" to timelineParent,
                "owner" to mapOf("nodeId" to System.identityHashCode(owner), "nodeClass" to owner.javaClass.name,
                    "presenterId" to System.identityHashCode(presenter), "pagePresenterId" to System.identityHashCode(read(owner, "presenter")),
                    "providerId" to System.identityHashCode(provider), "roomId" to System.identityHashCode(sdkRoom),
                    "readback" to "actual_composition_parameter",
                    "renderFunction" to if (state is MessagesState) "MessagesView" else "PinnedMessagesListView"),
                "parentRoute" to mapOf("nodeId" to System.identityHashCode(parent), "target" to target.toString(),
                    "focusedEventId" to ((target as? LoggedInFlowNode.NavTarget.Room)?.initialElement?.let { read(it, "focusedEventId") }
                        ?.let { read(it, "value") ?: it.toString() })),
                "state" to stateFacts, "sdkCalls" to sdk.calls.toList(), "construction" to bindings.construction.toList())
        }
        fun enterList(phase: String) {
            // Real header -> real room-details row -> production MessagesEntryPoint.PinnedMessages.
            click("Pinned runtime", phase)
            click(label(CommonStrings.screen_room_details_pinned_events_row_title), phase)
            until("mounted list node") { runCatching { currentNode().javaClass.name.endsWith(".PinnedMessagesListNode") }.getOrDefault(false) }
        }
        try {
            runBlocking { bindings.configureExistingFeatureFlag() }
            activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible().windowFocusChanged(true)
            val actual = activity.get()
            val integration = ActivityIntegrationPoint(actual, null)
            compose.mainClock.autoAdvance = false
            compose.runOnUiThread {
                actual.setContent {
                    readback.Observe { ElementTheme(darkTheme = false) {
                        NodeHost(integrationPoint = integration, modifier = Modifier.fillMaxSize()) { build ->
                            Host(build, bindings.nodes(bindings.sessionGraph)) { child ->
                                bindings.sessionGraph.make(LoggedInFlowNode::class.createType(),
                                    mapOf("buildContext" to child, "plugins" to emptyList<com.bumble.appyx.core.plugin.Plugin>())) as LoggedInFlowNode
                            }.also { host = it }
                        }
                    } }
                }
            }
            until("original logged-in owner") { host?.loggedIn != null }
            scope.launch { checkNotNull(host?.loggedIn).attachRoom(sdk.roomId.toRoomIdOrAlias()) }
            until("original room timeline") { runCatching { currentNode().javaClass.name.endsWith(".MessagesNode") }.getOrDefault(false) }
            timelineParent = System.identityHashCode(currentNode())
            checkpoint("common_room_timeline")
            if (key == "open_loading") {
                checkpoint("before")
                enterList("event")
                checkpoint("after")
            } else if (key in setOf("load_failure", "empty_success", "filled_list")) {
                enterList("prefix")
                checkpoint("before")
                actions += mapOf("sequence" to ++sequence, "episode" to episode, "phase" to "event",
                    "dispatch" to "external_sdk_completion", "boundary" to "Matrix SDK", "operation" to "pinnedTimelineComplete")
                sdk.completeOpen(failure = key == "load_failure")
                pump(400)
                checkpoint("after")
            } else {
                sdk.completeOpen()
                pump(400)
                enterList("prefix")
                pump(400)
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
                        pump(400)
                        checkpoint("after")
                        if (key == "unpin_failure_recovery") {
                            openActions("invariant")
                            click(label(CommonStrings.action_unpin), "invariant")
                            checkpoint("retry")
                        }
                    }
                }
            }
        } catch (failure: Throwable) { error = failure.stackTraceToString() }
        finally {
            val beforeCleanup = host?.let(::nodeTree)
            runCatching { activity?.pause()?.stop()?.destroy() }.onFailure { errors += it.stackTraceToString() }
            scope.cancel()
            Dispatchers.resetMain()
            val raw = mapOf("protocol" to "task17.android.connected-roomflow.v2", "taskId" to contract.getString("taskId"),
                "caseId" to spec.getString("caseId"), "traceDigest" to spec.getString("traceDigest"),
                "role" to checkNotNull(System.getProperty("task17.role")), "episode" to episode,
                "activityId" to activity?.get()?.let(System::identityHashCode),
                "canonicalAssertions" to mapOf("expected" to spec.getJSONObject("expected"), "invariants" to spec.getJSONArray("invariants")),
                "frames" to frames, "actions" to actions, "sdkCalls" to sdk.calls, "construction" to bindings.construction,
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
}
