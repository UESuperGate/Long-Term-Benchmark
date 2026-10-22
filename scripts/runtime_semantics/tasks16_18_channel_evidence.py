"""Fail closed for task18 positive OS-channel claims; no receipt format is trusted yet."""


def requires_os_channel_effect(case_spec):
    """Use canonical expectations, not candidate role, source names or evidence tags."""
    def positive(value):
        if isinstance(value, dict):
            return bool(value.get('recreateOrder')) or any(positive(item) for item in value.values())
        if isinstance(value, list):
            return any(positive(item) for item in value)
        return isinstance(value, str) and value in {'recreate_message_channel', 'recreate_call_channel'}

    return positive(case_spec.get('expected', {}))


def validate_task18_channel_pass(row, report, case_spec):
    if (report.get('platform') != 'arkts' or
            report.get('taskId') != '18_custom_notification_sounds' or
            row.get('status') != 'pass' or not requires_os_channel_effect(case_spec)):
        return
    # No implemented validator binds an original production notification-service
    # call to completion, effective OS slot/sound readback and a real consumer.
    # Source hashes, native scope labels, ledger rows, call arguments, and even
    # caller-supplied "verified" receipts cannot grant that missing capability.
    raise ValueError(
        f"{row.get('caseId')}: unsupported task18 OS channel PASS: no supported "
        "production service completion/effective slot-sound readback and consumer binding; "
        "ledger-only, args-only or claimed receipts cannot establish canonical channel effects")
