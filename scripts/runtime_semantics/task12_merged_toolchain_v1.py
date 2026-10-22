"""Prospective, same-worker actual toolchain observations; never historical adoption."""

import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from . import task12_arkts_merged_protocol_v4 as proof
from . import task12_arkts_merged_build_v2 as builder
from .task12_arkts_reviewed_controls import validate_versions

STUDIO = builder.STUDIO
SDK = builder.SDK / '23'
NODE = STUDIO / 'tools/node/bin/node'
JAVA_HOME = STUDIO / 'jbr/Contents/Home'
HDC = SDK / 'toolchains/hdc'


def require(value, reason):
    if not value:
        raise ValueError('Task12 prospective toolchain: ' + reason)


def roots():
    return [SDK, JAVA_HOME, STUDIO / 'tools/hvigor/hvigor', STUDIO / 'tools/hvigor/hvigor-ohos-plugin',
            builder.DEPENDENCIES, NODE]


def fingerprint(deadline):
    result, seen = [], set()
    pending = list(roots())
    while pending:
        proof.check(deadline)
        path = pending.pop()
        require(path.exists(), 'actual component missing: ' + str(path))
        if path.is_symlink():
            result.append({'path': str(path), 'type': 'symlink', 'target': os.readlink(path),
                           'resolved': str(path.resolve())})
            pending.append(path.resolve())
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        mode = path.stat().st_mode & 0o7777
        if path.is_dir():
            result.append({'path': str(resolved), 'type': 'directory', 'mode': mode})
            pending.extend(sorted(path.iterdir(), reverse=True))
        else:
            require(path.is_file(), 'unsupported toolchain input type')
            result.append({**proof.file_record(path, deadline), 'type': 'file', 'mode': mode})
    return sorted(result, key=lambda item: (item['path'], item['type']))


def probe(command, log, deadline):
    proof.check(deadline)
    started = time.monotonic()
    with log.open('x') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        try:
            process.wait(timeout=max(.001, deadline - time.monotonic()))
        except BaseException:
            if process.returncode is None:
                process.kill()  # Direct unreaped Popen child, never a numeric foreign PGID.
                process.wait(timeout=max(.001, deadline - time.monotonic()))
            raise
    require(process.returncode == 0, 'actual version probe failed: ' + str(command))
    return {'command': command, 'pid': process.pid, 'workerPid': os.getpid(),
            'startedLocal': started, 'finishedLocal': time.monotonic(), 'exitCode': process.returncode,
            'groupInherited': True, 'log': proof.file_record(log, deadline)}


def capture(output, serial, deadline):
    require(os.getpid() == os.getpgrp() == os.getsid(0), 'capturer is not the owned worker session')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    probes = {}
    for name, command in (
        ('buildNode', [str(NODE), '--version']), ('runtimeNode', [str(NODE), '--version']),
        ('java', [str(JAVA_HOME / 'bin/java'), '-version']), ('hdc', [str(HDC), '-v']),
        ('deviceApi', [str(HDC), '-t', serial, 'shell', 'param', 'get', 'const.ohos.apiversion']),
        ('deviceVersion', [str(HDC), '-t', serial, 'shell', 'param', 'get', 'const.ohos.fullname'])):
        probes[name] = probe(command, output / (name + '.log'), deadline)
    sdk = proof.load(SDK / 'ets/oh-uni-package.json')
    tool = proof.load(SDK / 'toolchains/oh-uni-package.json')
    require((sdk['version'], sdk['apiVersion']) == (tool['version'], tool['apiVersion']), 'SDK components differ')
    versions = {'sdkRelease': str(sdk['version']), 'sdkApi': str(sdk['apiVersion']),
                'hvigor': str(proof.load(STUDIO / 'tools/hvigor/hvigor/package.json')['version'])}
    versions.update({name: Path(item['log']['path']).read_text().strip() for name, item in probes.items()})
    validate_versions(versions)
    record = {'protocol': 'task12.prospective-toolchain.v1', 'nonce': uuid.uuid4().hex,
              'workerPid': os.getpid(), 'clockDomain': 'same_worker_process_local_monotonic',
              'startedLocal': started, 'finishedLocal': time.monotonic(), 'versions': versions,
              'serial': serial, 'probes': probes, 'files': fingerprint(deadline),
              'buildJavaHome': str(JAVA_HOME), 'buildNode': str(NODE), 'runtimeNode': str(NODE),
              'scope': {'fullRoots': [str(p) for p in roots()],
                        'configuredButNotClaimedFullRoot': str(STUDIO / 'sdk'),
                        'supportedProduct': {'runtimeOS': 'OpenHarmony', 'compileSdkVersion': 23},
                        'productionSourceNotInTheseRoots': True}}
    record['finishedLocal'] = time.monotonic()
    proof.write(output / 'snapshot.json', record)
    return proof.file_record(output / 'snapshot.json', deadline)


def compare(before, after, deadline):
    first, last = (proof.load(proof.checked(item, deadline)) for item in (before, after))
    require(first['workerPid'] == last['workerPid'] and first['nonce'] != last['nonce'] and
            first['serial'] == last['serial'] and first['files'] == last['files'] and
            first['scope'] == last['scope'] and first['versions'] == last['versions'] and
            first['finishedLocal'] < last['startedLocal'], 'actual before/after continuity differs')
    validate_versions(first['versions'])
    for snapshot in (first, last):
        for item in snapshot['probes'].values():
            require(item['workerPid'] == snapshot['workerPid'] and item['exitCode'] == 0 and
                    snapshot['startedLocal'] <= item['startedLocal'] <= item['finishedLocal'] <= snapshot['finishedLocal'],
                    'actual probe clock/worker binding differs')
            proof.checked(item['log'], deadline)
    return first, last
