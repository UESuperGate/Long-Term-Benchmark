# Spaces Lifecycle (Android v25.08.4 -> v25.10.0)

## User outcome

Users can discover their Spaces, browse Space children, act on invitations, join rooms, and leave a Space while deciding which child rooms to leave.

## Functional requirements

- The home surface shows joined Spaces and outstanding Space invitations and preserves the selected Space while its child list updates.
- A Space loads children incrementally and exposes a load-more state without duplicating entries or losing scroll context.
- Joinable child rooms can be joined independently; each row has its own loading, success, and failure state.
- Space invitations can be accepted or declined through the existing invite semantics and are marked seen consistently.
- Leaving a Space first loads affected child rooms, selects eligible rooms by default, and prevents selection that would violate a last-admin constraint.
- Users can select all, deselect all, or toggle individual eligible child rooms before confirming leave.
- Loading or join failures can be cleared and retried. A failed leave retains the current selection and does not report success.

## Invariants and non-goals

- Direct-message rooms are not treated as Space children to leave.
- Joining one child must not overwrite another child's in-flight or failed state.
- Creating, editing, or reordering Space hierarchies is outside this task.
