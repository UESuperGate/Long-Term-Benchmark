package io.element.android.x

/**
 * Public, answer-free integration point for Android semantic state tests.
 *
 * Candidate implementations should drive the same presenters, state holders,
 * fixtures, and event sinks used by the production feature. The benchmark
 * transport is already installed; this object only binds feature state to it.
 */
internal object StateTestScenario {
    fun capture(caseId: String, stateEvent: String): StateTestObservation {
        return StateTestObservation()
    }
}
