package com.bumptech.glide.request

import com.bumptech.glide.load.DataSource
import com.bumptech.glide.load.engine.GlideException
import com.bumptech.glide.request.target.Target

interface RequestListener<R> {
  fun onLoadFailed(e: GlideException?, model: Any?, target: Target<R?>?, isFirstResource: Boolean): Boolean
  fun onResourceReady(resource: R?, model: Any?, target: Target<R?>?, dataSource: DataSource?, isFirstResource: Boolean): Boolean
}
