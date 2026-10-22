package io.element.android.libraries.matrix.api.timeline
import io.element.android.libraries.matrix.api.core.EventId
import kotlinx.coroutines.flow.MutableStateFlow
class Timeline {
    val timelineItems = MutableStateFlow<List<Any>>(emptyList())
    suspend fun unpinEvent(eventId: EventId): Result<Unit> = error("Unexercised boundary")
    suspend fun redactEvent(eventId: EventId?, transactionId: String?, reason: String?): Result<Unit> = error("Unexercised boundary")
    fun close() = Unit
}
