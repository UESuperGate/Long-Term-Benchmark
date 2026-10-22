package io.element.android.libraries.designsystem.utils.snackbar
data class SnackbarMessage(val id: Int)
class SnackbarDispatcher { fun post(message: SnackbarMessage): Unit = error("Unexpected snackbar in load-only adapter") }
