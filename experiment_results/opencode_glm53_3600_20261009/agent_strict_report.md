# Snapshot State Matrix Run Report

- Generated: 2026-10-09T13:43:26
- Targets: 5
- Case-target rows: 150
- Platform filter: `arkts`
- Target role filter: `agent_result`
- Transition mode: `strict`
- Status counts: `{"matched": 112, "mismatch": 38}`
- Semantic status counts: `{"passed": 112, "failed": 38}`

## Notes

- ArkTS cases poll for a case-specific ready marker instead of using a fixed sleep.
- Every declared transition is delivered through the stateEvent Want parameter and captured separately.
- Scoring combines independently observed ArkUI node ids/states with runtime semantic facts.
- Compatible mode may accept aggregate transition facts from legacy golden targets; strict mode does not.

## Non-Matched Rows
- `01_user_status:arkts:agent_result` `us_state_002_empty_supported_entry` expected `pass` observed `fail` status `mismatch` missing `4`
- `01_user_status:arkts:agent_result` `us_state_003_custom_input_and_emoji_sheet` expected `pass` observed `fail` status `mismatch` missing `3`
- `01_user_status:arkts:agent_result` `us_state_004_save_success_propagates_surfaces` expected `pass` observed `fail` status `mismatch` missing `4`
- `01_user_status:arkts:agent_result` `us_state_005_save_failure_keeps_previous_status` expected `pass` observed `fail` status `mismatch` missing `2`
- `01_user_status:arkts:agent_result` `us_state_006_clear_status` expected `pass` observed `fail` status `mismatch` missing `4`
- `01_user_status:arkts:agent_result` `us_state_008_in_call_status` expected `pass` observed `fail` status `mismatch` missing `2`
- `01_user_status:arkts:agent_result` `us_state_010_predefined_status_selection` expected `pass` observed `fail` status `mismatch` missing `2`
- `01_user_status:arkts:agent_result` `us_state_011_dismiss_picker_keeps_status` expected `pass` observed `fail` status `mismatch` missing `1`
- `01_user_status:arkts:agent_result` `us_state_012_custom_input_dirty_state` expected `pass` observed `fail` status `mismatch` missing `2`
- `01_user_status:arkts:agent_result` `us_state_013_custom_input_cancel_clears_draft_only` expected `pass` observed `fail` status `mismatch` missing `1`
- `01_user_status:arkts:agent_result` `us_state_018_profile_status_refresh` expected `pass` observed `fail` status `mismatch` missing `2`
- `01_user_status:arkts:agent_result` `us_state_020_remote_status_removed` expected `pass` observed `fail` status `mismatch` missing `1`
- `01_user_status:arkts:agent_result` `us_state_023_remote_status_refresh_does_not_override_own_status` expected `pass` observed `fail` status `mismatch` missing `2`
- `01_user_status:arkts:agent_result` `us_state_024_status_text_never_leaks_to_timeline` expected `pass` observed `fail` status `mismatch` missing `2`
- `01_user_status:arkts:agent_result` `us_state_025_save_retry_after_failure_uses_latest_draft` expected `pass` observed `fail` status `mismatch` missing `4`
- `01_user_status:arkts:agent_result` `us_state_026_call_status_restore_manual_status` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_001_media_unknown_requests_validation` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_002_valid_media_renders_original_content` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_003_invalid_media_uses_safety_fallback` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_005_gallery_mixed_validation_aggregates` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_006_viewer_keeps_timeline_validation` expected `pass` observed `fail` status `mismatch` missing `3`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_007_active_call_joinable_card` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_009_render_only_selected_hides_unselected_media` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_010_accessibility_group_state` expected `pass` observed `fail` status `mismatch` missing `3`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_013_valid_state_not_downgraded_to_loading` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_017_voice_message_validation` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_019_banned_mime_type_maps_to_invalid` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_024_active_call_participant_update` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_025_navigation_ignores_invalid_media` expected `pass` observed `fail` status `mismatch` missing `2`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_026_action_menu_for_blocked_media` expected `pass` observed `fail` status `mismatch` missing `3`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_027_final_active_call_actionable_card` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_029_validation_cache_survives_scroll_rebind` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_031_active_call_end_update_removes_join_action` expected `pass` observed `fail` status `mismatch` missing `1`
- `03_timeline_protection_rich_events:arkts:agent_result` `tp_state_032_blocked_media_details_action_without_download` expected `pass` observed `fail` status `mismatch` missing `3`
- `04_live_location:arkts:agent_result` `ll_state_007_map_updates_location` expected `pass` observed `fail` status `mismatch` missing `2`
- `04_live_location:arkts:agent_result` `ll_state_018_map_no_last_location` expected `pass` observed `fail` status `mismatch` missing `3`
- `04_live_location:arkts:agent_result` `ll_state_028_background_resume_uses_latest_location` expected `pass` observed `fail` status `mismatch` missing `2`
- `05_link_new_device:arkts:agent_result` `lnd_state_017_stale_timer_ignored_after_retry` expected `pass` observed `fail` status `mismatch` missing `1`
