package org.wordpress.android

import org.wordpress.android.ui.pages.PagesActivity

object R { object id { const val fragment_container: Int = 10 } }
open class WordPress {
    fun component(): Component = Component()
    class Component { fun inject(activity: PagesActivity) {} }
}
