"""Package Task14's configured-session Matrix-SDK native evaluator."""

import json
from pathlib import Path
import subprocess
import types

from . import task14_full_native_packaging_v5 as previous

old = previous.old
ROOT, TASK, CONTRACT = previous.ROOT, previous.TASK, previous.CONTRACT
core, artifacts, snapshot = previous.core, previous.artifacts, previous.snapshot
PROTOCOL = 'task14.full-nine-configured-sdk.v6'
DIRECTORY = Path(__file__).with_name('task14_full_native_v6')
CASES = previous.CASES
NODE = previous.NODE


def clone(function, **overrides):
    result = types.FunctionType(function.__code__, {**function.__globals__, **overrides},
        name=function.__name__, argdefs=function.__defaults__, closure=function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def expected_fixtures():
    command = """const i=require(process.argv[1]),c=require('node:crypto');
const hash=x=>c.createHash('sha256').update(x).digest('hex');
process.stdout.write(JSON.stringify([{name:'Task14DeviceUi.js',sha256:hash(i.bridgeSource())},
{name:'Task14PageObserver.js',sha256:hash(i.pageObserverAlias)},
...i.sources().map(item=>({name:item.name,sha256:hash(item.source)}))]));"""
    result = subprocess.run([NODE, '-e', command, str(DIRECTORY / 'install.cjs')],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10)
    overrides = {item['name']: item for item in json.loads(result.stdout)}
    prior = {item['name']: item for item in old.expected_fixtures() if item['name'] not in {
        'Task14RealRoutesV4.adapter.js', 'Task14JoinOwnerV3.js', 'Task14RealRoutesV3.suite.js'}}
    return sorted({**prior, **overrides}.values(), key=lambda item: item['name'])


def implementation():
    files = {item['path']: item for item in old.implementation()['files']}
    own = [Path(__file__), ROOT / 'scripts/run_runtime_transition_matrix.py',
        Path(__file__).with_name('withdrawn_owner_boundaries_v1.py'),
        Path(__file__).with_name('withdrawn_sdk_boundaries_v1.py')]
    own += [path for path in DIRECTORY.iterdir() if path.is_file()]
    provider = Path(__file__).with_name('task14_matrix_provider_v1.cjs')
    if provider.is_file():
        own.append(provider)
    for path in own:
        files[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}
    records = [files[name] for name in sorted(files)]
    return {'protocol': PROTOCOL, 'files': records, 'sha256': artifacts.row_digest(records)}


def derive_builder(contract, epoch):
    return old.replace_once(previous.derive_builder(contract, epoch),
        'require(' + json.dumps(str(previous.DIRECTORY / 'install.cjs')) + ')',
        'require(' + json.dumps(str(DIRECTORY / 'install.cjs')) + ')')


def prepare(*, source, output, deadline, case_ids=None):
    return clone(old.prepare, CASES=CASES, derive_builder=derive_builder,
        implementation=implementation, expected_fixtures=expected_fixtures,
        guard=types.SimpleNamespace(PROTOCOL=PROTOCOL))(source=source, output=output,
            deadline=deadline, case_ids=case_ids)
