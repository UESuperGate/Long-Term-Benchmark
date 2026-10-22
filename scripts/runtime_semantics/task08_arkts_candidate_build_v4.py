"""Offline private candidate builder: exact v3 entry checks plus non-mutating givens.

This only derives build/execute entrypoints. It does not launch or score a candidate.
"""
import hashlib
import json
from pathlib import Path
from scripts.runtime_semantics import task08_arkts_focus_build_v3 as previous

ROOT = previous.ROOT
FIXTURES = ROOT / 'state_tests/runtime/arkts/native/task08_candidate_given_v2'
INSTALLER = FIXTURES / 'install.cjs'


def derive(output):
    output = Path(output)
    result = previous.derive(output)
    builder = Path(result['buildEntrypoint'])
    old_installer = "const installer = path.join(root, 'state_tests/runtime/arkts/native/task08_strict/Task08StrictNativeUi.install.cjs');"
    new_installer = 'const installer = ' + json.dumps(str(INSTALLER)) + ';'
    builder.write_text(previous.previous.replace_once(builder.read_text(), old_installer, new_installer))
    gate = output / 'task08-entry-binding.v3.cjs'
    old_gate = "const installer = path.resolve(benchmarkRoot, 'state_tests/runtime/arkts/native/task08_strict/Task08StrictNativeUi.install.cjs');"
    gate.write_text(previous.previous.replace_once(gate.read_text(), old_gate, new_installer))
    result['schema'] = 'task08.candidate.build.v4.non-mutating-given'
    result['candidateGiven'] = {'derivedFocusWritesAllowed': False, 'unreachableGiven': 'not_scored',
                                'prefixFailureInferred': False, 'publicPromotion': False}
    result['originalInputs'].extend({'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                                    for p in (Path(__file__), INSTALLER,
                                              FIXTURES / 'Task08TimelineUI.js',
                                              FIXTURES / 'Task08StrictNativeUiAdapter.js'))
    result['generated'] = [{'path': str(p), 'bytes': p.stat().st_size,
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                           for p in sorted(output.glob('*.cjs'))]
    (output / 'derivation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
