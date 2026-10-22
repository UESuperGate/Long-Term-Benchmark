package runtime.task17.connected

import androidx.compose.runtime.*
import androidx.compose.runtime.tooling.CompositionData
import androidx.compose.runtime.tooling.LocalInspectionTables
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.tooling.data.*
import io.element.android.features.messages.impl.MessagesState
import io.element.android.features.messages.impl.timeline.model.TimelineItem
import io.element.android.features.messages.impl.timeline.model.event.TimelineItemTextBasedContent

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
    private fun activeTables() = tables.filterNot { it.isEmpty }
    private fun allGroups(): List<Group> = activeTables().flatMap { groups(it.asTree()) }
    private fun surfaceGroups(primary: String, fallback: String): List<Group> {
        val all = allGroups()
        return all.filter { it.name == primary }.ifEmpty { all.filter { it.name == fallback } }
    }
    private inline fun <reified T> values(groups: List<Group>): List<T> = groups.flatMap { group ->
        group.parameters.mapNotNull { it.value as? T }.plus(group.data.filterIsInstance<T>())
    }.distinctBy { System.identityHashCode(it) }
    private inline fun <reified T> arguments(function: String): List<T> = activeTables().flatMap { groups(it.asTree()) }
        .filter { it.name == function }.flatMap { it.parameters.map { p -> p.value } }
        .filterIsInstance<T>().distinctBy { System.identityHashCode(it) }

    fun renderedSurface(): String? {
        val names = allGroups().mapNotNull { it.name }.toSet()
        val messages = names.any { it == "MessagesView" || it == "MessagesViewContent" }
        val pinned = names.any { it == "PinnedMessagesListView" || it == "PinnedMessagesListContent" }
        return when {
            messages && !pinned -> "room_timeline"
            pinned && !messages -> "pinned_messages"
            else -> null
        }
    }

    fun messages(): MessagesState {
        val all = allGroups()
        val candidates = values<MessagesState>(surfaceGroups("MessagesView", "MessagesViewContent"))
        if (candidates.size == 1) return candidates.single()
        val details = all.filter { it.name?.contains("Messages", ignoreCase = true) == true }.map { group ->
            mapOf(
                "name" to group.name,
                "parameterTypes" to group.parameters.map { it.value?.javaClass?.name },
                "dataTypes" to group.data.map { it?.javaClass?.name },
            )
        }
        error("Actual rendered MessagesView parameter is not unambiguous: candidates=${candidates.size}, " +
            "namedGroups=${all.mapNotNull { it.name }.distinct()}, messageGroups=$details")
    }
    fun pinned(): Any = values<Any>(surfaceGroups("PinnedMessagesListView", "PinnedMessagesListContent"))
        .filter { it.javaClass.name.startsWith("io.element.android.features.messages.impl.pinned.list.PinnedMessagesListState") }
        .singleOrNull()
        ?: error("Actual rendered PinnedMessagesListView parameter is not unambiguous")

    fun renderedEvents(surface: String): List<Map<String, String?>> {
        val roots = when (surface) {
            "PinnedMessagesListView" -> surfaceGroups(surface, "PinnedMessagesListContent")
            else -> allGroups().filter { it.name == surface }
        }
        check(roots.size == 1) { "Original rendered surface group is not unambiguous: $surface" }
        val descendants = groups(roots.single())
        val eventGroups = allGroups().filter { it.name == "TimelineItemEventContentViewWrapper" }.ifEmpty {
            descendants.filter { it.name == "TimelineItemRow" }
        }
        return eventGroups.flatMap { group ->
            group.parameters.map { it.value }.filterIsInstance<TimelineItem.Event>()
                .distinctBy { System.identityHashCode(it) }.map { event ->
                    mapOf("eventId" to event.eventId?.value,
                        "body" to (event.content as? TimelineItemTextBasedContent)?.body)
                }
        }.distinctBy { it["eventId"] }
    }

    fun renderedEventIds(surface: String) = renderedEvents(surface).mapNotNull { it["eventId"] }
}
