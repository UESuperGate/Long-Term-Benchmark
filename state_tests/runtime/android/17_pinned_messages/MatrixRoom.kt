package io.element.android.libraries.matrix.api.room
import io.element.android.libraries.matrix.api.timeline.Timeline
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
class MatrixRoom {
    var openCalls = 0
    val completion = CompletableDeferred<Result<Timeline>>()
    val syncUpdateFlow = MutableStateFlow(0L)
    val membersStateFlow = MutableStateFlow(MembersState())
    val displayName = "Room"
    suspend fun pinnedEventsTimeline(): Result<Timeline> { openCalls++; return completion.await() }
}
val MatrixRoom.isDm: Boolean get() = false
class MembersState
fun MembersState.roomMembers(): List<Any>? = emptyList()
