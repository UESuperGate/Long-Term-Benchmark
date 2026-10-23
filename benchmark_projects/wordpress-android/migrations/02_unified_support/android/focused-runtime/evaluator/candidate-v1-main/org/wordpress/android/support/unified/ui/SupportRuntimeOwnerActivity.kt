package org.wordpress.android.support.unified.ui

import android.net.Uri
import android.os.Bundle
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.ComposeView
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import java.util.concurrent.atomic.AtomicInteger

/** Compatibility owner for the method-level candidate-v1 ABI recorded by the visible build. */
class SupportRuntimeOwnerActivity : ComponentActivity() {
    internal val viewModel: UnifiedSupportViewModel by lazy {
        ViewModelProvider(this, requireNotNull(SupportRuntimeOwnerDependencies.factory))[
            UnifiedSupportViewModel::class.java
        ]
    }
    private lateinit var root: FrameLayout
    private lateinit var detailView: ComposeView
    internal val callLog = mutableListOf<String>()
    internal val entryLabel = "get_help"
    internal val surface: String get() = root.contentDescription.toString()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        root = FrameLayout(this).apply { contentDescription = SURFACE }
        detailView = ComposeView(this)
        root.addView(detailView)
        setContentView(root)
        viewModel
        generation = generations.incrementAndGet()
        current = this
        callLog += "SupportRuntimeOwnerActivity.onCreate"
        if (savedInstanceState == null) {
            callLog += "ConversationsSupportViewModel.init"
            viewModel.init()
        }
    }

    override fun onDestroy() {
        if (current === this) current = null
        super.onDestroy()
    }

    internal fun retryConversations() {
        callLog += "SupportRuntimeOwnerActivity.retryConversations"
        viewModel.clearError()
        viewModel.refreshConversations()
    }

    internal fun openConversation(id: Long) {
        callLog += "SupportRuntimeOwnerActivity.openConversation"
        viewModel.onConversationClick(id)
    }

    internal fun createBotConversation() {
        callLog += "SupportRuntimeOwnerActivity.createBotConversation"
        viewModel.onCreateNewBotConversationClick()
    }

    internal fun updateReplyMessage(message: String) {
        callLog += "SupportRuntimeOwnerActivity.updateReplyMessage"
        viewModel.updateReplyMessage(message)
    }

    internal fun addReplyAttachments(uris: List<Uri>) {
        callLog += "SupportRuntimeOwnerActivity.addReplyAttachments"
        viewModel.addReplyAttachments(uris)
    }

    internal fun updateReplyIncludeAppLogs(include: Boolean) {
        callLog += "SupportRuntimeOwnerActivity.updateReplyIncludeAppLogs"
        viewModel.updateReplyIncludeAppLogs(include)
    }

    internal fun updateReplySheetVisibility(visible: Boolean) {
        callLog += "SupportRuntimeOwnerActivity.updateReplySheetVisibility"
        viewModel.updateReplyBottomSheetVisibility(visible)
    }

    internal fun sendReply(message: String, includeAppLogs: Boolean = false) {
        callLog += "SupportRuntimeOwnerActivity.sendReply"
        viewModel.sendReply(message, includeAppLogs)
    }

    internal fun renderSelectedDetail() {
        callLog += "SupportRuntimeOwnerActivity.renderSelectedDetail"
        detailView.setContent {
            val conversation by viewModel.selectedConversation.collectAsState()
            val loading by viewModel.isLoadingConversation.collectAsState()
            val sending by viewModel.isSendingReply.collectAsState()
            val replyForm by viewModel.replyFormState.collectAsState()
            conversation?.let { value ->
                MaterialTheme {
                    UnifiedConversationDetailScreen(
                        conversation = value,
                        replyFormState = replyForm,
                        isSendingReply = sending,
                        isLoadingConversation = loading,
                        onReplyMessageChange = viewModel::updateReplyMessage,
                        onSendReply = viewModel::sendReply,
                        onOpenReplySheet = { viewModel.updateReplyBottomSheetVisibility(true) },
                        onDismissReplySheet = { viewModel.updateReplyBottomSheetVisibility(false) },
                        onToggleIncludeAppLogs = viewModel::updateReplyIncludeAppLogs,
                        onBackClick = viewModel::onBackClick,
                    )
                }
            }
        }
    }

    companion object {
        const val SURFACE = "unified_support"
        private val generations = AtomicInteger()
        @Volatile internal var current: SupportRuntimeOwnerActivity? = null
        @Volatile internal var generation: Int = 0
    }
}

internal object SupportRuntimeOwnerDependencies {
    @Volatile var factory: ViewModelProvider.Factory? = null
}
