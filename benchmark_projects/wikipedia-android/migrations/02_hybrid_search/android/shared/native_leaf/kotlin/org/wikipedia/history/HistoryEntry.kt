package org.wikipedia.history

import org.wikipedia.page.PageTitle

class HistoryEntry(val title: PageTitle, val source: Int) {
    companion object { const val SOURCE_SEARCH = 1 }
}
