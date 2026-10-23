package org.wordpress.android.support.unified.ui

import androidx.compose.runtime.Composable
import org.wordpress.android.support.unified.model.AttachmentState
import org.wordpress.android.support.unified.model.VideoDownloadState
import org.wordpress.android.support.unified.util.AttachmentActionsListener

object UnifiedSupportActivity {
    const val AUTHORIZATION_TAG = "Authorization"
}

@Composable
fun AttachmentFullscreenImagePreview(
    imageUrl: String,
    authorizationHeader: String,
    onDismiss: () -> Unit,
    onDownload: () -> Unit,
) = Unit

@Composable
fun AttachmentFullscreenVideoPlayer(
    videoUrl: String,
    onDismiss: () -> Unit,
    onDownload: () -> Unit,
    downloadState: VideoDownloadState,
    onStartVideoDownload: (String) -> Unit,
    onResetVideoDownloadState: () -> Unit,
) = Unit

@Composable
fun TicketMainContentView(
    messageText: String,
    includeAppLogs: Boolean,
    onMessageChanged: (String) -> Unit,
    onIncludeAppLogsChanged: (Boolean) -> Unit,
    enabled: Boolean = true,
    attachmentState: AttachmentState = AttachmentState(),
    attachmentActionsListener: AttachmentActionsListener,
) = Unit
