package io.element.android.features.messages.impl.timeline.model
import io.element.android.libraries.matrix.api.core.EventId
import io.element.android.libraries.matrix.api.timeline.item.TimelineItemDebugInfo
sealed interface TimelineItem {
    class Event(val eventId: EventId?, val transactionId: String?, val debugInfo: TimelineItemDebugInfo) : TimelineItem
}
