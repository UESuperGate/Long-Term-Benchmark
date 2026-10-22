"""Withdraw the projected confirmation state without discarding real entry proof."""

CASE = 'ir_state_003_confirm_starts_handle'
CASES = {CASE, 'ir_state_001_continue_requests_confirmation', 'ir_state_002_dismiss_confirmation'}


def validate_report_evidence(report, contract):
    if (report.get('taskId') != '16_identity_reset' or report.get('platform') != 'android'
            or contract.get('taskId') != report.get('taskId')):
        raise ValueError('Task16 Android admission used outside its task/platform boundary')
    for row in report['semantic']['cases']:
        if row.get('caseId') not in CASES or row['status'] == 'not_scored':
            continue
        if row['status'] == 'fail' and row.get('task16PrefixFailure'):
            continue
        raise ValueError('Task16 Android confirmation scores withdrawn: the flow slice projects '
                         'confirmationVisible=false and the separate root UI slice manually supplies '
                         'confirmation state instead of observing the connected original page owner; '
                         'runtime repair of cases001-003 is pending')
    return True
