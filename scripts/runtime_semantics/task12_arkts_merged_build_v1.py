"""Owned, hash-before-delete compiler boundary for merged Task12 only."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from . import task12_arkts_merged_protocol_v1 as proof

STUDIO = Path('/Applications/DevEco-Studio.app/Contents')
SDK = Path.home() / 'Library/OpenHarmony/Sdk'
DEPENDENCIES = proof.ROOT / 'elementx_harmony_full/oh_modules'


def compiler_group_members(deadline):
    """Do not delete a failed compiler's files while owned descendants still run."""
    if os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid():
        raise RuntimeError('Compiler worker is not the verified owned session leader')
    proof.check(deadline)
    process = subprocess.Popen(['ps', '-axo', 'pid=,pgid='], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = process.communicate(timeout=min(5, deadline - time.monotonic()))
    except BaseException:
        process.kill()  # Only the Popen-owned inspection child, not a foreign group.
        process.wait(timeout=max(.001, min(2, deadline - time.monotonic())))
        raise
    if process.returncode:
        raise RuntimeError('Cannot establish owned compiler quiescence: ' + stderr)
    members = []
    for line in stdout.splitlines():
        pid, pgid = map(int, line.split())
        if pgid == os.getpid() and pid not in (os.getpid(), process.pid):
            members.append(pid)
    return members


def remove_owned_tree(work, audit, deadline):
    """No automatic TemporaryDirectory finalizer can delete unaudited products."""
    audit.mkdir(parents=True, exist_ok=False)
    receipt = {'root': str(work), 'localOnly': True, 'complete': False, 'binaryHashes': [], 'filesRemoved': 0}
    try:
        with (audit / 'hashes.jsonl').open('x') as journal:
            for path in sorted(work.rglob('*')):
                proof.check(deadline)
                if path.is_symlink():
                    item = {'path': str(path), 'symlinkTarget': os.readlink(path)}
                elif path.is_file():
                    item = proof.file_record(path, deadline)
                    if path.suffix.lower() in {'.json', '.jsonl', '.log'}:
                        saved = audit / (hashlib.sha256(str(path).encode()).hexdigest() + path.suffix)
                        with path.open('rb') as incoming, saved.open('xb') as outgoing:
                            while True:
                                proof.check(deadline)
                                block = incoming.read(1024 * 1024)
                                if not block:
                                    break
                                outgoing.write(block)
                        item['retained'] = proof.file_record(saved, deadline)
                else:
                    continue
                journal.write(json.dumps(item) + '\n')
                journal.flush()
                os.fsync(journal.fileno())
                if path.suffix.lower() in proof.BINARIES and 'sha256' in item:
                    receipt['binaryHashes'].append(item)
                path.unlink()
                receipt['filesRemoved'] += 1
            for path in sorted(work.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                proof.check(deadline)
                if path.is_dir() and not path.is_symlink():
                    path.rmdir()
            work.rmdir()
        receipt['hashLedger'] = proof.file_record(audit / 'hashes.jsonl', deadline)
        receipt['complete'] = True
    except Exception as error:
        receipt['error'] = repr(error)
    proof.write(audit / 'cleanup.json', receipt)
    return receipt


def build_application(*, source, output, temporary, deadline):
    proof.check(deadline)
    source, output, temporary = source.resolve(), output.resolve(), temporary.resolve()
    if shutil.disk_usage(temporary).free < 8 * 1024**3:
        raise RuntimeError('Storage protection: below 8 GiB before compiler preparation')
    output.mkdir(parents=True, exist_ok=False)
    before = proof.inventory(source, deadline)
    # Deliberately no context-manager finalizer: parent owns recovery if killed.
    work = Path(tempfile.mkdtemp(prefix='task12-merged-build-', dir=str(temporary)))
    report = {'schemaVersion': 1, 'source': str(source), 'passed': False, 'productionUnchanged': False,
              'copiedProductionUnchanged': False, 'temporaryProjectRemoved': False,
              'sourceInventory': before, 'temporary': str(work)}
    error = None
    try:
        shutil.copytree(source, work, dirs_exist_ok=True,
                        ignore=lambda directory, names: [name for name in names if name in proof.EXCLUDES])
        if proof.inventory(work, deadline)['sha256'] != before['sha256']:
            raise ValueError('Copied standalone source differs before toolchain configuration')
        shutil.copytree(DEPENDENCIES, work / 'oh_modules', symlinks=True)
        (work / 'node_modules/@ohos').mkdir(parents=True)
        for name in ('hvigor', 'hvigor-ohos-plugin'):
            (work / 'node_modules/@ohos' / name).symlink_to(STUDIO / 'tools/hvigor' / name)
        (work / 'local.properties').write_text('sdk.dir=' + str(SDK) + '\nhwsdk.dir=' + str(STUDIO / 'sdk') + '\n')
        command = [str(STUDIO / 'tools/node/bin/node'), str(STUDIO / 'tools/hvigor/hvigor/bin/hvigor.js'),
                   'assembleHap', '--mode', 'module', '-p', 'module=entry@default', '-p', 'product=default',
                   '-p', 'buildMode=debug', '--no-daemon', '--no-parallel']
        environment = {**os.environ, 'DEVECO_SDK_HOME': str(STUDIO / 'sdk'), 'OHOS_SDK_HOME': str(SDK),
                       'NODE_PATH': str(work / 'node_modules'), 'JAVA_HOME': str(STUDIO / 'jbr/Contents/Home'),
                       'PATH': str(STUDIO / 'jbr/Contents/Home/bin') + ':' + str(STUDIO / 'tools/node/bin') + ':' +
                               str(STUDIO / 'tools/ohpm/bin') + ':' + os.environ.get('PATH', '')}
        report.update(command=command, effectiveEnvironment={key: environment[key] for key in
                      ('DEVECO_SDK_HOME', 'OHOS_SDK_HOME', 'NODE_PATH', 'JAVA_HOME', 'PATH')},
                      effectiveLocalProperties=proof.file_record(work / 'local.properties', deadline))
        # Cleanup has its own remaining reserve inside the already parent-bounded worker.
        budget = deadline - time.monotonic()
        compile_deadline = deadline - min(60, budget / 5)
        proof.check(compile_deadline)
        with (output / 'application-build.log').open('x') as log:
            process = subprocess.run(command, cwd=work, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=compile_deadline - time.monotonic(), check=False)
        report['exitCode'] = process.returncode
        report['log'] = proof.file_record(output / 'application-build.log', deadline)
        if process.returncode:
            raise RuntimeError('Production application compiler exited ' + str(process.returncode))
        haps = sorted((work / 'entry/build').rglob('*.hap'))
        application = next((p for p in haps if 'test' not in p.name.lower()), None)
        if application is None:
            raise RuntimeError('Production application HAP missing')
        report['copiedProductionUnchanged'] = all(
            proof.file_record(work / item['path'], deadline)['sha256'] == item['sha256'] for item in before['files']
            if item['path'] != 'local.properties')
        if not report['copiedProductionUnchanged']:
            raise ValueError('Compiler preparation/build modified copied production')
        retained = output / application.name
        with application.open('rb') as incoming, retained.open('xb') as outgoing:
            while True:
                proof.check(deadline)
                block = incoming.read(1024 * 1024)
                if not block:
                    break
                outgoing.write(block)
        report['hap'] = proof.file_record(retained, deadline)
        report['passed'] = True
    except BaseException as exception:
        error = exception
        report['error'] = repr(exception)
    finally:
        try:
            report['productionUnchanged'] = proof.inventory(source, deadline) == before
        except Exception as exception:
            report['sourceCheckError'] = repr(exception)
        try:
            members = compiler_group_members(deadline)
            report['compilerGroupMembersBeforeCleanup'] = members
            if members:
                raise RuntimeError('Live owned compiler descendants; parent must reap before hash-cleanup')
            cleanup = remove_owned_tree(work, output / 'owned-build-cleanup', deadline)
            report['temporaryProjectRemoved'] = cleanup['complete'] and not work.exists()
            report['ownedBuildCleanup'] = proof.file_record(output / 'owned-build-cleanup/cleanup.json', deadline)
        except Exception as exception:
            report['cleanupDeferredToOwnedParent'] = True
            report['cleanupError'] = repr(exception)
        report['passed'] = report['passed'] and report['productionUnchanged'] and report['temporaryProjectRemoved']
        proof.write(output / 'application-build.json', report)
    if error is not None:
        raise error
    if not report['passed']:
        raise RuntimeError('Production continuity or hash-before-delete cleanup incomplete')
    return report
