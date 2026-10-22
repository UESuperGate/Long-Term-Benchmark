package io.element.android.features.messages.impl.actionlist
import androidx.compose.runtime.Composable
import io.element.android.features.messages.impl.actionlist.model.TimelineItemActionPostProcessor
class ActionListState
class ActionListPresenter {
    @Composable fun present(): ActionListState = error("Production action presenter not linked")
    class Factory { fun create(postProcessor: TimelineItemActionPostProcessor) = ActionListPresenter() }
}
