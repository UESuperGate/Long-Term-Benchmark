# Report Room (Android v25.04.3 -> v25.05.0)

## User outcome

Users can report a room with a reason, optionally leave it, and recover correctly if either operation fails.

## Functional requirements

- The report form keeps an editable reason and an independent leave-room choice.
- Submission enters an in-flight state and prevents duplicate concurrent reports.
- Reporting without leave performs only the report action and returns a clear success result.
- Reporting with leave reports first and then leaves the room.
- If reporting fails, keep the form values and allow the full action to be retried.
- If reporting succeeds but leaving fails, show a partial failure and retry only the leave step; do not submit the report twice.
- Clearing an error returns to an editable state without discarding the reason or leave choice.
- The same report behavior can be reached from relevant room-details and invite-decline flows.

## Invariants and non-goals

- Canceling or dismissing the flow performs neither report nor leave.
- Reporting individual timeline events and changing moderation policy are outside this task.
