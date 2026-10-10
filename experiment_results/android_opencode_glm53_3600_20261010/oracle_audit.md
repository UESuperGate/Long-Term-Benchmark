# Strict State Oracle Audit

- Generated: 2026-10-10T18:04:13
- Total cases: 150
- Status counts: {'valid_oracle': 150}
- Polarity roles: {'new_feature_discriminator': 135, 'final_positive_discriminator': 15}
- Cases with transitions: 97
- Cases with property assertions: 30
- Cases with quality warnings: 0

## Production Quality Gates

- `01_user_status`: PASS; cases 26/26; missing areas: []
- `02_gallery_messages`: PASS; cases 28/28; missing areas: []
- `03_timeline_protection_rich_events`: PASS; cases 32/32; missing areas: []
- `04_live_location`: PASS; cases 30/30; missing areas: []
- `05_link_new_device`: PASS; cases 34/34; missing areas: []

## Blocking Issues

- None

## Runtime Fixture Needs

- Cases requiring controlled SDK/timer/permission fixtures: 62

## Functional Area Coverage

- `01_user_status`: action_menu=1, active_call=1, capability=4, cross_surface=5, editor=4, failure_recovery=1, persistence=4, profile=1, propagation=3, timeline=2
- `02_gallery_messages`: action_menu=2, content_scanning=7, media_viewer=4, pinned_event=1, reply_preview=1, share_forward=2, timeline_rendering=11
- `03_timeline_protection_rich_events`: accessibility_navigation=2, action_menu=2, active_call=8, gallery_aggregation=1, media_viewer=2, timeline_scanner=16, validation_cache=1
- `04_live_location`: active_manager=2, banner=2, composer_gate=6, failure_recovery=2, map_view=3, notification=2, permission_flow=2, stop_timeout=6, timeline_item=5
- `05_link_new_device`: capability=5, cleanup=2, desktop_qr=6, digits=3, mobile_scan=4, owner_gate=6, sdk_error_mapping=4, stale_event_protection=2, timeout_retry=2

## Fixture Kind Coverage

- `01_user_status`: call_state_side_effect=1, declarative_render_plus_sdk_callback=1, declarative_state_fixture=16, event_transition_fixture=2, sdk_callback_cross_surface=1, sdk_callback_fixture=2, sdk_failure_fixture=2, sdk_failure_then_user_edit=1
- `02_gallery_messages`: action_sheet_with_per_item_validation=1, declarative_state_fixture=12, event_replacement_state=1, event_transition_fixture=6, navigation_state_projection=1, per_item_sdk_callback=1, sdk_failure_fixture=6
- `03_timeline_protection_rich_events`: call_state_sdk_callback=1, declarative_state_fixture=13, event_transition_fixture=5, mixed_timeline_fixture=1, protected_action_sheet=1, sdk_callback_fixture=4, sdk_failure_fixture=6, timeline_rebind=1
- `04_live_location`: declarative_state_fixture=12, event_transition_fixture=6, lifecycle_resume_with_manager_snapshot=1, notification_intent_routing=1, runtime_permission_change=1, sdk_callback_fixture=3, sdk_failure_fixture=4, timer_fixture=1, timer_tick_with_location_age=1
- `05_link_new_device`: attempt_scoped_sdk_callback=1, cancellation_during_async_qr_loading=1, declarative_state_fixture=11, event_transition_fixture=3, owner_verification_error_recovery=1, sdk_error_mapping_with_timer=1, sdk_failure_fixture=10, timer_fixture=6
