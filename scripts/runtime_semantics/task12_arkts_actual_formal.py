"""Default Task12 ArkTS orchestration; frozen actual-UI producers stay unchanged."""

import argparse
import copy
from contextlib import contextmanager
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
import uuid

try:
    from . import task12_13_formal_core as core
    from . import task12_13_runtime_support as support
    from . import task12_actual_ui_protocol as actual
    from . import task12_arkts_runtime_admission as admission
except ImportError:
    from scripts.runtime_semantics import task12_13_formal_core as core
    from scripts.runtime_semantics import task12_13_runtime_support as support
    from scripts.runtime_semantics import task12_actual_ui_protocol as actual
    from scripts.runtime_semantics import task12_arkts_runtime_admission as admission

BINARIES = core.BINARY_SUFFIXES | {'.abc', '.har', '.so', '.app'}
PARENT_CLOCK = 'parent_process.time.monotonic.v1'
CHILD_CLOCK = 'worker_process.time.monotonic.v1'
CLOCK_TRANSLATION = 'parent_remaining_seconds.v1'


def check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('Task12 actual formal absolute deadline exhausted')


def file_record(path, deadline):
    check(deadline)
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            check(deadline)
            size += len(block)
            digest.update(block)
    return {'path': str(path.resolve()), 'bytes': size, 'sha256': digest.hexdigest()}


def inventory(source, deadline):
    files = []
    for path in sorted(source.rglob('*')):
        check(deadline)
        relative = path.relative_to(source)
        if any(part in core.INVENTORY_EXCLUDES for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError('Unsupported source symlink: ' + str(relative))
        if path.is_file() and path.suffix.lower() not in core.BINARY_SUFFIXES:
            files.append({**file_record(path, deadline), 'path': relative.as_posix()})
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'source': str(source), 'fileCount': len(files), 'sha256': digest, 'files': files}


def copy_source(source, target, expected, deadline):
    check(deadline)
    target.mkdir(parents=True, exist_ok=False)
    for item in expected['files']:
        check(deadline)
        origin, destination = source / item['path'], target / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        with origin.open('rb') as incoming, destination.open('xb') as outgoing:
            for block in iter(lambda: incoming.read(1024 * 1024), b''):
                check(deadline)
                outgoing.write(block)
        shutil.copystat(origin, destination)
    result = inventory(target, deadline)
    if result['sha256'] != expected['sha256']:
        raise ValueError('Random source copy differs from immutable input')
    return result


def cleanup(root, receipt, deadline, *, remove_all=False):
    """Persist each hash before unlink; partial cleanup is never called complete."""
    receipt.parent.mkdir(parents=True, exist_ok=True)
    ledger = receipt.with_suffix('.hashes.jsonl')
    result = {'performed': False, 'binaryHashesRecordedBeforeRemoval': True,
              'binaryHashes': [], 'filesRemoved': 0, 'temporaryBuildRemoved': False,
              'binariesRetained': True, 'root': str(root), 'ledger': str(ledger)}
    try:
        with ledger.open('x') as journal:
            paths = sorted(root.rglob('*')) if root.exists() else []
            for path in paths:
                check(deadline)
                transient = any(part in core.TRANSIENT_DIRECTORIES for part in path.relative_to(root).parts)
                binary = path.suffix.lower() in BINARIES
                if not (remove_all or transient or binary):
                    continue
                if path.is_symlink():
                    item = {'path': str(path), 'symlinkTarget': os.readlink(path)}
                elif path.is_file():
                    item = file_record(path, deadline)
                    if transient and path.suffix.lower() in {'.json', '.log'} and not remove_all:
                        saved = root / 'retained-audit' / (hashlib.sha256(str(path).encode()).hexdigest() + path.suffix)
                        saved.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, saved)
                        item['retained'] = file_record(saved, deadline)
                else:
                    continue
                journal.write(json.dumps(item, sort_keys=True) + '\n')
                journal.flush()
                os.fsync(journal.fileno())
                if binary and 'sha256' in item:
                    result['binaryHashes'].append(item)
                path.unlink()
                result['filesRemoved'] += 1
            for path in sorted(paths, key=lambda p: len(p.parts), reverse=True):
                check(deadline)
                if path.is_dir() and (remove_all or any(part in core.TRANSIENT_DIRECTORIES
                        for part in path.relative_to(root).parts)):
                    path.rmdir()
            if remove_all and root.exists():
                root.rmdir()
        result.update(performed=True, binariesRetained=False, temporaryBuildRemoved=True)
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    core.write(receipt, result)
    return result


def group_members(group, session, deadline):
    check(deadline)
    rows = subprocess.run(['ps', '-axo', 'pid=,pgid=,uid='], capture_output=True, text=True,
                          check=True, timeout=min(2, max(.001, deadline - time.monotonic())))
    members = []
    for line in rows.stdout.splitlines():
        pid, pgid, uid = map(int, line.split())
        if pgid != group:
            continue
        try:
            sid = os.getsid(pid)
        except ProcessLookupError:
            continue
        members.append({'pid': pid, 'pgid': pgid, 'uid': uid, 'sid': sid,
                        'owned': sid == session and uid == os.getuid()})
    return members


def bounded_worker(config, config_path, deadline):
    check(deadline)
    worker_started = time.monotonic()
    remaining = deadline - worker_started
    config = {**config, 'deadlineEpoch': time.time() + deadline - time.monotonic(),
              'workDeadlineMonotonic': deadline, 'lease': str(config_path.with_suffix('.lease.json')),
              'parentClockDomain': PARENT_CLOCK, 'parentPid': os.getpid(),
              'launchParentMonotonic': worker_started, 'remainingBudgetSeconds': remaining,
              'clockTranslation': CLOCK_TRANSLATION, 'workerConfigPath': str(config_path.resolve()),
              'workerClockReceipt': str(config_path.with_suffix('.clock.json').resolve())}
    core.write(config_path, config)
    environment = {**os.environ, 'TMPDIR': config['temporary']}
    Path(config['temporary']).mkdir(parents=True, exist_ok=False)
    process = subprocess.Popen([sys.executable, '-B', '-m', 'scripts.runtime_semantics.task12_arkts_actual_formal', '--worker', str(config_path)],
        cwd=core.ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True)
    out, err, primary, value = '', '', None, None
    cleanup_deadline = config.get('cleanupDeadlineMonotonic', deadline)
    state = {'pid': process.pid, 'cleanupSafe': False, 'signalFailures': [], 'groupChecks': [],
             'startedMonotonic': worker_started, 'parentPid': os.getpid(), 'clockDomain': PARENT_CLOCK}
    try:
        group, session = os.getpgid(process.pid), os.getsid(process.pid)
        state['isolation'] = {'pgid': group, 'sid': session, 'ownedNewSession': group == session == process.pid}
        if not state['isolation']['ownedNewSession']:
            raise RuntimeError('Worker did not obtain its own verified process group/session')
        out, err = process.communicate(timeout=max(0.001, deadline - time.monotonic()))
        if process.returncode:
            raise RuntimeError('Task12 bounded ' + config['phase'] + ' worker failed')
        check(deadline)
        value = core.load(Path(config['result']))
    except BaseException as error:
        primary = error
        state['primaryFailure'] = traceback.format_exc()
        if isinstance(error, subprocess.TimeoutExpired):
            out, err = error.stdout or '', error.stderr or ''
    finally:
        try:
            isolated = state.get('isolation', {}).get('ownedNewSession', False)
            for sig in (signal.SIGTERM, signal.SIGKILL):
                check(cleanup_deadline)
                members = group_members(process.pid, process.pid, cleanup_deadline) if isolated else []
                state['groupChecks'].append({'signal': sig, 'members': members})
                if members and all(member['owned'] for member in members):
                    try:
                        os.killpg(process.pid, sig)
                    except ProcessLookupError:
                        pass
                    except OSError:
                        state['signalFailures'].append({'signal': sig, 'traceback': traceback.format_exc()})
                elif members:
                    state['foreignGroupPreserved'] = True
                if process.poll() is None:
                    try:
                        tail_out, tail_err = process.communicate(timeout=min(.5, max(.001, cleanup_deadline - time.monotonic())))
                        out, err = out or tail_out, err or tail_err
                    except subprocess.TimeoutExpired:
                        pass
            if process.poll() is None:
                # Only this unreaped direct child, never a numerically guessed PGID.
                try:
                    process.kill()
                    process.wait(timeout=min(1, max(.001, cleanup_deadline - time.monotonic())))
                except (OSError, subprocess.TimeoutExpired):
                    state['signalFailures'].append({'directChild': True, 'traceback': traceback.format_exc()})
            members = group_members(process.pid, process.pid, cleanup_deadline) if isolated else []
            reap_stop = min(cleanup_deadline, time.monotonic() + 1)
            while members and all(member['owned'] for member in members) and time.monotonic() < reap_stop:
                time.sleep(min(.02, reap_stop - time.monotonic()))
                members = group_members(process.pid, process.pid, cleanup_deadline)
            state['remainingGroupMembers'] = members
            state['childReaped'] = process.poll() is not None
            state['exitCode'] = process.returncode
            state['finishedMonotonic'] = time.monotonic()
            state['cleanupSafe'] = isolated and state['childReaped'] and not members
            lease_path = Path(config['lease'])
            if state['cleanupSafe'] and lease_path.exists():
                lease = core.load(lease_path)
                lock = Path(lease['path'])
                if lease['pid'] == process.pid and lock.exists():
                    identity = lock.stat()
                    if (identity.st_ino, identity.st_ctime_ns) == (lease['inode'], lease['ctimeNs']):
                        lock.rmdir()
                        state['ownedLeaseRemoved'] = lease
                    else:
                        state['foreignLeasePreserved'] = True
        except BaseException:
            state['cleanupFailure'] = traceback.format_exc()
            state['cleanupSafe'] = False
        finally:
            if process.poll() is None:
                try:
                    check(cleanup_deadline)
                    process.kill()
                    process.wait(timeout=min(.5, max(.001, cleanup_deadline - time.monotonic())))
                except (OSError, subprocess.TimeoutExpired, TimeoutError):
                    state['finalReapFailure'] = traceback.format_exc()
                    state['cleanupSafe'] = False
            state['childReaped'] = process.poll() is not None
            try:
                state['workerConfig'] = file_record(config_path, cleanup_deadline)
                child_clock = Path(config['workerClockReceipt'])
                if child_clock.exists():
                    state['workerClockReceipt'] = file_record(child_clock, cleanup_deadline)
            except BaseException:
                state['clockBindingFailure'] = traceback.format_exc()
                state['cleanupSafe'] = False
            state['finishedMonotonic'] = time.monotonic()
            def text(data):
                return data.decode('utf-8', errors='replace') if isinstance(data, bytes) else data or ''
            config_path.with_suffix('.log').write_text(text(out) + text(err) + '\n' + state.get('primaryFailure', '') +
                '\nSIGNAL_AND_REAP_AUDIT\n' + json.dumps(state, indent=2))
            core.write(config_path.with_suffix('.process.json'), state)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
    if not state['cleanupSafe']:
        raise RuntimeError('Worker tree/lease cleanup is unproven; see ' + str(config_path.with_suffix('.process.json'))) from primary
    if isinstance(primary, subprocess.TimeoutExpired):
        raise TimeoutError('Task12 bounded ' + config['phase'] + ' exceeded the shared work deadline') from primary
    if primary:
        raise primary
    return value


def inherited_run(command, *, deadline, phase, log, cwd=core.ROOT, environment=None):
    """No inner killpg(child PID): only the verified outer session owns signals."""
    check(deadline)
    log.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(command, cwd=cwd, env=environment, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=False)
    try:
        out, err = process.communicate(timeout=max(.001, deadline - time.monotonic()))
    except subprocess.TimeoutExpired as error:
        log.write_text(str(error) + '\nOuter bounded worker owns descendant termination.\n')
        # Exit the worker promptly; its parent verifies and terminates the whole tree.
        raise TimeoutError('Shared worker deadline exhausted: ' + phase) from error
    log.write_text((out or '') + (err or ''))
    if process.returncode:
        raise RuntimeError(phase + ' failed with exit ' + str(process.returncode))


def worker(config):
    remaining = config['remainingBudgetSeconds']
    if (config.get('clockTranslation') != CLOCK_TRANSLATION or
            config.get('parentClockDomain') != PARENT_CLOCK or
            type(remaining) not in (float, int) or not math.isfinite(remaining) or not 0 < remaining <= 3600 or
            type(config.get('parentPid')) is not int or config['parentPid'] != os.getppid() or
            any(type(config.get(key)) not in (float, int) or not math.isfinite(config[key])
                for key in ('launchParentMonotonic', 'workDeadlineMonotonic')) or
            remaining != config['workDeadlineMonotonic'] - config['launchParentMonotonic']):
        raise ValueError('Worker requires a finite parent remaining budget and explicit clock domains')
    local_started = time.monotonic()
    deadline = local_started + remaining
    # Python 3.9 macOS monotonic origins are process-local. Only the parent's
    # communicate timeout is authoritative; launch/import overhead cannot extend it.
    core.write(Path(config['workerClockReceipt']), {'protocol': CLOCK_TRANSLATION,
        'clockDomain': CHILD_CLOCK, 'workerPid': os.getpid(), 'parentPid': os.getppid(),
        'startedLocalMonotonic': local_started, 'deadlineLocalMonotonic': deadline,
        'remainingBudgetSeconds': remaining, 'launchParentMonotonic': config['launchParentMonotonic'],
        'parentWorkDeadlineMonotonic': config['workDeadlineMonotonic'],
        'workerConfig': file_record(Path(config['workerConfigPath']), deadline),
        'parentHardTimeoutAuthority': True, 'epochIsDiagnosticOnly': True})
    original_popen, original_lock = subprocess.Popen, support.arkts_device_lock

    def inherited_group(*args, **kwargs):
        kwargs['start_new_session'] = False
        return original_popen(*args, **kwargs)

    def bounded_run(*args, **kwargs):
        kwargs['deadline'] = min(kwargs['deadline'], deadline)
        return inherited_run(*args, **kwargs)

    @contextmanager
    def tracked_lock(*, serial, deadline):
        with original_lock(serial=serial, deadline=deadline):
            path = Path('/tmp') / ('ltb-arkts-device-' + hashlib.sha256(serial.encode()).hexdigest()[:16])
            identity = path.stat()
            core.write(Path(config['lease']), {'pid': os.getpid(), 'path': str(path),
                       'inode': identity.st_ino, 'ctimeNs': identity.st_ctime_ns})
            yield

    subprocess.Popen, support.run = inherited_group, bounded_run
    support.arkts_device_lock = tracked_lock
    check(deadline)
    if config['phase'] == 'runtime':
        result = actual.evaluate(task=actual.specification(), platform='arkts', source=Path(config['source']),
            role=config['role'], output=Path(config['result']), deadline=deadline, serial=config['serial'])
    elif config['phase'] == 'calibration_snapshot':
        from . import task12_arkts_reviewed_controls as reviewed
        result = reviewed.capture_toolchain(Path(config['snapshotOutput']), config['serial'], deadline)
    elif config['phase'] == 'seal_controls':
        from . import task12_arkts_reviewed_controls as reviewed
        result = reviewed.create_receipt(bundle=Path(config['bundle']), version_evidence=Path(config['versionAudit']),
            base_source=Path(config['baseSource']), final_source=Path(config['finalSource']),
            output=Path(config['receiptOutput']), serial=config['serial'], deadline=deadline)
    elif config['phase'] in ('preflight', 'postflight'):
        from . import task12_arkts_reviewed_controls as reviewed
        record = reviewed.file_record(Path(config['controlReceipt']), deadline)
        receipt, proof = reviewed.verify_receipt(record, core.load(actual.CONTRACT),
            Path(config['baseSource']), Path(config['finalSource']), deadline)
        snapshot = reviewed.capture_toolchain(Path(config['snapshotOutput']), config['serial'], deadline)
        reviewed.verify_snapshot(snapshot, proof['versions'], deadline)
        result = {'receipt': record, 'proof': proof, 'snapshot': snapshot,
                  'controlsReused': True, 'freshControlExecutions': False}
    elif config['phase'] == 'compile':
        if config.get('receipt'):
            from .task12_application_evidence import reuse_compiler
            compiler = reuse_compiler(Path(config['receipt']))
        elif config.get('compiler'):
            module, name = config['compiler']
            compiler = getattr(importlib.import_module(module), name)
        else:
            compiler = support.compile_candidate
        result = compiler(platform='arkts', source=Path(config['source']), output=Path(config['buildOutput']),
                          deadline=deadline, command=config['command'])
    elif config['phase'] == 'validation':
        from scripts.run_runtime_transition_matrix import validate_report
        reports = []
        for name in config['reports']:
            check(deadline)
            report = core.load(Path(name))
            proof = actual.validate_report_evidence(report, core.load(actual.CONTRACT), deadline=deadline)
            admission.validate_report_evidence(report, core.load(actual.CONTRACT))
            validate_report(report, core.load(actual.CONTRACT))
            reports.append({'report': file_record(Path(name), deadline), 'proof': proof, 'publicPassed': True})
        result = {'reports': reports, 'allPublicPassed': True, 'nodeProcessGroupsInherited': True,
                  'deadlineEpoch': config['deadlineEpoch']}
    else:
        raise ValueError('Unknown Task12 isolated worker phase')
    check(deadline)
    core.write(Path(config['result']), result)


def compile_failure(root, deadline=None):
    deadline = deadline if deadline is not None else time.monotonic() + 120
    check(deadline)
    path = root / 'application-build/application-build.json'
    if path.exists():
        data = core.load(path)
        log = Path(data.get('log', {}).get('path', ''))
        chunks = []
        if log.is_file():
            with log.open(errors='replace') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), ''):
                    check(deadline)
                    chunks.append(chunk)
        text = ''.join(chunks)
        check(deadline)
        environmental = any(word in text.lower() for word in ('no space left', 'sdk location', 'sdk not found',
            'could not resolve', 'storage protection', 'network', 'timed out', 'terminated'))
        if (data.get('exitCode') not in (None, 0, 125, 137, 143, -15, -9) and not environmental and
                re.search(r'ArkTS:ERROR|ArkTS Compiler Error', text)):
            return {'passed': False, 'status': 'failed', 'scope': 'standalone_candidate_application_build',
                    'evidence': file_record(path, deadline), 'reason': 'Actual ArkTS compiler diagnostic'}
    return {'passed': None, 'status': 'not_scored', 'scope': 'standalone_candidate_application_build'}


def calibrate_controls(*, base_source, final_source, output, device_serial='127.0.0.1:5555', timeout=3600):
    """Explicit pre-agent calibration episode, never called by candidate score."""
    from . import task12_arkts_reviewed_controls as reviewed
    if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError('Calibration requires its own explicit 0 < timeout <= 3600 budget')
    started = time.monotonic()
    deadline = started + timeout
    reserve = min(120.0, timeout / 5)
    work_deadline = deadline - reserve
    output = Path(output).resolve()
    originals = {'base': Path(base_source).resolve(), 'final': Path(final_source).resolve()}
    if (not output.is_relative_to(core.ROOT / 'experiment_results') or output.exists() or
            any(output.is_relative_to(path) for path in originals.values())):
        raise ValueError('Fresh calibration requires a new private evaluator audit directory')
    output.mkdir(parents=True)
    summary = {'protocol': reviewed.CALIBRATION_PROTOCOL, 'purpose': 'separate_pre_agent_evaluator_calibration',
        'modelCalled': False, 'extendsExistingModelTask': False, 'timeoutSeconds': timeout,
        'startedMonotonic': started, 'deadlineMonotonic': deadline,
        'workDeadlineMonotonic': work_deadline, 'cleanupReserveSeconds': reserve,
        'calibrationPassed': False, 'receiptSealed': False, 'readyForCandidateScoring': False,
        'phases': {}, 'cleanup': [], 'remoteCleanup': {}, 'error': None,
        'parentPid': os.getpid(), 'clockDomain': PARENT_CLOCK}
    unsafe, sealed, inventories = False, None, {}

    def execute(config, path):
        nonlocal unsafe
        try:
            return bounded_worker({**config, 'cleanupDeadlineMonotonic': deadline}, path, work_deadline)
        finally:
            state_path = path.with_suffix('.process.json')
            if not state_path.exists() or not core.load(state_path).get('cleanupSafe'):
                unsafe = True

    try:
        check(work_deadline)
        if shutil.disk_usage(core.ROOT).free < 8 * 1024**3:
            raise RuntimeError('storage_protection: less than 8 GiB free')
        inventories = {name: inventory(path, work_deadline) for name, path in originals.items()}
        if (inventories['base']['sha256'], inventories['final']['sha256']) != (admission.BASE_SHA, admission.FINAL_SHA):
            raise ValueError('Immutable calibration inputs changed')
        copies = {}
        for label in reviewed.LABELS:
            origin = 'base' if label in ('base', 'negative') else 'final'
            copies[label] = copy_source(originals[origin], output / 'owned-sources' / uuid.uuid4().hex,
                                        inventories[origin], work_deadline)
        core.write(output / 'source-inventories.json', {'originals': inventories, 'copies': copies})
        policy_before = reviewed.execution_policy_records(work_deadline)
        snapshot_workers = {}
        def snapshot(label):
            result_path = output / (label + '.json')
            config_path = output / (label + '-worker.json')
            result = execute({'phase': 'calibration_snapshot', 'serial': device_serial,
                'snapshotOutput': str(output / label), 'result': str(output / (label + '.json')),
                'temporary': str(output / 'temporary' / label)}, config_path)
            core.write(result_path, result)
            snapshot_workers[label.removeprefix('toolchain-')] = {'snapshot': result,
                'result': file_record(result_path, work_deadline),
                'workerConfig': file_record(config_path, work_deadline),
                'workerProcess': file_record(config_path.with_suffix('.process.json'), work_deadline)}
            return result
        before = snapshot('toolchain-before')
        paths = []
        for label in reviewed.LABELS:
            check(work_deadline)
            path = output / label / 'runtime.json'
            config_path = path.parent / 'worker.json'
            role = label if label in ('base', 'final') else 'agent'
            summary['remoteCleanup'][label] = {'status': 'unknown', 'ownedAppUninstalled': 'unknown',
                                               'reverseRemoved': 'unknown'}
            try:
                report = execute({'phase': 'runtime', 'source': copies[label]['source'], 'role': role,
                    'serial': device_serial, 'result': str(path),
                    'temporary': str(output / 'temporary' / label)}, config_path)
            finally:
                if not unsafe:
                    summary['cleanup'].append(cleanup(path.parent, path.parent / 'cleanup.json', deadline))
                    summary['cleanup'].append(cleanup(output / 'temporary' / label,
                        path.parent / 'worker-temp-cleanup.json', deadline, remove_all=True))
            if unsafe or not all(item['performed'] for item in summary['cleanup']):
                raise RuntimeError('Calibration worker/local cleanup unproven')
            report['provenance']['runtimeEvidence']['currentCleanup'] = file_record(path.parent / 'cleanup.json', work_deadline)
            core.write(path, report)
            counts = [report['semantic'][key] for key in ('passed', 'failed', 'notScored')]
            expected = [0, 10, 0] if label in ('base', 'negative') else [10, 0, 0]
            if counts != expected:
                raise ValueError('Calibration polarity/invariant completeness failed: ' + label)
            raw = core.load(Path(report['provenance']['runtimeEvidence']['raw']['path']))
            remote = raw['diagnostics']['cleanup']
            if remote.get('ownedAppUninstalled') is not True or remote.get('reverseRemoved') is not True:
                raise ValueError('Calibration native remote cleanup incomplete: ' + label)
            summary['remoteCleanup'][label] = {'status': 'reported_by_bound_raw', **remote}
            summary['phases'][label] = {'counts': counts, 'report': file_record(path, work_deadline),
                'workerConfig': file_record(config_path, work_deadline),
                'workerProcess': file_record(config_path.with_suffix('.process.json'), work_deadline)}
            paths.append(path)
            core.write(output / 'progress.json', summary)
        after = snapshot('toolchain-after')
        bundle = {'nativeProtocol': actual.PROTOCOL, 'contract': file_record(actual.CONTRACT, work_deadline),
            'producerHashes': [file_record(p, work_deadline) for p in (actual.FACTS, actual.RUNNER, Path(actual.__file__))],
            'freshControlExecutions': True, 'sourceParameterizedControls': {}}
        for label, path in zip(reviewed.LABELS, paths):
            evidence = core.load(path)['provenance']['runtimeEvidence']
            bundle['sourceParameterizedControls'][label] = {'reportPath': str(path),
                **{key: evidence[key] for key in ('raw', 'sourceInventory', 'build', 'currentCleanup')}}
        bundle_path = output / 'admission-bundle.json'
        core.write(bundle_path, bundle)
        for label, path in zip(reviewed.LABELS, paths):
            report = core.load(path)
            report['provenance']['runtimeEvidence']['admissionBundle'] = file_record(bundle_path, work_deadline)
            core.write(path, report)
            summary['phases'][label]['report'] = file_record(path, work_deadline)
        envelope = {'protocol': reviewed.CALIBRATION_PROTOCOL, 'controlBundle': file_record(bundle_path, work_deadline),
            'executionToolchain': {'before': before, 'after': after},
            'snapshotWorkers': snapshot_workers, 'parentPid': os.getpid(), 'clockDomain': PARENT_CLOCK,
            'executionPolicyBefore': policy_before, 'executionPolicyAfter': reviewed.execution_policy_records(work_deadline),
            **{key: summary[key] for key in ('startedMonotonic', 'deadlineMonotonic', 'workDeadlineMonotonic',
                                           'timeoutSeconds', 'cleanupReserveSeconds', 'phases')}}
        envelope_path = output / 'execution-envelope.json'
        core.write(envelope_path, envelope)
        version_path = output / 'execution-bound-version-audit.json'
        reviewed.assemble_version_audit(bundle=file_record(bundle_path, work_deadline), before=before, after=after,
            envelope=file_record(envelope_path, work_deadline), output=version_path, deadline=work_deadline)
        validation = execute({'phase': 'validation', 'reports': [str(p) for p in paths],
            'result': str(output / 'public-validation.json'), 'temporary': str(output / 'temporary/validation')},
            output / 'validation-worker.json')
        if validation.get('allPublicPassed') is not True:
            raise ValueError('Fresh calibration public validation incomplete')
        sealed = execute({'phase': 'seal_controls', 'bundle': str(bundle_path), 'versionAudit': str(version_path),
            'baseSource': str(originals['base']), 'finalSource': str(originals['final']), 'serial': device_serial,
            'receiptOutput': str(output / 'reviewed-control-receipt.json'),
            'result': str(output / 'receipt-seal.json'), 'temporary': str(output / 'temporary/seal')},
            output / 'seal-worker.json')
        if sealed != file_record(output / 'reviewed-control-receipt.json', work_deadline):
            raise ValueError('Sealed calibration receipt differs')
        for name, path in originals.items():
            if inventory(path, work_deadline)['sha256'] != inventories[name]['sha256']:
                raise ValueError('Original immutable source changed during calibration')
        summary.update(calibrationPassed=True, receiptSealed=True, receipt=sealed)
    except (Exception, KeyboardInterrupt) as error:
        summary['error'] = f'{type(error).__name__}: {error}'
        summary['failureTraceback'] = traceback.format_exc()
    finally:
        if unsafe:
            summary['cleanup'].append({'performed': False, 'reason': 'Unproven worker; owned inputs retained'})
        else:
            for name in ('owned-sources', 'temporary'):
                summary['cleanup'].append(cleanup(output / name, output / (name + '-cleanup.json'), deadline, remove_all=True))
        summary['localCleanupComplete'] = all(item['performed'] for item in summary['cleanup'])
        summary['totalElapsedSeconds'] = time.monotonic() - started
        summary['readyForCandidateScoring'] = (summary['error'] is None and summary['receiptSealed'] and
            summary['localCleanupComplete'] and time.monotonic() < deadline)
        if not summary['readyForCandidateScoring'] and sealed:
            summary['receiptNotUsable'] = 'Calibration completion/cleanup failed; do not configure this receipt'
        core.write(output / 'calibration-completion.json', summary)
    return summary


def score(*, platform, source, base_source, final_source, output, compile_passed=None, compile_command='',
          application_compiler=None, application_compile_evidence=None, device_serial=None, timeout=3600,
          validate_public=True, control_receipt=None, **testing):
    if (platform != 'arkts' or isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or
            not math.isfinite(timeout) or not 0 < timeout <= 3600 or testing):
        raise ValueError('Actual formal scorer requires arkts and finite 0 < timeout <= 3600; no testing clock overrides')
    started = time.monotonic()
    deadline = started + timeout
    reserve = min(120.0, timeout / 5)
    work_deadline = deadline - reserve
    output = output.resolve()
    if output.exists():
        raise FileExistsError('Refusing existing formal report: ' + str(output))
    if not validate_public:
        raise ValueError('Default actual runtime cannot disable public admission')
    if application_compile_evidence is not None and (compile_passed is not None or application_compiler is not None):
        raise ValueError('Compile receipt conflicts with another compile result')
    if compile_passed is not None and type(compile_passed) is not bool:
        raise ValueError('compile_passed must be bool or None')
    check(work_deadline)
    originals = {key: Path(path).resolve() for key, path in
                 (('base', base_source), ('final', final_source), ('model', source))}
    audit = core.ROOT / 'experiment_results' / ('task12-actual-formal-' + uuid.uuid4().hex)
    if any(output.is_relative_to(path) or audit.is_relative_to(path) for path in originals.values()):
        raise ValueError('Formal report/audit must be outside supplied sources')
    audit.mkdir(parents=True, exist_ok=False)
    contract = core.load(actual.CONTRACT)
    compile_metric = {'passed': compile_passed, 'status': 'passed' if compile_passed is True else
        'failed' if compile_passed is False else 'not_scored', 'command': compile_command,
        'scope': 'standalone_candidate_application_build', 'providedByCaller': compile_passed is not None}
    phases, receipts, reports = [], [], []
    runtime_failed_bundle, unsafe_worker = None, False
    result, error, calibrated = None, None, False
    diagnostics = {'auditRoot': str(audit), 'timeoutSeconds': timeout, 'deadlineMonotonic': deadline,
        'workDeadlineMonotonic': work_deadline, 'cleanupReserveSeconds': reserve,
        'clockDomain': PARENT_CLOCK, 'parentPid': os.getpid(), 'workerClockTranslation': CLOCK_TRANSLATION,
        'phases': phases, 'cleanup': receipts, 'wrapper': file_record(Path(__file__), work_deadline),
        'mode': 'candidate_only_reviewed_controls', 'controlsReuseRequested': True, 'controlsReused': False,
        'freshControlExecutions': False,
        'cleanupScope': 'local_binary_build_temp_owned_source_only',
        'remoteCleanup': {'status': 'not_started'}}

    def run_worker(config, path):
        nonlocal unsafe_worker
        try:
            return bounded_worker(config, path, work_deadline)
        finally:
            state = path.with_suffix('.process.json')
            if not state.exists() or not core.load(state).get('cleanupSafe'):
                unsafe_worker = True
                receipts.append({'performed': False, 'reason': 'Worker termination unproven; inputs retained',
                                 'worker': str(path)})

    try:
        if len(set(originals.values())) != 3 or any(not path.is_dir() for path in originals.values()):
            raise ValueError('base, final and arbitrary candidate must be distinct existing sources')
        if any(output.is_relative_to(path) or audit.is_relative_to(path) for path in originals.values()):
            raise ValueError('Formal report/audit must be outside supplied sources')
        if shutil.disk_usage(core.ROOT).free < 8 * 1024**3:
            raise RuntimeError('storage_protection: less than 8 GiB free')
        inventories = {key: inventory(path, work_deadline) for key, path in originals.items()}
        if (inventories['base']['sha256'], inventories['final']['sha256']) != (admission.BASE_SHA, admission.FINAL_SHA):
            raise ValueError('Immutable Task12 calibration source inventories differ')
        core.write(audit / 'source-inventories.json', inventories)
        if control_receipt is None:
            raise ValueError('Missing parent-only reviewed control receipt; no implicit fresh-control fallback')
        receipt_path = Path(control_receipt).resolve()
        if any(receipt_path.is_relative_to(path) for path in originals.values()):
            raise ValueError('Private control receipt must not be supplied inside candidate/base/final inputs')
        check(work_deadline)
        receipt_record = file_record(receipt_path, work_deadline)
        preflight_config = {'phase': 'preflight', 'controlReceipt': str(receipt_path),
            'baseSource': str(originals['base']), 'finalSource': str(originals['final']),
            'serial': device_serial or '127.0.0.1:5555',
            'snapshotOutput': str(audit / 'toolchain-before'),
            'temporary': str(audit / 'temporary/preflight'),
            'result': str(audit / 'preflight.json'), 'cleanupDeadlineMonotonic': deadline}
        preflight = run_worker(preflight_config, audit / 'preflight-worker.json')
        if preflight['receipt'] != receipt_record:
            raise ValueError('Control receipt changed during preflight')
        diagnostics['reviewedControls'] = preflight
        diagnostics['controlsReused'] = True
        if compile_passed is None:
            compiler_ref = None
            if application_compiler is not None:
                name = application_compiler.__name__
                module = application_compiler.__module__
                if getattr(importlib.import_module(module), name, None) is not application_compiler:
                    raise ValueError('Bounded application compiler must be module-importable, or use a compile receipt')
                compiler_ref = [module, name]
            config = {'phase': 'compile', 'source': str(originals['model']), 'command': compile_command,
                'compiler': compiler_ref, 'receipt': str(application_compile_evidence.resolve()) if application_compile_evidence else None,
                'result': str(audit / 'application-compile/result.json'),
                'buildOutput': str(audit / 'application-compile/build'),
                'temporary': str(audit / 'temporary/application-compile'), 'cleanupDeadlineMonotonic': deadline}
            try:
                compile_metric = run_worker(config, audit / 'application-compile/worker.json')
            except Exception:
                compile_metric = compile_failure(audit / 'application-compile/build', work_deadline)
                raise
            finally:
                process_audit = audit / 'application-compile/worker.process.json'
                if not process_audit.exists() or not core.load(process_audit).get('cleanupSafe'):
                    unsafe_worker = True
                    receipts.append({'performed': False, 'reason': 'Compile worker termination unproven; files retained'})
                else:
                    receipts.append(cleanup(audit / 'application-compile', audit / 'application-compile-cleanup.json', deadline))
                    receipts.append(cleanup(audit / 'temporary/application-compile', audit / 'application-compile-temp-cleanup.json', deadline, remove_all=True))
        if compile_metric['passed'] is not True:
            raise RuntimeError('Standalone application compile did not pass; semantics remain NOT_SCORED')
        for label in ('model',):
            check(work_deadline)
            path, role = audit / label / 'runtime.json', label if label in ('base', 'final') else 'agent'
            current_source = Path(inventories[label]['source'])
            runtime_failed_bundle = actual.replay.frozen._bundle_name(current_source)
            diagnostics['remoteCleanup'] = {'status': 'unknown', 'ownedAppUninstalled': 'unknown',
                                            'reverseRemoved': 'unknown'}
            config = {'phase': 'runtime', 'source': str(current_source), 'role': role,
                'serial': device_serial or '127.0.0.1:5555', 'result': str(path),
                'temporary': str(audit / 'temporary' / label), 'cleanupDeadlineMonotonic': deadline}
            try:
                report = run_worker(config, path.parent / 'worker.json')
                runtime_failed_bundle = None
            finally:
                receipt = path.parent / 'cleanup.json'
                process_audit = path.parent / 'worker.process.json'
                if not process_audit.exists() or not core.load(process_audit).get('cleanupSafe'):
                    unsafe_worker = True
                    receipts.append({'performed': False, 'reason': 'Runtime worker termination unproven; files retained'})
                else:
                    receipts.append(cleanup(path.parent, receipt, deadline))
                    receipts.append(cleanup(audit / 'temporary' / label, path.parent / 'worker-temp-cleanup.json', deadline, remove_all=True))
            if not all(item['performed'] for item in receipts):
                raise RuntimeError('Hash-before-delete cleanup incomplete')
            report['provenance']['runtimeEvidence']['currentCleanup'] = file_record(receipt, work_deadline)
            core.write(path, report)
            counts = tuple(report['semantic'][key] for key in ('passed', 'failed', 'notScored'))
            if counts[2]:
                raise ValueError('Actual runtime/invariants remain NOT_SCORED')
            phases.append({'label': label, 'role': role, 'source': str(current_source), 'counts': list(counts),
                           'freshExecution': True, 'runtime': file_record(path, work_deadline)})
            reports.append(path)
            core.write(audit / 'progress.json', diagnostics)
        postflight_config = {**preflight_config, 'phase': 'postflight',
            'snapshotOutput': str(audit / 'toolchain-after'), 'temporary': str(audit / 'temporary/postflight'),
            'result': str(audit / 'postflight.json')}
        postflight = run_worker(postflight_config, audit / 'postflight-worker.json')
        if postflight['receipt'] != receipt_record or postflight['proof'] != preflight['proof']:
            raise ValueError('Frozen control evidence changed while candidate ran')
        for phase, path in zip(phases, reports):
            report = core.load(path)
            evidence = report['provenance']['runtimeEvidence']
            if 'admissionBundle' in evidence:
                raise ValueError('Candidate unexpectedly claims a calibration batch')
            evidence.update(reviewedControlReceipt=receipt_record, preCandidateToolchain=preflight['snapshot'],
                            postCandidateToolchain=postflight['snapshot'])
            report['calibration'] = {'passed': True, 'controlsReused': True, 'freshControlExecutions': False,
                                     'reviewedControls': preflight['proof']['counts']}
            raw = core.load(Path(evidence['raw']['path']))
            diagnostics['remoteCleanup'] = {'status': 'reported_by_bound_raw', 'raw': evidence['raw'],
                                            **raw['diagnostics']['cleanup']}
            core.write(path, report)
            phase['runtime'] = file_record(path, work_deadline)
        result = copy.deepcopy(core.load(reports[-1]))
        result['compile'] = compile_metric
        result['publication'] = {'eligible': False, 'reason': 'Pending full raw/public validation and cleanup'}
        formal_path = audit / 'formal.pending.json'
        core.write(formal_path, result)
        config = {'phase': 'validation', 'reports': [str(p) for p in reports] + [str(formal_path)],
            'result': str(audit / 'public-validation.json'), 'temporary': str(audit / 'temporary/validation'),
            'cleanupDeadlineMonotonic': deadline}
        try:
            validation = run_worker(config, audit / 'validation-worker.json')
        finally:
            process_audit = audit / 'validation-worker.process.json'
            if not process_audit.exists() or not core.load(process_audit).get('cleanupSafe'):
                unsafe_worker = True
                receipts.append({'performed': False, 'reason': 'Validation worker termination unproven; files retained'})
        if validation.get('allPublicPassed') is not True:
            raise ValueError('Full raw admission/public verification incomplete')
        calibrated = True
        for label, original in originals.items():
            if inventory(original, work_deadline)['sha256'] != inventories[label]['sha256']:
                raise ValueError('Caller source changed during formal scoring: ' + label)
    except (Exception, KeyboardInterrupt) as exception:
        error = f'{type(exception).__name__}: {exception}'
    finally:
        if error and runtime_failed_bundle and not unsafe_worker:
            try:
                with support.arkts_device_lock(serial=device_serial or '127.0.0.1:5555', deadline=deadline):
                    for bundle in [runtime_failed_bundle]:
                        check(deadline)
                        command = [str(actual.replay.frozen.HDC), '-t', device_serial or '127.0.0.1:5555', 'uninstall', bundle]
                        process = subprocess.run(command, capture_output=True, text=True,
                            timeout=min(10, max(0.001, deadline - time.monotonic())))
                        core.write(audit / ('device-cleanup-' + bundle + '.json'),
                            {'command': command, 'exitCode': process.returncode,
                             'stdout': process.stdout, 'stderr': process.stderr})
            except Exception as cleanup_error:
                diagnostics['deviceCleanupError'] = str(cleanup_error)
        if unsafe_worker:
            receipts.append({'performed': False, 'reason': 'Live/unproven worker may need owned inputs; no source/temp deletion'})
        else:
            receipts.append(cleanup(audit / 'owned-sources', audit / 'owned-source-cleanup.json', deadline, remove_all=True))
            receipts.append(cleanup(audit / 'temporary', audit / 'temporary-cleanup.json', deadline, remove_all=True))
        complete = all(item['performed'] for item in receipts) and time.monotonic() < deadline
        if not complete:
            error = error or 'Absolute deadline or final hash cleanup incomplete'
        if error or result is None or not calibrated:
            result = {'schemaVersion': 2, 'taskId': '12_report_room', 'platform': 'arkts', 'role': 'agent',
                'observationMode': 'runtime_state_transition', 'compile': compile_metric,
                'runtimeCompile': {'passed': None, 'status': 'not_scored'},
                'semantic': {'passed': 0, 'failed': 0, 'notScored': 10, 'total': 10,
                             'cases': core._not_scored(contract, error or 'Incomplete actual formal proof')},
                'calibration': {'passed': False}, 'publication': {'eligible': False, 'reason': error},
                'diagnostics': {'adapter': 'not_scored', 'transport': 'not_scored'}}
        else:
            result['publication'] = {'eligible': True, 'readinessPromotion': False}
        diagnostics.update(totalElapsedSeconds=time.monotonic() - started, error=error,
            cleanupComplete=complete, localCleanupComplete=complete, readyDecisionOwnedByMain=True)
        result['diagnostics']['actualFormal'] = diagnostics
        core.write(audit / 'completion.json', diagnostics)
        core.write(output, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--worker', type=Path)
    mode.add_argument('--calibrate-controls', action='store_true')
    parser.add_argument('--base-source', type=Path)
    parser.add_argument('--final-source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--device-serial', default='127.0.0.1:5555')
    args = parser.parse_args()
    if args.worker:
        worker(core.load(args.worker))
    else:
        if not all((args.base_source, args.final_source, args.output)):
            parser.error('Calibration needs --base-source, --final-source and --output')
        result = calibrate_controls(base_source=args.base_source, final_source=args.final_source,
            output=args.output, device_serial=args.device_serial, timeout=3600)
        print(json.dumps({key: result[key] for key in
              ('calibrationPassed', 'receiptSealed', 'readyForCandidateScoring', 'totalElapsedSeconds', 'error')}))
        raise SystemExit(0 if result['readyForCandidateScoring'] else 2)
