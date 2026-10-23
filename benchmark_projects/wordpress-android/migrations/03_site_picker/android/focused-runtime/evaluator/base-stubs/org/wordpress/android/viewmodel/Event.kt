package org.wordpress.android.viewmodel

class Event<T>(private val content: T) {
    fun peekContent(): T = content
}
