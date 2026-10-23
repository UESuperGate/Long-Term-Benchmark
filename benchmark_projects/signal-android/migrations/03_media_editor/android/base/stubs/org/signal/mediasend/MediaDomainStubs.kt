package org.signal.mediasend

import android.content.Context
import android.net.Uri
import android.os.Parcelable
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import org.signal.core.models.media.Media
import org.signal.core.models.media.MediaFolder
import org.signal.imageeditor.core.model.EditorModel
import org.signal.mediasend.preupload.PreUploadResult
import org.signal.mediasend.screens.edit.image.BrushWidths
import org.thoughtcrime.securesms.video.TranscodingConfig
import java.io.ByteArrayInputStream
import java.io.InputStream
import kotlin.time.Duration

data class MediaRecipientId(val id: Long = 1)
data class MediaSendRecipient(val id: MediaRecipientId = MediaRecipientId())

enum class SentMediaQuality(val code: Int) { STANDARD(0), HIGH(1) }

class MediaConstraints {
  companion object {
    var muteAvailable: Boolean = true
    @JvmStatic fun isMuteVideoAudioAvailable(): Boolean = muteAvailable
  }
}

object MediaSendFlowActivityContract {
  sealed interface Mode { data object SingleRecipient : Mode; data object ChooseAfterMediaSelection : Mode }
  data class Args(
    val isCameraFirst: Boolean = false,
    val recipientId: MediaRecipientId? = null,
    val additionalRecipients: List<MediaSendRecipient> = emptyList(),
    val mode: Mode = Mode.SingleRecipient,
    val isStory: Boolean = false,
    val isReply: Boolean = false,
    val isAddToGroupStoryFlow: Boolean = false,
    val maxSelection: Int = 32,
    val asTextStory: Boolean = false,
    val initialMessage: CharSequence? = null,
    val sendType: Int = 0,
    val initialMedia: List<Media> = emptyList()
  )
}

sealed interface MediaSendRoute : androidx.navigation3.runtime.NavKey {
  data object Edit : MediaSendRoute
  sealed interface Capture : MediaSendRoute { data object Camera : Capture; data object TextStory : Capture }
  sealed interface Select : MediaSendRoute { data object Folders : Select; data class Files(val folder: MediaFolder) : Select }
}

sealed interface MediaSendFlowHudCommand {
  data object CloseScreen : MediaSendFlowHudCommand
  data object GoToLinkedDevices : MediaSendFlowHudCommand
  data object SelectSticker : MediaSendFlowHudCommand
  data class GoToQuickTransfer(val value: String) : MediaSendFlowHudCommand
  data class GoToConversation(val recipientId: MediaRecipientId) : MediaSendFlowHudCommand
  data class ConfirmScheduledSend(val timeMs: Long) : MediaSendFlowHudCommand
  data object PickScheduledSendTime : MediaSendFlowHudCommand
  data class FinishWithResult(val payload: Parcelable) : MediaSendFlowHudCommand
  data object FinishWithoutResult : MediaSendFlowHudCommand
  data class ResolveUntrustedIdentities(val recipientIds: List<Long>) : MediaSendFlowHudCommand
  data class ShowAddAMessageDialog(val message: CharSequence, val startWithEmojiKeyboard: Boolean, val isViewOnceAvailable: Boolean) : MediaSendFlowHudCommand
  data class ScheduleSend(val option: org.signal.mediasend.screens.edit.ScheduleSendOption) : MediaSendFlowHudCommand
  data class SendComplete(val result: Any? = null) : MediaSendFlowHudCommand
}

data class SnackbarEvent(val message: Int)
sealed interface ToastMessage {
  data class Text(val value: Int) : ToastMessage
  data class Quantity(val id: Int, val count: Int) : ToastMessage
}
data class ToastEvent(val icon: Any?, val message: ToastMessage)

interface MediaSendQrRepository {
  sealed interface QrCheckResult {
    data object None : QrCheckResult
    data object LinkDevice : QrCheckResult
    data class ReRegistration(val value: String = "") : QrCheckResult
    data class Username(val username: String, val recipientId: MediaRecipientId) : QrCheckResult
  }
  suspend fun checkQrData(data: String): QrCheckResult = QrCheckResult.None
}

interface MediaSendRepository {
  var sentMediaQuality: SentMediaQuality
  var brushWidths: BrushWidths
  val storyMaxVideoDuration: Duration
  val hasDismissedSaveToStorageWarning: Boolean
  suspend fun validateAndFilterMedia(media: List<Media>, maxSelection: Int, isStory: Boolean): MediaFilterResult
  suspend fun deleteBlobs(media: List<Media>)
  suspend fun getDocumentInfo(media: Media): DocumentInfo?
  suspend fun getStorySendRequirements(media: List<Media>): Map<Uri, StorySendRequirements>
  suspend fun checkUntrustedIdentities(contactIds: Set<Long>, since: Long): List<Long>
  fun observeRecipientValid(recipientId: MediaRecipientId): Flow<Boolean> = flowOf(true)
  suspend fun saveImageToStorage(editorModel: EditorModel): SaveToStorageResult
  suspend fun send(request: SendRequest): SendResult
  fun getMaxVideoDurationUs(quality: SentMediaQuality, duration: Duration): Long
  fun getVideoTranscodingTiers(quality: SentMediaQuality): List<TranscodingConfig.QualityTier>
  fun isVideoTranscodeAvailable(): Boolean
  fun getMediaConstraints(): MediaConstraints
  fun markSaveToStorageWarningDismissed()
}

data class MediaFilterResult(val filteredMedia: List<Media>, val error: MediaFilterError?)
sealed interface MediaFilterError {
  data class ItemTooLarge(val media: Media?) : MediaFilterError
  data class ItemInvalidType(val media: Media?) : MediaFilterError
  data class TooManyItems(val max: Int) : MediaFilterError
}
data class DocumentInfo(val fileName: String?, val fileSize: Long, val extension: String)
enum class SaveToStorageResult { SUCCESS, FAILURE, NO_WRITE_ACCESS }
enum class StorySendRequirements { CAN_NOT_SEND, CAN_SEND, REQUIRES_CROP }
fun Collection<StorySendRequirements>.strictest(): StorySendRequirements = minByOrNull { it.ordinal } ?: StorySendRequirements.CAN_NOT_SEND
data class SendRequest(
  val selectedMedia: List<Media>, val editorStateMap: Map<Uri, EditorState>, val quality: SentMediaQuality,
  val message: CharSequence?, val isViewOnce: Boolean, val singleRecipientId: MediaRecipientId?,
  val recipients: List<MediaSendRecipient>, val scheduledTime: Long, val sendType: Int, val isStory: Boolean,
  val preUploadResults: List<PreUploadResult> = emptyList()
)
sealed interface SendResult {
  data object Success : SendResult
  data class Error(val message: String) : SendResult
  data class UntrustedIdentity(val recipientIds: List<Long>) : SendResult
  data class ReadyToSend(val payload: Parcelable) : SendResult
}

private class DefaultContext : Context()

private class DefaultRepository : MediaSendRepository {
  override var sentMediaQuality = SentMediaQuality.STANDARD
  override var brushWidths = BrushWidths()
  override val storyMaxVideoDuration = Duration.ZERO
  override val hasDismissedSaveToStorageWarning = true
  override suspend fun validateAndFilterMedia(media: List<Media>, maxSelection: Int, isStory: Boolean) = MediaFilterResult(media, null)
  override suspend fun deleteBlobs(media: List<Media>) = Unit
  override suspend fun getDocumentInfo(media: Media): DocumentInfo? = null
  override suspend fun getStorySendRequirements(media: List<Media>) = media.associate { it.uri to StorySendRequirements.CAN_SEND }
  override suspend fun checkUntrustedIdentities(contactIds: Set<Long>, since: Long) = emptyList<Long>()
  override suspend fun saveImageToStorage(editorModel: EditorModel) = SaveToStorageResult.SUCCESS
  override suspend fun send(request: SendRequest): SendResult = SendResult.Success
  override fun getMaxVideoDurationUs(quality: SentMediaQuality, duration: Duration) = duration.inWholeMicroseconds
  override fun getVideoTranscodingTiers(quality: SentMediaQuality) = emptyList<TranscodingConfig.QualityTier>()
  override fun isVideoTranscodeAvailable() = true
  override fun getMediaConstraints() = MediaConstraints()
  override fun markSaveToStorageWarningDismissed() = Unit
}

object MediaSendDependencies {
  var mediaSendRepository: MediaSendRepository = DefaultRepository()
  val qrRepository: MediaSendQrRepository = object : MediaSendQrRepository {}
  val application: Context = DefaultContext()
}

object R { object string {
  const val MediaSendViewModel__signal_needs_the_storage_permission = 1
  const val MediaSendViewModel__unable_to_save_without_storage_permission = 2
  const val MediaSendViewModel__media_saved = 3
  const val MediaSendViewModel__error_saving_media = 4
  const val MediaSendViewModel__video_will_be_sent_without_audio = 5
  const val MediaSendViewModel__video_trimmed_to_fit = 6
  const val MediaSendViewModel__one_or_more_items_were_too_large = 7
  const val MediaSendViewModel__one_or_more_items_were_invalid = 8
  const val MediaSendViewModel__too_many_items_selected = 9
  const val MediaReviewFragment__video_set_to_high_quality = 10
  const val MediaReviewFragment__video_set_to_standard_quality = 11
  const val MediaReviewFragment__photo_set_to_high_quality = 12
  const val MediaReviewFragment__photo_set_to_standard_quality = 13
  const val MediaSendViewModel__video_set_to_view_once = 14
  const val MediaSendViewModel__photo_set_to_view_once = 15
}; object plurals {
  const val MediaReviewFragment__items_set_to_high_quality = 20
  const val MediaReviewFragment__items_set_to_standard_quality = 21
} }
