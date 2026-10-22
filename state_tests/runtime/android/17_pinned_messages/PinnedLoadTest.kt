package runtime
import io.element.android.features.messages.impl.pinned.PinnedEventsTimelineProvider
import io.element.android.features.messages.impl.pinned.list.*
import io.element.android.features.messages.impl.timeline.factories.TimelineItemsFactory
import io.element.android.features.messages.impl.actionlist.ActionListPresenter
import io.element.android.features.networkmonitor.api.NetworkMonitor
import io.element.android.libraries.featureflag.api.FeatureFlagService
import io.element.android.libraries.matrix.api.room.MatrixRoom
import io.element.android.libraries.matrix.api.core.EventId
import io.element.android.libraries.matrix.api.timeline.item.TimelineItemDebugInfo
import io.element.android.libraries.designsystem.utils.snackbar.SnackbarDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Test
import org.junit.Assert.*

class PinnedLoadTest {
    @Test fun load_failure() = runTest {
        val room = MatrixRoom()
        val provider = PinnedEventsTimelineProvider(room, NetworkMonitor(), FeatureFlagService())
        provider.launchIn(backgroundScope)
        val nav = object : PinnedMessagesListNavigator {
            override fun onViewInTimelineClick(eventId: EventId) = error("Unexpected navigation")
            override fun onShowEventDebugInfoClick(eventId: EventId?, debugInfo: TimelineItemDebugInfo) = error("Unexpected navigation")
            override fun onForwardEventClick(eventId: EventId) = error("Unexpected navigation")
        }
        val presenter = PinnedMessagesListPresenter(nav, room, TimelineItemsFactory(), provider, SnackbarDispatcher(), ActionListPresenter.Factory())
        CompositionDriver(this) { presenter.present() }.use { driver ->
            Evidence.record("request_pending", "listState" to driver.state.toString(), "openPinnedTimelineCalls" to room.openCalls)
            assertEquals(PinnedMessagesListState.Loading, driver.state); assertEquals(1, room.openCalls)
            room.completion.complete(Result.failure(Exception("SDK timeline unavailable"))); driver.flush()
            Evidence.record("request_failed", "listState" to driver.state.toString(), "openPinnedTimelineCalls" to room.openCalls)
            Evidence.observe("listState" to if(driver.state == PinnedMessagesListState.Failed) "failed" else driver.state.toString(),
                "emptyStateVisible" to (driver.state == PinnedMessagesListState.Empty), "errorVisible" to (driver.state == PinnedMessagesListState.Failed))
            Evidence.invariant("a load failure is never rendered as an empty collection", driver.state == PinnedMessagesListState.Failed && driver.state != PinnedMessagesListState.Empty, driver.state.toString())
        }
    }
}
