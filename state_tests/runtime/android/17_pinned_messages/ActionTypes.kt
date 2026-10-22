package io.element.android.features.messages.impl.actionlist.model
sealed interface TimelineItemAction {
    data object Redact : TimelineItemAction
    data object ViewSource : TimelineItemAction
    data object Forward : TimelineItemAction
    data object Unpin : TimelineItemAction
    data object ViewInTimeline : TimelineItemAction
}
interface TimelineItemActionPostProcessor { fun process(actions: List<TimelineItemAction>): List<TimelineItemAction> }
