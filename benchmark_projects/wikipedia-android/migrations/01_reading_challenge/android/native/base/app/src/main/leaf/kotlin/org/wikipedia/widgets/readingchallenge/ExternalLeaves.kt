package org.wikipedia.widgets.readingchallenge

object RuntimeChallengeEffects {
    private val values = mutableListOf<String>()
    @Synchronized fun clear() = values.clear()
    @Synchronized fun record(value: String) = values.add(value)
    @Synchronized fun snapshot(): List<String> = values.toList()
}

object ReadingChallengeAnalyticsHelper {
    fun sendHeartbeatEvent(state: Any) {
        RuntimeChallengeEffects.record("heartbeat_requested")
    }
}

class ReadingChallengeWidget
class ReadingChallengeWidgetReceiver
