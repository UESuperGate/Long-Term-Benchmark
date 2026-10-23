package android.appwidget

import android.content.ComponentName
import android.content.Context

class AppWidgetManager {
    fun getAppWidgetIds(componentName: ComponentName): IntArray = intArrayOf()

    companion object {
        fun getInstance(context: Context): AppWidgetManager = AppWidgetManager()
    }
}
