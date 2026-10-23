package org.wordpress.android.util.image

import android.widget.ImageView

enum class BlavatarShape { SQUARE_WITH_ROUNDED_CORNERES }
enum class ImageType { BLAVATAR }
open class ImageManager { open fun loadImageWithCorners(view: ImageView, type: ImageType, url: String, radius: Int) = Unit }
