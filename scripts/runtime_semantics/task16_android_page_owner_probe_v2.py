"""Locked connected-owner diagnostic, never formal or standalone-app scoring."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import tasks16_17_native_controller_v3 as supervisor

FIXTURE = ROOT/'state_tests/runtime/android/16_identity_reset/page_owner'
LOCKS = [Path('/tmp/long-term-benchmark-android-full-build.lock'), ROOT/'state_tests/runtime/android/.build.lock']


def load(name):
    spec = importlib.util.spec_from_file_location('page_owner_'+name, FIXTURE/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(path):
    data = Path(path).read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def worker(request_path):
    from scripts.runtime_semantics import android_robolectric as robo
    from scripts.runtime_semantics.android_robolectric_ui_resources import compile_resources
    robo.compile_resources = compile_resources
    request_path = Path(request_path)
    root = request_path.parent
    request = json.loads(request_path.read_text())
    deadline = supervisor.timer.child_local_deadline(request['childBudget'])
    assert request['worker'] == record(__file__)
    task = json.loads((ROOT/'benchmark_tasks/16_identity_reset/task.json').read_text())
    # run_slice's immutable loader selects a manifest ref. This narrow diagnostic
    # refuses ANY mismatch instead of claiming arbitrary supplied-ref support.
    assert request['revision'] == task['android']['finalCommit']
    original_run, original_popen = subprocess.run, subprocess.Popen
    events = []
    attempt = 0
    def observed_popen(*args, **kwargs):
        assert not kwargs.get('start_new_session'), 'descendants must stay in owned process group'
        child = original_popen(*args, **kwargs)
        events.append(dict(command=args[0] if args else kwargs.get('args'), pid=child.pid, pgid=os.getpgid(child.pid)))
        supervisor.atomic(root/'actual-process-launches.json', events)
        return child
    def observed_run(*args, **kwargs):
        kwargs['timeout'] = min(kwargs.get('timeout') or 3600, supervisor.assembly.remaining(deadline))
        result = original_run(*args, **kwargs)
        argv = args[0] if args else kwargs['args']
        if isinstance(argv, list) and 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler' in argv:
            compile_root = Path(argv[argv.index('-d')+1])
            data = dict(command=argv, exitCode=result.returncode,
                actualCompiledInputs=[record(value) for value in argv if str(value).endswith('.kt')],
                classFiles=[record(path) for path in sorted(compile_root.rglob('*.class'))])
            target = root/f'attempt-{attempt:02d}'
            with tarfile.open(target/'compiled-classes.tar.gz', 'w:gz') as archive:
                for path in sorted(compile_root.rglob('*.class')):
                    archive.add(path, arcname=str(path.relative_to(compile_root)))
            data['retainedClasses'] = record(target/'compiled-classes.tar.gz')
            supervisor.atomic(target/'actual-kotlin-compilation.json', data)
        return result
    subprocess.run, subprocess.Popen = observed_run, observed_popen
    try:
        while True:
            supervisor.assembly.remaining(deadline)
            if shutil.disk_usage(root).free < 8*1024**3:
                raise OSError('8GiB floor before diagnostic attempt')
            attempt += 1
            target = root/f'attempt-{attempt:02d}'
            plan = load('plan').generate(Path(request['source']), request['revision'], target)
            for name in ('IdentityPageOwnerTest.kt', 'MainThreadClockDispatcher.kt'):
                shutil.copyfile(FIXTURE/name, target/name)
            supervisor.atomic(root/'progress.json', dict(stage='run_slice', attempt=attempt, pid=os.getpid(), formalStatus='not_scored'))
            result = robo.run_slice('16_identity_reset', 'final', Path(request['source']), FIXTURE.parent,
                target/'configuration.json', target/'slice.json', supervisor.assembly.remaining(deadline))
            bound = result.get('provenance', {}).get('commit') == request['revision']
            facts, gaps = {}, {}
            for row in result.get('observations', []):
                try:
                    facts[row['key']] = load('evidence').inspect_episode(row['key'], row['checkpoints'])
                except Exception as error:
                    gaps[str(row.get('key'))] = repr(error)
            supervisor.atomic(target/'independent-diagnostic.json', dict(explicitRevisionBound=bound,
                facts=facts, gaps=gaps, formalStatus='not_scored', standaloneAppCompile='not_run',
                runtimeResult=record(target/'slice.json'), actualWorker=record(__file__)))
            supervisor.atomic(root/'progress.json', dict(stage='attempt_complete' if result['status']=='passed' else 'awaiting_fixture_repair',
                attempt=attempt, status=result['status'], compile=result.get('runtimeCompile'), formalStatus='not_scored'))
            if result['status']=='passed' and bound:
                return
            decision = root/f'continue-attempt-{attempt+1:02d}.json'
            while not decision.exists():
                supervisor.assembly.remaining(deadline)
                time.sleep(0.25)
            action = json.loads(decision.read_text())
            if action.get('stop'):
                return
            assert action['fixtureSources'] == [record(FIXTURE/name) for name in ('IdentityPageOwnerTest.kt','MainThreadClockDispatcher.kt','plan.py')]
    finally:
        subprocess.run, subprocess.Popen = original_run, original_popen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--revision')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--budget-root', type=Path, required='--worker' not in sys.argv)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    output = args.output.resolve()
    origin_path = args.budget_root.resolve()/'request.json'
    origin = json.loads(origin_path.read_text())
    original_deadline = origin['deadlineEpochMs']/1000
    remaining = min(args.timeout, original_deadline-time.time()-1)
    if remaining <= 0:
        raise TimeoutError('Original repair budget exhausted; no new work')
    held = []
    def prepare(root, clock):
        clock.deadline = min(clock.deadline, time.monotonic()+original_deadline-time.time())
        clock.work_deadline = min(clock.work_deadline, clock.deadline-clock.reserve)
        signal.setitimer(signal.ITIMER_REAL, max(0.000001,clock.work_deadline-time.monotonic()))
        supervisor.atomic(root/'ready.json', dict(pid=os.getpid(), runRoot=str(root), stage='waiting_start_gate', heavyStarted=False))
        print(json.dumps(dict(pid=os.getpid(), runRoot=str(root), stage='waiting_start_gate')), flush=True)
        while not (root/'start.json').exists():
            clock.check_work()
            time.sleep(0.1)
        for path in LOCKS:
            handle = path.open('a')
            held.append(handle)
            while True:
                clock.check_work()
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(0.1)
        if shutil.disk_usage(root).free < 8*1024**3:
            raise OSError('8GiB floor after both locks, before worker preparation')
        supervisor.atomic(root/'android-locks.json', dict(paths=list(map(str, LOCKS)), ownerPid=os.getpid(), acquired=True))
        return dict(requestId='android16-connected-owner', source=str(args.source.resolve()), revision=args.revision,
            originalBudget=dict(request=record(origin_path), startedAtEpochMs=origin['startedAtEpochMs'],
                                deadlineEpochMs=origin['deadlineEpochMs'], fresh3600Granted=False),
            worker=record(__file__), fixtureSources=[record(FIXTURE/name) for name in ('IdentityPageOwnerTest.kt','MainThreadClockDispatcher.kt','plan.py')],
            deadlineEpochMs=int((time.time()+clock.deadline-time.monotonic())*1000), formalStatus='not_scored')
    def cleanup(root, deadline):
        cleaned = supervisor.cleanup_work(root, deadline)
        for handle in held:
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()
        held.clear()
        supervisor.atomic(root/'android-locks-released.json', dict(released=True, withinOriginalBudget=True))
        return cleaned
    try:
        supervisor._supervise(output, remaining, prepare,
            lambda request: [sys.executable,'-B',str(Path(__file__).resolve()),'--worker',str(request)],
            lambda *_: dict(diagnosticOnly=True, formalStatus='not_scored'), cleanup=cleanup)
    finally:
        # A hard abort can skip normal cleanup. Closing OUR FDs is not evidence
        # that a timed-out episode completed cleanup within its original budget.
        for handle in held:
            handle.close()


if __name__ == '__main__':
    main()
