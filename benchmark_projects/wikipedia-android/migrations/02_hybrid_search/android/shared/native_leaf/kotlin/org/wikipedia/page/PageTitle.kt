package org.wikipedia.page

import android.net.Uri
import org.wikipedia.dataclient.WikiSite

class PageTitle(
    val prefixedText: String,
    val wikiSite: WikiSite,
    var fragment: String = ""
) {
    var thumbUrl: String? = null
    var description: String? = null

    companion object {
        fun titleForUri(uri: Uri, wikiSite: WikiSite): PageTitle {
            val raw = uri.toString().substringAfterLast('/').substringAfter("wiki/")
            val parts = raw.split('#', limit = 2)
            return PageTitle(parts[0], wikiSite, parts.getOrElse(1) { "" })
        }
    }
}
