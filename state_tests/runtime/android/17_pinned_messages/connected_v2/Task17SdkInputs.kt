package runtime.task17.connected

import io.element.android.libraries.matrix.api.MatrixClient
import io.element.android.libraries.matrix.api.core.*
import io.element.android.libraries.matrix.api.room.*
import io.element.android.libraries.matrix.api.timeline.*
import io.element.android.libraries.matrix.api.timeline.item.TimelineItemDebugInfo
import io.element.android.libraries.matrix.api.timeline.item.event.*
import io.element.android.libraries.matrix.test.FakeMatrixClient
import io.element.android.libraries.matrix.test.room.FakeMatrixRoom
import io.element.android.libraries.matrix.test.timeline.FakeTimeline
import kotlinx.collections.immutable.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.util.Optional

/** Only Matrix SDK inputs, streams and completions. No feature/UI state is supplied. */
class Task17SdkInputs(val episode: String, scope: CoroutineScope) {
    val calls = mutableListOf<Map<String, Any?>>()
    // TimelineItemsFactory iterates the SDK cache in reverse; preserve that real boundary.
    val items = MutableStateFlow<List<MatrixTimelineItem>>(listOf(event("\$b", "Beta"), event("\$a", "Alpha")))
    private val openGate = CompletableDeferred<Result<Timeline>>()
    var allowPinUnpin = true
    var failUnpin = false
    val roomId = RoomId("!pinned-runtime:example.org")
    val userId = UserId("@runtime:example.org")
    val info = MutableStateFlow(roomInfo())
    private fun record(method: String, vararg fields: Pair<String, Any?>) {
        calls += mapOf("sequence" to calls.size, "episode" to episode, "boundary" to "Matrix SDK",
            "method" to method, "thread" to Thread.currentThread().name) + fields.toMap()
    }

    val pinned: Timeline = object : Timeline by FakeTimeline(name = "controlled-pinned", timelineItems = items) {
        override suspend fun unpinEvent(eventId: EventId): Result<Boolean> {
            record("Timeline.unpinEvent", "eventId" to eventId.value, "timelineId" to System.identityHashCode(this))
            if (failUnpin) return Result.failure(IllegalStateException("controlled SDK unpin failure"))
            // Deliver a server-authoritative update only after the actual SDK request.
            items.value = items.value.filterNot { (it as? MatrixTimelineItem.Event)?.eventId == eventId }
            info.value = info.value.copy(pinnedEventIds = items.value.mapNotNull {
                (it as? MatrixTimelineItem.Event)?.eventId
            }.toPersistentList())
            record("server.pinnedItems", "eventIds" to items.value.mapNotNull { (it as? MatrixTimelineItem.Event)?.eventId?.value })
            return Result.success(true)
        }
    }
    private val liveItems = MutableStateFlow<List<MatrixTimelineItem>>(items.value)
    val live = FakeTimeline(name = "controlled-live", timelineItems = liveItems)
    private val delegate = FakeMatrixRoom(sessionId = userId, roomId = roomId, displayName = "Pinned runtime",
        liveTimeline = live, updateMembersResult = {}, subscribeToSyncLambda = {},
        canUserPinUnpinResult = { Result.success(allowPinUnpin) },
        canRedactOwnResult = { Result.success(false) }, canRedactOtherResult = { Result.success(false) },
        canUserSendMessageResult = { _, _ -> Result.success(true) },
        canUserJoinCallResult = { Result.success(false) })
    val room: MatrixRoom = object : MatrixRoom by delegate {
        override val roomInfoFlow: Flow<MatrixRoomInfo> = info
        override suspend fun pinnedEventsTimeline(): Result<Timeline> {
            record("MatrixRoom.pinnedEventsTimeline", "roomId" to System.identityHashCode(this),
                "requestId" to System.identityHashCode(openGate))
            return openGate.await()
        }
        override suspend fun timelineFocusedOnEvent(eventId: EventId): Result<Timeline> {
            record("MatrixRoom.timelineFocusedOnEvent", "eventId" to eventId.value,
                "roomId" to System.identityHashCode(this))
            return Result.success(FakeTimeline(name = "controlled-focus-${eventId.value}", timelineItems = liveItems))
        }
    }
    val client: MatrixClient = FakeMatrixClient(sessionId = userId, sessionCoroutineScope = scope).also {
        it.givenGetRoomResult(roomId, room)
        it.getRoomInfoFlowLambda = { requested ->
            check(requested == roomId) { "Unexpected room requested: $requested" }
            info.map { value -> Optional.of(value) }
        }
        it.setAllSendQueuesEnabledLambda = { enabled -> record("MatrixClient.setAllSendQueuesEnabled", "enabled" to enabled) }
        (it.sessionVerificationService() as io.element.android.libraries.matrix.test.verification.FakeSessionVerificationService)
            .givenVerifiedStatus(io.element.android.libraries.matrix.api.verification.SessionVerifiedStatus.Verified)
    }

    fun emptyServerCollection() {
        items.value = emptyList()
        info.value = info.value.copy(pinnedEventIds = persistentListOf())
        record("server.pinnedItems", "eventIds" to emptyList<String>())
    }

    fun completeOpen(failure: Boolean = false) {
        check(calls.any { it["method"] == "MatrixRoom.pinnedEventsTimeline" }) { "SDK response before real request" }
        record("server.pinnedTimelineComplete", "failure" to failure, "timelineId" to System.identityHashCode(pinned))
        check(openGate.complete(if (failure) Result.failure(IllegalStateException("controlled SDK load failure"))
            else Result.success(pinned))) { "SDK completion duplicated" }
    }

    private fun roomInfo() = MatrixRoomInfo(
        id = roomId, name = "Pinned runtime", rawName = "Pinned runtime", topic = null, avatarUrl = null,
        isPublic = false, isDirect = false, isSpace = false, isTombstoned = false, isFavorite = false,
        canonicalAlias = null, alternativeAliases = persistentListOf(), currentUserMembership = CurrentUserMembership.JOINED,
        inviter = null, activeMembersCount = 3, invitedMembersCount = 0, joinedMembersCount = 3,
        userPowerLevels = persistentMapOf(), highlightCount = 0, notificationCount = 0,
        userDefinedNotificationMode = null, hasRoomCall = false, activeRoomCallParticipants = persistentListOf(),
        heroes = persistentListOf(), pinnedEventIds = persistentListOf(EventId("\$a"), EventId("\$b")),
    )

    private fun event(id: String, body: String) = MatrixTimelineItem.Event(
        uniqueId = UniqueId("runtime-$id"),
        event = EventTimelineItem(eventId = EventId(id), transactionId = null, isEditable = false,
            canBeRepliedTo = false, isLocal = false, isOwn = false, isRemote = true, localSendState = null,
            reactions = persistentListOf(), receipts = persistentListOf(), sender = UserId("@sender:example.org"),
            senderProfile = ProfileTimelineDetails.Ready("Sender", false, null), timestamp = if (id == "\$a") 1L else 2L,
            content = MessageContent(body, null, false, false, TextMessageType(body, null)),
            debugInfo = TimelineItemDebugInfo("runtime-$id", null, null), origin = null, messageShield = null),
    )
}
