package org.signal.core.util

import android.database.Cursor

fun Cursor.requireNonNullString(column: String): String = getString(getColumnIndexOrThrow(column))
