package io.element.android.x

/** Stable transport contract kept separate from the task-specific binding. */
internal data class StateTestObservation(
    val semanticFacts: Collection<String> = emptyList(),
    val appliedEvent: String = "",
)

/**
 * Answer-free lifecycle helper for deterministic feature fixtures.
 *
 * The candidate supplies its production-backed state factory, reducer, and
 * fact projection. This helper only owns reset and event acknowledgement.
 */
internal class DeterministicStateTestStore<S>(
    private val initialState: (caseId: String) -> S,
    private val applyEvent: (state: S, event: String) -> Boolean,
    private val semanticFacts: (state: S) -> Collection<String>,
) {
    private var currentCaseId: String? = null
    private var currentState: S? = null

    @Synchronized
    fun capture(caseId: String, stateEvent: String): StateTestObservation {
        val state = if (currentCaseId != caseId || currentState == null) {
            initialState(caseId).also {
                currentCaseId = caseId
                currentState = it
            }
        } else {
            checkNotNull(currentState)
        }
        val appliedEvent = if (stateEvent.isNotBlank() && applyEvent(state, stateEvent)) {
            stateEvent
        } else {
            ""
        }
        return StateTestObservation(
            semanticFacts = semanticFacts(state),
            appliedEvent = appliedEvent,
        )
    }
}
