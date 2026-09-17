# Element X Link New Device Base

Element X source base: Android `v26.05.0` / iOS `release/26.05.0`
Corresponding final development point: Android `v26.08.2` / iOS `release/26.08.2`
Task family: Link New Device Flow

This is a behavior-equivalent ArkTS/OpenHarmony base for SDK 23. It preserves the relevant base behavior needed by the benchmark and intentionally omits the target feature that appears by the final release point.

Base behavior:
- Security settings can be opened from Settings.
- Existing session verification state is visible.
- Manual recovery-key flow is available.
- A QR login placeholder is visible but non-rotating.
- No timeout or owner verification state transition occurs.

Intentionally absent at this base:
- No QR-code rotation loop.
- No device-owner verification gate.
- No scan-screen warning.
- No post-owner-verification timeout.
