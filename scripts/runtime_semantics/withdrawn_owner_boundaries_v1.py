"""Fail closed on known projected observations pending reviewed runtime repair."""


WITHDRAWN = {
    ('14_join_room_by_address', 'android'): frozenset({
        'jr_state_005_found_then_continue_navigates',
        'jr_state_006_continue_waits_for_resolution',
        'jr_state_009_dismiss_closes_flow',
    }),
    ('14_join_room_by_address', 'arkts'): frozenset({
        'jr_state_005_found_then_continue_navigates',
        'jr_state_006_continue_waits_for_resolution',
        'jr_state_009_dismiss_closes_flow',
    }),
    ('15_account_deactivation', 'arkts'): frozenset({
        'ad_state_002_default_form_blocks_submit',
        'ad_state_003_password_enables_submit',
        'ad_state_004_erase_data_option',
        'ad_state_007_success_completes',
        'ad_state_010_close_dialog_resets_action',
    }),
    ('17_pinned_messages', 'android'): frozenset({
        'pm_state_001_open_loading',
        'pm_state_007_view_in_timeline',
    }),
}


def validate_report_evidence(report):
    cases = WITHDRAWN.get((report.get('taskId'), report.get('platform')), ())
    for row in report['semantic']['cases']:
        if row['caseId'] not in cases or row['status'] == 'not_scored':
            continue
        # The public caller still independently validates the complete entry
        # policy/raw proof; this exception never admits an expected-shaped state.
        if row['status'] == 'fail' and row.get('entryFailureEvidence'):
            continue
        raise ValueError(
            row['caseId'] + ': runtime owner/navigation score withdrawn; '
            'a reviewed actual production-owner verifier is not yet registered. '
            'Callback records, detached presenters and self-declared native '
            'metadata cannot restore admission.')
