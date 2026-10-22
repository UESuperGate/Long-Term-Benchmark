"""Accept only the reviewed page-owned native and complete compiler evidence."""


def validate_report_evidence(report, contract):
    if (report.get('taskId') != '13_user_verification' or report.get('platform') != 'arkts'
            or contract.get('taskId') != report.get('taskId')):
        raise ValueError('Task13 ArkTS admission used outside its task/platform boundary')
    if any(row['status'] in {'pass', 'fail'} for row in report['semantic']['cases']):
        from .task13_page_owner_verify import verify_value
        try:
            verify_value(report)
        except (ValueError, KeyError, OSError, TypeError) as error:
            raise ValueError('Task13 ArkTS scores withdrawn or unverified: complete current '
                             'page-owned native/compiler evidence required: ' + str(error)) from error
    return True
