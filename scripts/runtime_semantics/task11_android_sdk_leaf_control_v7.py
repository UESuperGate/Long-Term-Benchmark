"""Original repair deadline, exact variants, bounded R input/diagnostic retention."""
import tarfile

from . import task11_android_sdk_leaf_control_v4 as exporter
from . import task11_android_sdk_leaf_worker_v5 as worker


def install():
    exporter.install()
    worker.install()
    previous_cleanup = exporter.previous.cleanup

    def cleanup(output, deadline):
        work = output / 'owned-work'
        records = []
        archive = output / 'execution-diagnostics.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            if work.exists():
                for path in sorted(work.rglob('*')):
                    exporter.previous.v2.remaining(deadline)
                    if path.is_file() and not path.is_symlink() and path.suffix in ('.log', '.pom', '.txt', '.properties'):
                        records.append(exporter.previous.record(path))
                        stream.add(path, arcname=path.relative_to(work).as_posix(), recursive=False)
        exporter.previous.supervisor.atomic(output / 'execution-diagnostics.json', dict(
            archive=exporter.previous.record(archive), files=records))
        return previous_cleanup(output, deadline)

    exporter.previous.cleanup = cleanup


if __name__ == '__main__':
    install()
    raise SystemExit(exporter.previous.main())
