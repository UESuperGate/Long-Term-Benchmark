"""Offline nineteen-case/four-pole plan and fail-closed retained-control audit.

There is deliberately no build/device/model executor here. Device scheduling is
coordinator-owned. Canonical definitions are copied intact, never generated from
roles, score markers or source text. The stable assembler v1 remains unchanged.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import tasks16_17_native_report_assembler_v1 as assembly

SCHEMA = 'tasks16_17.native-controls.offline.v1'
POLES = ('base', 'final', 'random_base_copy', 'random_final_copy')
COMMON_REQUIREMENTS = [
    'fresh original Ability/bootstrap; unavailable service is not canonical given',
    'actual original page lifecycle creates the canonical SDK-bound owner',
    'per-case prospective before/after complete input captures and actual build seal',
    'complete native UI inventory and actual given/event/after checkpoints',
    'original page callback and exact owner/service/SDK receiver provenance',
    'controlled external SDK inputs only; no detached production owner',
    'all original canonical observations/invariants; unknown evidence stays NS',
]
BOUNDARIES = {
    'continue_requests_confirmation': ['Continue physical UI; confirmation rendered; no SDK acquisition'],
    'dismiss_confirmation': ['Continue prefix establishes actual confirmation=true; physical Cancel; no SDK effect'],
    'confirm_starts_handle': ['actual confirmation=true -> single native Confirm -> held SDK/Loading',
        'separate DOMAIN reentry of same original page-owned public callback',
        'pending acquisition identity and success/cached same SDK handle; no UI double-click claim'],
    'password_handle_routes': ['held SDK start -> actual password handle -> original password page and identical handle input'],
    'oidc_handle_routes_and_resets': ['held SDK start -> actual OIDC handle -> real embedded WebView and delegated poll'],
    'handle_failure_recovers': ['held SDK -> real failure -> cleanup -> interactive root -> physical retry -> new pending acquisition'],
    'password_submit_calls_handle': ['actual password page; empty submit disabled; real text input; physical submit; SDK operation held'],
    'password_failure_clears_on_edit': ['actual input/submit; external SDK error; rendered failure; real edit clears error without replacing handle'],
    'success_waits_for_verification': ['SDK password success while unverified; actual modal held; external verification callback completes parent once'],
    'cancel_cleans_up': ['three distinct ORIGINAL page episodes: physical exit, native OIDC Back, real router destruction',
        'actual SDK cancel+destroy and settled pending poll; no completion after cleanup'],
    'open_loading': ['physical open -> delegated held timeline request -> actual loading; physical Back retains parent timeline'],
    'load_failure': ['physical open/held loading; external failure; real failed UI, not empty UI'],
    'empty_success': ['physical open/held loading; external open success and authoritative empty item flow; real empty UI'],
    'filled_list': ['actual SDK subscription consumes authoritative item flow; event identity/order equals visible native rows'],
    'unpin_permission_denied': ['server permission false; actual message action menu; unpin absent; no SDK/list mutation'],
    'unpin_permission_allowed': ['server permission true; actual menu; sync permission revocation removes unpin without local override'],
    'view_in_timeline': ['actual pinned menu navigation; original parent timeline consumes focused event and renders the target row'],
    'unpin_success': ['actual active timeline SDK unpin; acknowledgement does not filter list/cache',
        'only authoritative item flow updates visible list and actual native Preferences'],
    'unpin_failure_recovery': ['actual active timeline SDK error; original list/cache retained; real error/retry controls remain usable'],
}


def write(path, value):
    assembly.write_json(path, value)


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def create_plan(sources, policy_path, policy_sha256, output):
    """Sources: explicit task -> {base: path, final: path}; never role inference."""
    output = assembly.audit_path(output)
    assembly.require(not output.exists(), 'new control-plan path required')
    policy = assembly.load_policy(policy_path, policy_sha256)
    assembly.require(set(sources) == set(assembly.TASKS), 'exactly the two scoped tasks required')
    deadline = time.monotonic() + 120
    task_plans = []
    for task_id in assembly.TASKS:
        assembly.require(task_id in sources and set(sources[task_id]) == {'base', 'final'}, 'both explicit source inputs required per task')
        actual = {}
        for label, source in sources[task_id].items():
            rows = assembly.inventory(source, deadline)
            assembly.require(sum(row['taskId'] == task_id and row['completeInputs'] == rows for row in policy['variants']) == 1,
                             'unreviewed control source input')
            actual[label] = dict(source=str(Path(source).resolve()), inputDigest=digest(rows), completeInputs=rows)
        assembly.require(actual['base']['inputDigest'] != actual['final']['inputDigest'], 'base/final inputs must be distinct')
        contract_path = ROOT / 'benchmark_tasks' / task_id / 'transitions.json'
        contract = json.loads(contract_path.read_text())
        cases = contract['cases']
        assembly.require(all(case['key'] in BOUNDARIES for case in cases), 'missing native boundary definition')
        controls = []
        for pole in POLES:
            source_label = 'base' if pole in ('base', 'random_base_copy') else 'final'
            goal = 0 if source_label == 'base' else len(cases)
            controls.append(dict(pole=pole, source=actual[source_label], runtimeRole='agent',
                directoryPolicy='fresh arbitrary opaque directory; never inspect its name to assign a result',
                copyPolicy='independent byte-identical source copy with prospective capture; no code edits',
                expectedPolarityGoalOnly=dict(passed=goal, failed=len(cases)-goal, notScored=0),
                overallDeadlineSeconds=3600,
                deadlineScope='prepare+lock wait+all cases+build+runtime+archive+cleanup, NOT 3600 per phase/case',
                cases=[dict(caseId=case['caseId'], key=case['key'], traceDigest=case['traceDigest'], ordinal=index+1,
                    canonicalDefinition=copy.deepcopy(case), actualNativeEpisodeRequired=True,
                    prospectiveCaptureRequired=True, originalInvariantsUnevaluatedIfPhysicalFeatureMissing=True,
                    sameNativeReceiptReuseAllowed=False, boundaryProofRequirements=COMMON_REQUIREMENTS + BOUNDARIES[case['key']])
                    for index, case in enumerate(cases)]))
        task_plans.append(dict(taskId=task_id, canonicalContract=assembly.record(contract_path),
            caseCount=len(cases), controls=controls))
    value = dict(schemaVersion=SCHEMA, policy=assembly.record(policy_path), generator=assembly.record(__file__),
        taskPlans=task_plans, canonicalCaseCount=sum(task['caseCount'] for task in task_plans),
        plannedIndependentEpisodes=sum(task['caseCount'] * len(POLES) for task in task_plans),
        scheduling=dict(mode='offline_only_wait_for_coordinator_release', parallelism=1, diskFloorGiB=8,
            sharedLease='/tmp/ltb-arkts-device-6460677a198b1872', forceForeignLockRemovalAllowed=False,
            currentQueue='Task13 fresh default v2 -> Task12 prospective -> wait for explicit release'),
        resultStatus='not_run', benchmarkMetricsAvailable=False, publicAdmissionChanged=False,
        modelBuildOrDeviceStarted=False, fullCalibrationAvailable=False,
        knownUnprovenBoundaries=[
            'Only Task16/001 and Task17/001 have current same-owner native receipts; remaining cases and all four-pole reruns are pending',
            'Task16/006 current UI fixture aggregates warm-up managerTransitions; current strict derivation rejects mixed managers. Do not hide warm-up logs; needs reviewed test-only scoped derivation successor after freeze window',
            'Actual auth-handle type/URL, OIDC poll/lifecycle cancellation, permissions and native persistence still require their new native episodes',
            'Offline definitions/source binding are not semantic/runtime passes',
        ])
    assembly.require(value['canonicalCaseCount'] == 19 and value['plannedIndependentEpisodes'] == 76,
                     'nineteen-case/four-pole task boundary changed')
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output, value)
    return value


def ensure_unique_runtime_evidence(rows):
    """Four controls cannot relabel/reuse one real execution as another pole."""
    for key in ('receiptPath', 'rawSha256', 'executionNonce', 'candidateSource'):
        values = [row[key] for row in rows]
        assembly.require(all(values) and len(set(values)) == len(values), 'control cases reuse actual runtime ' + key)


def inspect_closure(plan_path, reports, policy_sha256, output):
    """Revalidate supplied completed reports; missing controls remain incomplete."""
    plan_path = assembly.audit_path(plan_path)
    plan = json.loads(plan_path.read_text())
    assembly.require(plan.get('schemaVersion') == SCHEMA and plan.get('resultStatus') == 'not_run', 'wrong offline plan')
    assembly.require([task['taskId'] for task in plan['taskPlans']] == list(assembly.TASKS) and
                     plan['canonicalCaseCount'] == 19 and plan['plannedIndependentEpisodes'] == 76, 'incomplete task/control plan')
    assembly.load_policy(plan['policy']['path'], policy_sha256)
    assembly.require(assembly.record(plan['policy']['path']) == plan['policy'], 'plan policy changed')
    assembly.require(set(reports) <= {(task, pole) for task in assembly.TASKS for pole in POLES}, 'unknown task/pole report would be silently ignored')
    findings, results, executions = [], [], []
    for task in plan['taskPlans']:
        task_id = task['taskId']
        contract_path = ROOT / 'benchmark_tasks' / task_id / 'transitions.json'
        assembly.require(assembly.record(contract_path) == task['canonicalContract'], 'plan canonical contract changed')
        canonical = json.loads(contract_path.read_text())['cases']
        assembly.require([row['pole'] for row in task['controls']] == list(POLES), 'missing/duplicate control pole')
        for control in task['controls']:
            pole = control['pole']
            expected_passes = 0 if pole in ('base', 'random_base_copy') else len(canonical)
            assembly.require(control['expectedPolarityGoalOnly'] == dict(passed=expected_passes,
                failed=len(canonical)-expected_passes, notScored=0), 'polarity goal was relaxed')
            assembly.require(control['overallDeadlineSeconds'] == 3600 and control['runtimeRole'] == 'agent', 'execution/deadline plan changed')
            assembly.require(pole in POLES and [row['canonicalDefinition'] for row in control['cases']] == canonical,
                             'plan dropped/relaxed canonical case')
            path = reports.get((task_id, pole))
            if path is None:
                findings.append(dict(taskId=task_id, pole=pole, reason='missing independently executed control'))
                continue
            verification = assembly.verify_assembled(path, policy_sha256)
            report = json.loads(Path(path).read_text())
            assembly.require(report['taskId'] == task_id, 'report assigned to wrong task')
            inventory_ref = report['provenance']['sourceInventory']
            inputs = json.loads(Path(inventory_ref['path']).read_text())['files']
            assembly.require(inputs == control['source']['completeInputs'], 'pole source does not match its explicitly planned input')
            for row in report['semantic']['cases']:
                if row['status'] == 'not_scored':
                    findings.append(dict(taskId=task_id, pole=pole, caseId=row['caseId'], reason='case lacks complete actual native proof'))
            expected = control['expectedPolarityGoalOnly']
            if any(report['counts'][key] != value for key, value in expected.items()):
                findings.append(dict(taskId=task_id, pole=pole, reason='actual polarity does not meet planned goal', actual=report['counts']))
            ledger = json.loads(Path(report['provenance']['fullRawLedger']['path']).read_text())
            for entry in ledger['cases']:
                receipt = json.loads(Path(entry['originalReceipt']['path']).read_text())
                execution = json.loads(Path(receipt['execution']['path']).read_text())
                executions.append(dict(taskId=task_id, pole=pole, caseId=entry['caseId'],
                    receiptPath=entry['originalReceipt']['path'], rawSha256=entry['nativeRaw']['sha256'],
                    executionNonce=execution['executionNonce'], candidateSource=receipt['candidateSource']))
            results.append(dict(taskId=task_id, pole=pole, verification=verification))
    ensure_unique_runtime_evidence(executions)
    complete = not findings and len(results) == 8 and len(executions) == 76
    value = dict(schemaVersion=SCHEMA + '.closure', plan=assembly.record(plan_path), results=results,
        completeFourPoleNativeClosure=complete, actualNativeEpisodes=len(executions), findings=findings,
        executions=executions, publicAdmissionChanged=False, benchmarkMetricsAvailable=False,
        modelBuildOrDeviceStarted=False, mainReviewStillRequired=True,
        overallTaskBudgetVerified=False, fullEndToEndControlClosure=False,
        remainingControllerWork='A scheduled executor and retained per-pole overall prepare/wait/build/runtime/cleanup budget receipts are still required; this module does not execute or attest them')
    output = assembly.audit_path(output)
    write(output, value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='command', required=True)
    plan = modes.add_parser('plan')
    plan.add_argument('--source', nargs=3, action='append', metavar=('TASK', 'BASE_SOURCE', 'FINAL_SOURCE'), required=True)
    plan.add_argument('--policy', type=Path, required=True)
    plan.add_argument('--policy-sha256', required=True)
    plan.add_argument('--output', type=Path, required=True)
    audit = modes.add_parser('closure')
    audit.add_argument('--plan', type=Path, required=True)
    audit.add_argument('--report', nargs=3, action='append', metavar=('TASK', 'POLE', 'REPORT'), default=[])
    audit.add_argument('--policy-sha256', required=True)
    audit.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'plan':
        assembly.require(len({row[0] for row in args.source}) == len(args.source), 'duplicate source task argument')
        explicit = {task: dict(base=base, final=final) for task, base, final in args.source}
        value = create_plan(explicit, args.policy, args.policy_sha256, args.output)
        print(json.dumps(dict(canonicalCases=value['canonicalCaseCount'], plannedEpisodes=value['plannedIndependentEpisodes'],
                              resultStatus=value['resultStatus'], output=str(args.output))))
    else:
        assembly.require(len({(row[0], row[1]) for row in args.report}) == len(args.report), 'duplicate report/pole arguments cannot overwrite history')
        value = inspect_closure(args.plan, {(task, pole): path for task, pole, path in args.report},
                                args.policy_sha256, args.output)
        print(json.dumps(dict(complete=value['completeFourPoleNativeClosure'], actualEpisodes=value['actualNativeEpisodes'],
                              findings=len(value['findings']), output=str(args.output))))
