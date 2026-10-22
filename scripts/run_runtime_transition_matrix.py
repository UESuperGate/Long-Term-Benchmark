#!/usr/bin/env python3
"""Reconstruct candidates and run runtime-only transition tests, with fail-closed calibration."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from .runtime_semantics.tasks16_18_channel_evidence import validate_task18_channel_pass
except ImportError:
    from runtime_semantics.tasks16_18_channel_evidence import validate_task18_channel_pass


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair/provenance'
NODE = '/Applications/DevEco-Studio.app/Contents/tools/node/bin/node'
TRUSTED_ENTRY_POLICIES = {
    'task14.initial.start-chat.entry.reviewed.v1': (
        'experiment_results/runtime_transition_20261019/arkts12_15_followup/task14-initial.reviewed-policy.json',
        '06e1ae3fa876a023599daad117554e982db7ecefbbfbe5e68c2a3c2128596aac'),
}
SOURCE_BOUND_ENTRY_POLICIES = {
    'arkts.task13.revision5.page-owner-entry.v8': (
        'task13_page_owner_entry_audit_v8', {'13_user_verification'}, {'arkts'}),
    'task08.arkts.native-common-entry.v1': (
        'task08_arkts_entry_evidence', {'08_threads'}, {'arkts'}),
    'task09.arkts.real-spaces-entry.v1': (
        'task09_arkts_entry_evidence', {'09_spaces_lifecycle'}, {'arkts'}),
    'task09.android.closed-original-home-ui-binding.v2': (
        'task09_android_entry_evidence', {'09_spaces_lifecycle'}, {'android'}),
    'tasks10_11.android.common-prefix.v1': (
        'tasks10_11_runtime_evidence',
        {'10_media_upload_quality', '11_room_upgrade_navigation'}, {'android', 'arkts'}),
    'task10.arkts.actual-prepared-prefix.v2': (
        'task10_repository_prefix_policy', {'10_media_upload_quality'}, {'arkts'}),
    'task12.live-exact-calibration-entry.v1': (
        'task12_live_entry_validation', {'12_report_room'}, {'android', 'arkts'}),
    'arkts.task12.actual-ui-disabled-action.v2': (
        'task12_actual_ui_protocol', {'12_report_room'}, {'arkts'}),
    'arkts.task12.merged-disabled-action.v4': (
        'task12_arkts_runtime_admission', {'12_report_room'}, {'arkts'}),
    'arkts.task12.merged-closed-entry.v4': (
        'task12_arkts_runtime_admission', {'12_report_room'}, {'arkts'}),
    'android.task13.revision5.live-profile-entry.v1': (
        'task13_android_entry_validation', {'13_user_verification'}, {'android'}),
    'task14_15.android.isolated-production-entry.v1': (
        'task14_15_android_entry_evidence',
        {'14_join_room_by_address', '15_account_deactivation'}, {'android'}),
    'task14_15.arkts.isolated-production-entry.v1': (
        'task14_15_arkts_entry_evidence',
        {'14_join_room_by_address', '15_account_deactivation'}, {'arkts'}),
    'task17.android.banner-appyx-runtime-prefix.v1': (
        'task17_android_entry_evidence', {'17_pinned_messages'}, {'android'}),
    'tasks16_17.arkts.real-common-entry.v1': (
        'tasks16_17_arkts_entry_evidence', {'16_identity_reset', '17_pinned_messages'}, {'arkts'}),
}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def counts(report):
    values = Counter(case['status'] for case in report['semantic']['cases'])
    return {'passed': values['pass'], 'failed': values['fail'], 'notScored': values['not_scored'], 'total': sum(values.values())}


def archived_agent_input_conflict(report, contract):
    """Reject known old-prompt candidates when their supplied public scenario changed."""
    if report.get('role') != 'agent':
        return None
    task_id, platform = report.get('taskId'), report.get('platform')
    audit_path = ROOT / 'experiment_results/runtime_transition_20261019/contract_audit/revision_2/manifest.json'
    if not audit_path.exists():
        return None
    patch = ARCHIVE / 'patches' / f'{platform}_{task_id}.patch'
    if not patch.exists() or report.get('provenance', {}).get('patchSha256') != hashlib.sha256(patch.read_bytes()).hexdigest():
        return None
    specs = {case['caseId']: case for case in contract['cases']}
    for change in load(audit_path)['changes']:
        if change['taskId'] != task_id or change['caseId'] not in specs:
            continue
        previous, current = change['before'], specs[change['caseId']]
        fields = ('caseId', 'functionalArea', 'given', 'event', 'invariants')
        if any(previous.get(field) != current.get(field) for field in fields):
            return {'caseId': change['caseId'], 'archivedPatchSha256': report['provenance']['patchSha256'],
                    'reason': 'Archived candidate was generated with different public transition inputs; replay is evaluator diagnostics, not a revised model result.'}
    return None


def unavailable(task_id, platform, role, reason):
    contract = load(ROOT / 'benchmark_tasks' / task_id / 'transitions.json')
    return {
        'schemaVersion': 2, 'taskId': task_id, 'platform': platform, 'role': role,
        'observationMode': 'runtime_state_transition', 'compile': {'passed': None},
        'semantic': {'cases': [{
            'caseId': case['caseId'], 'traceDigest': case['traceDigest'],
            'status': 'not_scored', 'reason': reason,
        } for case in contract['cases']]},
        'diagnostics': {'adapter': 'failed', 'reason': reason},
    }


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    """Only independently reviewed, source-bound runtime entry assertions may fail early."""
    evidence = row.get('entryFailureEvidence', {})
    policy = SOURCE_BOUND_ENTRY_POLICIES.get(evidence.get('policyId'))
    if policy:
        module_name, tasks, platforms = policy
        if report.get('taskId') not in tasks or report.get('platform') not in platforms:
            raise ValueError('Source-bound entry policy belongs to a different task/platform')
        if contract is None:
            contract = load(ROOT / 'benchmark_tasks' / report['taskId'] / 'transitions.json')
        prefix = __package__ + '.runtime_semantics.' if __package__ else 'runtime_semantics.'
        module = importlib.import_module(prefix + module_name)
        module.validate_entry_failure(row, report, used_observation_ids, contract=contract)
        if (evidence.get('policyId') == 'tasks10_11.android.common-prefix.v1' and
                report.get('taskId') == '10_media_upload_quality' and report.get('platform') == 'arkts'):
            closure = importlib.import_module(prefix + 'task10_arkts_closure_evidence')
            closure.validate_entry_failure(row, report, used_observation_ids, contract=contract)
        return
    if report.get('platform') == 'android':
        try:
            from .runtime_semantics.android_entry_evidence import validate_entry_failure as validate_android
        except ImportError:
            from runtime_semantics.android_entry_evidence import validate_entry_failure as validate_android
        validate_android(row, report, used_observation_ids)
        return
    trusted = TRUSTED_ENTRY_POLICIES.get(evidence.get('policyId'))
    if not trusted or report.get('platform') != 'arkts' or row['status'] != 'fail':
        raise ValueError('Unreviewed runtime entry assertion')
    if row.get('observed') is not None or row.get('invariantChecks') or row.get('transitionExecuted') is not False:
        raise ValueError('Entry failure must not invent post-state or evaluated invariants')
    policy = ROOT / trusted[0]
    if hashlib.sha256(policy.read_bytes()).hexdigest() != trusted[1]:
        raise ValueError('Reviewed entry policy changed')
    artifact = Path(evidence['report']).resolve()
    if not artifact.is_relative_to(ROOT / 'experiment_results'):
        raise ValueError('Entry execution evidence must belong to this repository')
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != evidence.get('reportSha256'):
        raise ValueError('Entry execution report digest changed')
    result = subprocess.run([NODE, str(ROOT / 'scripts/runtime_semantics/arkts_native_entry_validate.cjs'),
                             '--report', str(artifact), '--policy', str(policy)],
                            capture_output=True, text=True, timeout=30, check=True)
    assessment = json.loads(result.stdout)
    if assessment['status'] != 'fail' or any(assessment.get(key) != value for key, value in {
            'taskId': report['taskId'], 'role': report['role'], 'caseId': row['caseId'],
            'traceDigest': row['traceDigest']}.items()):
        raise ValueError('Native entry evidence did not establish this case failure')
    observation_ids = assessment.get('observationIds', [])
    if not observation_ids or used_observation_ids.intersection(observation_ids):
        raise ValueError('Entry observations missing or reused')
    used_observation_ids.update(observation_ids)


def validate_report(report, contract):
    expected = {case['caseId']: case['traceDigest'] for case in contract['cases']}
    if not expected or len(expected) != len(contract['cases']):
        raise ValueError('Canonical contract must contain unique nonempty cases')
    actual = {case['caseId']: case['traceDigest'] for case in report['semantic']['cases']}
    if actual != expected or len(report['semantic']['cases']) != len(expected):
        raise ValueError('Runtime report differs from canonical IDs/digests')
    if report.get('observationMode') != 'runtime_state_transition':
        raise ValueError('Source conformance is not runtime semantic evidence')
    if any(case['status'] not in {'pass', 'fail', 'not_scored'} for case in report['semantic']['cases']):
        raise ValueError('Unknown runtime result status')
    if report.get('taskId') != contract.get('taskId'):
        raise ValueError('Runtime report belongs to a different task')
    try:
        from .runtime_semantics.withdrawn_owner_boundaries_v1 import validate_report_evidence as validate_owner_boundaries
    except ImportError:
        from runtime_semantics.withdrawn_owner_boundaries_v1 import validate_report_evidence as validate_owner_boundaries
    validate_owner_boundaries(report)
    try:
        from .runtime_semantics.withdrawn_sdk_boundaries_v1 import validate_report_evidence as validate_sdk_boundaries
    except ImportError:
        from runtime_semantics.withdrawn_sdk_boundaries_v1 import validate_report_evidence as validate_sdk_boundaries
    validate_sdk_boundaries(report)
    if report.get('taskId') == '08_threads' and report.get('platform') == 'android':
        try:
            from .runtime_semantics.task08_android_runtime_evidence import validate_report_evidence
        except ImportError:
            from runtime_semantics.task08_android_runtime_evidence import validate_report_evidence
        validate_report_evidence(report, contract)
    if report.get('taskId') == '12_report_room' and report.get('platform') == 'arkts':
        try:
            from .runtime_semantics.task12_arkts_runtime_admission import validate_report_evidence
        except ImportError:
            from runtime_semantics.task12_arkts_runtime_admission import validate_report_evidence
        validate_report_evidence(report, contract)
    if report.get('taskId') == '13_user_verification' and report.get('platform') == 'arkts':
        try:
            from .runtime_semantics.task13_arkts_runtime_admission import validate_report_evidence
        except ImportError:
            from runtime_semantics.task13_arkts_runtime_admission import validate_report_evidence
        validate_report_evidence(report, contract)
    if report.get('taskId') == '16_identity_reset' and report.get('platform') == 'android':
        try:
            from .runtime_semantics.task16_android_runtime_admission import validate_report_evidence
        except ImportError:
            from runtime_semantics.task16_android_runtime_admission import validate_report_evidence
        validate_report_evidence(report, contract)
    if report.get('taskId') in {'16_identity_reset', '17_pinned_messages'} and report.get('platform') == 'arkts':
        try:
            from .runtime_semantics.tasks16_17_arkts_score_admission import validate_report_evidence
        except ImportError:
            from runtime_semantics.tasks16_17_arkts_score_admission import validate_report_evidence
        validate_report_evidence(report, contract)
    specs = {case['caseId']: case for case in contract['cases']}
    used_observation_ids = set()
    for row in report['semantic']['cases']:
        validate_task18_channel_pass(row, report, specs[row['caseId']])
        if row['status'] == 'not_scored':
            continue
        if report.get('platform') == 'arkts' and report.get('taskId') == '09_spaces_lifecycle':
            try:
                from .runtime_semantics.task09_arkts_entry_evidence import legacy_projection, prefix
            except ImportError:
                from runtime_semantics.task09_arkts_entry_evidence import legacy_projection, prefix
            if (legacy_projection(row) or prefix(row) is not None) and not row.get('entryFailureEvidence'):
                raise ValueError('Unexecuted Spaces lifecycle post-state inferred from common-entry absence')
        if (report.get('platform') == 'arkts' and
                report.get('taskId') in {'16_identity_reset', '17_pinned_messages'}):
            try:
                from .runtime_semantics.tasks16_17_arkts_entry_evidence import prefix_observation
            except ImportError:
                from runtime_semantics.tasks16_17_arkts_entry_evidence import prefix_observation
            if prefix_observation(row, report['taskId']) is not None and not row.get('entryFailureEvidence'):
                raise ValueError('Unexecuted canonical post-state inferred from common-entry absence')
        if 'task16PrefixFailure' in row:
            try:
                from .runtime_semantics.task16_android_prefix_evidence import validate_prefix_failure
            except ImportError:
                from runtime_semantics.task16_android_prefix_evidence import validate_prefix_failure
            validate_prefix_failure(row, report, used_observation_ids, contract)
            continue
        if 'conjunctFailureEvidence' in row or row.get('kind') == 'canonical_conjunct_failure':
            try:
                from .runtime_semantics.android_conjunct_evidence import validate_conjunct_failure
            except ImportError:
                from runtime_semantics.android_conjunct_evidence import validate_conjunct_failure
            validate_conjunct_failure(row, report, used_observation_ids, contract=contract)
            continue
        if row.get('entryFailureEvidence'):
            if (report.get('platform') == 'android' and report.get('taskId') == '12_report_room'
                    and row['entryFailureEvidence'].get('policyId') not in SOURCE_BOUND_ENTRY_POLICIES):
                try:
                    from .runtime_semantics.android_task12_entry_evidence import validate_entry_failure as validate_task12_entry
                except ImportError:
                    from runtime_semantics.android_task12_entry_evidence import validate_entry_failure as validate_task12_entry
                validate_task12_entry(row, report, used_observation_ids, contract=contract)
                continue
            validate_entry_failure(row, report, used_observation_ids, contract)
            continue
        if len(row.get('checkpoints', [])) < 2:
            raise ValueError(f"{row['caseId']}: scored runtime case has no before/after evidence")
        sources = row.get('productionSources') or report.get('provenance', {}).get('productionSources')
        if not sources:
            raise ValueError(f"{row['caseId']}: scored runtime case has no production provenance")
        checks = row.get('invariantChecks', [])
        checked = {check.get('description', check.get('invariant')) for check in checks
                   if isinstance(check.get('passed'), bool) or check.get('status') in ('pass', 'fail')}
        if any(description not in checked for description in specs[row['caseId']].get('invariants', [])):
            raise ValueError(f"{row['caseId']}: scored runtime case is missing invariant observations")
        missing, mismatches = [], []

        def compare(expected_value, observed_value, field=''):
            if isinstance(expected_value, dict):
                if not isinstance(observed_value, dict):
                    mismatches.append(field)
                    return
                for key, value in expected_value.items():
                    name = f'{field}.{key}' if field else key
                    if key not in observed_value:
                        missing.append(name)
                    else:
                        compare(value, observed_value[key], name)
            elif isinstance(expected_value, list):
                if not isinstance(observed_value, list) or len(expected_value) != len(observed_value):
                    mismatches.append(field)
                    return
                for index, value in enumerate(expected_value):
                    compare(value, observed_value[index], f'{field}[{index}]')
            elif expected_value != observed_value or isinstance(expected_value, bool) != isinstance(observed_value, bool):
                mismatches.append(field)

        compare(specs[row['caseId']].get('expected', {}), row.get('observed', {}))
        if missing:
            raise ValueError(f"{row['caseId']}: scored runtime case is missing canonical observations: {missing}")
        failed_invariant = any(check.get('passed') is False or check.get('status') == 'fail' for check in checks)
        if row['status'] == 'pass' and (mismatches or failed_invariant):
            raise ValueError(f"{row['caseId']}: PASS contradicts canonical runtime observations or invariants")
        if row['status'] == 'fail' and not (mismatches or failed_invariant):
            raise ValueError(f"{row['caseId']}: FAIL has no failed runtime assertion")


def incomplete_runtime_repeats(report):
    """A retained successful trace does not erase a later incomplete rerun."""
    return [{'caseId': entry['caseId'], 'reason': entry['incoming'].get('reason'),
             'execution': entry.get('execution')}
            for entry in report.get('diagnostics', {}).get('deviceSupplemental', [])
            if entry.get('action') == 'retain_unscored_diagnostic'
            and entry.get('previous', {}).get('status') in {'pass', 'fail'}
            and entry.get('incoming', {}).get('status') == 'not_scored']


def calibrates(reports, expected_count):
    if expected_count <= 0:
        return False
    for platform in ('android', 'arkts'):
        for role in ('base', 'final'):
            report = reports.get((platform, role))
            if not report or incomplete_runtime_repeats(report):
                return False
            result = counts(report)
            if result['notScored'] or result['total'] != expected_count:
                return False
            if result['passed'] != (0 if role == 'base' else expected_count):
                return False
    return True


def prepare_arkts(task, role, target):
    relative = task['arkts']['finalPath' if role == 'final' else 'basePath']
    provenance = {'baseSource': relative}
    source = ROOT / relative
    if role == 'agent':
        archived = json.loads(subprocess.check_output([
            NODE, str(ROOT / 'scripts/runtime_semantics/archived_arkts_base.cjs'), task['taskId']], text=True))
        if archived:
            source = Path(archived['source'])
            provenance.update(baseSource=str(source.relative_to(ROOT)), archivedBase=archived)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('.git', '.hvigor', 'build', 'oh_modules', 'node_modules'))
    if role == 'agent':
        patch = ARCHIVE / 'patches' / f"arkts_{task['taskId']}.patch"
        # git apply inside a non-repository directory must not inherit the parent repository.
        subprocess.run(['git', 'init', '-q', str(target)], check=True)
        subprocess.run(['git', 'apply', '--binary', str(patch)], cwd=target, check=True, capture_output=True)
        provenance.update({'patch': str(patch.relative_to(ROOT)), 'patchSha256': hashlib.sha256(patch.read_bytes()).hexdigest()})
    return provenance


def execute_native_matrix(task_ids, roles, output, timeout):
    catalog_ids = load(ROOT / 'benchmark_tasks/extraction_catalog.json')['acceptedTaskIds']
    selections = [('all', task_ids)] if set(task_ids) == set(catalog_ids) else [(task, [task]) for task in task_ids]
    role_selections = [('all', roles)] if set(roles) == {'base', 'final', 'agent'} else [(role, [role]) for role in roles]
    for selection, selected_tasks in selections:
        for role, selected_roles in role_selections:
            command = [NODE, str(ROOT / 'scripts/runtime_semantics/arkts_native_smoke.cjs'),
                       '--bundle', selection, '--role', role, '--output-dir', str(output)]
            try:
                subprocess.run(command, cwd=ROOT, check=True, timeout=timeout)
            except (OSError, subprocess.SubprocessError) as error:
                for task_id in selected_tasks:
                    for selected_role in selected_roles:
                        write(output / 'reports' / f'arkts_{task_id}_{selected_role}.json',
                              unavailable(task_id, 'arkts', selected_role, f'Native ArkVM execution failed: {error}'))


def write_readme(output, summary_rows):
    totals = {f'{platform}_{role}': Counter() for platform in ('android', 'arkts') for role in ('base', 'final', 'agent')}
    lines = [
        '# Accepted Tasks Runtime Revalidation', '',
        '**Incomplete: this is execution evidence and coverage diagnostics, not a valid benchmark score.**', '',
        'The earlier 99/202 result was source-pattern conformance. It did not run production transitions and cannot establish runtime polarity.', '',
        'This run reconstructs the same archived MiniMax-M3 candidates from base plus binary-safe patches. It does not generate new agents. The matrix does not re-score application compilation; test-slice/bundle compilation and separate device-fixture HAP packaging are diagnostics.', '',
        '## Runtime Scope', '',
        '- Android: immutable candidate Kotlin source slices, JUnit, real Compose Recomposer and coroutines; scripted external SDK boundaries. Robolectric adapters additionally execute Android framework APIs and real file-backed DataStore. Supplemental tasks08/09/10/11/12/14/15/16/17 tests mount original Compose views and inspect rendered semantics; only fully bound cases are scored. Task08 composer sending has a separately labeled original-presenter/domain chain, not rendered-UI credit. Domain-only evidence does not establish UI, and Robolectric is not device execution; inspect each case scope.',
        '- ArkTS: native Previewer/ArkVM/Hypium executes production domain modules and evaluator adapters. The direct task12 smoke additionally imports an unchanged production `.ets` module. Task14 case002 additionally uses a strictly validated isolated-clock host production replay; its row is explicitly host_transpiled_production, not ArkVM/UI or application compilation. Native filesystem/UI/service claims require per-case positive capability and execution evidence; importing a platform module alone proves none of them.',
        '- ArkTS device follow-up: API23 emulator executes fresh ohosTest HAPs with native ApplicationContext, Preferences, filesystem and AVMetadataExtractor. Per-case result files are pulled and hashed before uninstall. Native UI remains unscored wherever actual page, navigation or system-effect observations are incomplete. See `context-repair/README.md` and `device-calibration/`.',
        '- Reviewed initial-entry failures are case-specific: Android14 rendered Compose and ArkTS14 native UI establish their canonical initial givens and missing required entry. They do not claim post-state, evaluated invariants or failure of the other eight cases.',
        '- Every scored case requires canonical observations, invariant checks, before/after evidence and production hashes. Missing bindings, test compilation errors and unavailable UI/OS observations are `not_scored`, not inferred semantic failures.',
        '- UI-disabled actions must not be bypassed by injecting presenter events and reported as user-facing failures. Such probes are diagnostics until the real event boundary is observed.',
        '- Supplemental rows require matching immutable candidate tree, agent patch, contract, evaluator and production hashes. They merge per case without changing application compilation. Callback-only navigation and retry with unproven screen/media lifetime remain unscored.', '',
        '## Results', '',
        'Each cell is **pass / fail / not_scored**, with the full canonical denominator retained. These are diagnostic counts, not benchmark rates.', '',
        'A completed trace remains recorded when a fresh rerun is unscored, but that unresolved repeat blocks calibration. Task17 ArkTS Loading currently has one PASS and one NS fresh-device execution; its 9/9 retained trace count is not a reproducibility claim.', '',
        '| Task | Android base | Android final | Android agent | ArkTS base | ArkTS final | ArkTS agent |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for row in summary_rows:
        cells = []
        for name in totals:
            value = row['results'].get(name)
            cells.append(f"{value['passed']} / {value['failed']} / {value['notScored']}" if value else 'not run')
            if value:
                totals[name].update(value)
        lines.append(f"| {row['taskId']} | " + ' | '.join(cells) + ' |')
    lines.append('| Total | ' + ' | '.join(f"{v['passed']} / {v['failed']} / {v['notScored']}" for v in totals.values()) + ' |')
    lines += ['', '## Remaining Work', '',
        '1. Bind actual baseline app/navigation behavior. Missing introduced classes currently prevent baseline transitions from being observed; their absence is not counted as runtime failure. Some canonical givens already require final-only UI/history and cannot be reached in base; a versioned common-start/real-action-prefix proposal is awaiting review, with every original post-state assertion retained. No such contract rewrite has been applied.',
              '2. Bind native UI event dispatch, visible/enabled controls, navigation and OS persistence where the canonical contract requires them.',
              '3. Audit final mismatches against the upstream Android event boundary before changing contracts or migrated production code. Preserve agent production code unchanged.',
              '4. Recalibrate all four base/final poles and score every canonical agent case before publishing semantic benchmark metrics.', '',
              '## Reproduction', '', '```sh',
              'python3 scripts/run_runtime_transition_matrix.py --timeout 3600',
              'python3 scripts/run_runtime_transition_matrix.py --summarize-only', '```', '',
              'The first command defaults to native ArkVM for ArkTS. Exit 2 means runtime calibration/coverage is incomplete, not that every semantic case failed. `--arkts-runtime host` is explicitly transpiled host-domain diagnostics. `reports/` contains per-case observations. `native/` retains compact native evidence, bundle hashes and compressed execution logs. `summary.json` has `benchmarkSemanticMetric: null` until calibration succeeds. Overall elapsed time covers runtime revalidation and repairs, not model generation or summed subagent durations.', '',
              'Coverage explanations are in `state_tests/runtime/android/*/coverage.json` and each ArkTS case report. See `state_tests/runtime/arkts/native/README.md` for the native execution boundary.', '',
              '## Contract Audit', '',
              '- Approved shared contract [revision 2](contract_audit/revision_2/README.md) preserves old contracts, digests, reports and evidence. Only two clauses were corrected; IDs and invariants were retained.',
              '- Task09 `accept_invite`: expect the accepted invitation to be absent from the seen set. Android executes SpacePresenter -> AcceptDeclineInvitePresenter -> DefaultAcceptInvite -> file-backed store and close/reopen.',
              '- Task10 `estimate_video_presets`: real 1920x1080/60000ms inputs replace unreachable injected bitrates. Both adapters check exact output sizes, overhead and six inclusive/exclusive boundary points.',
              '- Task10 archived agents read the old explicit bitrate inputs. Their replays are evaluator diagnostics, not comparable model results under the revised public input. See [completed-read evidence](contract_audit/revision_2/agent_input_audit.json); fresh isolated one-shot runs are required after calibration.',
              '- Task18: real Android channel bootstrap migrates SystemDefault/v0 to ElementDefault/v1. A [separate reachability probe](android18_given_reachability/probe-v2.json) executes the legitimate presenter selection: SystemDefault is reachable at v2, then changing to ElementDefault reaches v3. Thus cases002/004 have an absolute-version expectation conflict, not an unreachable sound by itself; case009 still cannot establish its joint SystemDefault/v0 given. No preferences are reset after bootstrap and no canonical score changes from this diagnostic.', '']
    lines += ['## Migration Repair Audit', '',
              '- User-approved task18 URI-copy repair opens the actual picker URI through the native filesystem and passes the resulting file descriptor to `copyFile`, closing it in `finally`. No expected values, archived agent patches or production outcomes are replaced. Before/after source, hashes and failed evidence are retained in [the repair audit](migration_audit/task18_uri_copy_v1/README.md).',
              '- Task18 native picker evidence requires the actual mounted-page call chain, a pending SDK selector, system-provider identity and unchanged Preferences. See [the fresh device executions](device-calibration/README.md); a presenter callback alone is insufficient.', '']
    task18_final = next((row['results'].get('arkts_final') for row in summary_rows
                         if row['taskId'] == '18_custom_notification_sounds'), None)
    if task18_final:
        lines += [f"- Current task18 ArkTS final: {task18_final['passed']} pass / "
                  f"{task18_final['failed']} fail / {task18_final['notScored']} not_scored. "
                  'This single pole does not establish four-way calibration.', '']
    lines += ['- The [channel-effect audit](migration_audit/task18_channel_effect_review/WITHDRAWAL.md) withdraws five task18 ArkTS final ledger-only PASSes. Real Preferences/copy evidence is retained, but it does not establish notification-service recreation. The earlier 10/10 adapter result is not a complete final validation.',
              '- The archived task18 agent restore case now passes in a fresh Context-repaired device diagnostic. It remains separate from the primary agent matrix and is not a newly generated model result. See [device evidence](device-calibration/README.md).', '']
    lines += ['## Device Fixture Repair', '',
              '- Task17 `view_in_timeline` now passes in two fresh device installations. Fixture setup and invariant readback use the actual original AbilityContext, not a different application-level Preferences store. Real list click, timeline focus and unchanged pinned storage are recorded; production and assertions are unchanged.',
              '- Native module-identity and UI transport findings, including unsupported paths, are retained in [the device follow-up](device-calibration/README.md).', '']
    (output / 'README.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    catalog = load(ROOT / 'benchmark_tasks/extraction_catalog.json')
    parser.add_argument('--task', action='append', choices=catalog['acceptedTaskIds'])
    parser.add_argument('--platform', action='append', choices=('android', 'arkts'))
    parser.add_argument('--role', action='append', choices=('base', 'final', 'agent'))
    parser.add_argument('--output', type=Path, default=ROOT / f'experiment_results/runtime_transition_{datetime.now():%Y%m%d_%H%M%S}')
    parser.add_argument('--timeout', type=int, default=3600)
    parser.add_argument('--summarize-only', action='store_true', help='Validate and summarize existing runtime reports without rerunning')
    parser.add_argument('--arkts-runtime', choices=('native', 'host'), default='native',
                        help='Native ArkVM/Hypium by default; host is transpiled-domain diagnostics only')
    args = parser.parse_args()
    task_ids = args.task or catalog['acceptedTaskIds']
    platforms = args.platform or ['android', 'arkts']
    roles = args.role or ['base', 'final', 'agent']
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    previous_summary = output / 'summary.json'
    started_at = load(previous_summary)['startedAt'] if previous_summary.exists() else datetime.now(timezone.utc).isoformat()
    all_rows = []
    if not args.summarize_only and 'arkts' in platforms and args.arkts_runtime == 'native':
        execute_native_matrix(task_ids, roles, output, args.timeout)
    for task_id in ([] if args.summarize_only else task_ids):
        task = load(ROOT / 'benchmark_tasks' / task_id / 'task.json')
        contract = load(ROOT / 'benchmark_tasks' / task_id / 'transitions.json')
        reports = {}
        for platform in platforms:
            for role in roles:
                report_path = output / 'reports' / f'{platform}_{task_id}_{role}.json'
                provenance = {}
                with tempfile.TemporaryDirectory(prefix='ltb-runtime-') as temporary:
                    candidate = Path(temporary) / 'candidate'
                    try:
                        if platform == 'arkts' and args.arkts_runtime == 'native':
                            report = load(report_path)
                            validate_report(report, contract)
                            command = None
                        elif platform == 'arkts':
                            provenance = prepare_arkts(task, role, candidate)
                            command = [NODE, str(ROOT / 'scripts/runtime_semantics/arkts_runtime.cjs'),
                                       '--task', task_id, '--role', role, '--source', str(candidate), '--output', str(report_path)]
                        else:
                            command = ['python3', str(ROOT / 'scripts/runtime_semantics/android_runner.py'),
                                       '--task', task_id, '--role', role, '--output', str(report_path), '--timeout', str(args.timeout)]
                        if command:
                            completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                                       stderr=subprocess.STDOUT, timeout=args.timeout)
                            log = output / 'logs' / f'{platform}_{task_id}_{role}.txt'
                            log.parent.mkdir(parents=True, exist_ok=True)
                            log.write_text(completed.stdout, encoding='utf-8')
                            if completed.returncode or not report_path.exists():
                                raise RuntimeError(f'Runtime runner exit={completed.returncode}: {completed.stdout[-4000:]}')
                        report = load(report_path)
                        validate_report(report, contract)
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                        report = unavailable(task_id, platform, role, str(error))
                    report['provenance'] = {**report.get('provenance', {}), **provenance}
                    report['semantic'].update(counts(report))
                    write(report_path, report)
                    reports[(platform, role)] = report
                    result = {'taskId': task_id, 'platform': platform, 'role': role, **counts(report)}
                    print(json.dumps(result), flush=True)
                    all_rows.append(result)
                    write(output / 'progress.json', {'startedAt': started_at, 'rows': all_rows})
        # Include prior reports to support independent platform runs without mixing source scores.
        for platform in ('android', 'arkts'):
            for role in ('base', 'final', 'agent'):
                existing = output / 'reports' / f'{platform}_{task_id}_{role}.json'
                if (platform, role) not in reports and existing.exists():
                    previous = load(existing)
                    validate_report(previous, contract)
                    reports[(platform, role)] = previous
    summary_rows = []
    all_valid = True
    all_agents_scored = True
    input_conflicts = []
    incomplete_repeats = []
    for task_id in load(ROOT / 'benchmark_tasks/extraction_catalog.json')['acceptedTaskIds']:
        contract = load(ROOT / 'benchmark_tasks' / task_id / 'transitions.json')
        reports = {}
        for platform in ('android', 'arkts'):
            for role in ('base', 'final', 'agent'):
                p = output / 'reports' / f'{platform}_{task_id}_{role}.json'
                if p.exists():
                    reports[(platform, role)] = load(p)
                    validate_report(reports[(platform, role)], contract)
        valid = calibrates(reports, len(contract['cases']))
        all_valid = all_valid and valid
        agents_scored = all((platform, 'agent') in reports and
                            counts(reports[(platform, 'agent')])['notScored'] == 0
                            for platform in ('android', 'arkts'))
        all_agents_scored = all_agents_scored and agents_scored
        for (platform, role), report in reports.items():
            incomplete_repeats.extend({'taskId': task_id, 'platform': platform, 'role': role, **repeat}
                                      for repeat in incomplete_runtime_repeats(report))
            conflict = archived_agent_input_conflict(report, contract)
            if conflict:
                input_conflicts.append({'taskId': task_id, 'platform': platform, **conflict})
        summary_rows.append({'taskId': task_id, 'caseCount': len(contract['cases']), 'calibrationValid': valid,
                             'agentCoverageComplete': agents_scored,
                             'results': {f'{platform}_{role}': counts(report) for (platform, role), report in reports.items()}})
    validated = all_valid and all_agents_scored and not input_conflicts and not incomplete_repeats
    write(output / 'summary.json', {
        'schemaVersion': 2, 'observationMode': 'runtime_state_transition', 'allPolarityValid': all_valid,
        'allAgentCasesScored': all_agents_scored,
        'status': 'validated' if validated else 'incomplete_runtime_validation',
        'archivedAgentPublicInputConflicts': input_conflicts,
        'incompleteRuntimeRepeatDiagnostics': incomplete_repeats,
        'startedAt': started_at, 'finishedAt': datetime.now(timezone.utc).isoformat(),
        'durationSeconds': round((datetime.now(timezone.utc) - datetime.fromisoformat(started_at)).total_seconds(), 3),
        'timingScope': 'overall runtime revalidation wall clock including repairs and reruns; not new agent generation time',
        'tasks': summary_rows,
        'excludedTaskIds': catalog.get('excludedTaskIds', []),
        'benchmarkSemanticMetric': None if not validated else 'see calibrated per-case reports',
        'note': 'Unscored cases and invalid final calibration prohibit a claim of complete runtime benchmark validation.',
    })
    write_readme(output, summary_rows)
    write(output / 'progress.json', {
        'startedAt': started_at,
        'status': 'validated' if validated else 'incomplete_runtime_validation',
        'rows': [{'taskId': row['taskId'], 'platform': name.split('_')[0], 'role': name.split('_')[1], **result}
                 for row in summary_rows for name, result in row['results'].items()],
    })
    return 0 if validated else 2


if __name__ == '__main__':
    raise SystemExit(main())
