#!/usr/bin/env python3
"""Reconstruct the archived Task11 candidate exactly, never modify its sources."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / 'eval_runs/runtime_minimax_m3_20261020_fresh_v2'
AUDIT = ROOT / 'experiment_results/runtime_transition_20261020/task11_fresh_v2_evaluator_repair_v1'
WORK = ROOT / 'eval_runs/task11_fresh_v2_evaluator_repair_v1'
EXPECTED_TREE = '5d9765a84664c99c72120f75b6f87bd32ed7fb25'


def record(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    if WORK.exists() or (AUDIT / 'reconstruction.json').exists():
        raise FileExistsError('Refuse to overwrite replay source/evidence')
    if shutil.disk_usage(ROOT).free < 8 * 1024**3:
        raise RuntimeError('At least 8 GiB free required')
    AUDIT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir()
    receipt_path = ORIGINAL / 'inputs/arkts_11_room_upgrade_navigation/4cff279fee8851c18fa4edbc08f75edd5fc2efa5.tar.json'
    receipt = json.loads(receipt_path.read_text())
    archive = Path(receipt['path'])
    assert all(record(archive)[key] == receipt[key] for key in ('sha256', 'bytes'))
    assert receipt['capturePhase'] == 'before_agent'
    candidate = WORK / 'exact-candidate'
    candidate.mkdir()
    with tarfile.open(archive, 'r:gz') as stored:
        for member in stored.getmembers():
            target = (candidate / member.name).resolve()
            if not target.is_relative_to(candidate) or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe baseline archive member')
        stored.extractall(candidate)
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=candidate, text=True).strip()
    git('init', '--quiet')
    git('add', '--force', '--all')
    assert git('write-tree') == receipt['tree'], 'Baseline tree differs from pre-agent capture'
    patch = ORIGINAL / 'patches/arkts_11_room_upgrade_navigation.patch'
    git('apply', '--check', '--index', '--binary', str(patch))
    git('apply', '--index', '--binary', str(patch))
    tree = git('write-tree')
    assert tree == EXPECTED_TREE, 'Candidate tree differs from the actual completed model tree'
    task = json.loads((ROOT / 'benchmark_tasks/11_room_upgrade_navigation/task.json').read_text())
    controls = {}
    for role in ('base', 'final'):
        source, target = ROOT / task['arkts'][role + 'Path'], WORK / ('control-' + role)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns('.git', '.hvigor', 'build', 'node_modules', 'oh_modules'))
        controls[role] = str(target)
    protected = [path for folder in ('logs', 'patches', 'reports') for path in (ORIGINAL / folder).rglob('*')
                 if path.is_file() and ('arkts_11_' in path.name or 'arkts_11_' in str(path.parent))]
    protected += [archive, receipt_path]
    before = AUDIT / 'evaluator-before'
    before.mkdir()
    sources = [ROOT / 'scripts/runtime_semantics/task11_arkts_strict_runtime.cjs']
    sources += sorted((ROOT / 'state_tests/runtime/arkts/native/task11_strict').glob('*'))
    for source in sources:
        if source.is_file():
            shutil.copyfile(source, before / source.name)
    write(AUDIT / 'reconstruction.json', {'taskId': '11_room_upgrade_navigation', 'platform': 'arkts',
        'baselineReceipt': record(receipt_path), 'baselineArchive': record(archive), 'baselineTree': receipt['tree'],
        'patch': record(patch), 'candidateTree': tree, 'candidate': str(candidate), 'controls': controls,
        'protectedOriginalTask11Files': [record(path) for path in sorted(set(protected))],
        'productionOrModelPatchEdited': False, 'newModelCall': False,
        'oldNativeFailureReason': 'Unavailable: original temporary native bytes were deleted; not reconstructed or guessed.'})
    print(json.dumps({'candidate': str(candidate), 'candidateTree': tree, 'controls': controls}, indent=2))


if __name__ == '__main__':
    main()
