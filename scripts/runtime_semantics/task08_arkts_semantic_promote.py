"""Publish Task08 replay evidence only after strict controls and candidate validation."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_task08_arkts_strict as verifier

spec = importlib.util.spec_from_file_location('task08_replay_io', Path(__file__).with_name('task08_arkts_semantic_replay.py'))
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)


def promote(controls, candidate, output):
    output.mkdir(parents=True, exist_ok=False)
    builds = [controls / f'{role}/build/device-build-report.json' for role in ('base', 'final')]
    executions = [controls / f'{role}/execute/device-execution.json' for role in ('base', 'final')]
    agent_build = candidate / 'agent/build/device-build-report.json'
    agent_execution = candidate / 'agent/execute/device-execution.json'
    calibration = verifier.verify_matrix(builds[0], executions[0], builds[1], executions[1])
    scored = verifier.verify_candidate(agent_build, agent_execution, candidate / 'candidate-reconstruction.json')
    data = [io.load(path) for path in builds + [agent_build]]
    for build in data[1:]:
        for field in ('canonicalContract', 'wrapper', 'sharedBuilder', 'installer'):
            verifier.require(build['task08Strict'][field]['sha256'] == data[0]['task08Strict'][field]['sha256'],
                             'Controls and candidate used different build/contract inputs: ' + field)
        verifier.require({entry['file']: entry['sha256'] for entry in build['nativeUIObserver']['fixtures']} ==
                         {entry['file']: entry['sha256'] for entry in data[0]['nativeUIObserver']['fixtures']},
                         'Controls and candidate used different native semantic fixtures')
    report = copy.deepcopy(io.load(candidate / 'arkts_08_threads_agent.semantic-replay.json'))
    original = io.load(io.OLD_REPORT)
    verifier.require(report['compile'] == original['compile'] and report['codeGeneration'] == original['codeGeneration'],
                     'Application compile/code-generation metric was overwritten')
    verifier.require(report['semantic']['cases'] == io.load(agent_execution)['rows'], 'Candidate rows changed during assembly')
    for directory in (controls, candidate):
        cleanup = io.load(directory / 'binary-cleanup.json')
        verifier.require(cleanup['hashesRecordedBeforeRemoval'] and not cleanup['binariesRetained'] and
                         cleanup['remaining'] == [] and not any(file.is_file() and file.suffix in io.BINARY_SUFFIXES
                                                               for file in directory.rglob('*')), 'Binary cleanup incomplete')
    io.write(output / 'independent-controls.json', calibration)
    io.write(output / 'independent-candidate.json', scored)
    tests = [sys.executable, '-m', 'unittest', 'scripts.test_verify_task08_arkts_strict',
             'scripts.runtime_semantics.test_task08_arkts_entry_evidence', '-v']
    node_tests = ['node', '--test', 'scripts/runtime_semantics/task08_arkts_strict_execute.test.cjs',
                  'state_tests/runtime/arkts/native/task08_strict/Task08StrictNativeUi.test.cjs',
                  'state_tests/runtime/arkts/native/task08_strict/Task08TimelineUI.test.cjs']
    for name, command in [('python-tests.log', tests), ('node-tests.log', node_tests)]:
        with (output / name).open('x') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    report['diagnostics'].update(publishable=report['compile']['passed'] is True, adapter='ready',
        independentVerifier=True, benchmarkCompilePreserved=True, noSourceObserverFallback=True,
        calibration={'base': calibration['base'], 'final': calibration['final'],
                     'evidence': str(controls), 'candidateEvidence': str(candidate),
                     'nativeSemanticFixturesIdentical': True,
                     'transportOnlyDifference': 'Task08 aa-test subprocess wait increased from 150s to at most 600s, capped by the scorer deadline'})
    report['semantic']['counts'] = scored['counts']
    report['provenance']['calibrationArtifacts'] = [io.record(path) for path in builds + executions]
    report['provenance']['candidateArtifacts'] = [io.record(path) for path in
        (agent_build, agent_execution, candidate / 'candidate-reconstruction.json')]
    report['provenance']['binaryCleanup'] = [io.record(directory / 'binary-cleanup.json') for directory in (controls, candidate)]
    io.write(output / 'arkts_08_threads_agent.json', report)
    evidence_files = sorted({file for directory in (controls, candidate) for file in directory.rglob('*') if file.is_file()})
    source_files = sorted({Path(item['file']) for item in data[0]['nativeUIObserver']['fixtures']} |
        {Path(item['path']) if Path(item['path']).is_absolute() else ROOT / item['path']
         for item in data[0]['task08Strict'].values() if isinstance(item, dict) and item.get('path')} |
        {Path(__file__), Path(verifier.__file__), Path(io.__file__),
         Path(__file__).with_name('task08_arkts_strict_execute.cjs'), Path(__file__).with_name('task08_arkts_entry_evidence.py')})
    io.write(output / 'evidence-index.json', {'binariesRetained': False,
        'files': [io.record(path) for path in evidence_files], 'evaluatorSources': [io.record(path) for path in source_files]})
    print(json.dumps({'base': calibration['base'], 'final': calibration['final'], 'agent': scored['counts'],
                      'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controls', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    promote(args.controls.resolve(), args.candidate.resolve(), args.output.resolve())
