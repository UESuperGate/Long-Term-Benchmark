package org.wordpress.android.ui.pages

import org.wordpress.android.viewmodel.pages.PageListViewModel

open class PagesFragment {
    fun onSpecificPageRequested(id: Long) {}
    fun onSpecificPageListTypeRequested(type: PageListViewModel.PageListType) {}
    fun onPositiveClickedForBasicDialog(tag: String) {}
    fun onNegativeClickedForBasicDialog(tag: String) {}
    fun onPostResolutionConfirmed(event: org.wordpress.android.ui.posts.PostResolutionOverlayActionEvent.PostResolutionConfirmationEvent) {}
}
