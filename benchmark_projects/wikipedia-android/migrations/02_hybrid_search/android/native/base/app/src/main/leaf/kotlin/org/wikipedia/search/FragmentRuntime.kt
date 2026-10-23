package org.wikipedia.search

import android.app.Activity
import android.view.View
import androidx.compose.ui.Modifier
import androidx.fragment.app.Fragment
import org.wikipedia.extensions.RuntimeInstrument
import org.wikipedia.page.PageTitle

interface SearchResultCallback {
    fun navigateToTitle(title: PageTitle, inNewTab: Boolean, position: Int, location: Any?)
    fun setSearchText(text: String)
    fun onSearchProgressBar(enabled: Boolean)
}

class SearchFragment : Fragment() {
    val searchLanguageCode: String = "fr"
    fun setUpLanguageScroll(position: Int) = Unit
}

class SearchResultLongPressHandler(callback: SearchResultCallback?, position: Int)

object RuntimeFragmentLeaves {
    lateinit var activity: Activity
    val parent = SearchFragment()
    val instrument = RuntimeInstrument()
    lateinit var viewModel: Any
    private val mutableEffects = mutableListOf<Map<String, Any>>()
    var openHybrid: ((String, Boolean, Int) -> Unit)? = null
    var turnOff: ((String) -> Unit)? = null
    var rate: ((Boolean, PageTitle, Int) -> Unit)? = null
    val callback = object : SearchResultCallback {
        override fun navigateToTitle(title: PageTitle, inNewTab: Boolean, position: Int, location: Any?) = Unit
        override fun setSearchText(text: String) {
            mutableEffects += mapOf("name" to "standard_search_requested", "query" to text)
        }
        override fun onSearchProgressBar(enabled: Boolean) = Unit
    }

    fun reset(model: Any) {
        viewModel = model
        openHybrid = null
        turnOff = null
        rate = null
        mutableEffects.clear()
    }

    fun clearEffects() = mutableEffects.clear()
    fun effects(): List<Map<String, Any>> = mutableEffects.toList()

    fun recordInteraction(name: String, elementId: String?, pageData: Any?, context: Map<String, Any>) {
        if (name == "click" && elementId in setOf("thumb_up", "thumb_down")) {
            mutableEffects += mapOf(
                "leaf" to "feedback_transport",
                "payload" to mapOf(
                    "elementId" to elementId.orEmpty(),
                    "query" to context["query"]?.toString().orEmpty(),
                    "position" to (context["position"] ?: 0),
                    "title" to ((pageData as? PageTitle)?.prefixedText ?: "")
                )
            )
        }
    }
}

class HybridHarnessActivity : Activity()

fun HybridSearchResultsScreen(
    viewModel: SearchResultsViewModel,
    modifier: Modifier,
    onNavigateToTitle: (PageTitle, Boolean, Int, Any?) -> Unit,
    onSemanticCardImpression: (SearchResult, Int) -> Unit,
    onSemanticItemClick: (PageTitle, Boolean, Boolean, Int, Any?) -> Unit,
    onItemLongClick: (View, SearchResult, Int) -> Unit,
    onInfoClick: () -> Unit,
    onTurnOffExperimentClick: (String) -> Unit,
    onCloseSearch: () -> Unit,
    onRetrySearch: () -> Unit,
    onLoading: (Boolean) -> Unit,
    onRatingClick: (Boolean, PageTitle, Int) -> Unit,
    onLexicalResultsEmpty: () -> Unit,
    onSemanticResultsEmpty: () -> Unit,
    onError: (Throwable) -> Unit
) {
    RuntimeFragmentLeaves.turnOff = onTurnOffExperimentClick
    RuntimeFragmentLeaves.rate = onRatingClick
}

fun SearchResultsScreen(
    viewModel: SearchResultsViewModel,
    modifier: Modifier,
    onNavigateToTitle: (PageTitle, Boolean, Int, Any?) -> Unit,
    onItemLongClick: (View, SearchResult, Int) -> Unit,
    onSemanticSearchClick: (String, Boolean, Int) -> Unit,
    onCloseSearch: () -> Unit,
    onRetrySearch: () -> Unit,
    onLanguageClick: (Int) -> Unit,
    onLoading: (Boolean) -> Unit,
    onNoResults: () -> Unit
) {
    RuntimeFragmentLeaves.openHybrid = onSemanticSearchClick
}
