#!/usr/bin/env python3
"""Evaluator-owned live unknown-entry mutations; never edits a benchmark/model source."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.runtime_semantics.task10_repository_evidence import attach_control
from scripts.runtime_semantics.task10_arkts_closure_evidence import load_fixture
from scripts.runtime_semantics.task10_native_artifacts import read_native_artifact, retain_pair
from scripts.runtime_semantics.tasks10_11_runtime_evidence import record
from scripts.runtime_semantics.tasks10_11_formal_scorer import cleanup_evidence_artifacts, candidate_smoke


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError('Refusing earlier mutation smoke output')
    output = args.output_dir.resolve()
    output.mkdir(parents=True)
    fixture = load_fixture()
    relative = 'entry/src/main/ets/pages/Index.ets'
    expected = next(item['sha256'] for item in fixture['sourceFiles'] if item['path'] == relative)
    original = (args.source / relative).read_bytes()
    if hashlib.sha256(original).hexdigest() != expected:
        raise ValueError('Mutation fixture source is not the reviewed original page')
    contract = json.loads((ROOT / 'benchmark_tasks/10_media_upload_quality/transitions.json').read_text())
    started = time.monotonic()
    entries = []
    mutations = {
        'renamed-control': (".id('attachment_send')", ".id('renamed_upload_command')"),
        'extra-control': ('        Text(`Send state: ${this.sendState}`)',
                          "        Button('Unreviewed extra')\n          .id('unreviewed_extra')\n        Text(`Send state: ${this.sendState}`)"),
    }
    for name, (old, new) in mutations.items():
        target = output / name
        target.mkdir()
        artifacts = target / 'temporary'
        entry = {'mutation': name, 'role': 'agent', 'evaluatorMutationFixtureOnly': True,
                 'modelInvoked': False, 'passed': False}
        begin = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='ltb-task10-unknown-') as temporary:
            source = Path(temporary)
            shutil.copytree(args.source, source, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('.git', 'build', '.hvigor', 'oh_modules', 'node_modules'))
            text = original.decode()
            if text.count(old) != 1:
                raise ValueError('Mechanical evaluator mutation target is ambiguous')
            (source / relative).write_text(text.replace(old, new))
            before = candidate_smoke(source, 'arkts')
            entry['sourceInventory'] = before
            raw = target / 'raw.runtime.json'
            command = ['node', str(ROOT / 'scripts/runtime_semantics/task10_arkts_strict_runtime.cjs'),
                '--source', str(source), '--role', 'agent', '--platform', 'arkts', '--timeout', '3600',
                '--output', str(raw), '--artifact-root', str(artifacts)]
            entry['command'] = command
            try:
                completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=3600)
                (target / 'command.log').write_text(completed.stdout + completed.stderr)
                if completed.returncode or not raw.exists():
                    raise ValueError('Mutation runner did not produce a real complete initial probe')
                report = attach_control(json.loads(raw.read_text()), contract, artifacts, target / 'audit')
                if (report['semantic']['passed'], report['semantic']['failed'], report['semantic']['notScored']) != (0, 0, 9) or \
                        report['runtimeCompile'].get('passed') is not True or \
                        report['provenance'].get('entryEligibilityRejected') is not True:
                    raise ValueError('Unknown control was not a compile-positive/runtime-probed 0P/0F/9NS')
                for pair in [report['provenance']['unboundProbeArtifacts']['initialUI'],
                             report['provenance']['unboundProbeArtifacts']['build'],
                             *report['provenance']['unboundProbeArtifacts']['commandLogs']]:
                    read_native_artifact(pair)
                if candidate_smoke(source, 'arkts')['inventorySha256'] != before['inventorySha256']:
                    raise ValueError('Probe mutated its evaluator-only fixture source')
                accepted = target / 'not-scored.runtime.json'
                accepted.write_text(json.dumps(report, indent=2) + '\n')
                entry.update(passed=True, report=record(accepted), semantic={'passed': 0, 'failed': 0, 'notScored': 9})
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                entry['error'] = str(error)
                entry['failureRawArtifacts'] = [retain_pair(record(path), target / 'failure-raw')
                    for path in artifacts.rglob('*') if path.is_file() and path.suffix in {'.json', '.log'}]
            finally:
                cleanup = cleanup_evidence_artifacts(target, artifacts)
                (target / 'cleanup.json').write_text(json.dumps(cleanup, indent=2) + '\n')
                entry['cleanup'] = record(target / 'cleanup.json')
        entry.update(temporarySourceRemoved=not source.exists(), overallElapsedSeconds=round(time.monotonic() - begin, 3))
        entries.append(entry)
        (output / 'summary.json').write_text(json.dumps({'mutations': entries,
            'realModelPatchModified': False, 'productionSourceModified': False,
            'overallElapsedSeconds': round(time.monotonic() - started, 3)}, indent=2) + '\n')
        print(json.dumps({key: entry.get(key) for key in ('mutation', 'passed', 'semantic', 'error')}), flush=True)
    return 0 if all(entry['passed'] for entry in entries) else 1


if __name__ == '__main__':
    raise SystemExit(main())
