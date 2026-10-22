"""Retain partial UI evidence but reject incomplete changed-bridge calibration."""


WITHDRAWN = {
    ('10_media_upload_quality', 'android'): frozenset({
        'mq_state_001_async_loading',
        'mq_state_002_limit_fallback',
        'mq_state_009_failure_cancel_retry',
    }),
    ('11_room_upgrade_navigation', 'android'): frozenset({
        'ru_state_007_predecessor_banner',
        'ru_state_008_open_predecessor',
    }),
    ('12_report_room', 'android'): frozenset({
        'rr_state_004_report_only_success',
        'rr_state_005_report_then_leave',
        'rr_state_007_report_failure_stops_leave',
        'rr_state_008_leave_failure_is_partial',
        'rr_state_009_retry_leave_only',
        'rr_state_010_clear_failure_keeps_form',
    }),
    ('13_user_verification', 'android'): frozenset({
        'uv_state_002_request_targets_user',
        'uv_state_003_start_sas_after_acceptance',
        'uv_state_004_challenge_is_stable',
        'uv_state_005_accept_challenge_once',
        'uv_state_006_decline_challenge_once',
        'uv_state_007_finish_clears_violation',
        'uv_state_008_local_cancel',
        'uv_state_009_failure_reset',
        'uv_state_010_identity_violation_surfaces',
    }),
    ('15_account_deactivation', 'android'): frozenset({
        'ad_state_001_capability_gates_entry',
        'ad_state_006_confirm_sends_payload',
        'ad_state_007_success_completes',
        'ad_state_008_failure_preserves_form',
        'ad_state_009_retry_bypasses_confirmation',
        'ad_state_010_close_dialog_resets_action',
    }),
}


def validate_report_evidence(report):
    affected = WITHDRAWN.get((report.get('taskId'), report.get('platform')), ())
    for row in report['semantic']['cases']:
        if row['caseId'] not in affected or row['status'] == 'not_scored':
            continue
        # These early failures must still pass the caller's original independent
        # source-bound prefix/conjunct verifier; no bridge outcome is inferred.
        if row['status'] == 'fail' and (row.get('entryFailureEvidence') or
                                      row.get('conjunctFailureEvidence')):
            continue
        raise ValueError(
            row['caseId'] + ': changed production SDK bridge is not runtime-verified; '
            'application-interface doubles bypass the feature implementation. '
            'Partial UI/mapper evidence is retained but cannot calibrate this boundary.')
