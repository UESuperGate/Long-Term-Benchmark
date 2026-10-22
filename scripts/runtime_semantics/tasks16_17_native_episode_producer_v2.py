"""Actual scheduled native producer, one source/lease per pole, fresh app per case."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics import tasks16_17_native_controller_v2 as control
from scripts.runtime_semantics import tasks16_17_arkts_entry_binding_v2 as inputs
from scripts.runtime_semantics import tasks16_17_arkts_entry_binding_v3 as prefix
from scripts.runtime_semantics import tasks16_17_page_ports_evidence_v2 as native
from scripts.runtime_semantics import task16_case006_native_successor_v2 as successor


def command(argv, output, phase, deadline, epoch, env=None):
    """All descendants inherit this worker's owned process group, never detach."""
    control.assembly.remaining(deadline)
    log = output / (phase + '.log')
    started = int(time.time()*1000)
    control.atomic(output / (phase + '.started.json'), dict(command=argv, producerPid=os.getpid(), pgid=os.getpgrp(),
        deadlineEpochMs=epoch, startedAtEpochMs=started))
    with log.open('w') as stream:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   env={**os.environ, **(env or {})})
        process.wait(timeout=control.assembly.remaining(deadline))
    value = dict(command=argv, pid=process.pid, producerPid=os.getpid(), pgid=os.getpgrp(), exitCode=process.returncode,
        startedAtEpochMs=started, finishedAtEpochMs=int(time.time()*1000), deadlineEpochMs=epoch, log=inputs.record(log))
    control.atomic(output / (phase + '.command.json'), value)
    if process.returncode:
        raise RuntimeError('Actual native producer ' + phase + ' failed; semantic remains unavailable')


def produce_case(request, case, candidate, output, deadline):
    output.mkdir(parents=True, exist_ok=False)
    epoch = request['childBudget']['deadlineEpochMs']
    receipt = dict(taskId=request['taskId'], caseId=case['caseId'], canonicalContract=request['canonicalContract'],
        publicAdmissionChanged=False, integrationTier='actual_page_controlled_external_sdk', liveMatrixSdkOrServerVerified=False,
        candidateSource=str(candidate), actualProducer=dict(implementation=inputs.record(__file__),
            requestId=request['requestId'], caseId=case['caseId'], candidateSource=str(candidate),
            deadlineEpochMs=epoch, pid=os.getpid(), processGroup=os.getpgrp()))
    started = time.monotonic()
    try:
        receipt['before'] = inputs.capture_inputs(candidate, output / 'before.json', phase='before_runtime', deadline=deadline)
        with tarfile.open(output / 'input-source.tar.gz', 'x:gz') as archive:
            for row in request['inputs']:
                control.assembly.remaining(deadline)
                archive.add(candidate / row['path'], arcname=row['path'], recursive=False)
        receipt['inputArchive'] = inputs.record(output / 'input-source.tar.gz')
        receipt['validationSources'] = []
        for path in (Path(prefix.__file__), prefix.REFERENCE, Path(native.__file__)):
            snapshot = output / 'validation-sources' / path.name
            snapshot.parent.mkdir(exist_ok=True)
            shutil.copyfile(path, snapshot)
            receipt['validationSources'].append(dict(current=inputs.record(path), snapshot=inputs.record(snapshot)))
        receipt['successorSources'] = []
        for path in (Path(successor.__file__), successor.SCOPE,
                ROOT / 'state_tests/runtime/arkts/native/Tasks16_17PagePortsV2.install.cjs',
                ROOT / 'scripts/runtime_semantics/tasks16_17_arkts_page_ports_build_v2.cjs'):
            snapshot = output / 'successor-sources' / path.name
            snapshot.parent.mkdir(exist_ok=True)
            shutil.copyfile(path, snapshot)
            receipt['successorSources'].append(dict(current=inputs.record(path), snapshot=inputs.record(snapshot)))
        if shutil.disk_usage(output).free < 8*1024**3:
            raise OSError('8 GiB disk guard before case build')
        builder = ROOT / 'scripts/runtime_semantics/tasks16_17_arkts_page_ports_build_v2.cjs'
        command([control.NODE, str(builder), '--source', str(candidate), '--task', request['taskId'],
            '--case', case['caseId'], '--output-dir', str(output / 'build')], output, 'build', deadline, epoch,
            env={'LTB_PAGE_PORTS_DEADLINE_MS': str(epoch)})
        build_path = output / 'build/device-build-report.json'
        build = json.loads(build_path.read_text())
        receipt['buildExit'] = 0
        receipt['evaluatorSources'] = []
        for fixture in build['nativeUIObserver']['fixtures']:
            original = Path(fixture['file'])
            snapshot = output / 'evaluator-sources' / original.name
            snapshot.parent.mkdir(exist_ok=True)
            shutil.copyfile(original, snapshot)
            receipt['evaluatorSources'].append(dict(current=inputs.record(original), snapshot=inputs.record(snapshot)))
        command([control.NODE, str(ROOT / 'scripts/runtime_semantics/arkts_device_execute.cjs'), str(build_path),
            request['serial'], str(output / 'execution')], output, 'native-execution', deadline, epoch,
            env={'LTB_DEVICE_LOCK_PREACQUIRED': '1'})
        execution_path = output / 'execution/device-execution.json'
        execution = json.loads(execution_path.read_text())
        receipt.update(execution=inputs.record(execution_path), executionExit=0,
            transportCompleted=execution['transportCompleted'], ownedAppUninstalled=execution['cleanup']['ownedAppUninstalled'])
        receipt['after'] = inputs.capture_inputs(candidate, output / 'after.json', phase='after_runtime', deadline=deadline)
        receipt['inputBinding'] = inputs.seal_inputs(build_path, receipt['before'], receipt['after'], output / 'input-binding.json')
    except Exception as error:
        receipt['error'] = repr(error)
        raise
    finally:
        # The candidate intentionally remains shared within THIS pole. Controller
        # removes it after all cases/assembly; this receipt never claims otherwise.
        receipt['candidateRemoved'] = False
        receipt['binaryHashesBeforeRemoval'] = []
        for path in sorted(output.rglob('*')):
            control.assembly.remaining(deadline)
            if path.is_file() and path.suffix.lower() in ('.hap', '.abc', '.so', '.app', '.har'):
                receipt['binaryHashesBeforeRemoval'].append(inputs.record(path))
                path.unlink()
        receipt['binariesRetained'] = False
        receipt['overallElapsedSeconds'] = round(time.monotonic()-started, 3)
        control.atomic(output / 'receipt.pending.json', receipt)


def worker(request_path):
    request_path = Path(request_path).resolve()
    output = request_path.parent
    request = json.loads(request_path.read_text())
    if os.getpgrp() != os.getpid():
        raise ValueError('Actual producer must be its own supervisor-owned session leader')
    if request['implementation'] != control.implementation() or not request['calibrationOnly']:
        raise ValueError('Unknown controller/producer bytes or tier')
    claim = request['lease']
    if inputs.record(Path(claim['path']) / 'owner.json') != claim['ownerRecord']:
        raise ValueError('Actual preacquired shared lease not bound')
    deadline = control.timer.child_local_deadline(request['childBudget'])
    candidate = output / 'owned-work' / ('source-' + request['requestId'])
    source = Path(request['source'])
    candidate.mkdir()
    for item in request['inputs']:
        control.assembly.remaining(deadline)
        target = candidate / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / item['path'], target)
    if control.assembly.inventory(candidate, deadline) != request['inputs']:
        raise ValueError('Per-pole source copied incompletely/changed')
    contract = json.loads((ROOT / 'benchmark_tasks' / request['taskId'] / 'transitions.json').read_text())
    if request['caseIds'] != [case['caseId'] for case in contract['cases']]:
        raise ValueError('All canonical task cases required, no implicit single-only run')
    for case in contract['cases']:
        produce_case(request, case, candidate, output / 'cases' / case['caseId'], deadline)
    captured = control.assembly.inventory(candidate, deadline)
    if captured != request['inputs']:
        raise ValueError('Per-pole candidate changed before cleanup')
    control.atomic(output / 'pole-source-cleanup.pending.json', dict(source=str(candidate), files=captured, removed=False))
    shutil.rmtree(candidate)
    control.assembly.remaining(deadline)
    cleanup = dict(source=str(candidate), files=captured, removed=not candidate.exists(),
                   hashesRecordedBeforeRemoval=True, candidateWasUniquePerPole=True)
    control.atomic(output / 'pole-source-cleanup.json', cleanup)
    for case in contract['cases']:
        directory = output / 'cases' / case['caseId']
        receipt = json.loads((directory / 'receipt.pending.json').read_text())
        receipt.update(candidateRemoved=cleanup['removed'], poleSourceCleanup=inputs.record(output / 'pole-source-cleanup.json'))
        control.assembly.write_json(directory / 'receipt.json', receipt)
        control.atomic(directory / 'evidence-manifest.json', dict(files=[dict(**inputs.record(path), relativePath=str(path.relative_to(directory)))
            for path in sorted(directory.rglob('*')) if path.is_file() and path.name != 'evidence-manifest.json'],
            prospectiveInputsRequired=True, binariesRetained=False))
    control.atomic(output / 'worker-result.json', dict(requestId=request['requestId'], candidateSource=str(candidate),
        caseIds=request['caseIds'], producer=inputs.record(__file__), pid=os.getpid(),
        deadlineEpochMs=request['childBudget']['deadlineEpochMs'], finishedAtEpochMs=int(time.time()*1000)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    worker(parser.parse_args().request)
