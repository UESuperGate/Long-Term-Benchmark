#!/usr/bin/env python3
"""Reconstruct a retained Task09 patch and replay semantics without a model call."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import task09_verify_strict as verifier
import task09_formal_agent as formal

ROOT = HERE.parents[1]
OLD = ROOT / 'eval_runs/runtime_minimax_m3_20261020_fresh_v1'
TASK = '09_spaces_lifecycle'
NODE = '/Applications/DevEco-Studio.app/Contents/tools/node/bin/node'
BINARY = {'.hap', '.har', '.app', '.apk', '.abc', '.so'}


def read(file):
    return json.loads(file.read_text())


def record(file):
    data = file.read_bytes()
    return {'path': str(file.resolve()), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write(file, value):
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def guard():
    free = shutil.disk_usage(ROOT).free
    if free < 8 * 1024**3:
        raise RuntimeError(f'8 GiB guard: {free / 1024**3:.3f} GiB available')


def run(command, log, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Overall Task09 3600s build/device/execute deadline exhausted')
    with log.open('x') as stream:
        result = subprocess.run(command, cwd=ROOT, timeout=remaining, stdout=stream, stderr=subprocess.STDOUT)
    return result.returncode


def cleanup(output):
    binaries = []
    for file in output.rglob('*'):
        if file.is_file() and file.suffix.lower() in BINARY:
            binaries.append(record(file))
            file.unlink()
    write(output / 'binary-cleanup.json', {'removed': binaries, 'hashesRecordedBeforeRemoval': True,
          'binariesRetained': False, 'remaining': [str(p) for p in output.rglob('*')
          if p.is_file() and p.suffix.lower() in BINARY]})


def replay(output, roles, serial):
    guard()
    output.mkdir(parents=True, exist_ok=False)
    patch = OLD / 'patches/arkts_09_spaces_lifecycle.patch'
    original_report = OLD / 'reports/arkts_09_spaces_lifecycle_agent.json'
    original_runtime = OLD / 'reports/arkts_09_spaces_lifecycle_agent.runtime.json'
    original_evidence = OLD / 'reports/arkts_09_spaces_lifecycle_agent.runtime.evidence'
    archived_build = original_evidence / 'agent-sp_state_001_open_space/device-build-report.json'
    contract_file = ROOT / 'benchmark_tasks' / TASK / 'transitions.json'
    task = read(ROOT / 'benchmark_tasks' / TASK / 'task.json')
    protected = [patch, original_report, original_runtime, contract_file]
    hashes = [record(p) for p in protected]
    for file in protected:
        target = output / 'original' / file.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
    shutil.copytree(original_evidence, output / 'original/runtime-evidence')
    write(output / 'original/hashes.json', hashes)
    summaries = {}
    errors = {}
    try:
        with tempfile.TemporaryDirectory(prefix='ltb-task09-exact-replay-') as temporary:
            candidate = Path(temporary) / 'candidate'
            shutil.copytree(ROOT / task['arkts']['basePath'], candidate,
                ignore=shutil.ignore_patterns('.git', '.hvigor', 'build', 'oh_modules', 'node_modules'))
            subprocess.run(['git', 'init', '-q', str(candidate)], check=True)
            subprocess.run(['git', '-C', str(candidate), 'apply', '--check', str(patch)], check=True)
            subprocess.run(['git', '-C', str(candidate), 'apply', str(patch)], check=True)
            inventory = read(archived_build)['production']
            actual = {str(p.relative_to(candidate)): record(p)['sha256']
                      for p in (candidate / 'entry/src/main').rglob('*') if p.is_file()}
            if actual != {p['path']: p['sha256'] for p in inventory}:
                raise ValueError('Reconstructed candidate differs from archived production inventory')
            write(output / 'candidate-reconstruction.json', {'exactArchivedProduction': True,
                'patch': record(patch), 'archivedBuild': record(archived_build), 'production': inventory,
                'modelRun': False, 'candidateModified': False})
            verifier.retain_production_input(candidate, output / 'agent-source-snapshot', inventory)
            sources = {'base': ROOT / task['arkts']['basePath'],
                       'final': ROOT / task['arkts']['finalPath'], 'agent': candidate}
            for role in roles:
                guard()
                deadline = time.monotonic() + 3600
                source = sources[role]
                if role == 'agent':
                    old = read(original_report)
                    result = formal.score(platform='arkts', source=source,
                        output=output / 'agent.semantic.json', timeout=3600,
                        compile_passed=old['compile']['passed'], compile_command=old['compile']['command'])
                    result['compile'] = old['compile']
                    result['codeGeneration'] = old['codeGeneration']
                    result['semanticReplay'] = {'originalReport': record(original_report),
                        'archivedPatch': record(patch), 'newModelCall': False,
                        'originalStandaloneCompilePreserved': True}
                    if result.get('publication', {}).get('eligible'):
                        proof = verifier.verify_arkts_candidate(
                            output / 'agent.semantic.runtime.json', output / 'agent-source-snapshot/input.json',
                            read(contract_file))
                        write(output / 'agent-independent-verifier.json', proof)
                        result['semanticReplay']['independentVerification'] = record(output / 'agent-independent-verifier.json')
                    # This is a new report, never an update of the fresh run.
                    (output / 'agent.semantic.json').write_text(json.dumps(result, indent=2) + '\n')
                else:
                    app_output = output / (role + '-standalone')
                    status = run([NODE, str(HERE / 'task09_arkts_app_build.cjs'), '--source', str(source),
                        '--role', role, '--output-dir', str(app_output), '--timeout', '3600'],
                        output / (role + '-standalone.log'), deadline)
                    if status:
                        errors[role] = 'standalone app build failed'
                        continue
                    app_file = app_output / 'build-report.json'
                    verifier.verify_arkts_app_build(read(app_file), role=role, source=source,
                                                   contract_path=contract_file)
                    remaining = max(1, int(deadline - time.monotonic()))
                    runtime_file = output / (role + '.runtime.json')
                    status = run([NODE, str(HERE / 'task09_arkts_strict_runner.cjs'), '--source', str(source),
                        '--role', role, '--output', str(runtime_file), '--serial', serial, '--timeout', str(remaining)],
                        output / (role + '-runtime.log'), deadline)
                    result = read(runtime_file)
                    try:
                        verifier.verify_runtime(result, platform='arkts', role=role, source=source,
                                                contract=read(contract_file), contract_path=contract_file)
                        write(output / (role + '-independent-verifier.json'), {'validated': True,
                              'runtime': record(runtime_file), 'standalone': record(app_file)})
                    except verifier.VerificationError as error:
                        errors[role] = str(error)
                summaries[role] = {k: result['semantic'].get(k) for k in ('passed', 'failed', 'notScored')}
                print(json.dumps({'role': role, **summaries[role], 'error': errors.get(role)}), flush=True)
    finally:
        cleanup(output)
        write(output / 'completion.json', {'modelRun': False, 'candidateRemoved': True,
            'oldTask09EvidenceUnchanged': [record(p) for p in protected] == hashes,
            'freshManifestsTouched': False, 'semantic': summaries, 'errors': errors,
            'freeBytes': shutil.disk_usage(ROOT).free})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--roles', nargs='+', choices=['base', 'final', 'agent'], default=['base', 'final', 'agent'])
    parser.add_argument('--serial', default='127.0.0.1:5555')
    args = parser.parse_args()
    replay(args.output.resolve(), args.roles, args.serial)
