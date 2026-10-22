#!/usr/bin/env python3
"""Preflight untouched ArkTS bases through the actual model runner, without model calls."""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / 'scripts/run_new_tasks_opencode_eval_macos.py'
DEFAULT_TASKS = ('11_room_upgrade_navigation', '12_report_room')
TASKS = (*DEFAULT_TASKS, '14_join_room_by_address', '15_account_deactivation',
         '16_identity_reset', '17_pinned_messages')
BINARY_SUFFIXES = {'.apk', '.hap', '.aab', '.apks', '.har', '.app', '.abc', '.so'}


def load_runner():
    spec = importlib.util.spec_from_file_location('actual_agent_preflight_runner', RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def inventory(source):
    return [{**record(file), 'path': file.relative_to(source).as_posix()}
            for file in sorted((source / 'entry/src/main').rglob('*')) if file.is_file()]


def has_api_secret(value):
    if isinstance(value, dict):
        return any(key.lower() in {'apikey', 'api_key', 'authorization', 'access_token'} or has_api_secret(item)
                   for key, item in value.items())
    return isinstance(value, list) and any(has_api_secret(item) for item in value)


def checked_confirmation(path, runner):
    value = json.loads(path.read_text())
    reviewer = value.get('reviewer', value.get('confirmedBy'))
    if not isinstance(reviewer, str) or not reviewer.strip() or value.get('recursiveAuditStable') is not True:
        raise ValueError('Explicit recursive-audit stability confirmation and nonempty reviewer required')
    if value.get('runnerSha256') != record(runner.__file__)['sha256']:
        raise ValueError('Reviewed confirmation is for a different runner revision')
    if value.get('auditHelperSha256') != record(runner.subagent_audit.__file__)['sha256']:
        raise ValueError('Reviewed confirmation is for a different recursive audit helper')
    return record(path)


def shell_audit(runner, candidate):
    config = runner.opencode_config('arkts', candidate)
    policy = config['permission']
    allowed = runner.fixed_shell_allowlist('arkts', candidate)
    if policy.get('task') != 'allow' or policy['shell'] != policy['bash'] or policy['shell'].get('*') != 'deny':
        raise ValueError('Subagent or fixed shell policy changed')
    expected = {'true', 'pwd', 'ls', 'git status --short', 'git diff --stat', 'git diff --name-only',
                runner.agent_build_command('arkts')}
    if allowed != expected or has_api_secret(config):
        raise ValueError('Fixed allowlist or secret-free candidate configuration changed')
    return {'allowedShellCommands': sorted(allowed), 'subagentsAllowed': True,
            'recursiveAuditRequired': True, 'apiSecretsInCandidateConfig': False}


def preflight(output, confirmation, tasks=DEFAULT_TASKS, runner=None, *, diagnostic_before_freeze=False,
              timeout=3600):
    if not 0 < timeout <= 3600:
        raise ValueError('Preflight requires one 0 < timeout <= 3600 overall budget')
    started = time.monotonic()
    deadline = started + timeout
    work_deadline = deadline - min(15.0, timeout * .05)
    def remaining(phase, *, finalizing=False):
        value = (deadline if finalizing else work_deadline) - time.monotonic()
        if value <= 0:
            raise TimeoutError('Overall preflight deadline exhausted during ' + phase)
        return value
    runner = runner or load_runner()
    confirmation_record = record(confirmation) if diagnostic_before_freeze else checked_confirmation(confirmation, runner)
    if not tasks or any(task not in TASKS for task in tasks) or len(tasks) != len(set(tasks)):
        raise ValueError('This bounded preflight accepts distinct ArkTS Task11/12/14/15/16/17 only')
    output.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now().astimezone().isoformat(timespec='seconds')
    fingerprints = [record(runner.__file__), record(runner.subagent_audit.__file__)]
    results = []
    for task in tasks:
        evidence = output / task
        evidence.mkdir()
        row = {'taskId': task, 'platform': 'arkts', 'modelCalled': False,
               'observationScope': 'untouched base standalone application build; no evaluator fixtures or semantics',
               'availability': 'preflight_environment_unavailable', 'passed': False}
        candidate = None
        with tempfile.TemporaryDirectory(prefix='ltb-agent-standalone-preflight-') as temporary:
            try:
                remaining('prepare')
                runner.require_disk_space(output)
                source = runner.ROOT / runner.task_data(task)['arkts']['basePath']
                before = inventory(source)
                candidate = runner.prepare(task, 'arkts', Path(temporary), deadline=work_deadline)
                if not before or inventory(candidate) != before:
                    raise ValueError('Runner prepare did not preserve untouched production')
                policy = shell_audit(runner, candidate)
                baseline = runner.archive_candidate_baseline(candidate, evidence / 'baseline',
                    phase='preflight_before_standalone_build', deadline=work_deadline)
                env = runner.environment('arkts', candidate)
                if env.get('PWD') != str(candidate) or env.get('OLDPWD') != str(candidate):
                    raise ValueError('Runner environment escaped candidate')
                row.update(source=str(source), production=before, candidateBaseline=baseline, isolationPolicy=policy,
                    environment={key: env[key] for key in ('PWD', 'OLDPWD', 'DEVECO_SDK_HOME', 'JAVA_HOME') if key in env},
                    toolPaths={name: shutil.which(name, path=env.get('PATH')) for name in ('hvigorw', 'node', 'ohpm', 'java')})
                remaining('build')
                runner.require_disk_space(output)
                exit_code, command = runner.build('arkts', candidate, env, evidence / 'standalone-build.log',
                                                  deadline=work_deadline)
                unchanged = inventory(candidate) == before and inventory(source) == before
                changed = [path for path in runner.status_paths(candidate, deadline=work_deadline)
                           if runner.is_production(path, 'arkts')]
                if not unchanged or changed:
                    raise ValueError('Standalone preflight mutated source or candidate production')
                row.update(buildExit=exit_code, buildCommand=command,
                    applicationCompile={'passed': exit_code == 0, 'scope': 'untouched_base_standalone_application_build'},
                    productionUnchanged=True, passed=exit_code == 0,
                    availability='available' if exit_code == 0 else 'preflight_build_failed')
            except Exception as error:
                row.update(passed=False, reason=str(error), errorType=type(error).__name__)
            finally:
                if candidate and candidate.exists():
                    remaining('cleanup', finalizing=True)
                    artifacts = []
                    for parent, directories, files in os.walk(candidate):
                        directories[:] = [name for name in directories if name not in {'.git', 'node_modules', 'oh_modules'}]
                        for name in files:
                            file = Path(parent) / name
                            if file.suffix.lower() in BINARY_SUFFIXES:
                                artifacts.append(record(file))
                    write(evidence / 'all-binary-hashes.json', {'hashesRecordedBeforeRemoval': True, 'artifacts': artifacts})
                    runner.clean_application_build(candidate, evidence / 'runner-build-cleanup.json', deadline=deadline)
                    runner.clean_candidate(candidate, deadline=deadline)
                    cleaned_build = json.loads((evidence / 'runner-build-cleanup.json').read_text()).get('cleanupCompleted') is True
                    row['cleanup'] = {'candidateRemoved': not candidate.exists(), 'binariesRetained': False,
                                      'runnerHashBeforeCleaningUsed': True}
                    if not cleaned_build or candidate.exists():
                        row.update(passed=False, availability='preflight_cleanup_failed')
        write(evidence / 'standalone-preflight.json', row)
        results.append(row)
    unchanged_runner = fingerprints == [record(runner.__file__), record(runner.subagent_audit.__file__)]
    retained_binaries = [str(file) for file in output.rglob('*') if file.is_file() and file.suffix.lower() in BINARY_SUFFIXES]
    standalone_passed = not retained_binaries and all(row['passed'] for row in results)
    payload = {'schemaVersion': 1, 'phase': 'before_model', 'modelCalled': False,
               'mode': 'diagnostic_before_runner_freeze' if diagnostic_before_freeze else 'reviewed_runner_preflight',
               'reviewedStabilityGatePassed': not diagnostic_before_freeze,
               'standaloneBuildsPassed': standalone_passed,
               'excludedFromAgentTiming': True, 'confirmation': confirmation_record,
               'runnerInputs': fingerprints, 'runnerUnchanged': unchanged_runner,
               'startedAt': started_at, 'finishedAt': datetime.now().astimezone().isoformat(timespec='seconds'),
               'durationSeconds': round(time.monotonic() - started, 3),
               'overallTimeoutSeconds': timeout, 'deadlineIncludesPrepareBuildAndCleanup': True,
               'timingScope': 'overall preflight interval only; not a sum of subagent durations',
               'binariesRetained': retained_binaries,
               'passed': not diagnostic_before_freeze and unchanged_runner and standalone_passed, 'tasks': results}
    write(output / 'preflight.json', payload)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--confirmation-file', type=Path, required=True,
                        help='Review JSON: reviewer, recursiveAuditStable, runnerSha256, auditHelperSha256')
    parser.add_argument('--diagnostic-before-freeze', action='store_true',
                        help='Only probe standalone builds; never pass the model-start stability gate')
    parser.add_argument('--task', action='append', choices=TASKS)
    parser.add_argument('--timeout', type=float, default=3600)
    args = parser.parse_args()
    report = preflight(args.output.resolve(), args.confirmation_file.resolve(), args.task or DEFAULT_TASKS,
                       diagnostic_before_freeze=args.diagnostic_before_freeze, timeout=args.timeout)
    print(json.dumps({'passed': report['passed'], 'standaloneBuildsPassed': report['standaloneBuildsPassed'],
                      'reviewedStabilityGatePassed': report['reviewedStabilityGatePassed'], 'modelCalled': False,
                      'tasks': [{'taskId': row['taskId'], 'passed': row['passed'], 'availability': row['availability']}
                                for row in report['tasks']]}))
    raise SystemExit(0 if (report['standaloneBuildsPassed'] if args.diagnostic_before_freeze else report['passed']) else 1)
