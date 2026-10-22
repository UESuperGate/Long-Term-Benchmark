"""Withdraw detached positive transitions without discarding real entry evidence."""

TASKS = {'16_identity_reset', '17_pinned_messages'}


def validate_report_evidence(report, contract):
    if (report.get('taskId') not in TASKS or report.get('platform') != 'arkts'
            or contract.get('taskId') != report.get('taskId')):
        raise ValueError('Task16/17 ArkTS admission used outside its task/platform boundary')
    for row in report['semantic']['cases']:
        if row['status'] == 'not_scored':
            continue
        # Entry evidence is independently checked below by its source-bound
        # physical-UI policy. It cannot establish positive final calibration.
        if row['status'] == 'fail' and row.get('entryFailureEvidence'):
            continue
        raise ValueError('Task16/17 ArkTS transition scores withdrawn: detached presenter '
                         'execution does not establish the actual page-owned state transition')
    return True
