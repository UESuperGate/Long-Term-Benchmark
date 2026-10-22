package runtime.task17.connected

import io.mockk.*
import io.element.android.libraries.matrix.api.core.RoomId
import io.element.android.libraries.matrix.api.core.UserId
import kotlinx.coroutines.*
import org.matrix.rustcomponents.sdk.*
import uniffi.wysiwyg_composer.MentionDetector
import uniffi.wysiwyg_composer.newMentionDetector
import java.util.concurrent.CopyOnWriteArrayList

/** All doubles are below the application bridge, in the FFI SDK namespace. */
class Task17SdkInputs(val episode: String, scope: CoroutineScope) {
    val calls = CopyOnWriteArrayList<Map<String, Any?>>()
    val audit = Task17LeafAudit()
    private val excludedEventFilter = audit.watch(mockk<TimelineEventTypeFilter>())
    private val mentionDetector = audit.watch(mockk<MentionDetector>())
    private var eventFilterFactoryMocked = false
    private var mentionDetectorFactoryMocked = false
    val roomId = RoomId("!pinned-runtime:example.org")
    val userId = UserId("@runtime:example.org")
    var allowPinUnpin = true
    val serverPinnedEventIds: List<String> get() = pinned.messages.map { it.eventId }.reversed()
    val sdkCacheEventIds: List<String> get() = pinned.messages.map { it.eventId }
    @Synchronized fun record(method: String, values: Map<String, Any?> = emptyMap()) {
        calls += mapOf("sequence" to calls.size, "episode" to episode,
            "boundary" to "org.matrix.rustcomponents.sdk", "method" to method) + values
    }
    private val input = listOf(Task17ServerMessage("\$b", "Beta"), Task17ServerMessage("\$a", "Alpha"))
    val pinned = Task17LeafTimeline("pinned", audit, ::record, input)
    val live = Task17LeafTimeline("live", audit, ::record, input)
    val focusWindows = mutableListOf<Task17LeafTimeline>()
    private val openGate = CompletableDeferred<Timeline>()
    val innerRoom = audit.watch(mockk<Room>())
    val roomListItem = audit.watch(mockk<RoomListItem>())
    private val infoListeners = CopyOnWriteArrayList<RoomInfoListener>()
    lateinit var client: io.element.android.libraries.matrix.impl.RustMatrixClient
        private set
    fun hasBoundClient() = this::client.isInitialized
    val session = Task17LeafSession(audit, ::record, userId.value, innerRoom, roomListItem)
    var failUnpin: Boolean
        get() = pinned.failUnpin
        set(value) { pinned.failUnpin = value }

    init {
        // Preserve the production factory call while controlling its Rust-SDK leaf result.
        mockkObject(TimelineEventTypeFilter.Companion)
        eventFilterFactoryMocked = true
        every { TimelineEventTypeFilter.exclude(any()) } answers {
            record("sdk.TimelineEventTypeFilter.exclude", mapOf("eventTypeCount" to firstArg<List<*>>().size))
            excludedEventFilter
        }
        // The Android artifact has no macOS Rust dylib. Keep the production
        // converter/provider and isolate only its external UniFFI leaf.
        mockkStatic("uniffi.wysiwyg_composer.Wysiwyg_composerKt")
        mentionDetectorFactoryMocked = true
        every { newMentionDetector() } answers {
            audit.receipts += mapOf("operation" to "uniffi_factory", "method" to "newMentionDetector")
            mentionDetector
        }
        every { mentionDetector.isMention(any()) } answers {
            audit.receipts += mapOf("operation" to "uniffi_call", "method" to "MentionDetector.isMention",
                "url" to firstArg<String>())
            false
        }
        every { mentionDetector.close() } answers {
            audit.receipts += mapOf("operation" to "uniffi_close", "method" to "MentionDetector.close")
        }
        every { mentionDetector.destroy() } answers {
            audit.receipts += mapOf("operation" to "uniffi_destroy", "method" to "MentionDetector.destroy")
        }
        every { innerRoom.id() } returns roomId.value
        every { innerRoom.ownUserId() } returns userId.value
        every { innerRoom.displayName() } returns "Pinned runtime"
        every { innerRoom.rawName() } returns "Pinned runtime"
        every { innerRoom.topic() } returns null
        every { innerRoom.avatarUrl() } returns null
        every { innerRoom.isEncrypted() } returns false
        every { innerRoom.isDirect() } returns false
        every { innerRoom.isPublic() } returns false
        every { innerRoom.isSpace() } returns false
        every { innerRoom.canonicalAlias() } returns null
        every { innerRoom.alternativeAliases() } returns emptyList()
        every { innerRoom.activeMembersCount() } returns 3uL
        every { innerRoom.joinedMembersCount() } returns 3uL
        coEvery { innerRoom.timeline() } returns live.timeline
        coEvery { innerRoom.roomInfo() } answers { roomInfo() }
        every { innerRoom.subscribeToRoomInfoUpdates(any()) } answers {
            val listener = firstArg<RoomInfoListener>()
            infoListeners += listener
            audit.task("room-info") { infoListeners.remove(listener) }
        }
        every { innerRoom.subscribeToTypingNotifications(any()) } answers {
            firstArg<TypingNotificationsListener>().call(emptyList())
            audit.task("typing")
        }
        coEvery { innerRoom.pinnedEventsTimeline(any(), any()) } coAnswers {
            record("sdk.Room.pinnedEventsTimeline", mapOf("sdkRoomId" to System.identityHashCode(innerRoom),
                "internalIdPrefix" to firstArg<String>(), "maxEventsToLoad" to secondArg<Short>().toUShort().toInt()))
            openGate.await()
        }
        coEvery { innerRoom.timelineFocusedOnEvent(any(), any(), any()) } answers {
            val id = firstArg<String>()
            record("sdk.Room.timelineFocusedOnEvent", mapOf("eventId" to id,
                "sdkRoomId" to System.identityHashCode(innerRoom), "context" to secondArg<Short>().toUShort().toInt(),
                "internalIdPrefix" to thirdArg<String>()))
            Task17LeafTimeline("focus:$id", audit, ::record, input).also { focusWindows += it }.timeline
        }
        coEvery { innerRoom.canUserPinUnpin(any()) } answers {
            record("sdk.Room.canUserPinUnpin", mapOf("userId" to firstArg<String>(), "allowed" to allowPinUnpin))
            allowPinUnpin
        }
        coEvery { innerRoom.canUserSendMessage(any(), any()) } returns true
        coEvery { innerRoom.canUserRedactOwn(any()) } returns false
        coEvery { innerRoom.canUserRedactOther(any()) } returns false
        coEvery { innerRoom.canUserInvite(any()) } returns false
        coEvery { innerRoom.canUserSendState(any(), any()) } returns false
        coEvery { innerRoom.suggestedRoleForUser(any()) } returns uniffi.matrix_sdk.RoomMemberRole.USER
        coEvery { innerRoom.members() } answers { members() }
        coEvery { innerRoom.membersNoSync() } answers { members() }
        coEvery { innerRoom.setUnreadFlag(any()) } returns Unit
        coEvery { innerRoom.typingNotice(any()) } returns Unit
        coEvery { innerRoom.loadComposerDraft() } returns null
        coEvery { innerRoom.clearComposerDraft() } returns Unit
        coEvery { innerRoom.markAsRead(any()) } returns Unit
        every { innerRoom.enableSendQueue(any()) } returns Unit
        every { innerRoom.close() } answers { record("sdk.Room.close"); Unit }
        every { innerRoom.destroy() } answers { record("sdk.Room.destroy"); Unit }
        every { roomListItem.isTimelineInitialized() } returns true
        coEvery { roomListItem.fullRoom() } returns innerRoom
        every { roomListItem.avatarUrl() } returns null
        every { roomListItem.close() } returns Unit
        every { roomListItem.destroy() } returns Unit
        pinned.onServerChange = { infoListeners.forEach { it.call(roomInfo()) } }
    }

    fun bindClient(value: io.element.android.libraries.matrix.impl.RustMatrixClient) {
        check(!this::client.isInitialized)
        client = value
    }
    fun emptyServerCollection() { pinned.setInitialMessages(emptyList()) }
    fun completeOpen(failure: Boolean = false) {
        check(calls.any { it["method"] == "sdk.Room.pinnedEventsTimeline" }) { "Response before original RustMatrixRoom request" }
        record("server.pinnedTimelineComplete", mapOf("failure" to failure, "sdkTimelineId" to System.identityHashCode(pinned.timeline)))
        check(if (failure) openGate.completeExceptionally(IllegalStateException("controlled FFI load failure"))
            else openGate.complete(pinned.timeline))
    }
    fun hasPendingUnpin() = pinned.hasPendingUnpin()
    fun completeUnpin() = pinned.completeUnpin()
    fun assertComplete() {
        try {
            audit.assertComplete()
        } finally {
            if (eventFilterFactoryMocked) {
                unmockkObject(TimelineEventTypeFilter.Companion)
                eventFilterFactoryMocked = false
            }
            if (mentionDetectorFactoryMocked) {
                unmockkStatic("uniffi.wysiwyg_composer.Wysiwyg_composerKt")
                mentionDetectorFactoryMocked = false
            }
        }
    }

    private fun members(): RoomMembersIterator = audit.watch(mockk<RoomMembersIterator>()).also { iterator ->
        every { iterator.len() } returns 0u
        every { iterator.nextChunk(any()) } returns null
        every { iterator.close() } returns Unit
        every { iterator.destroy() } returns Unit
    }
    private fun roomInfo(): RoomInfo = audit.watch(mockk<RoomInfo>()).also { info ->
        every { info.id } returns roomId.value
        every { info.displayName } returns "Pinned runtime"
        every { info.rawName } returns "Pinned runtime"
        every { info.topic } returns null
        every { info.avatarUrl } returns null
        every { info.isDirect } returns false
        every { info.isPublic } returns false
        every { info.isSpace } returns false
        every { info.isTombstoned } returns false
        every { info.isFavourite } returns false
        every { info.canonicalAlias } returns null
        every { info.alternativeAliases } returns emptyList()
        every { info.membership } returns Membership.JOINED
        every { info.inviter } returns null
        every { info.heroes } returns emptyList()
        every { info.activeMembersCount } returns 3uL
        every { info.invitedMembersCount } returns 0uL
        every { info.joinedMembersCount } returns 3uL
        every { info.userPowerLevels } returns emptyMap()
        every { info.highlightCount } returns 0uL
        every { info.notificationCount } returns 0uL
        every { info.cachedUserDefinedNotificationMode } returns null
        every { info.hasRoomCall } returns false
        every { info.activeRoomCallParticipants } returns emptyList()
        every { info.pinnedEventIds } returns serverPinnedEventIds
    }
}
