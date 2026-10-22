"""Unregistered source-parameterized Task12 merged native evaluator.

Build/device execution is explicit only. Import and offline tests never launch it.
The caller's existing local monotonic deadline remains the sole budget authority.
"""

import argparse
from contextlib import contextmanager
import hashlib
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback

from . import task12_arkts_merged_protocol_v1 as proof
from . import task12_13_runtime_support as support

NODE = Path('/Applications/DevEco-Studio.app/Contents/tools/node/bin/node')
HDC = Path.home() / 'Library/OpenHarmony/Sdk/23/toolchains/hdc'
MODULE = 'scripts.runtime_semantics.task12_arkts_merged_runtime_v1'


class WorkerFailure(RuntimeError):
    def __init__(self, message, safe):
        super().__init__(message)
        self.cleanup_safe = safe


def remaining(deadline):
    proof.check(deadline)
    return deadline - time.monotonic()


def run(command, *, output, work_deadline, deadline, environment=None):
    """Own one process group; always retain logs and signal/reap failures separately."""
    proof.check(work_deadline)
    started = time.monotonic()
    receipt = {'command': command, 'parentPid': os.getpid(), 'parentClock': 'local_monotonic',
               'started': started, 'remainingBudgetSeconds': remaining(work_deadline), 'signalErrors': []}
    process = None
    original = None
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as log:
        try:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       env=environment, start_new_session=True)
            receipt.update(pid=process.pid, pgid=process.pid)
            receipt['newSessionVerified'] = os.getpgid(process.pid) == process.pid and os.getsid(process.pid) == process.pid
            if not receipt['newSessionVerified']:
                raise RuntimeError('Worker does not own the expected new process group/session')
            process.wait(timeout=remaining(work_deadline))
            if process.returncode:
                raise RuntimeError('Worker exited ' + str(process.returncode))
        except BaseException as error:
            original = error
            receipt['originalTraceback'] = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        finally:
            if process is not None:
                # Only the group created by our own start_new_session Popen is addressed.
                for sig in ((signal.SIGTERM, signal.SIGKILL) if receipt.get('newSessionVerified') else ()):
                    try:
                        os.killpg(process.pid, 0)
                    except ProcessLookupError:
                        break
                    except OSError as error:
                        receipt['signalErrors'].append(repr(error))
                        break
                    try:
                        os.killpg(process.pid, sig)
                    except ProcessLookupError:
                        break
                    except OSError as error:
                        receipt['signalErrors'].append(repr(error))
                    try:
                        process.wait(timeout=min(2, remaining(deadline)))
                    except (subprocess.TimeoutExpired, TimeoutError) as error:
                        receipt['signalErrors'].append(repr(error))
                try:
                    process.wait(timeout=min(2, remaining(deadline)))
                except (subprocess.TimeoutExpired, TimeoutError) as error:
                    receipt['signalErrors'].append(repr(error))
                try:
                    os.killpg(process.pid, 0)
                    gone = False
                except ProcessLookupError:
                    gone = True
                except OSError as error:
                    receipt['signalErrors'].append(repr(error))
                    gone = False
                receipt.update(exitCode=process.returncode, reaped=process.returncode is not None,
                               processGroupAbsent=gone, cleanupSafe=gone and process.returncode is not None and
                               receipt.get('newSessionVerified') is True)
            else:
                receipt.update(cleanupSafe=True, processNotStarted=True)
            receipt.update(finished=time.monotonic(), originalError=repr(original) if original else None)
            log.flush()
            proof.write(output.with_suffix('.process.json'), receipt)
    if original is not None or not receipt['cleanupSafe']:
        raise WorkerFailure(str(original or 'Owned descendants remain'), receipt['cleanupSafe']) from original
    return receipt


@contextmanager
def device_lease(serial, deadline, safe):
    lock = Path('/tmp') / ('ltb-arkts-device-' + hashlib.sha256(serial.encode()).hexdigest()[:16])
    while True:
        proof.check(deadline)
        try:
            lock.mkdir()
            break
        except FileExistsError:
            time.sleep(min(1, remaining(deadline)))
    own = lock.stat()
    try:
        yield
    finally:
        # Foreign/replaced leases and leases with surviving workers are never removed.
        if safe[0] and not lock.is_symlink() and lock.exists():
            now = lock.stat()
            if (own.st_ino, own.st_ctime_ns) == (now.st_ino, now.st_ctime_ns):
                lock.rmdir()
            else:
                raise RuntimeError('Owned device lease identity changed; not removed')


def cleanup(evidence, deadline):
    """Only this invocation's outputs; persist every owned hash before unlink."""
    ledger = evidence / 'cleanup.hashes.jsonl'
    receipt = {'localOnly': True, 'complete': False, 'removed': [], 'binaryHashes': [],
               'remoteCleanup': 'unknown', 'ledger': str(ledger)}
    try:
        with ledger.open('x') as stream:
            for path in sorted(evidence.rglob('*')):
                proof.check(deadline)
                relative = path.relative_to(evidence)
                temporary = relative.parts[0] == 'owned-temporary'
                transient = any(part in {'build', '.hvigor', '.gradle'} for part in relative.parts)
                if not (temporary or transient or path.suffix.lower() in proof.BINARIES):
                    continue
                if path.is_symlink():
                    item = {'path': str(path), 'symlinkTarget': os.readlink(path)}
                elif path.is_file():
                    item = proof.file_record(path, deadline)
                    if (temporary or transient) and path.suffix.lower() in {'.json', '.jsonl', '.log'}:
                        retained = evidence / 'retained-temporary-audit' / (hashlib.sha256(str(path).encode()).hexdigest() + path.suffix)
                        retained.parent.mkdir(exist_ok=True)
                        with path.open('rb') as incoming, retained.open('xb') as outgoing:
                            while True:
                                proof.check(deadline)
                                block = incoming.read(1024 * 1024)
                                if not block:
                                    break
                                outgoing.write(block)
                        item['retained'] = proof.file_record(retained, deadline)
                else:
                    continue
                stream.write(__import__('json').dumps(item) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
                if path.suffix.lower() in proof.BINARIES and 'sha256' in item:
                    receipt['binaryHashes'].append(item)
                path.unlink()
                receipt['removed'].append(str(path))
            for path in sorted(evidence.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                proof.check(deadline)
                if path.is_dir() and not path.is_symlink() and (path.name in {'build', '.hvigor', '.gradle'} or
                        path.relative_to(evidence).parts[0] == 'owned-temporary'):
                    path.rmdir()
        receipt['complete'] = True
    except Exception as error:
        receipt['error'] = repr(error)
    proof.write(evidence / 'cleanup.json', receipt)
    return receipt


def unavailable(contract, reason):
    return [dict(caseId=spec['caseId'], key=spec['key'], traceDigest=spec['traceDigest'], status='not_scored',
                 reason=reason, observed=None, invariantChecks=[], transitionExecuted=False) for spec in contract['cases']]


def evaluate(*, task, platform, source, role, output, deadline, serial='127.0.0.1:5555'):
    budget = remaining(deadline)
    if not math.isfinite(budget) or not 0 < budget <= 3600:
        raise ValueError('Merged evaluator requires an original remaining deadline in (0, 3600]')
    if platform != 'arkts' or task.task_id != '12_report_room' or role not in ('base', 'final', 'agent'):
        raise ValueError('Task12 ArkTS only')
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or source == output or source in output.parents:
        raise ValueError('Evidence must be fresh and outside candidate source')
    evidence = output.with_suffix('.merged-v1-evidence')
    evidence.mkdir(parents=True, exist_ok=False)
    reserve = min(90, budget / 5)
    work_deadline = deadline - reserve
    contract = proof.load(proof.CONTRACT)
    rows = unavailable(contract, 'Merged evaluator incomplete')
    safe = [True]
    runtime_compile = {'passed': False, 'status': 'not_scored', 'scope': 'source-bound runtime HAP; not standalone compile metric'}
    error = None
    retained = {}
    before = None
    def owned_run(command, **kwargs):
        try:
            return run(command, **kwargs)
        except WorkerFailure as exception:
            safe[0] = exception.cleanup_safe
            raise
    try:
        if proof.file_record(proof.CONTRACT, work_deadline)['sha256'] != proof.CONTRACT_SHA:
            raise ValueError('Canonical contract differs')
        before = proof.inventory(source, work_deadline)
        pins = proof.producer_records(work_deadline)
        proof.write(evidence / 'source-before.json', before)
        proof.write(evidence / 'producer-before.json', {'files': pins})
        if shutil.disk_usage(evidence).free < 8 * 1024**3:
            raise RuntimeError('Storage protection: below 8 GiB')
        temporary = evidence / 'owned-temporary'
        temporary.mkdir()
        build_dir = evidence / 'application-build'
        build_config = evidence / 'build-config.json'
        with support.android_full_build_lock(work_deadline):
            if shutil.disk_usage(evidence).free < 8 * 1024**3:
                raise RuntimeError('Storage protection after lock wait: below 8 GiB')
            proof.write(build_config, {'source': str(source), 'output': str(build_dir), 'temporary': str(temporary),
                                      'remainingBudgetSeconds': remaining(work_deadline)})
            environment = {**os.environ, 'TMPDIR': str(temporary), 'PYTHONDONTWRITEBYTECODE': '1'}
            owned_run([sys.executable, '-B', '-m', MODULE, '--build-worker', str(build_config)],
                output=evidence / 'build-worker.log', work_deadline=work_deadline, deadline=deadline, environment=environment)
        build_path = build_dir / 'application-build.json'
        build = proof.load(build_path)
        if any(build.get(key) is not True for key in ('passed', 'productionUnchanged',
                'copiedProductionUnchanged', 'temporaryProjectRemoved')):
            raise ValueError('Runtime build/source continuity failed')
        identity_code = """const fs=require('node:fs'),J=require(process.argv[1]);
const bundle=J.parse(fs.readFileSync(process.argv[2],'utf8')).app.bundleName;
if(typeof bundle!=='string'||!/^([a-zA-Z][a-zA-Z0-9_]*\\.)+[a-zA-Z][a-zA-Z0-9_]*$/.test(bundle))throw Error('Invalid app identity');
process.stdout.write(JSON.stringify({bundle}));"""
        owned_run([str(NODE), '-e', identity_code, str(proof.JSON5), str(source / 'AppScope/app.json5')],
                  output=evidence / 'application-identity.json', work_deadline=work_deadline, deadline=deadline)
        bundle = proof.load(evidence / 'application-identity.json')['bundle']
        runtime_compile.update(passed=True, status='passed')
        config_path = evidence / 'native-config.json'
        config = {'source': str(source), 'bundle': bundle, 'hap': build['hap']['path'],
                  'buildReport': str(build_path), 'contract': str(proof.CONTRACT), 'hdc': str(HDC),
                  'serial': serial, 'port': 18743, 'output': str(evidence / 'native')}
        with device_lease(serial, work_deadline, safe):
            support.wait_hdc_connected(serial=serial, deadline=work_deadline, log=evidence / 'hdc-readiness.log')
            config['remainingSeconds'] = remaining(work_deadline)
            proof.write(config_path, config)
            owned_run([str(NODE), str(proof.RUNNER), str(config_path)], output=evidence / 'native-worker.log',
                work_deadline=work_deadline, deadline=deadline)
            raw_path = evidence / 'native/runtime.native.json'
            raw = proof.load(raw_path)
            proof.validate_envelope(raw, source=source, source_inventory=before, build_path=build_path,
                                    config_path=config_path, deadline=work_deadline)
            owned_run([str(NODE), '-e', proof.NODE_VERIFY, str(proof.FACTS), str(raw_path), str(proof.CONTRACT),
                 config['bundle'], str(evidence / 'native')], output=evidence / 'independent-verification.log',
                work_deadline=work_deadline, deadline=deadline)
            recomputed = proof.load(evidence / 'independent-verification.log')
            if recomputed.get('validated') is not True or proof.producer_records(work_deadline) != pins:
                raise ValueError('Independent proof or frozen producer continuity failed')
            rows = raw['semantic']['cases']
            retained = {'raw': proof.file_record(raw_path, work_deadline),
                        'build': proof.file_record(build_path, work_deadline),
                        'recomputation': proof.file_record(evidence / 'independent-verification.log', work_deadline)}
    except BaseException as exception:
        if isinstance(exception, WorkerFailure):
            safe[0] = exception.cleanup_safe
        error = repr(exception)
        rows = unavailable(contract, error)
    finally:
        local_cleanup = cleanup(evidence, deadline) if safe[0] else {'complete': False, 'reason': 'owned workers may remain'}
    if not local_cleanup['complete']:
        rows = unavailable(contract, 'Owned local hash-cleanup incomplete: ' + str(local_cleanup))
    result = {'schemaVersion': 2, 'taskId': task.task_id, 'platform': platform, 'role': role,
              'observationMode': 'runtime_state_transition', 'runtimeProtocol': proof.PROTOCOL,
              'runtimeCompile': runtime_compile,
              'semantic': {'total': len(rows), 'passed': sum(r['status'] == 'pass' for r in rows),
                           'failed': sum(r['status'] == 'fail' for r in rows),
                           'notScored': sum(r['status'] == 'not_scored' for r in rows), 'cases': rows},
              'provenance': {'candidateSource': str(source), 'sourceInventory': before, 'runtimeEvidence': retained},
              'diagnostics': {'error': error, 'localCleanup': local_cleanup, 'ownedWorkersGone': safe[0],
                              'rawRetainedOnFailure': str(evidence), 'sourceObserverUsed': False,
                              'hostTranspilationUsed': False, 'historicalRuntimeUsed': False},
              'publication': {'eligible': False, 'reason': 'New protocol awaits independent review/public registration/fresh four controls'}}
    proof.write(output, result)
    return result


def build_worker(config_path):
    """Child-local deadline from remaining budget; outer owned group is hard-bounded."""
    from .task12_arkts_merged_build_v1 import build_application
    config = proof.load(config_path)
    budget = config['remainingBudgetSeconds']
    if not math.isfinite(budget) or not 0 < budget <= 3600:
        raise ValueError('Invalid child remaining budget')
    deadline = time.monotonic() + budget
    build_application(source=Path(config['source']), output=Path(config['output']),
                      temporary=Path(config['temporary']), deadline=deadline)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-worker', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--role', choices=('base', 'final', 'agent'), default='agent')
    parser.add_argument('--timeout', type=float, default=3600)
    parser.add_argument('--device-serial', default='127.0.0.1:5555')
    args = parser.parse_args()
    if args.build_worker:
        build_worker(args.build_worker)
        return
    if args.source is None or args.output is None or not math.isfinite(args.timeout) or not 0 < args.timeout <= 3600:
        parser.error('fresh --source/--output and 0 < timeout <= 3600 required')
    from types import SimpleNamespace
    result = evaluate(task=SimpleNamespace(task_id='12_report_room'), platform='arkts', source=args.source,
                      role=args.role, output=args.output, deadline=time.monotonic() + args.timeout, serial=args.device_serial)
    print(__import__('json').dumps(result['semantic'] | {'cases': 'retained in report'}))


if __name__ == '__main__':
    main()
