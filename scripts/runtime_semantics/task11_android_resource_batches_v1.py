"""Bounded packaging of aapt-generated R classes; no production source changes.

The SDK resource linker still assigns all IDs. Only generated package headers
are expanded in small batches. Consumed batch inputs are retained losslessly
before removal, after the synchronous javac process has exited.
"""
import hashlib
import io
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

from . import android_robolectric_ui_resources as original

ORIGINAL_COMPILE = original.compile_resources
BATCH_SIZE = 6


def compile_resources(candidate, config, work, java_home):
    from . import tasks16_17_native_controller_v3 as supervisor
    from .task11_android_sdk_leaf_preparation import record

    # The owned worker's TMPDIR is enforced by frozen v2 before this call.
    output = Path(tempfile.gettempdir()).resolve().parents[1]
    work = Path(work)
    required_packages = []
    old_processes = original.subprocess
    batches, archive_rows = [], []

    class Processes:
        def __getattr__(self, name):
            return getattr(old_processes, name)

        def run(self, command, **kwargs):
            command = list(map(str, command))
            if Path(command[0]).name == 'aapt2' and 'link' in command and '--extra-packages' in command:
                index = command.index('--extra-packages')
                required_packages.extend(command[index + 1].split(':'))
                reduced = command[:index] + command[index + 2:]
                return old_processes.run(reduced, **kwargs)
            if Path(command[0]).name != 'javac' or not required_packages:
                return old_processes.run(command, **kwargs)

            java = work / 'rendered-resources/java'
            template_path = java / 'runtime/evaluator/resources/R.java'
            template = template_path.read_text()
            pattern = r'^package runtime\.evaluator\.resources;$'
            if len(re.findall(pattern, template, re.M)) != 1:
                raise ValueError('Unknown real aapt R.java package header; refuse adaptation')
            # Compile the real root R.java and original BuildConfig inputs first.
            first = old_processes.run(command, **kwargs)
            if first.returncode:
                return first
            classes = command[command.index('-d') + 1]
            packages = sorted(set(required_packages) - {'runtime.evaluator.resources'})
            for offset in range(0, len(packages), BATCH_SIZE):
                inputs = []
                rows = []
                archive_path = output / ('resource-java-batch-%03d.tar.gz' % (offset // BATCH_SIZE))
                with tarfile.open(archive_path, 'w:gz') as archive:
                    for package in packages[offset:offset + BATCH_SIZE]:
                        if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', package):
                            raise ValueError('Invalid aapt extra-package name')
                        text = re.sub(pattern, 'package ' + package + ';', template, count=1, flags=re.M)
                        path = java / package.replace('.', '/') / 'R.java'
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(text)
                        data = path.read_bytes()
                        row = dict(relative=path.relative_to(java).as_posix(), **record(path))
                        entry = tarfile.TarInfo(row['relative'])
                        entry.size = len(data)
                        archive.addfile(entry, io.BytesIO(data))
                        rows.append(row)
                        inputs.append(path)
                restored = []
                with tarfile.open(archive_path, 'r:gz') as archive:
                    for entry in archive:
                        data = archive.extractfile(entry).read()
                        restored.append((entry.name, len(data), hashlib.sha256(data).hexdigest()))
                if restored != [(row['relative'], row['bytes'], row['sha256']) for row in rows]:
                    raise ValueError('Independent generated-source archive readback mismatch')
                archive_rows.append(dict(archive=record(archive_path), files=rows,
                                         independentlyDecodedHashesVerified=True))
                argv = [str(java_home / 'bin/javac'), '-d', classes, *map(str, inputs)]
                result = old_processes.run(argv, **kwargs)
                log = output / ('resource-java-batch-%03d.log' % (offset // BATCH_SIZE))
                log.write_text((result.stdout or '') + (result.stderr or ''))
                batches.append(dict(command=argv, exitCode=result.returncode,
                    inputs=[record(path) for path in inputs], log=record(log),
                    completedBeforeInputRemoval=result.returncode == 0))
                supervisor.atomic(output / 'generated-resource-batches.json', dict(
                    generatedBy='real aapt2 resource IDs; only package header expanded',
                    batchSize=BATCH_SIZE, batches=batches, sourceArchives=archive_rows))
                if result.returncode:
                    return result
                # Exact bytes already retained, no javac process still uses these
                # generated inputs. Original candidate/AAR inputs are never removed.
                for path in inputs:
                    path.unlink()
            return subprocess.CompletedProcess(command, 0, first.stdout, first.stderr)

    original.subprocess = Processes()
    try:
        return ORIGINAL_COMPILE(candidate, config, work, java_home)
    finally:
        original.subprocess = old_processes
        supervisor.atomic(output / 'generated-resource-input-archive.json', dict(
            archives=archive_rows, losslessOriginalGeneratedInputs=True,
            productionResourcesOrAssertionsChanged=False))
