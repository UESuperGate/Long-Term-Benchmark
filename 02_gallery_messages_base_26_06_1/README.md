# Element X Gallery Messages Base

Element X source base: Android `v26.06.1` / iOS `release/26.06.1`
Corresponding final development point: Android `v26.08.1` / iOS `release/26.08.1`
Task family: Gallery Messages

This is a behavior-equivalent ArkTS/OpenHarmony base for SDK 23. It preserves the relevant base behavior needed by the benchmark and intentionally omits the target feature that appears by the final release point.

Base behavior:
- Timeline renders text messages.
- Timeline renders a single image media event.
- Media browser opens a single media preview.
- Gallery event fixture is shown as unsupported content.
- Reply preview ignores gallery item count.

Intentionally absent at this base:
- No gallery grid renderer.
- No gallery list renderer for non-visual attachments.
- No full-screen gallery item preview.
- No gallery replies or gallery media browser support.
