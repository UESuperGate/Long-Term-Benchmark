"""Released 8.35GiB entry, unchanged 8GiB runtime floor, original repair cap."""
import argparse
from pathlib import Path
import shutil
import subprocess
import time

from . import task11_android_sdk_leaf_control_v7 as previous


def install():
    previous.install()
    base = previous.exporter.previous
    export = base.export_control
    original_wait = base.supervisor.wait_leader
    failed_floor = False

    def wait_leader(process, deadline):
        nonlocal failed_floor
        while True:
            # On a storage error, let the SAME supervisor revoke first and use
            # its existing stop/reap/cleanup path without another floor exception.
            if not failed_floor and shutil.disk_usage(base.v2.ROOT).free < 8 * 1024**3:
                failed_floor = True
                raise OSError('8GiB hard storage floor while owned child was running')
            try:
                return original_wait(process, min(deadline, time.monotonic() + .2))
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    raise

    def released_export(repository, commit, budget_root, output, clock):
        clock.check_work()
        free = shutil.disk_usage(output).free
        base.v2.require(free >= int(8.35 * 1024**3), 'Coordinator 8.35GiB entry headroom unavailable')
        base.supervisor.atomic(output / 'released-space-entry.json', dict(
            actualStartFreeBytes=free, actualStartFreeGiB=free / 1024**3,
            coordinatorEntryFloorGiB=8.35, hardRuntimeFloorGiB=8,
            continuousParentCheck=True, caller=base.record(__file__),
            originalDeadlineEpochMs=1792529889000, originalBudgetReset=False))
        return export(repository, commit, budget_root, output, clock)

    base.supervisor.wait_leader = wait_leader
    base.export_control = released_export
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--budget-root', type=Path, required=True)
    parser.add_argument('--original-start-epoch-ms', type=int, required=True)
    args = parser.parse_args()
    base = install()
    # attempt6's original queued-controller receipt is preserved without edits.
    result = base.run(args.repository, args.commit, args.budget_root,
                      'attempt6/actual-v1', args.original_start_epoch_ms)
    return 0 if result and result['runtimeCompile']['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
