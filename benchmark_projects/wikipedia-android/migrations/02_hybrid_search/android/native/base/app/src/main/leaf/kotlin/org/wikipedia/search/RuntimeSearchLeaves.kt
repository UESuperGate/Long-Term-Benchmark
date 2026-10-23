package org.wikipedia.search

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.wikipedia.dataclient.HttpResponse
import org.wikipedia.dataclient.mwapi.MwQueryPage
import org.wikipedia.dataclient.mwapi.MwQueryResponse
import org.wikipedia.dataclient.mwapi.Query

object RuntimeSearchLeaves {
    @Volatile var group: String = "lexicalSemantic"
    @Volatile var enabled: Boolean = true
    private var prefixTitles: List<String> = emptyList()
    private var fullTextTitles: List<String> = emptyList()
    private var semanticTitles: List<String> = emptyList()
    private var lexicalFailure = false
    private var semanticFailure = false
    private var held = false
    private var started = CountDownLatch(2)
    private var release = CountDownLatch(1)
    private var lexicalAttempt = 0
    private var semanticAttempt = 0
    private val mutableCalls = mutableListOf<MutableMap<String, Any>>()

    @Synchronized
    fun reset() {
        prefixTitles = emptyList()
        fullTextTitles = emptyList()
        semanticTitles = emptyList()
        lexicalFailure = false
        semanticFailure = false
        held = false
        started = CountDownLatch(2)
        release = CountDownLatch(1)
        lexicalAttempt = 0
        semanticAttempt = 0
        mutableCalls.clear()
    }

    @Synchronized
    fun configure(
        prefix: List<String>,
        fullText: List<String>,
        semantic: List<String>,
        lexicalError: Boolean,
        semanticError: Boolean,
        hold: Boolean
    ) {
        prefixTitles = prefix
        fullTextTitles = fullText
        semanticTitles = semantic
        lexicalFailure = lexicalError
        semanticFailure = semanticError
        held = hold
        if (hold) {
            started = CountDownLatch(2)
            release = CountDownLatch(1)
        }
    }

    fun prefix(): HttpResponse<MwQueryResponse> {
        val call = synchronized(this) {
            lexicalAttempt += 1
            record("prefix_http", lexicalAttempt)
        }
        awaitIfHeld()
        if (lexicalFailure) {
            finish(call, "failed")
            error("lexical failure")
        }
        finish(call, "completed")
        return HttpResponse(response(prefixTitles), mapOf("x-search-id" to "lex-$lexicalAttempt"))
    }

    fun fullText(): MwQueryResponse {
        val call = synchronized(this) { record("fulltext_http", lexicalAttempt) }
        finish(call, "completed")
        return response(fullTextTitles)
    }

    fun semantic(): HttpResponse<MwQueryResponse> {
        val call = synchronized(this) {
            semanticAttempt += 1
            record("semantic_http", semanticAttempt)
        }
        awaitIfHeld()
        if (semanticFailure) {
            finish(call, "failed")
            error("semantic failure")
        }
        finish(call, "completed")
        return HttpResponse(response(semanticTitles), mapOf("x-search-id" to "sem-$semanticAttempt"))
    }

    fun awaitBothStarted(): Boolean = started.await(3, TimeUnit.SECONDS)
    fun releaseHeld() = release.countDown()

    @Synchronized
    fun clearCalls() = mutableCalls.clear()

    @Synchronized
    fun calls(): List<Map<String, Any>> = mutableCalls.map { it.toMap() }

    @Synchronized
    fun operationEffects(): List<Map<String, Any>> =
        listOf("prefix_http", "fulltext_http", "semantic_http")
            .filter { leaf -> mutableCalls.any { it["leaf"] == leaf } }
            .map { mapOf("leaf" to it) }

    @Synchronized
    fun channelEffects(): List<Map<String, Any>> = listOf(
        mapOf("leaf" to "lexical_http", "status" to channelStatus(setOf("prefix_http", "fulltext_http"))),
        mapOf("leaf" to "semantic_http", "status" to channelStatus(setOf("semantic_http")))
    )

    @Synchronized
    fun attemptEffects(): List<Map<String, Any>> = listOf(
        mapOf("leaf" to "lexical_http", "attempt" to lexicalAttempt),
        mapOf("leaf" to "semantic_http", "attempt" to semanticAttempt)
    )

    @Synchronized
    private fun record(leaf: String, attempt: Int): MutableMap<String, Any> {
        return mutableMapOf<String, Any>("leaf" to leaf, "attempt" to attempt, "status" to "started")
            .also(mutableCalls::add)
    }

    @Synchronized
    private fun finish(call: MutableMap<String, Any>, status: String) {
        call["status"] = status
    }

    private fun channelStatus(leaves: Set<String>): String {
        val selected = mutableCalls.filter { it["leaf"] in leaves }
        return when {
            selected.any { it["status"] == "failed" } -> "failed"
            selected.any { it["status"] == "started" } -> "started"
            selected.any { it["status"] == "completed" } -> "completed"
            else -> "not_started"
        }
    }

    private fun awaitIfHeld() {
        if (!held) return
        started.countDown()
        release.await()
    }

    private fun response(titles: List<String>): MwQueryResponse = MwQueryResponse(
        Query(titles.mapIndexed { index, title -> MwQueryPage(title, index) })
    )

    fun emptySemanticSearchResult(loader: ClassLoader): Any {
        val type = loader.loadClass("org.wikipedia.search.SemanticSearchResults")
        return type.getDeclaredConstructor().newInstance()
    }
}
