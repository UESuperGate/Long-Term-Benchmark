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
import io.element.android.features.messages.impl.MessagesFlowNode
import io.element.android.features.messages.impl.MessagesNode
import io.element.android.features.messages.impl.MessagesPresenter
import io.element.android.features.messages.impl.pinned.banner.PinnedMessagesBannerItem
import io.element.android.features.messages.impl.pinned.banner.PinnedMessagesBannerState
import io.element.android.features.messages.impl.pinned.banner.PinnedMessagesBannerView
import io.element.android.features.messages.impl.timeline.TimelineController
import io.element.android.features.messages.impl.timeline.di.TimelineItemPresenterFactories
import io.element.android.features.poll.api.create.CreatePollEntryPoint
import io.element.android.libraries.architecture.*
import io.element.android.libraries.di.DaggerComponentOwner
import io.element.android.libraries.matrix.api.MatrixClient
import io.element.android.libraries.matrix.api.core.EventId
import io.element.android.libraries.matrix.api.room.MatrixRoom
import io.element.android.libraries.matrix.api.room.MatrixRoomMembersState
import io.element.android.libraries.matrix.api.permalink.PermalinkParser
import io.element.android.libraries.matrix.ui.messages.RoomMemberProfilesCache
import io.element.android.libraries.mediaplayer.api.MediaPlayer
import io.element.android.libraries.textcomposer.mentions.MentionSpanTheme
import io.element.android.libraries.ui.strings.CommonStrings
import io.element.android.services.analytics.api.AnalyticsService
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class BasePrefixRuntimeTest {
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

    @Test fun open_loading() = probe("open_loading")
    @Test fun load_failure() = probe("load_failure")
    @Test fun empty_success() = probe("empty_success")
    @Test fun filled_list() = probe("filled_list")
    @Test fun unpin_permission_denied() = probe("unpin_permission_denied")
    @Test fun unpin_permission_allowed() = probe("unpin_permission_allowed")
    @Test fun view_in_timeline() = probe("view_in_timeline")
    @Test fun unpin_success() = probe("unpin_success")
    @Test fun unpin_failure_recovery() = probe("unpin_failure_recovery")

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

    private fun probe(key: String) {
        val callbacks = mutableListOf<MessagesNode.Callback>()
        val room = mockk<MatrixRoom>(relaxed = true)
        every { room.membersStateFlow } returns MutableStateFlow(MatrixRoomMembersState.Unknown)
        val presenterFactory = mockk<MessagesPresenter.Factory>()
        every { presenterFactory.create(any()) } returns mockk(relaxed = true)
        val context = ApplicationProvider.getApplicationContext<Context>()
        val bindings = object : NodeFactoriesBindings {
            override fun nodeFactories(): Map<Class<out Node>, AssistedNodeFactory<*>> = mapOf(
                MessagesNode::class.java to factory { buildContext, plugins ->
                    callbacks += plugins.filterIsInstance<MessagesNode.Callback>().single()
                    MessagesNode(
                        buildContext = buildContext,
                        plugins = plugins,
                        room = room,
                        analyticsService = mockk(relaxed = true),
                        presenterFactory = presenterFactory,
                        timelineItemPresenterFactories = mockk<TimelineItemPresenterFactories>(relaxed = true),
                        mediaPlayer = mockk<MediaPlayer>(relaxed = true),
                        permalinkParser = mockk<PermalinkParser>(relaxed = true),
                        context = context,
                        timelineController = mockk<TimelineController>(relaxed = true),
                    )
                },
            )
        }
        val host = TestHost(bindings) { buildContext ->
            MessagesFlowNode(
                buildContext = buildContext,
                plugins = listOf(MessagesFlowNode.Inputs(focusedEventId = null)),
                matrixClient = mockk<MatrixClient>(relaxed = true),
                sendLocationEntryPoint = mockk<SendLocationEntryPoint>(relaxed = true),
                showLocationEntryPoint = mockk<ShowLocationEntryPoint>(relaxed = true),
                createPollEntryPoint = mockk<CreatePollEntryPoint>(relaxed = true),
                elementCallEntryPoint = mockk<ElementCallEntryPoint>(relaxed = true),
                analyticsService = mockk<AnalyticsService>(relaxed = true),
                room = room,
                roomMemberProfilesCache = mockk<RoomMemberProfilesCache>(relaxed = true),
                mentionSpanTheme = mockk<MentionSpanTheme>(relaxed = true),
            )
        }
        val helper = host.parentNodeTestHelper()
        try {
            helper.moveTo(Lifecycle.State.RESUMED)
            val flow = host.childNode("session") as MessagesFlowNode
            flow.backstack.onTransitionFinished(flow.backstack.elements.value.map { it.key })
            val callback = callbacks.single()
            val before = flow.backstack.activeElement
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
            val after = flow.backstack.activeElement
            assertEquals(1, uiDispatches)
            assertNotNull(before)
            assertEquals(before, after)
            assertEquals(MessagesFlowNode.NavTarget.Messages, after)
            val output = File(System.getProperty("runtime.evidence.dir"), "$key.json")
            output.parentFile.mkdirs()
            output.writeText(
                """{
                  "key": ${json(key)},
                  "status": "fail",
                  "reason": "The real base banner dispatched View all, but the immutable production flow kept the room timeline active and could not establish the pinned-list prefix.",
                  "checkpoints": [
                    {"name": "common_start", "state": {
                      "screen": "room_timeline", "pinnedBannerVisible": true, "viewAllLabel": ${json(label)},
                      "flowClass": ${json(flow.javaClass.name)}, "childClass": ${json(host.childNode("session")?.javaClass?.name.orEmpty())},
                      "backstackTarget": ${json(before.toString())}, "callbackClass": ${json(callback.javaClass.name)}
                    }},
                    {"name": "post_event", "state": {
                      "event": "open_pinned_messages", "uiDispatches": $uiDispatches,
                      "backstackTarget": ${json(after.toString())}, "screen": "room_timeline",
                      "pinnedListReachable": false
                    }}
                  ],
                  "observed": {"screen": "room_timeline", "pinnedListReachable": false},
                  "invariantChecks": [{
                    "invariant": "the room timeline remains the navigation parent",
                    "status": "pass",
                    "evidence": {"before": ${json(before.toString())}, "after": ${json(after.toString())}}
                  }]
                }
                """.trimIndent() + "\n"
            )
        } finally {
            helper.moveTo(Lifecycle.State.DESTROYED)
        }
    }
}
