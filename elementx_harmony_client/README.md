# Element X Harmony Client

This directory is the unified ArkTS/OpenHarmony client shell for Element X parity work.

SDK policy:
- `compileSdkVersion`: 23
- `compatibleSdkVersion`: 23
- `minAPIVersion`: 23
- `targetAPIVersion`: 23

Current scope:
- Android-aligned signed-out onboarding, manual sign-in, QR sign-in and create-account routes.
- Signed-in Home, Timeline, Settings and Devices tabs.
- The five migrated benchmark final feature surfaces are available inside one client shell.
- A method-level ArkTS `MatrixClientContract` mirrors the Android `MatrixClient.kt` method names where practical.
- A REST-backed Matrix subset covers homeserver discovery, versions, password login, sync, send message, media upload, profile updates, receipts, account data, room join and basic moderation calls.
- Fixture-backed paths remain available for no-credential UI regression and offline dynamic tests.

Production status:
- This is not yet a production-complete ArkTS reimplementation of Element X plus Matrix/Rust SDK.
- The current Harmony client still lacks a real Matrix Rust SDK-equivalent runtime for encryption, verification, sliding sync, room-list services, media decryption/cache, pushers, notification rules, secure session/crypto storage and live Flow/StateFlow semantics.
- Run `python C:\Users\xiexi\qingyu\scripts\audit_production_readiness.py` for the current production gap report. The audit intentionally exits non-zero until those blockers are removed.

Build:
- `ohpm install`
- `hvigorw assembleHap --no-daemon`
