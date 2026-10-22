package runtime.task17.connected

import android.content.Context
import com.bumble.appyx.core.modality.BuildContext
import com.bumble.appyx.core.node.Node
import com.bumble.appyx.core.plugin.Plugin
import io.element.android.appnav.di.RoomComponentFactory
import io.element.android.libraries.architecture.AssistedNodeFactory
import io.element.android.libraries.architecture.NodeFactoriesBindings
import io.element.android.libraries.architecture.Presenter
import io.element.android.libraries.core.coroutine.CoroutineDispatchers
import io.element.android.libraries.core.meta.BuildMeta
import io.element.android.libraries.core.meta.BuildType
import io.element.android.libraries.featureflag.api.FeatureFlagService
import io.element.android.libraries.featureflag.api.FeatureFlags
import io.element.android.libraries.featureflag.impl.DefaultFeatureFlagService
import io.element.android.libraries.featureflag.impl.PreferencesFeatureFlagProvider
import io.element.android.libraries.matrix.api.MatrixClient
import io.element.android.libraries.matrix.api.room.MatrixRoom
import io.element.android.libraries.matrix.api.core.UserId
import io.element.android.libraries.matrix.api.verification.SessionVerificationService
import io.element.android.libraries.preferences.api.store.SessionPreferencesStore
import io.element.android.libraries.preferences.impl.store.DefaultSessionPreferencesStore
import kotlinx.coroutines.*
import kotlin.reflect.*
import kotlin.reflect.full.*

/** Actual constructors and DI aliases only. Missing bindings throw, never supply feature states. */
class Task17ProductionBindings(context: Context, scope: CoroutineScope, val sdk: Task17SdkInputs) {
    val construction = mutableListOf<Map<String, Any?>>()
    val graphs = mutableListOf<Task17ConstructorGraph>()
    private val platform = mapOf<KClass<*>, Any>(Context::class to context, CoroutineScope::class to scope,
        CoroutineDispatchers::class to CoroutineDispatchers(Dispatchers.IO, Dispatchers.Default, Dispatchers.Main),
        MatrixClient::class to sdk.client, MatrixRoom::class to sdk.room, UserId::class to sdk.userId,
        SessionVerificationService::class to sdk.client.sessionVerificationService(),
        SessionPreferencesStore::class to DefaultSessionPreferencesStore(context, sdk.userId, scope))
    private val build = BuildMeta(BuildType.DEBUG, true, "Element X", "Element X", "Element", "io.element.android.x",
        false, false, "runtime-source-parameterized", 1, "not-a-ref-inference", "", "Gplay", "gplay")
    private val flags = DefaultFeatureFlagService(setOf(PreferencesFeatureFlagProvider(context, build)), build)

    suspend fun configureExistingFeatureFlag() {
        check(flags.setFeatureEnabled(FeatureFlags.PinnedEvents, true)) { "Original feature-flag store refused setup" }
    }

    private fun graph(): Task17ConstructorGraph = Task17ConstructorGraph(construction).also { graph ->
        graphs += graph
        graph.values.putAll(platform)
        graph.values[BuildMeta::class] = build
        graph.values[FeatureFlagService::class] = flags
        val aliases = mapOf(
            "io.element.android.features.preferences.api.PreferencesEntryPoint" to "io.element.android.features.preferences.impl.DefaultPreferencesEntryPoint",
            "io.element.android.features.createroom.api.CreateRoomEntryPoint" to "io.element.android.features.createroom.impl.DefaultCreateRoomEntryPoint",
            "io.element.android.features.securebackup.api.SecureBackupEntryPoint" to "io.element.android.features.securebackup.impl.DefaultSecureBackupEntryPoint",
            "io.element.android.features.userprofile.api.UserProfileEntryPoint" to "io.element.android.features.userprofile.impl.DefaultUserProfileEntryPoint",
            "io.element.android.features.ftue.api.FtueEntryPoint" to "io.element.android.features.ftue.impl.DefaultFtueEntryPoint",
            "io.element.android.features.roomdirectory.api.RoomDirectoryEntryPoint" to "io.element.android.features.roomdirectory.impl.DefaultRoomDirectoryEntryPoint",
            "io.element.android.features.share.api.ShareEntryPoint" to "io.element.android.features.share.impl.DefaultShareEntryPoint",
            "io.element.android.features.logout.api.LogoutEntryPoint" to "io.element.android.features.logout.impl.DefaultLogoutEntryPoint",
            "io.element.android.features.joinroom.api.JoinRoomEntryPoint" to "io.element.android.features.joinroom.impl.DefaultJoinRoomEntryPoint",
            "io.element.android.features.roomaliasesolver.api.RoomAliasResolverEntryPoint" to "io.element.android.features.roomaliasesolver.impl.DefaultRoomAliasResolverEntryPoint",
            "io.element.android.features.call.api.ElementCallEntryPoint" to "io.element.android.features.call.impl.DefaultElementCallEntryPoint",
            "io.element.android.features.location.api.SendLocationEntryPoint" to "io.element.android.features.location.impl.DefaultSendLocationEntryPoint",
            "io.element.android.features.location.api.ShowLocationEntryPoint" to "io.element.android.features.location.impl.DefaultShowLocationEntryPoint",
            "io.element.android.features.poll.api.create.CreatePollEntryPoint" to "io.element.android.features.poll.impl.DefaultCreatePollEntryPoint",
            "io.element.android.features.lockscreen.api.LockScreenService" to "io.element.android.features.lockscreen.impl.DefaultLockScreenService",
            "io.element.android.libraries.permissions.api.PermissionStateProvider" to "io.element.android.libraries.permissions.impl.DefaultPermissionStateProvider",
            "io.element.android.services.analytics.api.AnalyticsService" to "io.element.android.services.analytics.impl.DefaultAnalyticsService",
            "io.element.android.features.messages.api.MessagesEntryPoint" to "io.element.android.features.messages.impl.DefaultMessagesEntryPoint",
            "io.element.android.features.roomdetails.api.RoomDetailsEntryPoint" to "io.element.android.features.roomdetails.impl.DefaultRoomDetailsEntryPoint",
            "io.element.android.features.roomlist.api.RoomListEntryPoint" to "io.element.android.features.roomlist.impl.DefaultRoomListEntryPoint",
            "io.element.android.features.ftue.api.state.FtueService" to "io.element.android.features.ftue.impl.state.DefaultFtueService",
            "io.element.android.features.networkmonitor.api.NetworkMonitor" to "io.element.android.features.networkmonitor.impl.DefaultNetworkMonitor",
            "io.element.android.services.appnavstate.api.AppNavigationStateService" to "io.element.android.services.appnavstate.impl.DefaultAppNavigationStateService",
            "io.element.android.services.appnavstate.api.AppForegroundStateService" to "io.element.android.services.appnavstate.impl.DefaultAppForegroundStateService",
            "io.element.android.libraries.preferences.api.store.SessionPreferencesStore" to "io.element.android.libraries.preferences.impl.store.DefaultSessionPreferencesStore",
            "io.element.android.libraries.preferences.api.store.AppPreferencesStore" to "io.element.android.libraries.preferences.impl.store.DefaultAppPreferencesStore",
            "io.element.android.libraries.preferences.api.store.PreferenceDataStoreFactory" to "io.element.android.libraries.preferences.impl.store.DefaultPreferencesDataStoreFactory",
            "io.element.android.libraries.matrix.api.permalink.PermalinkParser" to "io.element.android.libraries.matrix.impl.permalink.DefaultPermalinkParser",
            "io.element.android.libraries.matrix.api.permalink.PermalinkBuilder" to "io.element.android.libraries.matrix.impl.permalink.DefaultPermalinkBuilder",
            "io.element.android.libraries.textcomposer.mentions.MentionSpanUpdater" to "io.element.android.libraries.textcomposer.mentions.DefaultMentionSpanUpdater",
            "io.element.android.libraries.textcomposer.mentions.MentionSpanFormatter" to "io.element.android.libraries.textcomposer.mentions.DefaultMentionSpanFormatter",
            "io.element.android.features.messages.api.timeline.HtmlConverterProvider" to "io.element.android.features.messages.impl.timeline.DefaultHtmlConverterProvider",
            "io.element.android.features.messages.impl.actionlist.ActionListPresenter" to "io.element.android.features.messages.impl.actionlist.DefaultActionListPresenter",
            "io.element.android.features.messages.api.pinned.IsPinnedMessagesFeatureEnabled" to "io.element.android.features.messages.impl.pinned.DefaultIsPinnedMessagesFeatureEnabled",
            "io.element.android.services.toolbox.api.strings.StringProvider" to "io.element.android.services.toolbox.impl.strings.AndroidStringProvider",
            "io.element.android.services.toolbox.api.sdk.BuildVersionSdkIntProvider" to "io.element.android.services.toolbox.impl.sdk.DefaultBuildVersionSdkIntProvider",
            "io.element.android.libraries.androidutils.clipboard.ClipboardHelper" to "io.element.android.libraries.androidutils.clipboard.DefaultClipboardHelper",
            "io.element.android.libraries.mediaplayer.api.MediaPlayer" to "io.element.android.libraries.mediaplayer.impl.DefaultMediaPlayer",
        )
        aliases.forEach { (api, implementation) ->
            val a = runCatching { Class.forName(api).kotlin }.getOrNull()
            val b = runCatching { Class.forName(implementation).kotlin }.getOrNull()
            if (a != null && b != null) graph.aliases[a] = b
        }
        val names = listOf("pinned.banner.PinnedMessagesBannerPresenter", "typing.TypingNotificationPresenter",
            "timeline.components.customreaction.CustomReactionPresenter", "timeline.components.reactionsummary.ReactionSummaryPresenter",
            "timeline.components.receipt.bottomsheet.ReadReceiptBottomSheetPresenter", "voicemessages.composer.VoiceMessageComposerPresenter")
        names.forEach { name ->
            val klass = runCatching { Class.forName("io.element.android.features.messages.impl.$name").kotlin }.getOrNull()
            if (klass != null && !klass.java.isInterface) {
                val state = klass.allSupertypes.singleOrNull { it.classifier == Presenter::class }
                    ?.arguments?.single()?.type?.classifier as? KClass<*>
                if (state != null) graph.presenters[state] = klass
            }
        }
    }

    val sessionGraph = graph()
    private val nodeNames = listOf(
        "io.element.android.appnav.LoggedInFlowNode", "io.element.android.appnav.LoggedInFlowNode\$PlaceholderNode",
        "io.element.android.appnav.loggedin.LoggedInNode", "io.element.android.appnav.room.RoomFlowNode",
        "io.element.android.appnav.room.joined.JoinedRoomFlowNode", "io.element.android.appnav.room.joined.JoinedRoomLoadedFlowNode",
        "io.element.android.features.messages.impl.MessagesFlowNode", "io.element.android.features.messages.impl.MessagesNode",
        "io.element.android.features.messages.impl.pinned.list.PinnedMessagesListNode",
        "io.element.android.features.roomdetails.impl.RoomDetailsFlowNode", "io.element.android.features.roomdetails.impl.RoomDetailsNode",
        "io.element.android.features.roomlist.impl.RoomListFlowNode", "io.element.android.features.roomlist.impl.RoomListNode",
    )

    fun nodes(graph: Task17ConstructorGraph): NodeFactoriesBindings = object : NodeFactoriesBindings {
        override fun nodeFactories(): Map<Class<out Node>, AssistedNodeFactory<*>> = nodeNames.mapNotNull { name ->
            val klass = runCatching { Class.forName(name).asSubclass(Node::class.java) }.getOrNull() ?: return@mapNotNull null
            klass to object : AssistedNodeFactory<Node> {
                override fun create(buildContext: BuildContext, plugins: List<Plugin>): Node =
                    graph.make(klass.kotlin.createType(), mapOf("buildContext" to buildContext, "plugins" to plugins)) as Node
            }
        }.toMap()
    }

    init {
        sessionGraph.values[RoomComponentFactory::class] = object : RoomComponentFactory {
            override fun create(room: MatrixRoom): Any {
                check(room === sdk.room) { "Original room-component input differs from controlled SDK room" }
                // A replacement room gets a fresh real room scope, not a shared detached presenter.
                return nodes(graph())
            }
        }
    }
}
