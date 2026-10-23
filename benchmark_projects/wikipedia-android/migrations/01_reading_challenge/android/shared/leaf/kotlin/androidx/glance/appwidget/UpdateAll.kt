package androidx.glance.appwidget

import android.content.Context
import org.wikipedia.widgets.readingchallenge.ReadingChallengeWidget
import org.wikipedia.widgets.readingchallenge.RuntimeChallengeEffects

suspend fun ReadingChallengeWidget.updateAll(context: Context) {
    RuntimeChallengeEffects.record("widget_update_requested")
}
