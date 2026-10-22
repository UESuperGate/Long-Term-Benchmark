"""Offline adoption plan, not a registered/default scorer or device runner."""
from pathlib import Path

from . import task14_15_formal_core as core

ROOT = core.ROOT
REPLAY = ROOT / 'experiment_results/runtime_transition_20261020/postrun_task14_15_evaluator_repair_v1'
TASK = '14_join_room_by_address'
PROOF_SHA = '339896b204893fec9e8eb24944b5d47ab316335bcd0801f126bf2e8794fe7c29'
SOURCE_PROOF_SHA = 'b95bc484ee5be0fb3c2b48871fa076bab9baba1bc5f30b60ed76e4a6ebe48911'
WEAK_CASES = {'jr_state_005_found_then_continue_navigates', 'jr_state_006_continue_waits_for_resolution',
              'jr_state_009_dismiss_closes_flow'}


def record(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}


def plan():
    proof_path = REPLAY / 'task14-actual-poles-verified-v1.json'
    closure_path = REPLAY / 'task14-evaluator-only-aggregate-v2/closure-inventory.json'
    if core.sha256(proof_path) != PROOF_SHA or core.sha256(closure_path) != SOURCE_PROOF_SHA:
        raise ValueError('Preserve immutable model evidence/source proof; do not replace historical pins')
    proof = core.load(proof_path)
    candidate = proof['controls']['candidate_score']
    if candidate['semantic'] != {'passed': 7, 'failed': 2, 'notScored': 0}:
        raise ValueError('Historical actual model result changed')
    suite = ROOT / 'state_tests/runtime/arkts/native/Task14RealFlowV2.suite.js'
    text = suite.read_text()
    if "spec.caseId === 'jr_state_001_entry_opens_address_flow'" not in text or 'real_flow_v2 executes only canonical case001' not in text:
        raise ValueError('Native delegate surface changed; issue a reviewed successor plan')
    contract = core.load(ROOT / 'benchmark_tasks' / TASK / 'transitions.json')
    requirements = {
        'jr_state_001_entry_opens_address_flow': 'reuse original RealFlowV2 root/address/create/DM/room action chain',
        'jr_state_002_update_trims_and_debounces': 'own original page input; original trim/debounce and stale-response receiver, real UI frame; clock only explicitly scoped time evidence',
        'jr_state_003_invalid_after_continue': 'own original page invalid input/Continue/rendered error',
        'jr_state_004_valid_address_resolves': 'own original page input and external resolver completion, rendered state; no detached presenter',
        'jr_state_005_found_then_continue_navigates': 'real physical Continue -> page receiver -> production navigator -> native route/RoomPresenter load; actual serverNames propagation',
        'jr_state_006_continue_waits_for_resolution': 'physical Continue before pending resolution; same page owner pending action; actual route after own external response',
        'jr_state_007_not_found_recovers': 'own original page not-found/error/recovery event and native frame',
        'jr_state_008_timeout_recovers': 'own page pending request/actual timer completion/error and recovery; no invented screen',
        'jr_state_009_dismiss_closes_flow': 'physical Cancel/Back -> original page lifecycle/dispose -> actual native root route; no synthetic navigator.closed',
    }
    if set(requirements) != {case['caseId'] for case in contract['cases']}:
        raise ValueError('Exact canonical nine-case obligations changed')
    native_files = [ROOT / 'state_tests/runtime/arkts/native' / name for name in (
        'Task14RealFlowV2.suite.js', 'Task14RealFlowV2.adapter.js', 'Task14RealFlowV2Observer.js',
        'Task14RealFlowV2Frame.js', 'Task14DeviceUi.core.js', 'Task14PageObserver.js')]
    return {'protocol': 'task14.arkts.actual-default-adoption.v1', 'status': 'staged_not_ready',
        'historicalModelReassessment': {'counts': candidate['semantic'], 'modelDurationSeconds': 302.552,
            'proof': record(proof_path), 'sourceProof': record(closure_path),
            'newModelRun': False, 'revalidatedOrRelabeled': False, 'originalBytesChanged': False},
        'delegateSources': [record(path) for path in native_files],
        'currentNativeSuiteCaseIds': ['jr_state_001_entry_opens_address_flow'],
        'notAStraightFullNineDelegate': True,
        'caseRequirements': requirements, 'forbiddenWeakHostCases': sorted(WEAK_CASES),
        'noFallbackToOldFormalFinalPoles': True,
        'implementationBeforeDefault': ['new source-parameterized actual-page nine-case suite/guard',
            'physical navigation branches005/006/009 with native route + same production owner/effect receipts',
            'each other case own native setup/event/frames; explicitly scoped domain/timer observations only on same page owner',
            'unknown controls/ambiguous owner/runtime failure -> NS; source absence never semantic FAIL'],
        'defaultApiAfterReview': 'score(platform=arkts, source, base_source, final_source, output, compile_passed, compile_command, timeout<=3600, device_serial)',
        'calibrationRequired': {'poles': ['base', 'final', 'base-copy-agent', 'final-copy-agent'],
            'expectedPFNS': [[0, 9, 0], [9, 0, 0], [0, 9, 0], [9, 0, 0]], 'sameEvaluator': True,
            'oneOverallDeadlineSeconds': 3600, 'includesWaitHashVerifyWriteCleanup': True},
        'compileScope': 'separate source-bound standalone application preflight; never infer app compile from runtime HAP',
        'preservedShared': [record(ROOT / 'scripts/run_runtime_transition_matrix.py'),
            record(ROOT / 'scripts/runtime_semantics/task14_15_formal_core.py')],
        'deviceStarted': False, 'modelCalled': False, 'centralOrReadinessChanged': False,
        'fullNineDelegateImplemented': False, 'hardwareReleaseRequired': True}
