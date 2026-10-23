package org.signal.imageeditor.core.renderers

open class UriGlideRenderer(
  uri: android.net.Uri,
  fit: Boolean,
  width: Int,
  height: Int,
  blur: Int,
  listener: com.bumptech.glide.request.RequestListener<android.graphics.Bitmap>
) { companion object { const val STRONG_BLUR = 1 } }
