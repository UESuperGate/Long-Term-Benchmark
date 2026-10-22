package runtime

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import com.google.gson.JsonParser
import io.element.android.compound.theme.ElementTheme
import io.element.android.features.messages.impl.actionlist.*
import io.element.android.features.messages.impl.actionlist.model.TimelineItemActionPostProcessor
import io.element.android.features.messages.impl.pinned.PinnedEventsTimelineProvider
import io.element.android.features.messages.impl.pinned.DefaultIsPinnedMessagesFeatureEnabled
import io.element.android.features.messages.impl.pinned.list.*
import io.element.android.features.messages.impl.timeline.factories.TimelineItemsFactory
import io.element.android.features.networkmonitor.api.NetworkMonitor
import io.element.android.features.networkmonitor.api.NetworkStatus
import io.element.android.libraries.architecture.AsyncData
import io.element.android.libraries.core.coroutine.CoroutineDispatchers
import io.element.android.libraries.designsystem.utils.snackbar.SnackbarDispatcher
import io.element.android.libraries.featureflag.api.FeatureFlagService
import io.element.android.libraries.matrix.api.core.RoomId
import io.element.android.libraries.matrix.api.room.*
import io.element.android.libraries.matrix.api.timeline.Timeline
import io.element.android.libraries.matrix.api.timeline.MatrixTimelineItem
import io.element.android.libraries.preferences.api.store.AppPreferencesStore
import io.element.android.libraries.ui.strings.CommonStrings
import kotlinx.collections.immutable.persistentListOf
import kotlinx.collections.immutable.persistentMapOf
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.collect
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.LooperMode
import runtime.foundation.EvidenceRobolectricRunner
import java.io.File
import java.lang.reflect.Proxy
import java.security.MessageDigest
import kotlin.coroutines.Continuation
import kotlin.coroutines.intrinsics.COROUTINE_SUSPENDED

@RunWith(EvidenceRobolectricRunner::class)
@Config(sdk = [36], qualifiers = "en-rUS-w411dp-h891dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@LooperMode(LooperMode.Mode.PAUSED)
class PinnedEmptyUiTest {
    @get:Rule val compose = createEmptyComposeRule()
    private val calls = mutableListOf<Map<String, Any?>>()
    private val unexpected = mutableListOf<String>()
    private val constructed = mutableListOf<String>()

    private fun port(type: Class<*>, block: (String, Array<out Any?>) -> Any?): Any =
        Proxy.newProxyInstance(type.classLoader, arrayOf(type)) { proxy, method, args ->
            when (method.name) {
                "equals" -> proxy === args?.firstOrNull()
                "hashCode" -> System.identityHashCode(proxy)
                "toString" -> "ControlledBoundary:${type.simpleName}"
                else -> {
                    val actual = args ?: emptyArray()
                    calls.add(mapOf("port" to type.name, "method" to method.name,
                        "args" to actual.filterNot { it is Continuation<*> }.map { it.toString() }))
                    block(method.name, actual)
                }
            }
        }

    private fun unexpected(message: String): Nothing {
        unexpected.add(message)
        error(message)
    }

    // Invoke real constructors. Unused interface ports fail on every method; no
    // factory/presenter state, service result, or constructor is substituted.
    private fun construct(type: Class<*>, context: Context, dispatchers: CoroutineDispatchers): Any {
        if (type == Context::class.java) return context
        if (type == CoroutineDispatchers::class.java) return dispatchers
        if (type.isInterface) return port(type) { name, _ -> unexpected("Unused port invoked: ${type.name}.$name") }
        check(type.name.startsWith("io.element.android.")) { "Unreviewed constructor ${type.name}" }
        val constructors = type.constructors.filterNot { it.isSynthetic }
        val constructor = constructors.singleOrNull { it.getAnnotation(javax.inject.Inject::class.java) != null }
            ?: constructors.single()
        constructed.add(type.name)
        return constructor.newInstance(*constructor.parameterTypes.map { construct(it, context, dispatchers) }.toTypedArray())
    }

    private fun pixels(activity: ComponentActivity, label: String): Map<String, Any> {
        fun owner(view: View): View? {
            if (view.javaClass.name == "androidx.compose.ui.platform.AndroidComposeView") return view
            if (view is ViewGroup) for (i in 0 until view.childCount) owner(view.getChildAt(i))?.let { return it }
            return null
        }
        val view = checkNotNull(owner(activity.window.decorView))
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        compose.runOnUiThread { view.draw(Canvas(bitmap)) }
        val file = File(System.getProperty("runtime.rendered.output"), "$label.png")
        file.parentFile.mkdirs()
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        return mapOf("path" to file.absolutePath, "bytes" to file.length(), "width" to bitmap.width, "height" to bitmap.height,
            "sha256" to MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) })
    }

    @Test fun empty_success() {
        val contract = JsonParser.parseString(File(System.getProperty("runtime.contract.path")).readText()).asJsonObject
        val spec = contract.getAsJsonArray("cases").single { it.asJsonObject["key"].asString == "empty_success" }.asJsonObject
        assertEquals("loading", spec.getAsJsonObject("given")["listState"].asString)
        assertEquals(0, spec.getAsJsonObject("given").getAsJsonArray("pinnedTimelineItems").size())
        val controller = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        val activity = controller.get()
        val dispatchers = CoroutineDispatchers(Dispatchers.Main.immediate, Dispatchers.Main.immediate, Dispatchers.Main.immediate)
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        var continuation: Continuation<Any?>? = null
        var openCalls = 0
        var timelineCloses = 0
        val sdkItems = MutableStateFlow<List<MatrixTimelineItem>>(emptyList())
        val timeline = port(Timeline::class.java) { name, _ ->
            when (name) {
                "getTimelineItems" -> sdkItems
                "close" -> { timelineCloses++; Unit }
                else -> unexpected("Timeline.$name")
            }
        } as Timeline
        val roomId = RoomId("!pinned-audit:example.org")
        val roomInfo = MutableStateFlow(MatrixRoomInfo(id = roomId, name = "Pinned audit", rawName = "Pinned audit", topic = null, avatarUrl = null,
            isPublic = true, isDirect = false, isSpace = false,
            isTombstoned = false, isFavorite = false, canonicalAlias = null, alternativeAliases = persistentListOf(),
            currentUserMembership = CurrentUserMembership.JOINED, inviter = null, activeMembersCount = 2L,
            invitedMembersCount = 0L, joinedMembersCount = 2L, userPowerLevels = persistentMapOf(),
            highlightCount = 0L, notificationCount = 0L, userDefinedNotificationMode = null,
            hasRoomCall = false, activeRoomCallParticipants = persistentListOf(),
            heroes = persistentListOf(), pinnedEventIds = persistentListOf()))
        val room = port(MatrixRoom::class.java) { name, args ->
            when {
                name.startsWith("pinnedEventsTimeline") -> {
                    check(continuation == null)
                    openCalls++
                    @Suppress("UNCHECKED_CAST")
                    val pending = args.last() as Continuation<Any?>
                    continuation = pending
                    COROUTINE_SUSPENDED
                }
                name == "getRoomInfoFlow" -> roomInfo
                name == "isDirect" -> roomInfo.value.isDirect
                name == "getActiveMemberCount" -> roomInfo.value.activeMembersCount
                name == "getDisplayName" -> checkNotNull(roomInfo.value.name)
                name == "getSyncUpdateFlow" -> MutableStateFlow(0L)
                name == "getMembersStateFlow" -> MutableStateFlow<MatrixRoomMembersState>(MatrixRoomMembersState.Unknown)
                name.startsWith("getRoomId") -> roomId.value
                name.startsWith("getSessionId") -> "@member:example.org"
                name.startsWith("canUserRedactOwn") || name.startsWith("canUserRedactOther") || name.startsWith("canUserPinUnpin") -> false
                else -> unexpected("MatrixRoom.$name")
            }
        } as MatrixRoom
        val flags = port(FeatureFlagService::class.java) { name, _ ->
            when (name) {
                "isFeatureEnabledFlow" -> MutableStateFlow(true)
                "isFeatureEnabled" -> true
                else -> unexpected("FeatureFlagService.$name")
            }
        } as FeatureFlagService
        val network = object : NetworkMonitor { override val connectivity = MutableStateFlow(NetworkStatus.Online) }
        val provider = PinnedEventsTimelineProvider(room, network, flags)
        val factory = construct(TimelineItemsFactory::class.java, activity, dispatchers) as TimelineItemsFactory
        val actionFactory = object : ActionListPresenter.Factory {
            override fun create(postProcessor: TimelineItemActionPostProcessor): ActionListPresenter =
                DefaultActionListPresenter(postProcessor,
                    port(AppPreferencesStore::class.java) { name, _ -> unexpected("Unexercised preferences.$name") } as AppPreferencesStore,
                    DefaultIsPinnedMessagesFeatureEnabled(flags), room)
        }
        val navigator = port(PinnedMessagesListNavigator::class.java) { name, _ -> unexpected("Navigation must not occur: $name") } as PinnedMessagesListNavigator
        val presenter = PinnedMessagesListPresenter(navigator, room, factory, provider, SnackbarDispatcher(), actionFactory)
        var observed: PinnedMessagesListState? = null
        val factoryEmissions = mutableListOf<Int>()
        val identities = mapOf("presenter" to System.identityHashCode(presenter), "factory" to System.identityHashCode(factory),
            "provider" to System.identityHashCode(provider), "timeline" to System.identityHashCode(timeline))
        fun snapshot(label: String) {
            val roots = compose.onAllNodes(isRoot(), useUnmergedTree = true)
            Evidence.record(label, "state" to observed.toString(), "providerState" to provider.timelineStateFlow.value.javaClass.simpleName,
                "identities" to identities, "sdkItemsCount" to sdkItems.value.size, "openCalls" to openCalls,
                "factoryEmissions" to factoryEmissions.toList(), "sdkCalls" to calls.toList(), "unexpected" to unexpected.toList(),
                "constructors" to constructed.toList(), "pixels" to pixels(activity, label),
                "semantics" to (0 until roots.fetchSemanticsNodes().size).joinToString("\n") { roots[it].printToString(maxDepth = 100) })
        }
        try {
            compose.runOnUiThread {
                scope.launch { factory.timelineItems.collect { factoryEmissions.add(it.size) } }
                provider.launchIn(scope)
                activity.setContent {
                    ElementTheme(darkTheme = false) {
                        val state = presenter.present()
                        SideEffect { observed = state }
                        PinnedMessagesListView(state, onBackClick = { unexpected("Back navigation") },
                            onEventClick = { unexpected("Event navigation") }, onUserDataClick = { unexpected("User navigation") },
                            onLinkClick = { unexpected("Link navigation") })
                    }
                }
            }
            compose.waitUntil(5000) { continuation != null && observed == PinnedMessagesListState.Loading }
            compose.waitForIdle()
            assertTrue(provider.timelineStateFlow.value is AsyncData.Loading)
            assertEquals(1, openCalls)
            assertTrue(factoryEmissions.isEmpty())
            compose.onNode(SemanticsMatcher.keyIsDefined(SemanticsProperties.ProgressBarRangeInfo)).assertIsDisplayed()
            val headline = activity.getString(CommonStrings.screen_pinned_timeline_empty_state_headline)
            val error = activity.getString(CommonStrings.error_failed_loading_messages)
            compose.onNodeWithText(headline).assertDoesNotExist()
            compose.onNodeWithText(error).assertDoesNotExist()
            Evidence.record("canonical_given", "given" to mapOf("listState" to "loading", "pinnedTimelineItems" to sdkItems.value),
                "event" to mapOf("name" to "timeline_load_completed"), "identities" to identities,
                "sdkCompletionHeld" to true, "fullAppNavigationClaimed" to false)
            snapshot("pending_original_ui")
            // A suspended Result-returning SDK method resumes with a boxed Result payload.
            compose.runOnUiThread { checkNotNull(continuation).resumeWith(Result.success(Result.success(timeline))) }
            Shadows.shadowOf(Looper.getMainLooper()).idle()
            compose.waitUntil(10000) {
                Shadows.shadowOf(Looper.getMainLooper()).idle()
                observed == PinnedMessagesListState.Empty && factoryEmissions.isNotEmpty()
            }
            compose.waitForIdle()
            compose.onNodeWithText(headline).assertIsDisplayed()
            compose.onNodeWithText(error).assertDoesNotExist()
            compose.onNode(SemanticsMatcher.keyIsDefined(SemanticsProperties.ProgressBarRangeInfo)).assertDoesNotExist()
            assertTrue(provider.timelineStateFlow.value is AsyncData.Success)
            assertSame(timeline, provider.timelineStateFlow.value.dataOrNull())
            assertEquals(listOf(0), factoryEmissions)
            assertTrue(unexpected.isEmpty())
            snapshot("empty_original_ui")
            Evidence.observe("listState" to "empty", "loadedPinnedMessagesCount" to factoryEmissions.last(),
                "failureVisible" to compose.onAllNodes(hasText(error)).fetchSemanticsNodes().isNotEmpty())
            Evidence.invariant("the empty state is a successful load",
                provider.timelineStateFlow.value is AsyncData.Success && observed == PinnedMessagesListState.Empty,
                "Original provider Success -> original factory emitted [] -> original presenter Empty -> original View empty headline; error absent")
        } finally {
            compose.runOnUiThread { scope.cancel() }
            Shadows.shadowOf(Looper.getMainLooper()).idle()
            controller.pause().stop().destroy()
        }
    }
}
