package evaluator.support

import android.app.Instrumentation
import android.content.Intent
import android.net.Uri
import android.view.accessibility.AccessibilityNodeInfo
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import evaluator.support.leaf.EvaluatorLeaf
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.OkHttpClient
import org.wordpress.android.fluxc.store.AccountStore
import org.wordpress.android.fluxc.utils.AppLogWrapper
import org.wordpress.android.networking.restapi.WpComApiClientProvider
import org.wordpress.android.support.common.ui.ConversationsSupportViewModel
import org.wordpress.android.support.unified.model.UnifiedConversation
import org.wordpress.android.support.unified.repository.UnifiedSupportRepository
import org.wordpress.android.support.unified.ui.SupportRuntimeOwnerActivity
import org.wordpress.android.support.unified.ui.SupportRuntimeOwnerDependencies
import org.wordpress.android.support.unified.ui.UnifiedSupportViewModel
import org.wordpress.android.support.unified.util.AttachmentStateValidator
import org.wordpress.android.support.unified.util.EncryptedAppLogsUploader
import org.wordpress.android.support.unified.util.TempAttachmentsUtil
import org.wordpress.android.util.EncryptedLogging
import org.wordpress.android.util.LogFileProviderWrapper
import org.wordpress.android.util.NetworkUtilsWrapper
import rs.wordpress.api.kotlin.WpComApiClient
import uniffi.wp_api.BotConversation
import uniffi.wp_api.BotMessage
import uniffi.wp_api.UnifiedConversationSummary
import java.io.File
import java.util.Date

private data class Check(val invariant: String, val passed: Boolean, val evidence: Any?)
private data class Outcome(
    val before: Any?,
    val after: Any?,
    val observed: Any?,
    val checks: List<Check>,
    val productionBodies: List<String>,
)

private class Fixture {
    val accountStore = AccountStore()
    val appLog = AppLogWrapper()
    val repository = UnifiedSupportRepository(appLog, WpComApiClientProvider(WpComApiClient()), Dispatchers.Default)
    val tempAttachments = TempAttachmentsUtil(
        Dispatchers.Default, OkHttpClient(), appLog, EvaluatorLeaf.application, accountStore
    )
    val viewModel = UnifiedSupportViewModel(
        accountStore,
        repository,
        tempAttachments,
        AttachmentStateValidator(EvaluatorLeaf.application, Dispatchers.Default),
        EncryptedAppLogsUploader(
            EncryptedLogging(), LogFileProviderWrapper(), appLog, Dispatchers.Default
        ),
        Dispatchers.Default,
        appLog,
        NetworkUtilsWrapper(),
    )
}

private class OwnerSession(
    private val instrumentation: Instrumentation,
    fixtureFactory: () -> Fixture = ::Fixture,
) : AutoCloseable {
    lateinit var fixture: Fixture
    val owner: SupportRuntimeOwnerActivity
        get() = requireNotNull(SupportRuntimeOwnerActivity.current)

    init {
        SupportRuntimeOwnerDependencies.factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                fixture = fixtureFactory()
                return fixture.viewModel as T
            }
        }
        val intent = Intent(instrumentation.targetContext, SupportRuntimeOwnerActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        instrumentation.startActivitySync(intent)
        instrumentation.waitForIdleSync()
    }

    fun event(block: SupportRuntimeOwnerActivity.() -> Unit) {
        instrumentation.runOnMainSync { owner.block() }
        instrumentation.waitForIdleSync()
    }

    override fun close() {
        instrumentation.runOnMainSync { owner.finish() }
        instrumentation.waitForIdleSync()
        SupportRuntimeOwnerDependencies.factory = null
    }
}

private fun now() = Date(1_700_000_000_000)
private fun apiSummary(id: Long, status: String, canReply: Boolean = true) = UnifiedConversationSummary(
    id.toULong(), "Conversation $id", "Description $id", status, canReply, now(), now()
)
private fun apiMessage(id: Long, author: String, text: String) = uniffi.wp_api.UnifiedMessage(
    id.toULong(), text, author, author, now()
)
private fun apiConversation(
    id: Long,
    status: String = "open",
    canReply: Boolean = true,
    messages: List<uniffi.wp_api.UnifiedMessage> = emptyList(),
) = uniffi.wp_api.UnifiedConversation(
    id.toULong(), "Conversation $id", "Description $id", status, canReply, now(), now(), messages
)

private suspend fun waitFor(label: String = "condition", predicate: () -> Boolean) {
    withTimeout(10_000) {
        while (!predicate()) delay(10)
    }
}

private suspend fun observeFor(timeoutMillis: Long = 1_000, predicate: () -> Boolean): Boolean {
    val deadline = System.currentTimeMillis() + timeoutMillis
    while (System.currentTimeMillis() < deadline) {
        if (predicate()) return true
        delay(10)
    }
    return predicate()
}

private fun errorName(vm: UnifiedSupportViewModel): String? = vm.errorMessage.value?.name?.lowercase()
private fun messageIds(value: UnifiedConversation?): List<Any> = value?.messages.orEmpty().map {
    if (it.id < 0) "optimistic" else it.id
}
private fun draft(vm: UnifiedSupportViewModel) = vm.replyFormState.value
private fun calls(owner: SupportRuntimeOwnerActivity) = owner.callLog.toList()
private fun rows(vm: UnifiedSupportViewModel) = vm.conversations.value.map {
    buildMap<String, Any> {
        put("id", it.id)
        put("presentation", if (it.isBot) "bot" else "ticket")
        if (!it.isBot) put("status", it.status)
    }
}

private fun leafEvents(): List<Map<String, Any?>> = synchronized(EvaluatorLeaf.events) {
    EvaluatorLeaf.events.map { it.toMap() }
}

private fun canonicalEffects(names: List<String>, includeReplyMessage: Boolean = true): List<Map<String, Any?>> {
    val selected = mutableListOf<Map<String, Any?>>()
    names.forEach { name ->
        val event = leafEvents().firstOrNull { it["name"] == name && selected.none { prior -> prior["name"] == name } }
            ?: return@forEach
        selected += when (name) {
            "uploadEncryptedLogs", "removeTempAttachments" -> mapOf("name" to name)
            "createTempAttachments" -> mapOf("name" to name, "inputs" to event["inputs"])
            "replyToUnifiedConversation" -> buildMap {
                put("name", name)
                put("conversationId", event["conversationId"])
                if (includeReplyMessage) put("message", event["message"])
            }
            else -> event
        }
    }
    return selected
}

private suspend fun awaitList(owner: SupportRuntimeOwnerActivity) {
    waitFor("conversation list") {
        owner.viewModel.conversationsState.value in setOf(
            ConversationsSupportViewModel.ConversationsState.Loaded,
            ConversationsSupportViewModel.ConversationsState.Error,
        )
    }
}

private suspend fun openConversation(session: OwnerSession, id: Long, ids: List<Long>) {
    awaitList(session.owner)
    session.event { openConversation(id) }
    waitFor("conversation $id detail") {
        !session.owner.viewModel.isLoadingConversation.value &&
            session.owner.viewModel.selectedConversation.value?.messages?.map { it.id } == ids
    }
}

private suspend fun listSuccess(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.conversationList = listOf(apiSummary(1, "bot"), apiSummary(2, "open"))
    return OwnerSession(instrumentation).use { session ->
        awaitList(session.owner)
        val vm = session.owner.viewModel
        val observed = mapOf(
            "surface" to session.owner.surface,
            "entryLabel" to session.owner.entryLabel,
            "loading" to false,
            "error" to errorName(vm),
            "rows" to rows(vm),
            "serviceEffect" to leafEvents().single { it["name"] == "loadUnifiedConversations" },
        )
        Outcome(
            mapOf("state" to "loading", "rows" to emptyList<Any>()),
            mapOf("state" to "loaded", "rows" to rows(vm)),
            observed,
            listOf(
                Check("bot and Happiness Engineer conversations share one ordered list", vm.conversations.value.map { it.id } == listOf(1L, 2L), vm.conversations.value.map { it.id }),
                Check("the retired separate entries are not rendered", rows(vm).all { it["presentation"] in setOf("bot", "ticket") }, rows(vm)),
            ),
            calls(session.owner),
        )
    }
}

private suspend fun listFailure(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.failuresRemaining = 1
    return OwnerSession(instrumentation).use { session ->
        awaitList(session.owner)
        val vm = session.owner.viewModel
        val observed = mapOf(
            "surface" to session.owner.surface,
            "loading" to false,
            "error" to errorName(vm),
            "emptyState" to (vm.conversationsState.value == ConversationsSupportViewModel.ConversationsState.Loaded && rows(vm).isEmpty()),
            "rows" to rows(vm),
        )
        Outcome(
            mapOf("state" to "loading"), mapOf("state" to "error", "requestCount" to EvaluatorLeaf.requestCount), observed,
            listOf(
                Check("a failed request is not represented as an empty successful list", vm.conversationsState.value == ConversationsSupportViewModel.ConversationsState.Error, vm.conversationsState.value::class.simpleName),
                Check("the repository body reaches the controlled service leaf", EvaluatorLeaf.requestCount == 1, leafEvents()),
            ), calls(session.owner)
        )
    }
}

private suspend fun listRetry(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.failuresRemaining = 1
    EvaluatorLeaf.conversationList = listOf(apiSummary(3, "bot"))
    return OwnerSession(instrumentation).use { session ->
        awaitList(session.owner)
        val before = mapOf("state" to "error", "requestCount" to EvaluatorLeaf.requestCount)
        session.event { retryConversations() }
        waitFor { session.owner.viewModel.conversationsState.value == ConversationsSupportViewModel.ConversationsState.Loaded }
        val vm = session.owner.viewModel
        val observed = mapOf(
            "surface" to session.owner.surface, "error" to errorName(vm), "rows" to rows(vm),
            "requestCount" to EvaluatorLeaf.requestCount,
        )
        Outcome(
            before, mapOf("state" to "loaded", "rows" to rows(vm)), observed,
            listOf(
                Check("retry uses the same unified repository path", leafEvents().map { it["name"] } == listOf("loadUnifiedConversations", "loadUnifiedConversations"), leafEvents()),
                Check("recovery replaces the error state without recreating separate support flows", errorName(vm) == null && rows(vm).size == 1, observed),
            ), calls(session.owner)
        )
    }
}

private suspend fun newBotSuccess(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.botResult = BotConversation(44u, now(), listOf(BotMessage(101u, "Here is how.", "bot", now())))
    return OwnerSession(instrumentation).use { session ->
        awaitList(session.owner)
        session.event { createBotConversation() }
        waitFor { session.owner.viewModel.selectedConversation.value?.id == 0L }
        session.event { updateReplyMessage("How do I publish?") }
        val before = mapOf("selectedConversationId" to 0L, "listSize" to session.owner.viewModel.conversations.value.size)
        session.event { sendReply("How do I publish?") }
        waitFor { !session.owner.viewModel.isSendingReply.value && session.owner.viewModel.selectedConversation.value?.id == 44L }
        val vm = session.owner.viewModel
        val selected = requireNotNull(vm.selectedConversation.value)
        val effect = leafEvents().single { it["name"] == "createBotConversation" }
        val observed = mapOf(
            "surface" to session.owner.surface,
            "selectedConversation" to mapOf(
                "id" to selected.id, "type" to if (selected.isBot) "bot" else "ticket",
                "messages" to selected.messages.map { mapOf("author" to it.authorRole, "text" to it.formattedText.text) },
            ),
            "listFirstId" to vm.conversations.value.first().id,
            "draft" to draft(vm).message,
            "sending" to vm.isSendingReply.value,
            "serviceEffect" to effect,
        )
        Outcome(
            before, mapOf("selectedConversationId" to selected.id, "listIds" to vm.conversations.value.map { it.id }), observed,
            listOf(
                Check("the local user question remains exactly once", selected.messages.count { it.formattedText.text == "How do I publish?" } == 1, selected.messages.map { it.formattedText.text }),
                Check("the application-owned create mapping executes before the service leaf response is consumed", selected.id == 44L && selected.messages.size == 2, messageIds(selected)),
            ), calls(session.owner)
        )
    }
}

private suspend fun replySuccess(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.conversationList = listOf(apiSummary(5, "open"))
    EvaluatorLeaf.conversationDetails = mapOf(5L to apiConversation(5, messages = listOf(apiMessage(10, "user", "message-10"))))
    EvaluatorLeaf.replyResult = apiConversation(5, messages = listOf(
        apiMessage(10, "user", "message-10"), apiMessage(11, "user", "Please help"), apiMessage(12, "support", "Done")
    ))
    return OwnerSession(instrumentation).use { session ->
        openConversation(session, 5, listOf(10))
        EvaluatorLeaf.events.clear()
        EvaluatorLeaf.requestCount = 0
        val uri = Uri.parse("content://org.wordpress.evaluator.support.files/image-a")
        EvaluatorLeaf.uriContents[uri.toString()] = byteArrayOf(1, 2, 3)
        EvaluatorLeaf.uriMimeTypes[uri.toString()] = "image/jpeg"
        EvaluatorLeaf.uriSizes[uri.toString()] = 3L
        EvaluatorLeaf.logFiles = listOf(File(EvaluatorLeaf.cacheDir, "app.log").apply { writeText("log") })
        EvaluatorLeaf.logIds += "log-uuid"
        session.event { addReplyAttachments(listOf(uri)); updateReplyMessage("Please help"); updateReplyIncludeAppLogs(true) }
        waitFor { draft(session.owner.viewModel).attachmentState.acceptedUris == listOf(uri) }
        val before = mapOf("draft" to "Please help", "attachments" to listOf("image-a"), "includeAppLogs" to true)
        session.event { sendReply("Please help", includeAppLogs = true) }
        waitFor { !session.owner.viewModel.isSendingReply.value && session.owner.viewModel.selectedConversation.value?.messages?.size == 3 }
        observeFor { leafEvents().any { it["name"] == "removeTempAttachments" } }
        val vm = session.owner.viewModel
        val effects = canonicalEffects(listOf("uploadEncryptedLogs", "createTempAttachments", "replyToUnifiedConversation", "removeTempAttachments"))
        val observed = mapOf(
            "surface" to session.owner.surface,
            "selectedMessages" to messageIds(vm.selectedConversation.value),
            "listConversationId" to vm.conversations.value.single().id,
            "draft" to draft(vm).message,
            "attachments" to draft(vm).attachmentState.acceptedUris.map(Uri::toString),
            "includeAppLogs" to draft(vm).includeAppLogs,
            "sending" to vm.isSendingReply.value,
            "effects" to effects,
        )
        Outcome(
            before, mapOf("selectedMessages" to messageIds(vm.selectedConversation.value), "tempFilesExist" to EvaluatorLeaf.lastReplyAttachments.map { File(it).exists() }), observed,
            listOf(
                Check("the input is cleared while the request is pending", draft(vm).message.isEmpty(), draft(vm).message),
                Check("temporary files are removed after completion", EvaluatorLeaf.lastReplyAttachments.none { File(it).exists() }, leafEvents()),
                Check("the list and selected detail refer to the same conversation identity", vm.conversations.value.single().id == vm.selectedConversation.value?.id, mapOf("list" to vm.conversations.value.single().id, "detail" to vm.selectedConversation.value?.id)),
            ), calls(session.owner)
        )
    }
}

private suspend fun offlineReply(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.conversationList = listOf(apiSummary(6, "open"))
    EvaluatorLeaf.conversationDetails = mapOf(6L to apiConversation(6, messages = listOf(apiMessage(20, "user", "message-20"))))
    return OwnerSession(instrumentation).use { session ->
        openConversation(session, 6, listOf(20))
        EvaluatorLeaf.events.clear()
        EvaluatorLeaf.requestCount = 0
        session.event { updateReplyMessage("Still there?") }
        EvaluatorLeaf.networkAvailable = false
        val before = mapOf("messageIds" to messageIds(session.owner.viewModel.selectedConversation.value), "draft" to "Still there?")
        session.event { sendReply("Still there?") }
        waitFor { errorName(session.owner.viewModel) == "offline" && !session.owner.viewModel.isSendingReply.value }
        val vm = session.owner.viewModel
        val observed = mapOf(
            "surface" to session.owner.surface, "selectedMessages" to messageIds(vm.selectedConversation.value),
            "draft" to draft(vm).message, "error" to errorName(vm), "sending" to vm.isSendingReply.value,
            "repositoryCallCount" to EvaluatorLeaf.requestCount,
        )
        Outcome(
            before, mapOf("error" to errorName(vm), "requestCount" to EvaluatorLeaf.requestCount), observed,
            listOf(
                Check("offline detection occurs before optimistic insertion", messageIds(vm.selectedConversation.value) == listOf(20L), messageIds(vm.selectedConversation.value)),
                Check("the user's draft remains retryable", draft(vm).message == "Still there?", draft(vm).message),
            ), calls(session.owner)
        )
    }
}

private suspend fun replyFailure(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.conversationList = listOf(apiSummary(7, "open"))
    EvaluatorLeaf.conversationDetails = mapOf(7L to apiConversation(7, messages = listOf(apiMessage(30, "user", "message-30"))))
    EvaluatorLeaf.replyResult = apiConversation(7)
    return OwnerSession(instrumentation).use { session ->
        openConversation(session, 7, listOf(30))
        EvaluatorLeaf.events.clear()
        EvaluatorLeaf.requestCount = 0
        val uri = Uri.parse("content://org.wordpress.evaluator.support.files/image-b")
        EvaluatorLeaf.uriContents[uri.toString()] = byteArrayOf(4)
        EvaluatorLeaf.uriMimeTypes[uri.toString()] = "image/jpeg"
        EvaluatorLeaf.uriSizes[uri.toString()] = 1L
        session.event { addReplyAttachments(listOf(uri)); updateReplyMessage("Retry me") }
        waitFor { draft(session.owner.viewModel).attachmentState.acceptedUris == listOf(uri) }
        EvaluatorLeaf.failuresRemaining = 1
        EvaluatorLeaf.requestEntered = CompletableDeferred()
        EvaluatorLeaf.requestRelease = CompletableDeferred()
        val before = mapOf("messageIds" to listOf(30L), "draft" to "Retry me", "attachments" to listOf("image-b"))
        session.event { sendReply("Retry me") }
        EvaluatorLeaf.requestEntered.await()
        waitFor { session.owner.viewModel.isSendingReply.value && messageIds(session.owner.viewModel.selectedConversation.value).size == 2 }
        val pending = mapOf("draft" to draft(session.owner.viewModel).message, "messageIds" to messageIds(session.owner.viewModel.selectedConversation.value))
        EvaluatorLeaf.requestRelease!!.complete(Unit)
        waitFor { !session.owner.viewModel.isSendingReply.value && errorName(session.owner.viewModel) == "general" }
        observeFor { leafEvents().any { it["name"] == "removeTempAttachments" } }
        val vm = session.owner.viewModel
        val settled = mapOf("draft" to draft(vm).message, "messageIds" to messageIds(vm.selectedConversation.value), "error" to errorName(vm), "sending" to vm.isSendingReply.value)
        val observed = mapOf(
            "surface" to session.owner.surface, "pending" to pending, "settled" to settled,
            "effects" to canonicalEffects(listOf("replyToUnifiedConversation", "removeTempAttachments"), includeReplyMessage = false),
        )
        Outcome(
            before, settled, observed,
            listOf(
                Check("only the optimistic message is rolled back", messageIds(vm.selectedConversation.value) == listOf(30L), messageIds(vm.selectedConversation.value)),
                Check("pre-existing messages remain unchanged", vm.selectedConversation.value?.messages?.single()?.formattedText?.text == "message-30", vm.selectedConversation.value?.messages?.map { it.formattedText.text }),
                Check("temporary files are removed on failure", EvaluatorLeaf.lastReplyAttachments.none { File(it).exists() }, leafEvents()),
            ), calls(session.owner)
        )
    }
}

private suspend fun concurrentGuard(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.conversationList = listOf(apiSummary(8, "open"))
    EvaluatorLeaf.conversationDetails = mapOf(8L to apiConversation(8))
    EvaluatorLeaf.replyResult = apiConversation(8)
    return OwnerSession(instrumentation).use { session ->
        openConversation(session, 8, emptyList())
        EvaluatorLeaf.events.clear()
        EvaluatorLeaf.requestCount = 0
        EvaluatorLeaf.requestEntered = CompletableDeferred()
        EvaluatorLeaf.requestRelease = CompletableDeferred()
        val before = mapOf("sending" to false, "requestCount" to 0)
        session.event { sendReply("first"); sendReply("second") }
        EvaluatorLeaf.requestEntered.await()
        delay(50)
        val observed = mapOf(
            "surface" to session.owner.surface,
            "sendingWhileHeld" to session.owner.viewModel.isSendingReply.value,
            "repositoryCallCountWhileHeld" to EvaluatorLeaf.requestCount,
            "sentMessages" to EvaluatorLeaf.sentMessages.toList(),
        )
        val checks = listOf(
            Check("the sending guard is set before asynchronous work begins", session.owner.viewModel.isSendingReply.value, session.owner.viewModel.isSendingReply.value),
            Check("the second event cannot reach the repository or external leaf", EvaluatorLeaf.requestCount == 1 && EvaluatorLeaf.sentMessages == listOf("first"), leafEvents()),
        )
        EvaluatorLeaf.requestRelease!!.complete(Unit)
        waitFor { !session.owner.viewModel.isSendingReply.value }
        Outcome(before, mapOf("sending" to false, "requestCount" to EvaluatorLeaf.requestCount), observed, checks, calls(session.owner))
    }
}

private suspend fun draftLifecycle(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.conversationList = listOf(apiSummary(9, "open"), apiSummary(10, "open"))
    EvaluatorLeaf.conversationDetails = mapOf(9L to apiConversation(9), 10L to apiConversation(10))
    return OwnerSession(instrumentation).use { session ->
        openConversation(session, 9, emptyList())
        val uri = Uri.parse("content://org.wordpress.evaluator.support.files/a")
        EvaluatorLeaf.uriSizes[uri.toString()] = 1L
        session.event {
            updateReplyMessage("draft-a")
            addReplyAttachments(listOf(uri))
            updateReplyIncludeAppLogs(true)
            updateReplySheetVisibility(true)
        }
        waitFor { draft(session.owner.viewModel).attachmentState.acceptedUris == listOf(uri) }
        val oldOwner = session.owner
        val oldGeneration = SupportRuntimeOwnerActivity.generation
        val oldIdentity = System.identityHashCode(oldOwner.viewModel)
        val before = mapOf("viewModelIdentity" to oldIdentity, "generation" to oldGeneration)
        instrumentation.runOnMainSync { oldOwner.recreate() }
        waitFor("owner recreation") { SupportRuntimeOwnerActivity.generation > oldGeneration && SupportRuntimeOwnerActivity.current !== oldOwner }
        instrumentation.waitForIdleSync()
        val recreated = session.owner
        val afterRecreate = mapOf(
            "selectedConversationId" to recreated.viewModel.selectedConversation.value!!.id,
            "message" to draft(recreated.viewModel).message,
            "attachments" to draft(recreated.viewModel).attachmentState.acceptedUris.map { it.lastPathSegment },
            "includeAppLogs" to draft(recreated.viewModel).includeAppLogs,
            "sheetVisible" to draft(recreated.viewModel).isBottomSheetVisible,
        )
        session.event { openConversation(10) }
        waitFor { !session.owner.viewModel.isLoadingConversation.value && session.owner.viewModel.selectedConversation.value?.id == 10L }
        val vm = session.owner.viewModel
        val afterSwitch = mapOf(
            "selectedConversationId" to vm.selectedConversation.value!!.id,
            "message" to draft(vm).message,
            "attachments" to draft(vm).attachmentState.acceptedUris.map(Uri::toString),
            "includeAppLogs" to draft(vm).includeAppLogs,
            "sheetVisible" to draft(vm).isBottomSheetVisible,
        )
        val observed = mapOf("surface" to session.owner.surface, "afterRecreate" to afterRecreate, "afterSwitch" to afterSwitch)
        Outcome(
            before, afterSwitch, observed,
            listOf(
                Check("page recreation reuses the production view model", oldIdentity == System.identityHashCode(vm), mapOf("before" to oldIdentity, "after" to System.identityHashCode(vm))),
                Check("draft state from conversation 9 never appears in conversation 10", draft(vm).message.isEmpty() && draft(vm).attachmentState.acceptedUris.isEmpty(), afterSwitch),
            ), calls(session.owner)
        )
    }
}

private fun accessibilityStrings(root: AccessibilityNodeInfo?): Set<String> {
    if (root == null) return emptySet()
    val values = linkedSetOf<String>()
    fun visit(node: AccessibilityNodeInfo) {
        node.text?.toString()?.takeIf(String::isNotBlank)?.let(values::add)
        node.contentDescription?.toString()?.takeIf(String::isNotBlank)?.let(values::add)
        repeat(node.childCount) { index -> node.getChild(index)?.let(::visit) }
    }
    visit(root)
    return values
}

private suspend fun detailAffordances(instrumentation: Instrumentation): Outcome {
    EvaluatorLeaf.conversationList = listOf(
        apiSummary(11, "bot", true), apiSummary(12, "open", true), apiSummary(13, "closed", false)
    )
    EvaluatorLeaf.conversationDetails = mapOf(
        11L to apiConversation(11, "bot", true),
        12L to apiConversation(12, "open", true),
        13L to apiConversation(13, "closed", false),
    )
    EvaluatorLeaf.replyResult = apiConversation(11, "bot", true)
    return OwnerSession(instrumentation).use { session ->
        awaitList(session.owner)
        val affordances = mutableListOf<Map<String, Any>>()

        openConversation(session, 11, emptyList())
        EvaluatorLeaf.requestEntered = CompletableDeferred()
        EvaluatorLeaf.requestRelease = CompletableDeferred()
        session.event { renderSelectedDetail(); updateReplyMessage("probe"); sendReply("probe") }
        EvaluatorLeaf.requestEntered.await()
        instrumentation.waitForIdleSync()
        delay(100)
        val botSemantics = accessibilityStrings(instrumentation.uiAutomation.rootInActiveWindow)
        affordances += mapOf(
            "id" to 11L,
            "composer" to if (botSemantics.contains("Message")) "inline_chat" else "missing",
            "typingIndicatorSupported" to botSemantics.contains("Bot is typing"),
        )
        EvaluatorLeaf.requestRelease!!.complete(Unit)
        waitFor { !session.owner.viewModel.isSendingReply.value }

        session.event { openConversation(12) }
        waitFor { !session.owner.viewModel.isLoadingConversation.value && session.owner.viewModel.selectedConversation.value?.id == 12L }
        session.event { renderSelectedDetail() }
        instrumentation.waitForIdleSync()
        delay(100)
        val ticketSemantics = accessibilityStrings(instrumentation.uiAutomation.rootInActiveWindow)
        affordances += mapOf(
            "id" to 12L,
            "composer" to if (ticketSemantics.contains("Reply")) "reply_sheet_button" else "none",
            "closedBanner" to ticketSemantics.contains("This conversation is closed"),
        )

        session.event { openConversation(13) }
        waitFor { !session.owner.viewModel.isLoadingConversation.value && session.owner.viewModel.selectedConversation.value?.id == 13L }
        session.event { renderSelectedDetail() }
        instrumentation.waitForIdleSync()
        delay(100)
        val closedSemantics = accessibilityStrings(instrumentation.uiAutomation.rootInActiveWindow)
        affordances += mapOf(
            "id" to 13L,
            "composer" to if (closedSemantics.contains("Reply") || closedSemantics.contains("Message")) "unexpected" else "none",
            "closedBanner" to closedSemantics.contains("This conversation is closed"),
        )
        val observed = mapOf("surface" to session.owner.surface, "affordances" to affordances)
        Outcome(
            mapOf("conversationIds" to listOf(11L, 12L, 13L)), affordances, observed,
            listOf(
                Check("affordances derive from status and reply capability", affordances.map { it["composer"] } == listOf("inline_chat", "reply_sheet_button", "none"), affordances),
                Check("closed tickets cannot dispatch replies", affordances.last()["composer"] == "none" && affordances.last()["closedBanner"] == true, closedSemantics),
            ), calls(session.owner)
        )
    }
}

private fun toJson(value: Any?): JsonElement = when (value) {
    null -> JsonNull
    is JsonElement -> value
    is String -> JsonPrimitive(value)
    is Boolean -> JsonPrimitive(value)
    is Number -> JsonPrimitive(value)
    is Map<*, *> -> JsonObject(value.entries.associate { it.key.toString() to toJson(it.value) })
    is Iterable<*> -> JsonArray(value.map(::toJson))
    is Array<*> -> JsonArray(value.map(::toJson))
    else -> JsonPrimitive(value.toString())
}

fun runCase(key: String, instrumentation: Instrumentation): String = runBlocking {
    EvaluatorLeaf.reset()
    val outcome = when (key) {
        "list_success" -> listSuccess(instrumentation)
        "list_failure" -> listFailure(instrumentation)
        "list_retry" -> listRetry(instrumentation)
        "new_bot_success" -> newBotSuccess(instrumentation)
        "reply_success" -> replySuccess(instrumentation)
        "offline_reply" -> offlineReply(instrumentation)
        "reply_failure" -> replyFailure(instrumentation)
        "concurrent_guard" -> concurrentGuard(instrumentation)
        "draft_lifecycle" -> draftLifecycle(instrumentation)
        "detail_affordances" -> detailAffordances(instrumentation)
        else -> error("unknown case $key")
    }
    toJson(mapOf(
        "key" to key,
        "before" to outcome.before,
        "after" to outcome.after,
        "observed" to outcome.observed,
        "invariantChecks" to outcome.checks.map { mapOf("invariant" to it.invariant, "passed" to it.passed, "evidence" to it.evidence) },
        "productionBodies" to outcome.productionBodies,
    )).toString()
}
