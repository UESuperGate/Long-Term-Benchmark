# Cross-Platform Semantic Report

- Overall status: **BLOCKED**
- Android official reference tests: **127/127 passed** across 10 selected classes.
- ArkTS semantic checks: **0/64 executed**; the ohosTest HAP compiles, but HDC reports no connected target.
- Combined executed/pass accounting: **127/191**.

ArkTS compilation is build evidence, not semantic testcase execution. Full parity
cannot be claimed until the test HAP is signed, installed, and all 64 registered
checks run on a HarmonyOS/OpenHarmony target.
