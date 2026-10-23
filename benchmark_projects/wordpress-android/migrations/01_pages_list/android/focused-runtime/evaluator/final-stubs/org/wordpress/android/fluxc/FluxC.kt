package org.wordpress.android.fluxc

open class Dispatcher {
    open fun register(target: Any) {}
    open fun unregister(target: Any) {}
    open fun dispatch(action: Any) {}
}
