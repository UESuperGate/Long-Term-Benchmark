package org.wordpress.android

import android.app.Application
import org.wordpress.android.ui.main.ChooseSiteViewHolder
import org.wordpress.android.ui.prefs.AppPrefsWrapper
import org.wordpress.android.util.image.ImageManager

class WordPress : Application() {
    override fun onCreate() { super.onCreate(); instance = this }
    fun component() = Component
    object Component {
        fun inject(holder: ChooseSiteViewHolder) {
            holder.imageManager = ImageManager()
            holder.appPrefs = AppPrefsWrapper()
        }
    }
    companion object { lateinit var instance: WordPress }
}
