package org.wordpress.android.ui.posts

object BasicFragmentDialog {
    interface BasicDialogPositiveClickInterface { fun onPositiveClicked(instanceTag: String) }
    interface BasicDialogNegativeClickInterface { fun onNegativeClicked(instanceTag: String) }
}
sealed class PostResolutionOverlayActionEvent { class PostResolutionConfirmationEvent : PostResolutionOverlayActionEvent() }
interface PostResolutionOverlayListener { fun onPostResolutionConfirmed(event: PostResolutionOverlayActionEvent.PostResolutionConfirmationEvent) }
