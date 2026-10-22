#!/usr/bin/env python3
"""Audit new guarded four-way runtime controls, live NS mutations and retained M3."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_runtime_transition_matrix import validate_report as public_validate
from scripts.runtime_semantics import task10_arkts_closure_evidence as closure
from scripts.runtime_semantics.task10_native_artifacts import read_native_artifact, verify_device_ui_row
from scripts.runtime_semantics.task10_retained_integrity import verify_report as independent_native_verify
from scripts.runtime_semantics.tasks10_11_runtime_evidence import validate_report as evidence_validate, record


def audit_cleanup(report):
    cleanup = report['diagnostics']['strictRuntime']['cleanup']
    binaries = cleanup.get('binaryHashes', [])
    if not (cleanup.get('performed') is True and cleanup.get('temporaryBuildRemoved') is True and
            cleanup.get('binaryArtifactsRetained') is False and not cleanup.get('remainingBinaries') and
            binaries and all(item['bytes'] > 0 and len(item['sha256']) == 64 and
                             not Path(item['path']).exists() for item in binaries) and
            not Path(report['target']).exists()):
        raise ValueError('Hash-before-delete or temporary source/build cleanup is incomplete')
    return {'verified': True, 'binaryHashes': binaries, 'temporarySourceRemoved': True}


def audit_control(path, name, contract):
    report = json.loads(path.read_text())
    public_validate(report, contract)
    evidence_validate(report, contract)
    eligible = closure.validate_report(report, contract)
    expected = 'fail' if name in {'base', 'base-copy'} else 'pass'
    rows = report['semantic']['cases']
    if len(rows) != 9 or any(row['status'] != expected for row in rows):
        raise ValueError('Guarded Task10 polarity is not closed')
    for row in rows:
        verify_device_ui_row(row, report)
    return {'control': name, 'report': record(path), 'semantic': {
        'passed': sum(row['status'] == 'pass' for row in rows),
        'failed': sum(row['status'] == 'fail' for row in rows), 'notScored': 0},
        'publicAccepted': True, 'losslessRawAccepted': True,
        'reviewedClosureEligibleCases': sum(item.get('closureEligible') is True for item in eligible),
        'sourceInventory': report['provenance']['sourceInventory'],
        'temporarySourceRemoved': not Path(report['target']).exists(),
        'cleanup': audit_cleanup(report)}


def audit_mutation(path, contract):
    report = json.loads(path.read_text())
    public_validate(report, contract)
    evidence_validate(report, contract)
    if len(report['semantic']['cases']) != 9 or report['runtimeCompile'].get('passed') is not True or any(
            row['status'] != 'not_scored' or row['observed'] is not None or row['invariantChecks'] or
            row.get('transitionExecuted') is not False for row in report['semantic']['cases']):
        raise ValueError('Unknown UI mutation did not remain entirely NS after real compiled entry probe')
    probe = report['provenance']['unboundProbeArtifacts']
    for pair in [probe['initialUI'], probe['build'], *probe['commandLogs']]:
        read_native_artifact(pair)
    tree = json.loads(read_native_artifact(probe['initialUI']))
    attributes = list(closure._attributes(closure.project_tree(tree)))
    ids = {node.get('id') for node in attributes}
    name = path.parent.name
    required = 'renamed_upload_command' if name == 'renamed-control' else 'unreviewed_extra'
    if required not in ids or (name == 'renamed-control' and 'attachment_send' in ids):
        raise ValueError('Actual native UI did not render the intended evaluator mutation')
    return {'report': record(path), 'semantic': {'passed': 0, 'failed': 0, 'notScored': 9},
            'realEntryProbeCompilePassed': True, 'losslessInitialProbeAccepted': True,
            'actualRenderedMutationId': required, 'cleanup': audit_cleanup(report),
            'temporarySourceRemoved': not Path(report['target']).exists(),
            'evaluatorMutationFixtureOnly': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controls-dir', type=Path, required=True)
    parser.add_argument('--mutations-dir', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Never overwrite a previous audit')
    started = time.monotonic()
    contract_path = ROOT / 'benchmark_tasks/10_media_upload_quality/transitions.json'
    contract = json.loads(contract_path.read_text())
    controls = [audit_control(args.controls_dir / name / 'accepted.runtime.json', name, contract)
                for name in ('base', 'final', 'base-copy', 'final-copy')]
    historical_root = ROOT / 'experiment_results/runtime_transition_20261020/task10_raw_retention_v1/controls'
    historical_controls = [audit_control(historical_root / name / 'accepted.runtime.json', name, contract)
                           for name in ('base', 'final', 'base-copy', 'final-copy')]
    for left, right in ((controls[0], controls[2]), (controls[1], controls[3])):
        if any(left['sourceInventory'][key] != right['sourceInventory'][key] for key in ('files', 'sha256')):
            raise ValueError('Standalone control does not share the matching calibration source inventory')
    mutants = [audit_mutation(args.mutations_dir / name / 'not-scored.runtime.json', contract)
               for name in ('renamed-control', 'extra-control')]
    candidate = json.loads(args.candidate.read_text())
    public_validate(candidate, contract)
    evidence_validate(candidate, contract)
    candidate_result = independent_native_verify(args.candidate, contract)
    if any(item['applies'] for item in closure.validate_report(candidate, contract)):
        raise ValueError('Actual full native M3 candidate cannot use a common-entry source whitelist')
    result = {'taskId': contract['taskId'], 'platform': 'arkts', 'contract': record(contract_path),
        'fixture': record(closure.FIXTURE), 'extraPublicConjunct': record(Path(closure.__file__)),
        'liveGuard': record(ROOT / 'scripts/runtime_semantics/task10_arkts_closure_guard.cjs'),
        'liveRunner': record(ROOT / 'scripts/runtime_semantics/task10_arkts_strict_runtime.cjs'),
        'review': record(closure.FIXTURE.parent / 'REVIEW.md'), 'auditImplementation': record(Path(__file__)),
        'existingSharedPolicyImplementation': record(ROOT / 'scripts/runtime_semantics/tasks10_11_runtime_evidence.py'),
        'controls': controls, 'historicalControlsUnmodified': historical_controls,
        'liveUnknownUiMutations': mutants,
        'originalRealCandidate': {'report': record(args.candidate), 'independentValidation': candidate_result,
            'publicAccepted': True, 'modelOrDeviceReplayPerformed': False},
        'centralModified': False, 'readinessModified': False, 'sharedPolicyModified': False,
        'parentOwnedIntegrityHelperModified': False, 'modelInvoked': False,
        'publicDispatcher': record(ROOT / 'scripts/run_runtime_transition_matrix.py'),
        'publicConjunctIntegrated': True, 'publicationPromoted': False,
        'overallAuditElapsedSeconds': round(time.monotonic() - started, 3)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'controls': [(r['control'], r['semantic']) for r in controls],
                      'unknownMutations': [r['semantic'] for r in mutants],
                      'originalRealCandidate': candidate_result}))


if __name__ == '__main__':
    main()
