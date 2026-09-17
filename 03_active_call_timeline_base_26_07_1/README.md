# Element X Active Call Timeline Base

Element X source base: Android `v26.07.1` / iOS `release/26.07.1`
Corresponding final development point: Android `v26.08.0` / iOS `release/26.08.0`
Task family: Active Call Timeline Rendering

This is a behavior-equivalent ArkTS/OpenHarmony base for SDK 23. It preserves the relevant base behavior needed by the benchmark and intentionally omits the target feature that appears by the final release point.

Base behavior:
- Room timeline opens from the room list.
- Text/media events render in chronological order.
- A call event fixture is present in the data layer.
- The call event renders as unsupported content.
- No call-specific primary action is exposed.

Intentionally absent at this base:
- No active call timeline card.
- No join-call action from timeline.
- No participant/call-state rendering in the timeline.
- No active-call snapshot coverage.
