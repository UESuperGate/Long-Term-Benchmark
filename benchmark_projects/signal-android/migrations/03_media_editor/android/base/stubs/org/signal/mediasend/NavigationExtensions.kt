package org.signal.mediasend

import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import org.signal.core.models.media.MediaFolder

fun NavBackStack<NavKey>.goToCamera() { add(MediaSendRoute.Capture.Camera) }
fun NavBackStack<NavKey>.goToEdit() { add(MediaSendRoute.Edit) }
fun NavBackStack<NavKey>.goToFiles(folder: MediaFolder) { add(MediaSendRoute.Select.Files(folder)) }
fun NavBackStack<NavKey>.goToFolders() { add(MediaSendRoute.Select.Folders) }
fun NavBackStack<NavKey>.goToSend() = Unit
fun NavBackStack<NavKey>.goToTextStory() { add(MediaSendRoute.Capture.TextStory) }
