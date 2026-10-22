package io.element.android.features.messages.impl.timeline.factories
import io.element.android.features.messages.impl.timeline.model.TimelineItem
import kotlinx.collections.immutable.ImmutableList
import kotlinx.coroutines.flow.StateFlow
// Successful item mapping is intentionally unsupported; it cannot yield scored outcomes.
class TimelineItemsFactory {
    val timelineItems: StateFlow<ImmutableList<TimelineItem>> get() = error("Production timeline item mapper not linked")
    suspend fun replaceWith(timelineItems: List<Any>, roomMembers: List<Any>): Unit = error("Production timeline item mapper not linked")
}
