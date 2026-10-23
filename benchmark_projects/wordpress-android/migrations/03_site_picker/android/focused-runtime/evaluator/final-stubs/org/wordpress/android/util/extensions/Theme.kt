package org.wordpress.android.util.extensions

import android.content.Context
import android.content.res.Configuration

fun Context.getColorFromAttribute(attr: Int): Int = getColor(android.R.color.darker_gray)
fun Configuration.isDarkTheme(): Boolean = (uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
