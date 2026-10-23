package org.wikipedia.benchmark.hybrid.native

import android.content.Context
import android.os.Bundle
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.wikipedia.search.HybridSearchPageActionPrefix
import org.wikipedia.search.HybridSearchPageEffects
import org.wikipedia.search.HybridSearchPageSnapshot
import org.wikipedia.search.RuntimeSearchLeaves
import org.wikipedia.settings.Prefs

object NativeHybridEpisode {
    fun run(options: Bundle, context: Context): String = runBlocking {
        val key = options.getString("caseKey") ?: error("caseKey missing")
        RuntimeSearchLeaves.reset()
        configure(key)
        Prefs.attach(context)
        Prefs.reset()
        Prefs.isHybridSearchEnabled = true
        Prefs.reopen(context)

        val effectLeaf = RecordingPageEffects()
        val page = HybridSearchPageActionPrefix(effectLeaf)
        val invoked = mutableListOf<String>()

        if (key != "enable_supported") {
            page.openHybridSearch()
            invoked += "HybridSearchPageActionPrefix.openHybridSearch"
        }
        if (key in setOf("retry_recovers", "feedback_mapping", "opt_out")) {
            page.submitSearch()
            invoked += "HybridSearchPageActionPrefix.submitSearch>SearchResultsViewModel.loadHybridSearchResults"
            awaitSettled(page)
        }

        Prefs.reopen(context)
        val before = snapshot(page.snapshot())
        effectLeaf.clear()
        val effects: List<Map<String, Any>>

        when (key) {
            "enable_supported" -> {
                page.openHybridSearch()
                invoked += "HybridSearchPageActionPrefix.openHybridSearch"
                effects = emptyList()
            }
            "concurrent_dispatch" -> {
                page.submitSearch()
                invoked += "HybridSearchPageActionPrefix.submitSearch>SearchResultsViewModel.loadHybridSearchResults"
                RuntimeSearchLeaves.awaitBothStarted()
                val after = snapshot(page.snapshot())
                effects = RuntimeSearchLeaves.channelEffects()
                RuntimeSearchLeaves.releaseHeld()
                return@runBlocking episode(before, after, effects, invoked, effectLeaf)
            }
            "retry_recovers" -> {
                RuntimeSearchLeaves.configure(
                    prefix = listOf("Paris"),
                    fullText = emptyList(),
                    semantic = listOf("History_of_Paris#Origins"),
                    lexicalError = false,
                    semanticError = false,
                    hold = false
                )
                page.retry()
                invoked += "HybridSearchPageActionPrefix.retry>SearchResultsViewModel.loadHybridSearchResults"
                awaitSettled(page)
                effects = RuntimeSearchLeaves.attemptEffects()
            }
            "feedback_mapping" -> {
                page.rateSemanticResult(position = 0, positive = false)
                invoked += "HybridSearchPageActionPrefix.rateSemanticResult"
                effects = effectLeaf.snapshot()
            }
            "opt_out" -> {
                page.turnOffHybridSearch()
                invoked += "HybridSearchPageActionPrefix.turnOffHybridSearch"
                effects = effectLeaf.snapshot()
            }
            else -> {
                page.submitSearch()
                invoked += "HybridSearchPageActionPrefix.submitSearch>SearchResultsViewModel.loadHybridSearchResults"
                awaitSettled(page)
                effects = if (key.startsWith("both_sources")) {
                    RuntimeSearchLeaves.operationEffects()
                } else {
                    RuntimeSearchLeaves.channelEffects()
                }
            }
        }

        Prefs.reopen(context)
        episode(before, snapshot(page.snapshot()), effects, invoked, effectLeaf)
    }

    private fun episode(
        before: Map<String, Any?>,
        after: Map<String, Any?>,
        effects: List<Map<String, Any>>,
        invoked: List<String>,
        effectLeaf: RecordingPageEffects
    ): String {
        val observed = after.toMutableMap().also {
            it["effects"] = effects
            it["rawLeafCalls"] = RuntimeSearchLeaves.calls()
            it["pageLeafCalls"] = effectLeaf.snapshot()
        }
        return json(
            mapOf(
                "before" to before,
                "after" to after,
                "observed" to observed,
                "entryOwner" to "HybridSearchPageActionPrefix",
                "invokedProductionMethods" to invoked,
                "transitionExecuted" to true,
                "storageReopened" to true
            )
        )
    }

    private fun configure(key: String) {
        RuntimeSearchLeaves.enabled = true
        RuntimeSearchLeaves.group = if (key == "both_sources_semantic_first") "semanticLexical" else "lexicalSemantic"
        when (key) {
            "enable_supported" -> RuntimeSearchLeaves.configure(emptyList(), emptyList(), emptyList(), false, false, false)
            "concurrent_dispatch" -> RuntimeSearchLeaves.configure(emptyList(), emptyList(), emptyList(), false, false, true)
            "both_sources_lexical_first" -> RuntimeSearchLeaves.configure(
                listOf("Paris", "Paris"), listOf("Paris", "Paris,_Texas"),
                listOf("History_of_Paris#Origins", "Paris_agreement#Background"), false, false, false
            )
            "both_sources_semantic_first" -> RuntimeSearchLeaves.configure(
                listOf("Paris"), emptyList(), listOf("History_of_Paris#Origins"), false, false, false
            )
            "lexical_failure_fallback" -> RuntimeSearchLeaves.configure(
                emptyList(), emptyList(), listOf("History_of_Paris#Origins"), true, false, false
            )
            "semantic_failure_fallback" -> RuntimeSearchLeaves.configure(
                listOf("Paris"), emptyList(), emptyList(), false, true, false
            )
            "both_fail", "retry_recovers" -> RuntimeSearchLeaves.configure(
                emptyList(), emptyList(), emptyList(), true, true, false
            )
            "feedback_mapping", "opt_out" -> RuntimeSearchLeaves.configure(
                emptyList(), emptyList(), listOf("History_of_Paris#Origins"), false, false, false
            )
            else -> error("unknown case $key")
        }
    }

    private suspend fun awaitSettled(page: HybridSearchPageActionPrefix) {
        repeat(300) {
            if (page.snapshot().phase != "loading") return
            delay(10)
        }
        error("production page and view model did not settle")
    }

    private fun snapshot(value: HybridSearchPageSnapshot): Map<String, Any?> = mapOf(
        "featureAvailable" to value.featureAvailable,
        "state" to linkedMapOf(
            "mode" to value.mode,
            "phase" to value.phase,
            "query" to value.query,
            "sections" to value.sections,
            "lexicalTitles" to value.lexicalTitles,
            "semanticTitles" to value.semanticTitles,
            "retryAvailable" to value.retryAvailable,
            "notice" to value.notice
        ),
        "persistence" to mapOf("hybridEnabled" to Prefs.isHybridSearchEnabled)
    )

    private class RecordingPageEffects : HybridSearchPageEffects {
        private val calls = mutableListOf<Map<String, Any>>()

        override fun submitFeedback(payload: Map<String, Any>) {
            calls += mapOf("leaf" to "feedback_transport", "payload" to payload)
        }

        override fun requestStandardSearch(query: String) {
            calls += mapOf("name" to "standard_search_requested", "query" to query)
        }

        fun clear() = calls.clear()
        fun snapshot(): List<Map<String, Any>> = calls.toList()
    }

    private fun json(value: Any?): String = when (value) {
        null -> "null"
        is String -> "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
        is Number, is Boolean -> value.toString()
        is Map<*, *> -> value.entries.joinToString(prefix = "{", postfix = "}") { "${json(it.key.toString())}:${json(it.value)}" }
        is Iterable<*> -> value.joinToString(prefix = "[", postfix = "]") { json(it) }
        else -> error("unsupported JSON value ${value.javaClass}")
    }
}
