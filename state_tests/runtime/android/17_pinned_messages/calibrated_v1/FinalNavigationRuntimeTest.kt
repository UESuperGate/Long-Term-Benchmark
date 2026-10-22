package runtime.task17

import android.content.Context
import androidx.activity.ComponentActivity
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.lifecycle.Lifecycle
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.bumble.appyx.core.modality.BuildContext
import com.bumble.appyx.core.node.Node
import com.bumble.appyx.core.plugin.Plugin
import com.bumble.appyx.navmodel.backstack.BackStack
import com.bumble.appyx.navmodel.backstack.activeElement
import com.bumble.appyx.testing.unit.common.helper.parentNodeTestHelper
import io.element.android.features.call.api.ElementCallEntryPoint
import io.element.android.features.location.api.SendLocationEntryPoint
import io.element.android.features.location.api.ShowLocationEntryPoint
import io.element.android.features.messages.api.MessagesEntryPoint
import io.element.android.features.messages.impl.MessagesFlowNode
import io.element.android.features.messages.impl.MessagesNode
import io.element.android.features.messages.impl.MessagesPresenter
import io.element.android.features.messages.impl.pinned.PinnedEventsTimelineProvider
import io.element.android.features.messages.impl.pinned.banner.PinnedMessagesBannerItem
import io.element.android.features.messages.impl.pinned.banner.PinnedMessagesBannerState
import io.element.android.features.messages.impl.pinned.banner.PinnedMessagesBannerView
import io.element.android.features.messages.impl.pinned.list.PinnedMessagesListNode
import io.element.android.features.messages.impl.pinned.list.PinnedMessagesListPresenter
import io.element.android.features.messages.impl.timeline.TimelineController
import io.element.android.features.messages.impl.timeline.di.TimelineItemPresenterFactories
import io.element.android.features.poll.api.create.CreatePollEntryPoint
import io.element.android.libraries.architecture.AssistedNodeFactory
import io.element.android.libraries.architecture.BaseFlowNode
import io.element.android.libraries.architecture.NodeFactoriesBindings
import io.element.android.libraries.architecture.childNode
import io.element.android.libraries.di.DaggerComponentOwner
import io.element.android.libraries.matrix.api.MatrixClient
import io.element.android.libraries.matrix.api.core.EventId
import io.element.android.libraries.matrix.api.permalink.PermalinkParser
import io.element.android.libraries.matrix.api.room.MatrixRoom
import io.element.android.libraries.matrix.api.room.MatrixRoomMembersState
import io.element.android.libraries.matrix.ui.messages.RoomMemberProfilesCache
import io.element.android.libraries.mediaplayer.api.MediaPlayer
import io.element.android.libraries.textcomposer.mentions.MentionSpanTheme
import io.element.android.libraries.ui.strings.CommonStrings
import io.element.android.services.analytics.api.AnalyticsService
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class FinalNavigationRuntimeTest {
    @get:Rule val compose = createAndroidComposeRule<ComponentActivity>()

    private class TestHost(
        override val daggerComponent: NodeFactoriesBindings,
        private val create: (BuildContext) -> Node,
    ) : BaseFlowNode<String>(
        backstack = BackStack("session", savedStateMap = null),
        buildContext = BuildContext.root(savedStateMap = null),
        plugins = emptyList(),
    ), DaggerComponentOwner {
        override fun resolve(navTarget: String, buildContext: BuildContext): Node = create(buildContext)
    }

    private fun <T : Node> factory(create: (BuildContext, List<Plugin>) -> T) = object : AssistedNodeFactory<T> {
        override fun create(buildContext: BuildContext, plugins: List<Plugin>): T = create(buildContext, plugins)
    }

    private fun json(value: String): String = buildString {
        append('"')
        value.forEach { character ->
            when (character) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> append(character)
            }
        }
        append('"')
    }

    @Test
    fun open_loading_navigation() {
        val callbacks = mutableListOf<MessagesNode.Callback>()
        var pinnedNodeBuilds = 0
        val room = mockk<MatrixRoom>(relaxed = true)
        every { room.membersStateFlow } returns MutableStateFlow(MatrixRoomMembersState.Unknown)
        val messagesPresenterFactory = mockk<MessagesPresenter.Factory>()
        every { messagesPresenterFactory.create(any()) } returns mockk(relaxed = true)
        val pinnedPresenterFactory = mockk<PinnedMessagesListPresenter.Factory>()
        every { pinnedPresenterFactory.create(any()) } returns mockk(relaxed = true)
        val context = ApplicationProvider.getApplicationContext<Context>()
        val bindings = object : NodeFactoriesBindings {
            override fun nodeFactories(): Map<Class<out Node>, AssistedNodeFactory<*>> = mapOf(
                MessagesNode::class.java to factory { buildContext, plugins ->
                    callbacks += plugins.filterIsInstance<MessagesNode.Callback>().single()
                    MessagesNode(
                        buildContext = buildContext,
                        plugins = plugins,
                        room = room,
                        analyticsService = mockk<AnalyticsService>(relaxed = true),
                        presenterFactory = messagesPresenterFactory,
                        timelineItemPresenterFactories = mockk<TimelineItemPresenterFactories>(relaxed = true),
                        mediaPlayer = mockk<MediaPlayer>(relaxed = true),
                        permalinkParser = mockk<PermalinkParser>(relaxed = true),
                        context = context,
                    )
                },
                PinnedMessagesListNode::class.java to factory { buildContext, plugins ->
                    pinnedNodeBuilds++
                    PinnedMessagesListNode(
                        buildContext = buildContext,
                        plugins = plugins,
                        presenterFactory = pinnedPresenterFactory,
                        timelineItemPresenterFactories = mockk<TimelineItemPresenterFactories>(relaxed = true),
                        permalinkParser = mockk<PermalinkParser>(relaxed = true),
                    )
                },
            )
        }
        val host = TestHost(bindings) { buildContext ->
            MessagesFlowNode(
                buildContext = buildContext,
                plugins = listOf(MessagesEntryPoint.Params(MessagesEntryPoint.InitialTarget.Messages(null))),
                matrixClient = mockk<MatrixClient>(relaxed = true),
                sendLocationEntryPoint = mockk<SendLocationEntryPoint>(relaxed = true),
                showLocationEntryPoint = mockk<ShowLocationEntryPoint>(relaxed = true),
                createPollEntryPoint = mockk<CreatePollEntryPoint>(relaxed = true),
                elementCallEntryPoint = mockk<ElementCallEntryPoint>(relaxed = true),
                analyticsService = mockk<AnalyticsService>(relaxed = true),
                room = room,
                roomMemberProfilesCache = mockk<RoomMemberProfilesCache>(relaxed = true),
                mentionSpanTheme = mockk<MentionSpanTheme>(relaxed = true),
                pinnedEventsTimelineProvider = mockk<PinnedEventsTimelineProvider>(relaxed = true),
                timelineController = mockk<TimelineController>(relaxed = true),
            )
        }
        val helper = host.parentNodeTestHelper()
        try {
            helper.moveTo(Lifecycle.State.RESUMED)
            val flow = host.childNode("session") as MessagesFlowNode
            flow.backstack.onTransitionFinished(flow.backstack.elements.value.map { it.key })
            val callback = callbacks.single()
            val before = flow.backstack.activeElement
            val beforeKeys = flow.backstack.elements.value.map { it.key.toString() }
            var uiDispatches = 0
            val state = PinnedMessagesBannerState.Loaded(
                currentPinnedMessage = PinnedMessagesBannerItem(EventId("\$a"), AnnotatedString("Alpha")),
                currentPinnedMessageIndex = 0,
                loadedPinnedMessagesCount = 1,
                eventSink = {},
            )
            compose.setContent {
                PinnedMessagesBannerView(
                    state = state,
                    onClick = {},
                    onViewAllClick = {
                        uiDispatches++
                        callback.onViewAllPinnedEvents()
                    },
                )
            }
            val label = context.getString(CommonStrings.screen_room_pinned_banner_view_all_button_title)
            compose.onNodeWithText(label).assertIsDisplayed().performClick()
            compose.waitForIdle()
            flow.backstack.onTransitionFinished(flow.backstack.elements.value.map { it.key })
            val after = flow.backstack.activeElement
            val afterKeys = flow.backstack.elements.value.map { it.key.toString() }
            val parentRetained = beforeKeys.size == 1 && afterKeys.size == 2 && afterKeys.first() == beforeKeys.single()
            val beforeKeysJson = beforeKeys.joinToString(prefix = "[", postfix = "]") { json(it) }
            val afterKeysJson = afterKeys.joinToString(prefix = "[", postfix = "]") { json(it) }
            val reached = before == MessagesFlowNode.NavTarget.Messages(null) &&
                after == MessagesFlowNode.NavTarget.PinnedMessagesList && uiDispatches == 1 && pinnedNodeBuilds == 1 && parentRetained
            val output = File(System.getProperty("runtime.evidence.dir"), "open_loading_navigation.json")
            output.parentFile.mkdirs()
            output.writeText(
                """{
                  "evidenceSchemaVersion": 3,
                  "key": "open_loading",
                  "status": ${json(if (reached) "pass" else "fail")},
                  "observed": {"backstackTarget": ${json(after.toString())}, "pinnedNodeBuilds": $pinnedNodeBuilds},
                  "checkpoints": [
                    {"name": "common_start", "state": {
                      "screen": "room_timeline", "pinnedBannerVisible": true, "viewAllLabel": ${json(label)},
                      "flowClass": ${json(flow.javaClass.name)}, "backstackTarget": ${json(before.toString())},
                      "backstackKeys": $beforeKeysJson
                    }},
                    {"name": "post_event", "state": {
                      "event": "open_pinned_messages", "uiDispatches": $uiDispatches,
                      "backstackTarget": ${json(after.toString())}, "pinnedNodeBuilds": $pinnedNodeBuilds,
                      "backstackKeys": $afterKeysJson, "timelineParentRetained": $parentRetained
                    }}
                  ],
                  "navigation": {
                    "before": ${json(before.toString())}, "after": ${json(after.toString())},
                    "uiDispatches": $uiDispatches, "pinnedNodeBuilds": $pinnedNodeBuilds,
                    "bannerLabel": ${json(label)}, "flowClass": ${json(flow.javaClass.name)},
                    "callbackClass": ${json(callback.javaClass.name)}
                    ,"beforeKeys": $beforeKeysJson, "afterKeys": $afterKeysJson, "timelineParentRetained": $parentRetained
                  },
                  "invariantChecks": [{
                    "invariant": "the room timeline remains the navigation parent", "status": ${json(if (parentRetained) "pass" else "fail")},
                    "evidence": {"beforeKeys": $beforeKeysJson, "afterKeys": $afterKeysJson}
                  }]
                }
                """.trimIndent() + "\n"
            )
            assertEquals(MessagesFlowNode.NavTarget.Messages(null), before)
            assertEquals(MessagesFlowNode.NavTarget.PinnedMessagesList, after)
            assertEquals(1, uiDispatches)
            assertEquals(1, pinnedNodeBuilds)
            assertTrue("the room timeline remains the navigation parent", parentRetained)
        } finally {
            helper.moveTo(Lifecycle.State.DESTROYED)
        }
    }
}
