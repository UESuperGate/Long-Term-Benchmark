# Element X tasks 08-18 benchmark

This bundle records 11 tasks calibrated on Android and migrated to ArkTS with one shared transition contract per task.

Evaluation coverage is complete.

| Metric | Result |
| --- | ---: |
| Code generation | 22/22 |
| Compile | 18/22 |
| Semantic testcase | 99/202 |
| Evaluation coverage | 22/22 runs |

| Platform | Code generation | Compile | Semantic testcase |
| --- | ---: | ---: | ---: |
| Android | 11/11 | 7/11 | 47/101 |
| ArkTS | 11/11 | 11/11 | 52/101 |

| Task | Requirement | Cases/platform | Android agent | ArkTS agent |
| --- | --- | ---: | ---: | ---: |
| `08_threads` | Read and participate in message threads | 9 | 7/9 (compile pass) | 7/9 (compile pass) |
| `09_spaces_lifecycle` | Browse, join, and leave Spaces and their rooms | 9 | 4/9 (compile fail) | 3/9 (compile pass) |
| `10_media_upload_quality` | Choose upload quality within the homeserver media limit | 9 | 4/9 (compile fail) | 6/9 (compile pass) |
| `11_room_upgrade_navigation` | Navigate between predecessor and successor rooms after upgrades | 6 | 1/6 (compile pass) | 5/6 (compile pass) |
| `12_report_room` | Report a room with optional leave and retry | 10 | 6/10 (compile pass) | 10/10 (compile pass) |
| `13_user_verification` | Verify another user and surface identity violations | 10 | 0/10 (compile pass) | 2/10 (compile pass) |
| `14_join_room_by_address` | Resolve and join a room by Matrix address | 9 | 6/9 (compile pass) | 4/9 (compile pass) |
| `15_account_deactivation` | Deactivate an account with confirmation and retry | 10 | 5/10 (compile fail) | 4/10 (compile pass) |
| `16_identity_reset` | Reset a cryptographic identity when recovery is unavailable | 10 | 0/10 (compile fail) | 2/10 (compile pass) |
| `17_pinned_messages` | Browse and manage pinned messages | 9 | 9/9 (compile pass) | 8/9 (compile pass) |
| `18_custom_notification_sounds` | Choose and persist message sounds and call ringtones | 10 | 5/10 (compile pass) | 1/10 (compile pass) |

Four-way polarity valid: `true`. Agent discrimination is reported as evidence and is not forced by changing semantic expectations.

The authoritative semantic mode for this repair is `source_transition_conformance`; no Android emulator or ArkTS device was used for these semantic scores. Base/final polarity is `0/N -> N/N` on both platforms, with no unscored cases. Toolchain details are in `environment.json`. `provenance/` contains the run manifest, calibration and rescore summaries, all 22 reconstructable candidate patches, and an evidence index. Full OpenCode/build logs remain in the ignored local run archive; their SHA-256 digests are recorded in the index without publishing credentials or bulky logs.
