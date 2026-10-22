"""Private fresh-control consumer: only the legacy timeout equality is versioned."""
import hashlib
import importlib.util
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / 'scripts/verify_task08_arkts_strict.py'
ANCHOR = 'strict["timeoutSeconds"] == 3600'


def consumer(build_budgets):
    if set(build_budgets) != {'base', 'final'} or any(type(v) is not int or not 1 <= v <= 3600 for v in build_budgets.values()):
        raise ValueError('Exact per-command supervisor budgets required for both fresh poles')
    source = LEGACY.read_text()
    if source.count(ANCHOR) != 1:
        raise ValueError('Historical verifier shape changed; refuse rather than weaken assertions')
    replacement = 'strict["timeoutSeconds"] == SUPERVISED_BUILD_BUDGETS[role]'
    derived = source.replace(ANCHOR, replacement)
    module = types.ModuleType('task08_fresh_supervised_consumer_v1')
    module.__file__ = str(LEGACY)
    module.SUPERVISED_BUILD_BUDGETS = dict(build_budgets)
    exec(compile(derived, str(LEGACY) + '.supervised.v1', 'exec'), module.__dict__)
    module.supervisedDerivation = {'legacySha256': hashlib.sha256(source.encode()).hexdigest(),
                                  'derivedSha256': hashlib.sha256(derived.encode()).hexdigest(),
                                  'onlyReplacement': {'before': ANCHOR, 'after': replacement},
                                  'originalReportsChanged': False, 'semanticAssertionsChanged': False}
    return module


def verify(output, commands):
    output = Path(output)
    budgets = {}
    for role in ('base', 'final'):
        stages = [c for c in commands if c['role'] == role and c['stage'] == 'build']
        if len(stages) != 1 or stages[0]['exitCode'] != 0:
            raise ValueError('Missing unique completed build budget: ' + role)
        budgets[role] = stages[0]['timeoutSeconds']
    checker = consumer(budgets)
    proof = checker.verify_matrix(output / 'base/build/device-build-report.json', output / 'base/execute/device-execution.json',
                                  output / 'final/build/device-build-report.json', output / 'final/execute/device-execution.json')
    for role in ('base', 'final'):
        execution = json.loads((output / role / 'execute/device-execution.json').read_text())
        lease = execution.get('task08CanonicalLease', {})
        expected = '/tmp/ltb-arkts-device-' + hashlib.sha256(execution['serial'].encode()).hexdigest()[:16]
        if lease.get('path') != expected or lease.get('acquired') is not True or execution['cleanup'].get('canonicalLeaseReleased') is not True:
            raise ValueError('Canonical owned lease acquisition/release evidence incomplete')
        if execution['cleanup'].get('canonicalLeasePath') != expected or any(k.endswith('Error') or k == 'error' for k in execution['cleanup']):
            raise ValueError('Device cleanup incomplete; no semantic admission')
        receipts = list((output / role / 'build').glob('temporary-cleanup-*.json'))
        if len(receipts) != 1:
            raise ValueError('Missing unique hash-before-delete intermediate receipt')
        cleanup = json.loads(receipts[0].read_text())
        if cleanup.get('hashesRecordedBeforeRemoval') is not True or cleanup.get('removedWorkspace') is not True:
            raise ValueError('Temporary build cleanup incomplete')
    return dict(proof, supervisedVerifier=checker.supervisedDerivation)
