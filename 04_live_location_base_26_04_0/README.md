# Element X Live Location Base

Element X source base: Android `v26.04.0` / iOS `release/26.04.0`
Corresponding final development point: Android `v26.05.1` / iOS `release/26.05.1`
Task family: Live Location Sharing

This is a behavior-equivalent ArkTS/OpenHarmony base for SDK 23. It preserves the relevant base behavior needed by the benchmark and intentionally omits the target feature that appears by the final release point.

Base behavior:
- Timeline renders ordinary messages.
- Settings exposes generic permissions information.
- Location permission state can be displayed from mock data.
- Live location fixture is present as unsupported content.
- No live-sharing action can be started.

Intentionally absent at this base:
- Live-location event branches exist, but no active live-location side effect is wired.
- No live location timeline renderer.
- No active live-location manager or background update service.
- No thread restriction for live location sharing.

