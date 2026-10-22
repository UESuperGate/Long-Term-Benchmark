"""Immutable control export inside the reviewed supervisor, one repair deadline.

No verdict depends on commit/role. The frozen v2 arbitrary-source worker is used
unchanged. Export Git builtins are direct owned children, never a foreign PGID.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import uuid

from . import task11_android_sdk_leaf_launcher_v2 as v2

supervisor = v2.supervisor
record = v2.fixture.record


def git_command(repository, args, target, clock, output):
    clock.check_work()
    command = ['git', '-C', str(repository), *args]
    process = None
    try:
        with target.open('wb') as stream:
            process = subprocess.Popen(command, stdout=stream, stderr=subprocess.PIPE)
            supervisor.atomic(output / ('export-process-' + target.name + '.json'), dict(
                command=command, pid=process.pid, pgid=os.getpgid(process.pid),
                ownedDirectBuiltin=True, newSession=False))
            supervisor.wait_leader(process, clock.work_deadline)
            v2.require(process.returncode == 0, 'Immutable control Git builtin failed: ' + str(args))
    except BaseException:
        # Revoke before process operations; never signal the inherited parent group.
        pending = output / 'revocation-ready.json'
        if pending.exists():
            os.replace(pending, output / 'controller-admission.json')
        if process is not None and process.returncode is None:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.kill(process.pid, sig)
                except ProcessLookupError:
                    pass
            supervisor.reap_nonblocking(process)
        raise
    finally:
        if process is not None and process.stderr is not None:
            process.stderr.close()


def source_rows(source, clock):
    rows = []
    for path in sorted(source.rglob('*')):
        clock.check_work()
        v2.require(not path.is_symlink(), 'Control symlink unsupported')
        if path.is_file():
            rows.append(dict(relative=path.relative_to(source).as_posix(),
                             mode=path.stat().st_mode & 0o777, **record(path)))
    return rows


def export_control(repository, commit, budget_root, output, clock):
    v2.require(re.fullmatch('[a-f0-9]{40}', commit), 'Exact immutable commit required')
    source = budget_root / 'supplied-control'
    receipt = budget_root / 'control-export.json'
    if receipt.exists():
        previous = json.loads(receipt.read_text())
        v2.require(previous['commit'] == commit and previous['repository'] == str(repository),
                   'Control identity changed between attempts')
        v2.require(record(budget_root / 'original-control.tar.gz') == previous['archive'], 'Original archive changed')
        v2.require(source_rows(source, clock) == previous['files'], 'Exported raw source changed')
        return source, previous
    v2.require(not source.exists(), 'Never overwrite an incomplete control export')
    v2.require_floor(output)
    tree = output / 'immutable-tree.txt'
    git_command(repository, ['rev-parse', commit + '^{tree}'], tree, clock, output)
    listing = output / 'immutable-ls-tree.raw'
    git_command(repository, ['ls-tree', '-rz', commit], listing, clock, output)
    blobs, gitlinks = {}, []
    for raw in listing.read_bytes().split(b'\0'):
        if not raw:
            continue
        metadata, name = raw.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        name = name.decode()
        if kind == 'commit' and mode == '160000':
            gitlinks.append(dict(path=name, commit=oid, materialized=False))
            continue
        v2.require(kind == 'blob' and mode in ('100644', '100755'), 'Unsupported control entry')
        blobs[name] = (mode, oid)
    archive = budget_root / 'original-control.tar.gz'
    git_command(repository, ['archive', '--format=tar.gz', commit], archive, clock, output)
    source.mkdir()
    restored = set()
    with tarfile.open(archive, 'r|gz') as stream:
        for entry in stream:
            clock.check_work()
            if entry.isdir():
                continue
            v2.require(entry.isfile() and entry.name in blobs and not entry.name.startswith('/') and
                       '..' not in Path(entry.name).parts and entry.name not in restored, 'Unsafe export entry')
            data = stream.extractfile(entry).read()
            actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            v2.require(actual == blobs[entry.name][1], 'Export must preserve exact immutable blob bytes')
            target = source / entry.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o755 if blobs[entry.name][0] == '100755' else 0o644)
            restored.add(entry.name)
    v2.require(restored == set(blobs), 'Incomplete control export')
    value = dict(repository=str(repository), commit=commit, tree=tree.read_text().strip(),
                 archive=record(archive), files=source_rows(source, clock), externalGitlinks=gitlinks,
                 exactGitBlobsVerified=True, noMutableHeadRead=True, semanticScore=None)
    supervisor.atomic(receipt, value)
    return source, value


def cleanup(output, deadline):
    # Worker has finished and the reused supervisor has confirmed groupGone.
    work = output / 'owned-work'
    members = []
    archive = output / 'compiled-inputs-and-classes.tar.gz'
    with tarfile.open(archive, 'w:gz') as stream:
        if work.exists():
            for path in sorted(work.rglob('*')):
                v2.remaining(deadline)
                if path.is_file() and not path.is_symlink() and path.suffix in ('.class', '.kt', '.java'):
                    members.append(dict(relative=path.relative_to(work).as_posix(), **record(path)))
                    stream.add(path, arcname=path.relative_to(work).as_posix(), recursive=False)
    supervisor.atomic(output / 'compiled-inputs-and-classes.json', dict(
        archive=record(archive), members=members, retainedForIndependentReview=True))
    return supervisor.cleanup_work(output, deadline)


def run(repository, commit, budget_root, attempt, original_start_ms):
    end_ms = original_start_ms + 3600000
    remaining = min(3600, (end_ms - time.time()*1000) / 1000)
    v2.require(0 < remaining <= 3600, 'Original repair deadline expired; no renewal')
    budget_root = Path(budget_root).resolve()
    repository = Path(repository).resolve()
    output = budget_root / attempt

    def prepare(root, clock):
        expected = dict(originalStartEpochMs=original_start_ms, originalDeadlineEpochMs=end_ms,
                        maximumSeconds=3600, noModel=True)
        budget = budget_root / 'original-budget.json'
        if budget.exists():
            v2.require(json.loads(budget.read_text()) == expected, 'Never reset original repair budget')
        else:
            supervisor.atomic(budget, expected)
        source, exported = export_control(repository, commit, budget_root, root, clock)
        return dict(schema=v2.SCHEMA, requestId=uuid.uuid4().hex, source=str(source),
                    controllerPid=os.getpid(), deadlineEpochMs=min(end_ms, int(
                        (time.time()+clock.deadline-time.monotonic())*1000)),
                    implementation=v2.implementation(), resourceSchedule='coordinator_released_small_slice',
                    originalRepairBudget=expected, controlExport=record(budget_root / 'control-export.json'),
                    caller=record(__file__), semanticPromotionEligible=False, semanticScore=None)

    return supervisor._supervise(output, remaining, prepare,
        lambda request: [sys.executable, '-B', '-m', v2.MODULE, '--worker', str(request)],
        v2.finalize, cleanup=cleanup)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--budget-root', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--original-start-epoch-ms', type=int, required=True)
    args = parser.parse_args()
    v2.require(re.fullmatch(r'attempt[0-9]+', args.attempt), 'Fresh numbered attempt required')
    result = run(args.repository, args.commit, args.budget_root, args.attempt, args.original_start_epoch_ms)
    return 0 if result and result['runtimeCompile']['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
