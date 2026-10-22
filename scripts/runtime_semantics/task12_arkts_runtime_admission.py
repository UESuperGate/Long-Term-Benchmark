"""Task12 actual-native admission; legacy projections remain withdrawn.

Neither readiness flags nor labels grant admission. Recompute the supplied
source-bound raw run and four independent actual-native calibration controls.
"""

from pathlib import Path


BASE_SHA = 'dcdfee285d5cd027b43abe78850350113ff7258a0eb0f3acf0d12ebd37f663c9'
FINAL_SHA = 'aad374ecce30168ede22c209f5a4fef111ac4d510bbb8b3c8b1ad457008d7183'
PRODUCER_SHAS = (
    '64121fb07d7b58f87283bd13e06266fddb08202ba58786e16d12ed999f57ea69',
    '7a4b2e55a883f9d9007fb3f006a2c861a57a7db6ea2ab644b27f3d1a1369659d',
    '7dce29ec6216453f01f84539430b33f1e8ca72e6993d5aee1f71c9bfcba77fbf',
)
MERGED_POLICY_V1 = 'arkts.task12.merged-source-bound.v4'
MERGED_POLICY_HINT_V4 = 'arkts.task12.merged-source-bound.hint-profile-v4'


def _merged_validator(report):
    policy = report.get('provenance', {}).get('runtimeEvidence', {}).get('policyId')
    if policy == MERGED_POLICY_V1:
        from . import task12_merged_pipeline_v1 as merged
        return merged
    if policy == MERGED_POLICY_HINT_V4:
        from . import task12_merged_pipeline_hint_v4 as merged
        return merged
    return None


def _admit(report, contract):
    evidence = report.get('provenance', {}).get('runtimeEvidence', {})
    merged = _merged_validator(report)
    if merged is not None:
        return merged.validate_report_evidence(report, contract)
    from . import task12_actual_ui_protocol as current
    from . import task12_13_formal_core as core
    require = current.require
    require(report.get('diagnostics', {}).get('strictRuntime', {}).get('nativeProtocol') == current.PROTOCOL,
            'legacy final-template/marker producer is not the replacement actual-native protocol')
    evidence = report['provenance']['runtimeEvidence']
    if 'reviewedControlReceipt' in evidence:
        from .task12_arkts_reviewed_controls import validate_candidate
        return validate_candidate(report, contract)
    bundle_path = current.checked(evidence['admissionBundle'])
    require(bundle_path.is_relative_to(core.ROOT / 'experiment_results'), 'admission bundle outside audit root')
    bundle = core.load(bundle_path)
    require(bundle.get('nativeProtocol') == current.PROTOCOL and
            bundle.get('contract') == core.file_record(current.CONTRACT) and core.load(current.CONTRACT) == contract,
            'actual-native canonical admission boundary differs')
    expected_producers = [core.file_record(path) for path in (current.FACTS, current.RUNNER, Path(current.__file__))]
    require(tuple(item['sha256'] for item in expected_producers) == PRODUCER_SHAS,
            'unreviewed actual-native producer revision')
    require(bundle.get('producerHashes') == expected_producers, 'actual-native fixture/validator version differs')
    controls = bundle['sourceParameterizedControls']
    require({'base', 'final', 'negative', 'positive'} <= controls.keys(), 'four actual source-parameterized controls missing')
    declared = [item for item in controls.values() if all(evidence.get(key) == item.get(key)
                for key in ('raw', 'sourceInventory', 'build', 'currentCleanup'))]
    require(len(declared) == 1, 'new candidate is not declared in the original batch; use a reviewed reuse receipt')
    original = core.load(Path(declared[0]['reportPath']))
    require(original['role'] == report['role'] and
            original['provenance']['candidateSource'] == report['provenance']['candidateSource'] and
            original['semantic']['cases'] == report['semantic']['cases'],
            'report rewritten after actual execution: does not match its originally declared source/role/runtime cases')
    source_paths, run_ids = set(), set()
    for label, sha, counts, role in (
        ('base', BASE_SHA, (0, 10, 0), 'base'), ('final', FINAL_SHA, (10, 0, 0), 'final'),
        ('negative', BASE_SHA, (0, 10, 0), 'agent'), ('positive', FINAL_SHA, (10, 0, 0), 'agent')):
        declared = controls[label]
        path = Path(declared['reportPath']).resolve()
        require(path.is_relative_to(bundle_path.parent) and path.parent != bundle_path.parent,
                'control report outside current batch')
        control = core.load(path)
        actual = control['provenance']['runtimeEvidence']
        require(actual.get('admissionBundle') == evidence['admissionBundle'],
                'control belongs to a different admission batch')
        require(control['role'] == role and control['provenance']['sourceInventorySha256'] == sha and
                all(actual.get(key) == declared[key] for key in ('raw', 'sourceInventory', 'build', 'currentCleanup')),
                'control metadata differs from actual bound runtime artifacts')
        proof = current.validate_report_evidence(control, contract)
        require(tuple(proof['counts'][key] for key in ('passed', 'failed', 'notScored')) == counts,
                'actual control polarity is not exact')
        source = control['provenance']['candidateSource']
        require(source not in source_paths, 'control source directory reused instead of independent copies')
        source_paths.add(source)
        raw = core.load(current.checked(actual['raw']))
        for row in raw['semantic']['cases']:
            identity = row.get('caseRunId') or row.get('entryFailureEvidence', {}).get('caseRunId')
            require(identity and identity not in run_ids, 'actual control execution identity missing/reused')
            run_ids.add(identity)
    # Also recompute the passed-in candidate; no filename, role or source-tree
    # allowlist determines its semantic result.
    current.validate_report_evidence(report, contract)
    return True


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    """Route merged entry evidence by the exact report producer policy."""
    if (report.get('taskId'), report.get('platform')) != ('12_report_room', 'arkts'):
        raise ValueError('Task12 ArkTS entry admission used for a different task/platform')
    if contract is None or contract.get('taskId') != report['taskId']:
        raise ValueError('Task12 ArkTS entry admission requires its canonical contract')
    merged = _merged_validator(report)
    if merged is None:
        raise ValueError('Task12 merged entry report has an unknown producer policy')
    return merged.validate_entry_failure(
        row, report, used_observation_ids, contract=contract)


def validate_report_evidence(report, contract):
    if (report.get('taskId'), report.get('platform')) != ('12_report_room', 'arkts'):
        raise ValueError('Task12 ArkTS admission policy used for a different task/platform')
    if contract.get('taskId') != report['taskId']:
        raise ValueError('Task12 ArkTS admission requires its canonical contract')
    if any(row.get('status') in {'pass', 'fail'} for row in report['semantic']['cases']):
        try:
            return _admit(report, contract)
        except Exception as error:
            raise ValueError('Task12 ArkTS scores withdrawn: old projection/marker or incomplete actual-native '
                             'four-control admission evidence: ' + str(error)) from error
    return True
