package runtime.task17.connected

import io.mockk.*
import kotlinx.coroutines.CompletableDeferred
import org.matrix.rustcomponents.sdk.*
import uniffi.matrix_sdk_ui.LiveBackPaginationStatus

data class Task17ServerMessage(val eventId: String, val body: String)

/** Only the FFI listener/diff boundary. RustTimeline owns all mapping and postprocessing. */
class Task17LeafTimeline(val label: String, private val audit: Task17LeafAudit,
    private val record: (String, Map<String, Any?>) -> Unit,
    initial: List<Task17ServerMessage>,
) {
    var messages = initial
        private set
    private val listeners = java.util.concurrent.CopyOnWriteArrayList<TimelineListener>()
    private var pending: Pair<String, CompletableDeferred<Boolean>>? = null
    var failUnpin = false
    var onServerChange: (() -> Unit)? = null
    val timeline = audit.watch(mockk<Timeline>())

    init {
        coEvery { timeline.addListener(any()) } answers {
            val listener = firstArg<TimelineListener>()
            listeners += listener
            record("sdk.Timeline.addListener", mapOf("label" to label, "sdkTimelineId" to System.identityHashCode(timeline)))
            listener.onUpdate(listOf(reset()))
            audit.task("timeline:$label") { listeners.remove(listener) }
        }
        coEvery { timeline.fetchMembers() } answers { record("sdk.Timeline.fetchMembers", mapOf("label" to label)); Unit }
        coEvery { timeline.fetchDetailsForEvent(any()) } answers { record("sdk.Timeline.fetchDetailsForEvent", mapOf("eventId" to firstArg<String>())); Unit }
        coEvery { timeline.subscribeToBackPaginationStatus(any()) } answers {
            firstArg<PaginationStatusListener>().onUpdate(LiveBackPaginationStatus.Idle(true))
            audit.task("pagination:$label")
        }
        coEvery { timeline.paginateBackwards(any()) } returns true
        coEvery { timeline.focusedPaginateForwards(any()) } returns true
        coEvery { timeline.sendReadReceipt(any(), any()) } returns Unit
        coEvery { timeline.unpinEvent(any()) } coAnswers {
            val eventId = firstArg<String>()
            val gate = CompletableDeferred<Boolean>()
            synchronized(this@Task17LeafTimeline) {
                check(pending == null) { "Overlapping SDK requests" }
                pending = eventId to gate
            }
            record("sdk.Timeline.unpinEvent", mapOf("eventId" to eventId, "label" to label,
                "sdkTimelineId" to System.identityHashCode(timeline)))
            gate.await()
        }
        every { timeline.close() } answers { record("sdk.Timeline.close", mapOf("label" to label)); Unit }
        every { timeline.destroy() } answers { record("sdk.Timeline.destroy", mapOf("label" to label)); Unit }
    }

    @Synchronized fun hasPendingUnpin() = pending != null
    @Synchronized fun completeUnpin() {
        val (id, gate) = checkNotNull(pending) { "No original bridge SDK unpin request" }
        record("server.unpinComplete", mapOf("eventId" to id, "failure" to failUnpin))
        if (failUnpin) gate.completeExceptionally(IllegalStateException("controlled FFI unpin failure"))
        else {
            messages = messages.filterNot { it.eventId == id }
            record("server.pinnedItems", mapOf("eventIds" to messages.map { it.eventId }))
            listeners.forEach { it.onUpdate(listOf(reset())) }
            onServerChange?.invoke()
            check(gate.complete(true))
        }
        pending = null
    }

    fun setInitialMessages(values: List<Task17ServerMessage>) {
        check(listeners.isEmpty()) { "Initial SDK input cannot replace a subscribed production state" }
        messages = values
    }

    private fun reset(): TimelineDiff = audit.watch(mockk<TimelineDiff>()).also { diff ->
        val input = messages.map(::event)
        every { diff.change() } returns TimelineChange.RESET
        every { diff.reset() } returns input
        every { diff.destroy() } returns Unit
        every { diff.close() } returns Unit
        record("sdk.TimelineListener.reset", mapOf("label" to label, "eventIds" to messages.map { it.eventId },
            "bodies" to messages.map { it.body }, "sdkTimelineId" to System.identityHashCode(timeline)))
    }

    private fun event(input: Task17ServerMessage): TimelineItem {
        val item = audit.watch(mockk<TimelineItem>())
        val event = audit.watch(mockk<EventTimelineItem>())
        val content = audit.watch(mockk<TimelineItemContent>())
        val message = audit.watch(mockk<Message>())
        val debug = audit.watch(mockk<EventTimelineItemDebugInfo>())
        every { item.uniqueId() } returns "runtime-${input.eventId}"
        every { item.asEvent() } returns event
        every { item.asVirtual() } returns null
        every { item.close() } returns Unit
        every { item.destroy() } returns Unit
        every { event.eventId() } returns input.eventId
        every { event.transactionId() } returns null
        every { event.isEditable() } returns false
        every { event.canBeRepliedTo() } returns false
        every { event.isLocal() } returns false
        every { event.isOwn() } returns false
        every { event.isRemote() } returns true
        every { event.localSendState() } returns null
        every { event.reactions() } returns emptyList()
        every { event.readReceipts() } returns emptyMap()
        every { event.sender() } returns "@sender:example.org"
        every { event.senderProfile() } returns ProfileDetails.Ready("Sender", false, null)
        every { event.timestamp() } returns if (input.eventId == "\$a") 1uL else 2uL
        every { event.content() } returns content
        every { event.debugInfo() } returns debug
        every { event.origin() } returns null
        every { event.getShield(any()) } returns null
        every { event.close() } returns Unit
        every { event.destroy() } returns Unit
        every { debug.model } returns "runtime-${input.eventId}"
        every { debug.originalJson } returns null
        every { debug.latestEditJson } returns null
        every { content.kind() } returns TimelineItemContentKind.Message
        every { content.asMessage() } returns message
        every { content.close() } returns Unit
        every { content.destroy() } returns Unit
        every { message.msgtype() } returns MessageType.Text(TextMessageContent(input.body, null))
        every { message.inReplyTo() } returns null
        every { message.body() } returns input.body
        every { message.isEdited() } returns false
        every { message.isThreaded() } returns false
        every { message.close() } returns Unit
        every { message.destroy() } returns Unit
        return item
    }
}
