# ArkTS native runtime test design

The final ArkUI Index page owns ReadingChallengeStore and ReadingChallengePreferences. Base and final publish the same `ReadingPageOwner` integration ABI, and an arbitrary candidate binds it through `Index.createRuntimeOwner`. The evaluator replaces only ChallengeClock and the effect leaves, then drives the same page-owner Join, Open article, and Refresh actions used by the rendered controls. It reopens the preferences file for persistence assertions and captures page-owned store state before and after each event.

The base HAP exposes the same article-opening workflow but has no challenge store or challenge UI. A common-entry native probe may observe this absence only after the page is mounted and the article action remains usable.

The role-neutral hidden adapter accepts the untouched base without inspecting filenames or selecting a base/final implementation. Its case branch mounts the candidate page owner; the normal branch preserves the candidate lifecycle body. API23 EntryAbility/ArkUI calibration produced base `0/10` and final `10/10`, and the untouched-base no-change run produced `0/10`, all with zero `not_scored` rows. Runtime boundary checks require one mounted page owner, page-store observations, reopened ArkData values, and the exact revision-2 enrollment effects `heartbeat_requested` plus `widget_update_requested`.
