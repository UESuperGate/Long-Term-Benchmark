"""Narrow v5 successor for the observed v4 metadata-loader setup failure.

Frozen v4 files/raw are never rewritten. Source-derived local functions below
bind the exact new installer/protocol at preparation/execution/admission. No
candidate source or imported module global is patched.
"""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import sys
import time
import types

from . import task14_actual_routes_packaging_v4 as old
from . import task14_actual_routes_scorer_v4 as driver
from . import task14_actual_routes_guard_v4 as prior_guard

ROOT, TASK, CONTRACT, CASES = old.ROOT, old.TASK, old.CONTRACT, old.CASES
snapshot, core, artifacts = old.snapshot, old.core, old.artifacts
PROTOCOL = 'task14.arkts.actual-route-envelope.v5'
INSTALLER = Path(__file__).with_name('task14_route_slot_v5.install.cjs')


def adapter_source():
    source = (old.DIRECTORY / 'Task14RealRoutesV4.adapter.js').read_text()
    source = old.replace_once(source, 'for (const source of config.productionSources || []) args.load(source.path);',
        "for (const source of config.productionSources || []) if (source.path.startsWith('entry/src/main/ets/features/')) args.load(source.path);")
    return old.replace_once(source, "'task14.arkts.actual-route-envelope.v4'", repr(PROTOCOL))


def expected_fixtures():
    return [{**item, 'sha256': hashlib.sha256(adapter_source().encode()).hexdigest()} if
        item['name'] == 'Task14RealRoutesV4.adapter.js' else item for item in old.expected_fixtures()]


def implementation():
    value = old.implementation()
    files = {item['path']: item for item in value['files']}
    for path in (Path(__file__), INSTALLER):
        files[str(path)] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': core.sha256(path)}
    records = [files[name] for name in sorted(files)]
    return {'protocol': PROTOCOL, 'files': records, 'sha256': artifacts.row_digest(records)}


def derive_builder(contract, epoch):
    return old.replace_once(old.derive_builder(contract, epoch),
        'require(' + json.dumps(str(old.DIRECTORY / 'install.cjs')) + ')',
        'require(' + json.dumps(str(INSTALLER)) + ')')


def _clone(function, **overrides):
    value = types.FunctionType(function.__code__, {**function.__globals__, **overrides},
        name=function.__name__, argdefs=function.__defaults__, closure=function.__closure__)
    value.__kwdefaults__ = function.__kwdefaults__
    return value


def prepare(**kwargs):
    return _clone(old.prepare, derive_builder=derive_builder, implementation=implementation,
        expected_fixtures=expected_fixtures, guard=types.SimpleNamespace(PROTOCOL=PROTOCOL))(**kwargs)


def envelope(bundle, contract):
    source = old.replace_once(inspect.getsource(prior_guard.envelope),
        'from . import task14_actual_routes_packaging_v4 as packaging',
        'from . import task14_actual_routes_slot_v5 as packaging')
    namespace = {**prior_guard.envelope.__globals__, 'PROTOCOL': PROTOCOL}
    exec(compile(source, str(Path(__file__)) + ':exact_envelope_derivation', 'exec'), namespace)
    return namespace['envelope'](bundle, contract)


def inspect_episode(episode, spec, profile):
    return _clone(prior_guard.inspect_episode, PROTOCOL=PROTOCOL)(episode, spec, profile)


REVIEWED_PROFILES = {}


def admit(bundle, contract, *, profile_key):
    data, episode, spec = envelope(bundle, contract)
    artifacts.require(profile_key in REVIEWED_PROFILES, 'No reviewed native v5 source/layout profile; NS')
    profile = json.loads(artifacts.bound(REVIEWED_PROFILES[profile_key]))
    artifacts.require(profile['sourceRootSha256'] == data['inputs']['rootSha256'] and
        profile['compiledProduction'] == data['build']['production'], 'Unknown actual source/layout binding')
    return {**inspect_episode(episode, spec, profile), 'rawEpisode': bundle, 'productionSources': data['build']['production']}


def assemble(*args, **kwargs):
    return _clone(driver.assemble, packaging=sys.modules[__name__], guard=sys.modules[__name__],
        _fallback=_clone(driver._fallback, guard=sys.modules[__name__]))(*args, **kwargs)


def evaluate(**kwargs):
    source = old.replace_once(inspect.getsource(driver.evaluate),
        "'scripts.runtime_semantics.task14_actual_routes_scorer_v4'",
        "'scripts.runtime_semantics.task14_actual_routes_slot_v5'")
    namespace = {**driver.evaluate.__globals__, 'packaging': sys.modules[__name__], 'assemble': assemble,
        '_fallback': _clone(driver._fallback, guard=sys.modules[__name__])}
    exec(compile(source, str(Path(__file__)) + ':exact_supervisor_derivation', 'exec'), namespace)
    return namespace['evaluate'](**kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path)
    args = parser.parse_args()
    if args.worker:
        _clone(driver._worker, packaging=sys.modules[__name__])(args.worker)
    else:
        parser.error('Use explicit released-slot caller; no implicit hardware execution')


if __name__ == '__main__':
    # Canonical module identity for scoped imports in admission.
    import importlib
    module = importlib.import_module('scripts.runtime_semantics.task14_actual_routes_slot_v5')
    module.main()
