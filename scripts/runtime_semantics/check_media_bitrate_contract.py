#!/usr/bin/env python3
"""Execute the immutable Android helper to audit canonical input reachability.

This is deliberately not a semantic case or a replacement estimation algorithm.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from android_runner import ASSETS, Candidate, JAVA, ROOT, toolchain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    task = json.loads((ROOT / 'benchmark_tasks/10_media_upload_quality/task.json').read_text())
    source_path = 'libraries/androidutils/src/main/kotlin/io/element/android/libraries/androidutils/media/VideoCompressorHelper.kt'
    fixture = ASSETS / '10_media_upload_quality'
    logs = []
    result = {'status': 'not_run', 'canonicalSemanticScore': False}
    try:
        jars, compiler, _ = toolchain()
        cp = os.pathsep.join(map(str, jars))
        with tempfile.TemporaryDirectory(prefix='ltb-bitrate-audit-') as temporary:
            work = Path(temporary)
            candidate = Candidate(ROOT / '_sources/element-x-android', task, 'final', work)
            source = work / 'VideoCompressorHelper.kt'
            source.write_bytes(candidate.read(source_path))
            evaluator = [fixture / 'AndroidSize.kt', fixture / 'diagnostics/BitrateReachabilityProbe.kt']
            result['provenance'] = candidate.provenance
            result['provenance']['evaluatorSources'] = [
                {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in evaluator
            ]
            command = [str(JAVA), '-Xmx768m', '-cp', str(compiler) + os.pathsep + cp,
                       'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-no-stdlib', '-no-reflect',
                       '-jvm-target', '17', '-classpath', cp, '-d', str(work / 'classes'), str(source), *map(str, evaluator)]
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=120)
            logs.append(compiled.stdout + compiled.stderr)
            if compiled.returncode:
                raise RuntimeError('Unmodified production helper failed to compile')
            command = [str(JAVA), '-cp', str(work / 'classes') + os.pathsep + cp, 'runtime.BitrateReachabilityProbeKt']
            executed = subprocess.run(command, capture_output=True, text=True, timeout=60)
            logs.append(executed.stdout + executed.stderr)
            if executed.returncode:
                raise RuntimeError('Reachability probe failed')
            result.update(status='executed', observation=json.loads(executed.stdout), runtimeCommand=command)
    except Exception as error:
        result.update(status='infrastructure_failure', reason=f'{type(error).__name__}: {error}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    log = args.output.with_suffix('.log')
    log.write_text('\n'.join(logs))
    result['log'] = {'path': str(log.resolve()), 'sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'output': str(args.output)}))
    return 0 if result['status'] == 'executed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
