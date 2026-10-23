# ArkTS runtime test design

Each clean API23 project is copied to a temporary calibration directory. Task-local evaluator sources and launch wiring are injected only there, then `hvigorw` builds the HAP and deletes the temporary source tree. On the emulator, `EntryAbility` loads the actual ArkUI `Index`; its page-owned `EvergreenStore` executes canonical events and persists through ArkData Preferences. Runtime episodes are emitted through hilog and scored outside the app.
