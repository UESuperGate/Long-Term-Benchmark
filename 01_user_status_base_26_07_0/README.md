# Element X User Status Base

Element X source base: Android `v26.07.0` / iOS `release/26.07.0`
Corresponding final development point: Android `v26.08.4` / iOS `release/26.08.4`
Task family: User Status

This is a behavior-equivalent ArkTS/OpenHarmony base for SDK 23. It preserves the relevant base behavior needed by the benchmark and intentionally omits the target feature that appears by the final release point.

Base behavior:
- Room list renders direct and group rooms from mock Matrix data.
- Timeline renders text and single-media messages.
- Settings screen renders account identity and privacy rows.
- Emoji data exists as generic reaction data only.
- Searching for a status action returns no actionable UI.

Intentionally absent at this base:
- No own-status row in Settings.
- No custom user status composer.
- No user status badge on the settings avatar or room heroes.
- No automatic call status integration.
