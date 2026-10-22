"""Source-parameterized Task15 ten-case composition. CLI is OFFLINE by default.

Execution is explicit and uses one absolute budget, serial native scenarios,
and the existing canonical lease. No model, contract or central changes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from . import task15_fresh_protocol_v2 as native
from . import task15_fresh_admission_v2 as raw
from . import task14_15_formal_core as core

ROOT = native.ROOT
TASK = native.TASK
PROTOCOL = 'task15.arkts.full-ten-case.v3'
HOST_PROTOCOL = 'task15.arkts.own-host-episode.v3'
POLICY = 'task15.arkts.full-ten-case-blocked-action.v3'
REVIEW = ROOT / 'experiment_results/runtime_transition_20261020/task15_full_report_v3'
ENGINE = Path(__file__).with_name('task15_full_v3') / 'Task15FreshActionsV2.js'
HOST = Path(__file__).with_name('task15_fresh_host_v3.cjs')
HOST_CASES = core.HOST_RUNTIME_CASES[TASK]
NODE = '/Applications/DevEco-Studio.app/Contents/tools/node/bin/node'


def implementation():
    old = native.implementation()
    files = {item['path']: item for item in old['files']
             if Path(item['path']) != native.NATIVE / 'Task15FreshActionsV2.js'}
    for path in (ENGINE, HOST, Path(__file__), Path(__file__).with_name('task15_full_report_verify_v3.py'),
                 Path(__file__).with_name('task15_native_transition_v3.py'),
                 Path(__file__).with_name('task15_prefix_v3.py'), Path(__file__).with_name('task15_capability_v3.py'),
                 Path(__file__).with_name('Task15BaseAllDevice.cjs'),
                 Path(__file__).with_name('task14_15_device_lease.py'),
                 Path(__file__).with_name('arkts_strict_agent_scorer.py')):
        files[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}
    records = [files[key] for key in sorted(files)]
    return {'protocol': native.PROTOCOL, 'reportProtocol': PROTOCOL,
            'files': records, 'sha256': raw.artifacts.row_digest(records)}


def prepare_native(*, source, case_id, output, deadline, serial):
    plan = native.prepare_case(source=source, case_id=case_id, output=output, deadline=deadline, serial=serial)
    output = Path(output)
    # This is a pre-execution versioned derivation, never relabeling an executed raw row.
    (output / 'v2-preparation-plan.json').write_bytes((output / 'plan.json').read_bytes())
    engine = output / 'native-environment-fixtures/Task15FreshActionsV2.js'
    engine.write_bytes(ENGINE.read_bytes())
    manifest = engine.parent / 'manifest.json'
    data = core.load(manifest)
    data['files'] = [raw.artifacts.artifact(path) for path in sorted(engine.parent.iterdir())
                     if path.is_file() and path != manifest]
    core.write(manifest, data)
    plan.update(evaluator=implementation(), reportProtocol=PROTOCOL,
                preparationVersion='full-v3-before-execution')
    plan['derivedFiles'] = [raw.artifacts.artifact(path) for path in sorted(engine.parent.iterdir())
                            if path.is_file()] + [raw.artifacts.artifact(output / 'fresh-host.cjs')]
    core.write(output / 'plan.json', plan)
    return plan


def prepare_host(*, source, case_id, output, deadline, inputs):
    remaining = core.remaining_deadline(deadline, 'host episode preparation')
    raw.require(0 < remaining <= 3600 and case_id in HOST_CASES, 'Own host case and remaining budget required')
    output = native.canonical_output(output)
    raw.require(not output.exists(), 'Never overwrite an episode')
    output.mkdir(parents=True)
    contract = core.load(native.CONTRACT)
    spec = raw.spec_for(contract, case_id)
    (output / 'canonical-contract.json').write_bytes(native.CONTRACT.read_bytes())
    plan = {'schemaVersion': 3, 'protocol': PROTOCOL, 'taskId': TASK, 'source': str(Path(source).resolve()),
        'caseId': case_id, 'canonicalCase': spec, 'contract': raw.artifacts.artifact(output / 'canonical-contract.json'),
        'inputInventory': inputs, 'evaluator': implementation(), 'rawOutput': str(output / 'raw.json'),
        'deadlineEpochMs': int((time.time() + remaining) * 1000), 'preparedOnly': True,
        'command': [NODE, str(HOST), '--plan', str(output / 'plan.json')], 'deviceOrModelStarted': False}
    core.write(output / 'plan.json', plan)
    return plan


def command(command, *, log, deadline, lease_serial=None):
    started = time.time()
    remaining = core.remaining_deadline(deadline, 'Task15 own episode')
    try:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        stdout, stderr = process.communicate(timeout=remaining)
        log.write_text(stdout + stderr)
        value = {'command': command, 'exit': process.returncode, 'timedOut': False, 'pid': process.pid}
    except subprocess.TimeoutExpired as error:
        def text(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=max(0.01, min(5, deadline - time.monotonic())))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        log.write_text(text(stdout) + text(stderr))
        value = {'command': command, 'exit': process.returncode, 'timedOut': True, 'pid': process.pid,
                 'ownedProcessGroupStopped': True}
        if '--serial' in command or lease_serial is not None:
            serial = command[command.index('--serial') + 1] if '--serial' in command else lease_serial
            lock = Path('/tmp') / ('ltb-arkts-device-' + hashlib.sha256(serial.encode()).hexdigest()[:16])
            owner_file = lock / 'owner.json'
            if owner_file.is_file() and not owner_file.is_symlink():
                before = owner_file.read_bytes()
                owner = json.loads(before)
                if owner.get('pid') == process.pid and owner.get('token') == 'task15-' + str(process.pid):
                    try:
                        os.kill(process.pid, 0)
                    except ProcessLookupError:
                        if owner_file.read_bytes() == before:
                            owner_file.unlink(); lock.rmdir()
                            value['ownedDeadDeviceLeaseRemoved'] = True
    value.update(startedAtEpochMs=int(started * 1000), finishedAtEpochMs=int(time.time() * 1000),
                 log=raw.artifacts.artifact(log))
    core.write(log.with_suffix('.command.json'), value)
    return value


def native_bundle(directory):
    directory = Path(directory)
    run = directory / 'native-e2e'
    return {key: raw.artifacts.artifact(path) for key, path in {
        'plan': directory / 'plan.json', 'raw': run / 'execution/native-result.json',
        'provider': run / 'execution/provider-transcript.json', 'run': run / 'run.json',
        'build': run / 'retained-build-text/build/device-build-report.json',
        'cleanup': run / 'cleanup-manifest.json', 'aaLog': run / 'execution/aa-test.log'}.items()}


def _retained(directory):
    files = []
    for path in sorted(Path(directory).rglob('*')):
        raw.require(not path.is_symlink(), 'No symlink in retained evidence')
        if path.is_file():
            raw.require(path.suffix.lower() not in core.BINARY_SUFFIXES, 'Build/binary escaped hash cleanup')
            files.append({**raw.artifacts.artifact(path), 'path': path.relative_to(directory).as_posix()})
    return {'path': str(directory), 'files': files, 'binariesRetained': False}


def assemble(index_reference, *, output):
    """No optional verifier bypass. All ten rows are independently reconstructed."""
    from . import task15_full_report_verify_v3 as guard
    output = native.canonical_output(output)
    raw.require(not output.exists(), 'Never overwrite an original model or earlier runtime report')
    index = raw.read(index_reference)
    contract = raw.read(index['contract'])
    rows, sources = guard.derive_rows(index, contract)
    counts = guard.counts(rows)
    inventory = raw.read(index['inputInventory'])
    snapshots = {item['path']: item['snapshot'] for item in inventory['files']}
    ready = counts['notScored'] == 0
    report = {'schemaVersion': 3, 'taskId': TASK, 'platform': 'arkts', 'role': 'agent',
        'observationMode': 'runtime_state_transition', 'runtime': PROTOCOL,
        'compile': copy.deepcopy(index['applicationCompile']),
        'runtimeCompile': {'passed': guard.packaging_complete(index),
            'status': 'passed' if guard.packaging_complete(index) else 'not_scored',
            'scope': 'evaluator native HAP packaging only; not full application compile'},
        'semantic': {**counts, 'cases': rows},
        'provenance': {'candidateMode': 'standalone_directory', 'archivedPatchApplied': False,
            'candidateSource': index['source'], 'candidateRootSha256': inventory['rootSha256'],
            'productionSources': sources, 'productionSourceSnapshots': {item['path']: snapshots[item['path']] for item in sources},
            'fullTask15': {'protocol': PROTOCOL, 'index': index_reference,
                'evaluatorSha256': index['evaluator']['sha256'], 'controlLabel': index.get('controlLabel')},
            'retainedEvidence': _retained(Path(index['evidenceRoot']))},
        'diagnostics': {'adapter': 'ready' if ready else 'incomplete', 'transport': 'transport_completed' if ready else 'incomplete',
            'environmentFailureIsNotSemanticFailure': True,
            'cleanup': {'temporaryBuildRemoved': True, 'binariesRetained': False,
                        'binaryHashesRecordedBeforeRemoval': True},
            'originalModelMetricsChanged': False, 'newModelCalled': False,
            'scorerDeadlineEpochMs': index['deadlineEpochMs']}}
    # Guard checks every row against its own raw episode AND calls public validation.
    guard.verify_value(report, contract)
    core.write(output, report)
    receipt = guard.verify_report(output)
    core.write(output.with_suffix('.verified.json'), receipt)
    return report


def prepare_index(*, source, output, timeout=3600, deadline=None, control_label=None,
                  compile_passed=None, compile_command='', compile_evidence=None):
    raw.require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 3600,
                'One 0 < timeout <=3600 budget required')
    raw.require(compile_passed is None or type(compile_passed) is bool, 'Compile is a separate nullable boolean')
    if compile_passed is True:
        proof = raw.read(compile_evidence)
        raw.require(proof.get('passed') is True and proof.get('candidateRootSha256') == core.directory_digest(Path(source)),
                    'Application compile needs its own source-bound full-build proof before any device work')
    deadline = time.monotonic() + timeout if deadline is None else deadline
    remaining = core.remaining_deadline(deadline, 'full Task15 preparation')
    raw.require(0 < remaining <= timeout, 'Do not reset/extend an outer scorer deadline')
    output = native.canonical_output(output)
    raw.require(not output.exists(), 'Refuse existing run/evidence root')
    output.mkdir(parents=True)
    inventory = native.snapshot_inputs(source, output)
    core.write(output / 'input-inventory.json', inventory)
    (output / 'canonical-contract.json').write_bytes(native.CONTRACT.read_bytes())
    (output / 'task-manifest.json').write_bytes((ROOT / 'benchmark_tasks' / TASK / 'task.json').read_bytes())
    (output / 'public-validator-at-start.py').write_bytes((ROOT / 'scripts/run_runtime_transition_matrix.py').read_bytes())
    index = {'schemaVersion': 3, 'protocol': PROTOCOL, 'source': str(Path(source).resolve()),
        'evidenceRoot': str(output), 'inputInventory': raw.artifacts.artifact(output / 'input-inventory.json'),
        'contract': raw.artifacts.artifact(output / 'canonical-contract.json'), 'evaluator': implementation(),
        'taskManifest': raw.artifacts.artifact(output / 'task-manifest.json'),
        'startedAtEpochMs': int(time.time() * 1000), 'deadlineEpochMs': int((time.time() + remaining) * 1000),
        'budgetSeconds': remaining, 'native': {}, 'host': {}, 'prefix': None, 'capability': None,
        'controlLabel': control_label, 'applicationCompile': {'passed': compile_passed, 'command': compile_command,
            'evidence': compile_evidence, 'scope': 'separate full application preflight; never inferred from runtime packaging'},
        'publicValidator': {'path': str(ROOT / 'scripts/run_runtime_transition_matrix.py'),
            'sha256': core.sha256(ROOT / 'scripts/run_runtime_transition_matrix.py'),
            'snapshot': raw.artifacts.artifact(output / 'public-validator-at-start.py')},
        'errors': {}, 'controls': None, 'executionStarted': False}
    core.write(output / 'episode-index.json', index)
    return index, deadline


def _cleanup_orphans(output):
    """Keep unique compiler text before removing only this run's build products."""
    removed = []
    for parent in (Path(output) / 'native').glob('*/native-e2e'):
        for name in ('build', 'certificates', 'preserved-work'):
            directory = parent / name
            if not directory.exists():
                continue
            for path in sorted(directory.rglob('*')):
                if not path.is_file():
                    continue
                record = raw.artifacts.artifact(path)
                if path.suffix in ('.json', '.log', '.txt', '.js', '.cjs', '.ets', '.ts'):
                    target = parent / 'retained-recovery-text' / path.relative_to(parent)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
                    record['retainedText'] = raw.artifacts.artifact(target)
                removed.append(record)
            shutil.rmtree(directory)
    removed.extend(core.remove_binary_artifacts(Path(output)))
    core.write(Path(output) / 'outer-cleanup.json', {'hashesRecordedBeforeRemoval': True,
        'files': removed, 'binariesRetained': False, 'scope': 'owned evidence root only; never foreign device leases'})


def evaluate(*, source, output, timeout=3600, deadline=None, device_serial='127.0.0.1:5555',
             controls=None, control_label=None, compile_passed=None, compile_command='', compile_evidence=None):
    """Explicit execution API, not used by offline audit/unit preparation."""
    from . import task15_formal_agent as legacy
    from . import task14_15_arkts_entry_evidence as entry
    from . import task15_capability_v3 as capability
    from . import task15_prefix_v3 as prefix
    source, output = Path(source).resolve(), Path(output).absolute()
    index, deadline = prepare_index(source=source, output=output, timeout=timeout, deadline=deadline,
        control_label=control_label, compile_passed=compile_passed, compile_command=compile_command,
        compile_evidence=compile_evidence)
    index.update(executionStarted=True, controls=controls)
    try:
        device_serial = legacy._discover_device(device_serial, deadline)
        if entry.closure.reviewed_source(TASK, core.directory_digest(source)):
            # Source equality selects only an eligible probe, never a semantic verdict.
            # Each case still needs actual isolated native UI absence + positive controls.
            core.require_build_space()
            prefix.evaluate(source=source, evidence=output, deadline=deadline, device_serial=device_serial)
            index['prefix'] = raw.artifacts.artifact(output / 'base-device/report.json')
        else:
            for case_id in sorted(HOST_CASES):
                directory = output / 'host' / case_id
                try:
                    plan = prepare_host(source=source, case_id=case_id, output=directory, deadline=deadline,
                                        inputs=index['inputInventory'])
                    command(plan['command'], log=directory / 'host.log', deadline=deadline)
                    index['host'][case_id] = {key: raw.artifacts.artifact(path) for key, path in {
                        'plan': directory / 'plan.json', 'raw': directory / 'raw.json',
                        'command': directory / 'host.command.json'}.items()}
                except Exception as error:
                    index['errors'][case_id] = str(error)
            for case_id in sorted(native.NATIVE_CASES):
                directory = output / 'native' / case_id
                try:
                    core.require_build_space()
                    plan = prepare_native(source=source, case_id=case_id, output=directory,
                        deadline=deadline, serial=device_serial)
                    command(plan['command'], log=directory / 'host.log', deadline=deadline)
                    index['native'][case_id] = native_bundle(directory)
                except Exception as error:
                    index['errors'][case_id] = str(error)
            try:
                core.require_build_space()
                capability.evaluate(source=source, output=output / 'unsupported-capability',
                    deadline=deadline, device_serial=device_serial)
                index['capability'] = raw.artifacts.artifact(output / 'unsupported-capability/report.json')
            except Exception as error:
                index['errors']['capability'] = str(error)
    except Exception as error:
        index['errors']['execution'] = str(error)
    finally:
        _cleanup_orphans(output)
        index['finishedAtEpochMs'] = int(time.time() * 1000)
        core.write(output / 'episode-index.json', index)
    return assemble(raw.artifacts.artifact(output / 'episode-index.json'), output=output / 'report.json')


def run_four_controls(*, base_source, final_source, output, timeout=3600,
                      device_serial='127.0.0.1:5555', execute=False):
    """Review-gated serial driver. All four controls share ONE outer budget."""
    raw.require(execute is True, 'Device execution requires explicit coordinator release/execute=True')
    raw.require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 3600,
                'One <=3600s group budget required')
    started = time.monotonic()
    deadline = started + timeout
    output = native.canonical_output(output)
    raw.require(not output.exists(), 'Refuse existing control group')
    output.mkdir()
    manifest = core.load(ROOT / 'benchmark_tasks' / TASK / 'task.json')['arkts']
    raw.require(core.directory_digest(Path(base_source)) == core.directory_digest(ROOT / manifest['basePath']) and
        core.directory_digest(Path(final_source)) == core.directory_digest(ROOT / manifest['finalPath']),
        'Four controls must use approved immutable base/final byte identities')
    reports, cleanup = {}, []
    result = {'protocol': PROTOCOL, 'status': 'not_ready', 'modelCalled': False, 'timeoutSeconds': timeout,
              'evaluator': implementation(), 'reports': reports}
    try:
        for pole in ('base', 'final', 'base_copy_agent', 'final_copy_agent'):
            core.remaining_deadline(deadline, 'serial four-control group')
            source = output / 'sources' / pole
            core._copy_project(Path(base_source) if pole in ('base', 'base_copy_agent') else Path(final_source), source)
            evaluate(source=source, output=output / pole, timeout=timeout, deadline=deadline,
                     device_serial=device_serial, control_label=pole)
            reports[pole] = raw.artifacts.artifact(output / pole / 'report.json')
        from . import task15_full_report_verify_v3 as guard
        result['verification'] = guard.verify_controls(reports, evaluator_sha=result['evaluator']['sha256'])
        result['status'] = 'passed'
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    finally:
        if (output / 'sources').exists():
            for source in sorted((output / 'sources').iterdir()):
                cleanup.append(core.tree_artifact_record(source))
                shutil.rmtree(source)
            (output / 'sources').rmdir()
        result['cleanup'] = {'sourceCopiesHashRecordedThenRemoved': True, 'trees': cleanup,
                             'binariesRetained': False, 'canonicalDeviceLeasePerScenario': True}
        result['elapsedSecondsOverall'] = time.monotonic() - started
        if result['elapsedSecondsOverall'] > timeout:
            result.update(status='not_ready', error='Whole group deadline exhausted including cleanup')
        core.write(output / 'four-controls.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--index', type=Path, help='offline assemble an existing episode index')
    parser.add_argument('--execute', action='store_true', help='explicit device execution; coordinator release required')
    parser.add_argument('--device-serial', default='127.0.0.1:5555')
    parser.add_argument('--four-controls', action='store_true')
    parser.add_argument('--base-source', type=Path)
    parser.add_argument('--final-source', type=Path)
    args = parser.parse_args()
    if args.four_controls:
        raw.require(args.base_source and args.final_source, '--base-source and --final-source required')
        run_four_controls(base_source=args.base_source, final_source=args.final_source,
            output=args.output, device_serial=args.device_serial, execute=args.execute)
    elif args.index:
        assemble(raw.artifacts.artifact(args.index), output=args.output)
    elif args.execute:
        raw.require(args.source is not None, '--source required')
        evaluate(source=args.source, output=args.output, device_serial=args.device_serial)
    else:
        parser.error('No execution by default: supply an existing --index for offline assembly')


if __name__ == '__main__':
    main()
