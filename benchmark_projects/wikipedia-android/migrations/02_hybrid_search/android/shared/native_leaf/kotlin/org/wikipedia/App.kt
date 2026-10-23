package org.wikipedia

object Constants {
    enum class InvokeSource { SEARCH, PLACES }
}

class LanguageState(var appLanguageCode: String = "fr")

class WikipediaApp private constructor() {
    val languageState = LanguageState()
    companion object { val instance = WikipediaApp() }
}
