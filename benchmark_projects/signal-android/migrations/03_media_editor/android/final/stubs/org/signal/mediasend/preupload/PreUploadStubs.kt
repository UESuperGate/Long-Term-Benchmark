package org.signal.mediasend.preupload

import org.signal.core.models.media.Media

data class PreUploadResult(val id: String = "result")
open class PreUploadController {
  open fun cancelUpload(media: Media) = Unit
  open fun cancelUpload(media: Set<Media>) = Unit
  open fun cancelAllUploads() = Unit
  open fun updateDisplayOrder(media: List<Media>) = Unit
  open fun updateCaptions(media: List<Media>) = Unit
  open fun deleteAbandonedAttachments() = Unit
  open fun startUpload(media: List<Media>, recipientId: org.signal.mediasend.MediaRecipientId?) = Unit
  open fun getPreUploadResults(callback: (Collection<PreUploadResult>) -> Unit) { callback(emptyList()) }
}
