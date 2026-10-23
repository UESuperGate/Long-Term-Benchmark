package org.wordpress.android.ui.prefs

import org.wordpress.android.ui.posts.AuthorFilterSelection
import java.io.File

object EvaluatorPagesPreferenceIo {
    lateinit var root: File
    val writes = mutableListOf<String>()
    fun isReady(): Boolean = ::root.isInitialized

    fun reset() {
        writes.clear()
        if (::root.isInitialized) File(root, "pages-author-selection").delete()
    }
}

open class AppPrefsWrapper {
    open var pagesListAuthorSelection: AuthorFilterSelection
        get() {
            if (!EvaluatorPagesPreferenceIo.isReady()) return AuthorFilterSelection.EVERYONE
            val value = File(EvaluatorPagesPreferenceIo.root, "pages-author-selection")
                .takeIf(File::isFile)?.readText()
            return AuthorFilterSelection.entries.firstOrNull { it.name == value }
                ?: AuthorFilterSelection.EVERYONE
        }
        set(value) {
            check(EvaluatorPagesPreferenceIo.isReady())
            EvaluatorPagesPreferenceIo.root.mkdirs()
            File(EvaluatorPagesPreferenceIo.root, "pages-author-selection").writeText(value.name)
            EvaluatorPagesPreferenceIo.writes += value.name
        }
}
