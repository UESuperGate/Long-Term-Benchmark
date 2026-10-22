"""One next-stage attempt only after 8.55GiB; original repair end never renewed."""
import argparse
from pathlib import Path
import shutil

from . import task11_android_sdk_leaf_control_v9 as previous
from . import task11_android_sdk_leaf_worker_v6 as worker


def install():
    # V9 installs v5 and the reviewed parent protocol. Install the v6 telemetry
    # around that evaluator without installing v5 twice (which nests resolvers).
    base = previous.install()
    implementation = worker.v2.implementation
    worker.v2.implementation = lambda: implementation() + [worker.v2.fixture.record(worker.__file__)]
    worker.v2.require_floor = worker.require_floor
    worker.v2.MODULE = worker.MODULE
    export, cleanup = base.export_control, base.cleanup

    def headroom(repository, commit, budget_root, output, clock):
        clock.check_work()
        free = shutil.disk_usage(output).free
        base.v2.require(free >= int(8.55 * 1024**3), '8.55GiB next-stage entry headroom unavailable')
        base.supervisor.atomic(output / 'next-stage-headroom.json', dict(
            actualFreeBytes=free, entryFloorGiB=8.55, hardRuntimeFloorGiB=8,
            caller=base.record(__file__), originalBudgetReset=False))
        return export(repository, commit, budget_root, output, clock)

    def allocated_cleanup(output, deadline):
        groups = {}
        seen = set()
        for path in sorted((output / 'owned-work').rglob('*')):
            base.v2.remaining(deadline)
            if path.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
            if (stat.st_dev, stat.st_ino) in seen:
                continue
            seen.add((stat.st_dev, stat.st_ino))
            kind = 'snapshot' if '/snapshot/' in str(path) else 'resource' if '/rendered-resources/' in str(path) else 'other'
            row = groups.setdefault(kind, dict(files=0, logicalBytes=0, statReportedBlockBytes=0))
            row['files'] += 1
            row['logicalBytes'] += stat.st_size
            row['statReportedBlockBytes'] += stat.st_blocks * 512
        base.supervisor.atomic(output / 'owned-allocation-before-cleanup.json', dict(
            groups=groups, freeBytes=shutil.disk_usage(output).free,
            scope='owned-work only after groupGone, before cleanup',
            sharedApfsExtentsOrExternalSwapNotAttributed=True, diagnosticOnly=True))
        return cleanup(output, deadline)

    base.export_control, base.cleanup = headroom, allocated_cleanup
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--budget-root', type=Path, required=True)
    parser.add_argument('--original-start-epoch-ms', type=int, required=True)
    args = parser.parse_args()
    base = install()
    result = base.run(args.repository, args.commit, args.budget_root,
                      'attempt7', args.original_start_epoch_ms)
    return 0 if result and result['runtimeCompile']['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
