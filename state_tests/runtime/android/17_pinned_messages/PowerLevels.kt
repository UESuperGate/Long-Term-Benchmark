package io.element.android.libraries.matrix.api.room.powerlevels
import io.element.android.libraries.matrix.api.room.MatrixRoom
suspend fun MatrixRoom.canPinUnpin() = Result.success(false)
suspend fun MatrixRoom.canRedactOwn() = Result.success(false)
suspend fun MatrixRoom.canRedactOther() = Result.success(false)
