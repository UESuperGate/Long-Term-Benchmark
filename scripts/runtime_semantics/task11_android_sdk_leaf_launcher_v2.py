"""Queued Task11 diagnostic using the reviewed v3 owned-process supervisor.

No timer is implemented here. No work starts on import. Coordinator release is
technical resource scheduling, not semantic admission or human authorization.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from . import task11_android_sdk_leaf_preparation as fixture
from . import tasks16_17_native_controller_v3 as supervisor

ROOT = fixture.ROOT
SCHEMA = 'task11.android-sdk-leaf-launcher.v2'
MODULE = 'scripts.runtime_semantics.task11_android_sdk_leaf_launcher_v2'
LOCKS = [Path('/tmp/long-term-benchmark-android-full-build.lock'),
         ROOT / 'state_tests/runtime/android/.build.lock']


def require(value, reason):
    if not value:
        raise ValueError(reason)


def implementation():
    paths = [Path(__file__), Path(fixture.__file__), Path(supervisor.__file__),
             Path(supervisor.timer.__file__), Path(supervisor.assembly.__file__),
             fixture.ORIGINAL, fixture.LEAF, fixture.TEMPLATE,
             fixture.TASK / 'navigation/source_closure.py']
    paths += [ROOT / 'scripts/runtime_semantics' / name for name in (
        'task11_plaintext_sdk.py', 'task10_11_android_strict_common.py',
        'task14_15_formal_core.py', 'android_robolectric.py',
        'android_robolectric_ui_resources.py', 'android_robolectric_dependencies.py')]
    return [fixture.record(path) for path in paths]


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError('Original Task11 worker budget exhausted; no stage reset')
    return value


def require_floor(path):
    require(shutil.disk_usage(path).free >= 8 * 1024**3, '8GiB floor; heavy work refused')


@contextlib.contextmanager
def inherited_processes(output, deadline):
    """Record all child launches; only the existing parent owns group termination."""
    output = Path(output)
    pid, pgid = os.getpid(), os.getpgrp()
    require(pid == pgid, 'Worker must be the supervisor-owned session/group leader')
    original_popen, original_run = subprocess.Popen, subprocess.run
    launches, compilations = [], []

    def popen(*args, **kwargs):
        remaining(deadline)
        require_floor(output)
        argv = args[0] if args else kwargs.get('args')
        require(isinstance(argv, (list, tuple)) and not kwargs.get('shell'), 'Fixed argv only')
        require(not kwargs.get('start_new_session') and kwargs.get('process_group') is None and
                kwargs.get('preexec_fn') is None and not kwargs.get('creationflags'),
                'Nested session/group manipulation prohibited')
        process = original_popen(*args, **kwargs)
        actual_group = os.getpgid(process.pid)
        require(actual_group == pgid, 'Child escaped the owned group')
        launches.append(dict(pid=process.pid, pgid=actual_group, command=list(map(str, argv)),
                             startedAtEpochMs=int(time.time()*1000)))
        supervisor.atomic(output / 'actual-process-launches.json', launches)
        return process

    def run(*args, **kwargs):
        remaining(deadline)
        # Direct-child timeout/kill is NOT the process-tree supervisor. Keep the
        # worker alive and blocked until the original parent stops its whole PGID.
        kwargs.pop('timeout', None)
        raw_argv = args[0] if args else kwargs.get('args')
        require(isinstance(raw_argv, (list, tuple)) and not kwargs.get('shell'), 'Fixed argv only')
        argv = list(map(str, raw_argv))
        compiler = ('org.jetbrains.kotlin.cli.jvm.K2JVMCompiler' in argv or
                    Path(argv[0]).name == 'javac')
        compiled = None
        if compiler:
            paths = {Path(argv[0])}
            paths.update(Path(arg) for arg in argv if arg.endswith(('.kt', '.java')))
            for index, arg in enumerate(argv[:-1]):
                if arg in ('-cp', '-classpath'):
                    paths.update(Path(name) for name in argv[index + 1].split(os.pathsep)
                                 if Path(name).is_file())
            paths.update(Path(arg.split('=', 1)[1]) for arg in argv if arg.startswith('-Xplugin='))
            compiled = dict(command=argv, inputsBeforeCompile=[fixture.record(p) for p in sorted(paths)],
                            compilerExitCode=None, binaryHashesBeforeCleanup=[])
            compilations.append(compiled)
            supervisor.atomic(output / 'actual-compilation.json', compilations)
        process = original_run(*args, **kwargs)
        remaining(deadline)
        if compiled is not None:
            compiled['compilerExitCode'] = process.returncode
            if '-d' in argv:
                classes = Path(argv[argv.index('-d') + 1])
                compiled['binaryHashesBeforeCleanup'] = [fixture.record(p) for p in sorted(classes.rglob('*.class'))]
            supervisor.atomic(output / 'actual-compilation.json', compilations)
        return process

    subprocess.Popen, subprocess.run = popen, run
    try:
        yield launches
    finally:
        subprocess.Popen, subprocess.run = original_popen, original_run


@contextlib.contextmanager
def defer_owned_cleanup(output):
    """Do not let shared runtime finalizers remove inputs of surviving descendants."""
    output = Path(output).resolve()
    owned = (output / 'owned-work').resolve()
    original = shutil.rmtree
    deferred = []

    def retain(path, *args, **kwargs):
        require(kwargs.get('dir_fd') is None, 'Unbound relative directory removal refused')
        resolved = Path(path).resolve()
        require(resolved.is_relative_to(owned) and resolved != owned,
                'Worker may only defer its own temporary directories; no foreign deletion')
        deferred.append(str(resolved))
        supervisor.atomic(output / 'deferred-temporary-cleanup.json', dict(
            paths=deferred, removedByWorker=False, parentGroupGoneRequired=True))

    shutil.rmtree = retain
    try:
        yield
    finally:
        shutil.rmtree = original


def run_runtime(source, plan, output, deadline):
    """Same v1 fixture/configuration; no v1 wall_deadline or execute_prepared."""
    runtime, resources, mechanics, _ = fixture.runtime_modules()
    original_prepare, original_resources = runtime.prepare, runtime.compile_resources
    config = copy.deepcopy(plan['configurationRecipe'])
    jna = fixture.TASK / 'messages/.native/jna-5.17.0.jar'
    require(jna.is_file(), 'Existing desktop JNA required; no download/native build')
    for binding in (plan['evaluatorInputs'] + [plan['derivedEvaluator']] +
                    plan['entrypointBindings'] + plan['configuredEvaluatorInputs']):
        require(fixture.record(binding['path']) == {key: binding[key] for key in ('path', 'bytes', 'sha256')},
                'Frozen candidate/evaluator input changed')
    try:
        with mechanics.bound_git_snapshot(source, output / 'owned-work/snapshot') as (control, snapshot), \
                mechanics.patched_candidate(control, source):
            spec = importlib.util.spec_from_file_location('task11_v2_whole_source_closure',
                                                        fixture.TASK / 'navigation/source_closure.py')
            closure = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(closure)
            config['sources'] = closure.closure(control, snapshot['snapshotTree'], config['entrypoints'])
            config['offlineDependencies'] = True
            configuration = output / 'runtime.config.json'
            supervisor.atomic(configuration, config)

            def environment(configuration, work):
                value = original_prepare(configuration, work)
                value['jars'] = [jna] + [p for p in value['jars'] if not p.name.startswith('jna-')]
                value['jvmArgs'] += [
                    f'-Druntime.contract.path={ROOT / "benchmark_tasks/11_room_upgrade_navigation/transitions.json"}',
                    f'-Druntime.rendered.output={output / "rendered"}',
                ]
                return value

            runtime.prepare, runtime.compile_resources = environment, resources.compile_resources
            raw = runtime.run_slice('11_room_upgrade_navigation', 'agent', control,
                fixture.TASK / 'sdk_leaf_v1', configuration, output / 'runtime.raw.json', remaining(deadline))
            supervisor.atomic(output / 'runtime-source-binding.json', dict(sourceSnapshot=snapshot,
                configuration=fixture.record(configuration), desktopJna=fixture.record(jna)))
            return raw
    finally:
        runtime.prepare, runtime.compile_resources = original_prepare, original_resources


def worker(request_path):
    request_path = Path(request_path).resolve(strict=True)
    output = request_path.parent
    request = json.loads(request_path.read_text())
    require(request['schema'] == SCHEMA and request['implementation'] == implementation(),
            'Task11 request/implementation version mismatch')
    require(request['resourceSchedule'] == 'coordinator_released_small_slice', 'Queue release required')
    require(0 < request['deadlineEpochMs'] - request['startedAtEpochMs'] <= 3600000,
            'One original overall budget <=3600 required')
    deadline = supervisor.timer.child_local_deadline(request['childBudget'])
    require(os.getpid() == os.getpgrp(), 'Worker is not owned group leader')
    require(Path(tempfile.gettempdir()).resolve() == (output / 'owned-work/tmp').resolve(),
            'Worker temporary compiler inputs must stay under supervisor-owned work')
    require(os.getppid() == request['controllerPid'], 'Worker parent is not the recorded supervisor')
    launch_path = output / 'worker-launch.json'
    while not launch_path.exists():
        time.sleep(min(.01, remaining(deadline)))
    launch = json.loads(launch_path.read_text())
    require(launch['pid'] == launch['pgid'] == os.getpid() and
            launch['request'] == fixture.record(request_path) and
            launch['command'] == [sys.executable, '-B', '-m', MODULE, '--worker', str(request_path)],
            'Worker launch/request is not source-bound to the owned parent')
    source = Path(request['source']).resolve(strict=True)
    require(not (output.is_relative_to(source) or source.is_relative_to(output)),
            'Input candidate and output must be disjoint')
    from .task14_15_formal_core import bounded_file_lock
    result = dict(schema=SCHEMA, pid=os.getpid(), pgid=os.getpgrp(),
                  request=fixture.record(request_path), semanticPromotionEligible=False,
                  semanticScore=None, status='not_scored', runtimeCompile={'status': 'not_run'})
    try:
        with inherited_processes(output, deadline), defer_owned_cleanup(output), \
                bounded_file_lock(LOCKS[0], deadline, 'Task11 v2 global Android queue'), \
                bounded_file_lock(LOCKS[1], deadline, 'Task11 v2 runtime queue'):
            require_floor(output)
            require(shutil.which('mvn') is not None, 'Existing Maven required; no installation')
            # Preparation/export is INSIDE the original parent clock, not a new run.
            plan = fixture.prepare(source, output / 'evaluator-plan')
            result['preparation'] = fixture.record(output / 'evaluator-plan/preparation.json')
            raw = run_runtime(source, plan, output, deadline)
            result.update(status='diagnostic_completed', runtimeCompile=raw.get('runtimeCompile', {'status': 'not_run'}),
                          diagnosticSliceStatus=raw['status'], raw=fixture.record(output / 'runtime.raw.json'))
            require(fixture.record(output / 'evaluator-plan/preparation.json') == result['preparation'],
                    'Preparation changed during runtime')
    except Exception as failure:
        result.update(status='not_scored', error=f'{type(failure).__name__}: {failure}')
    remaining(deadline)
    result['finishedAtEpochMs'] = int(time.time()*1000)
    supervisor.atomic(output / 'worker-result.json', result)
    return result


def finalize(output, request, clock):
    clock.check_work()
    result = json.loads((output / 'worker-result.json').read_text())
    launch = json.loads((output / 'worker-launch.json').read_text())
    require(result['schema'] == SCHEMA and result['semanticPromotionEligible'] is False and
            result['semanticScore'] is None, 'Task11 diagnostic identity/authority mismatch')
    require(result['pid'] == result['pgid'] == launch['pid'] == launch['pgid'], 'Worker identity mismatch')
    require(result['request'] == fixture.record(output / 'request.json'), 'Worker request binding mismatch')
    require(request['implementation'] == implementation(), 'Implementation changed during diagnostic')
    require(request['startedAtEpochMs'] <= result['finishedAtEpochMs'] <= request['childBudget']['deadlineEpochMs'],
            'Worker finished outside original remaining budget')
    launches = output / 'actual-process-launches.json'
    if launches.exists():
        for child in json.loads(launches.read_text()):
            require(child['pgid'] == launch['pgid'], 'Descendant process group mismatch')
    if result.get('raw'):
        require(fixture.record(output / 'runtime.raw.json') == result['raw'], 'Raw report binding changed')
    clock.check_work()
    supervisor.atomic(output / 'task11-diagnostic.json', result)
    return result


def supervise(source, output, *, resource_clear_reviewed=False, timeout=3600):
    require(resource_clear_reviewed, 'Await coordinator small-slice release; no JVM started')

    def prepare(root, clock):
        clock.check_work()
        candidate = Path(source).resolve(strict=True)
        require((candidate / 'gradlew').is_file(), 'Explicit standalone candidate required')
        require(not (root.is_relative_to(candidate) or candidate.is_relative_to(root)),
                'Candidate and new diagnostic output must be disjoint')
        return dict(schema=SCHEMA, requestId=uuid.uuid4().hex, source=str(candidate),
                    controllerPid=os.getpid(),
                    deadlineEpochMs=int((time.time()+clock.deadline-time.monotonic())*1000),
                    implementation=implementation(), resourceSchedule='coordinator_released_small_slice',
                    semanticPromotionEligible=False, semanticScore=None)

    # Reuse, do not fork, the tested atomic-revoke/unreaped-PGID/hard-stop protocol.
    # Its admission seal is a diagnostic controller seal, NOT Task11 publication.
    return supervisor._supervise(output, timeout, prepare,
        lambda request: [sys.executable, '-B', '-m', MODULE, '--worker', str(request)], finalize)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source', type=Path)
    mode.add_argument('--worker', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--resource-clear-reviewed', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return 0
    if args.output is None:
        parser.error('--output required')
    result = supervise(args.source, args.output, resource_clear_reviewed=args.resource_clear_reviewed,
                       timeout=args.timeout)
    return 0 if (result is not None and result['runtimeCompile']['status'] == 'passed' and
                 result.get('diagnosticSliceStatus') == 'passed') else 2


if __name__ == '__main__':
    raise SystemExit(main())
