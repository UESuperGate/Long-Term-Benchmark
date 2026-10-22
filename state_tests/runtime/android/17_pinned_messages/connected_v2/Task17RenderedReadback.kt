package runtime.task17.connected

import androidx.compose.runtime.*
import androidx.compose.runtime.tooling.CompositionData
import androidx.compose.runtime.tooling.LocalInspectionTables
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.tooling.data.*
import io.element.android.features.messages.impl.MessagesState
import io.element.android.features.messages.impl.timeline.model.TimelineItem

/** Read-only observation of production view arguments; never runs present() itself. */
@OptIn(InternalComposeApi::class, UiToolingDataApi::class)
class Task17RenderedReadback {
    private val tables = java.util.Collections.newSetFromMap(java.util.IdentityHashMap<CompositionData, Boolean>())

    @Composable fun Observe(content: @Composable () -> Unit) {
        check(!LocalInspectionMode.current) { "Preview is not production runtime" }
        currentComposer.collectParameterInformation()
        tables.add(currentComposer.compositionData)
        CompositionLocalProvider(LocalInspectionTables provides tables) { content() }
    }

    private fun groups(group: Group): List<Group> = listOf(group) + group.children.flatMap(::groups)
    private inline fun <reified T> arguments(function: String): List<T> = tables.flatMap { groups(it.asTree()) }
        .filter { it.name == function }.flatMap { it.parameters.map { p -> p.value } + it.data }
        .filterIsInstance<T>().distinctBy { System.identityHashCode(it) }

    fun messages(): MessagesState = arguments<MessagesState>("MessagesView").singleOrNull()
        ?: error("Actual rendered MessagesView parameter is not unambiguous")
    fun pinned(): Any = arguments<Any>("PinnedMessagesListView")
        .filter { it.javaClass.name.startsWith("io.element.android.features.messages.impl.pinned.list.PinnedMessagesListState") }
        .singleOrNull()
        ?: error("Actual rendered PinnedMessagesListView parameter is not unambiguous")

    fun renderedEventIds(surface: String): List<String> {
        val roots = tables.flatMap { groups(it.asTree()) }.filter { it.name == surface }
        check(roots.size == 1) { "Original rendered surface group is not unambiguous: $surface" }
        return groups(roots.single()).filter { it.name == "TimelineItemRow" }.flatMap { group ->
            (group.parameters.map { it.value } + group.data).filterIsInstance<TimelineItem.Event>()
                .distinctBy { System.identityHashCode(it) }.mapNotNull { it.eventId?.value }
        }.distinct()
    }
}
