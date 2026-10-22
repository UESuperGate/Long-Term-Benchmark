"""V7 preparation with coordinator's 8.8GiB gate on the SAME original clock."""
import shutil
import time

from . import task11_android_sdk_leaf_control_v7 as previous


def install():
    previous.install()
    base = previous.exporter.previous
    export = base.export_control

    def await_space(repository, commit, budget_root, output, clock):
        required = int(8.8 * 1024**3)
        marker = output / 'awaiting-8_8GiB.json'
        base.supervisor.atomic(marker, dict(state='waiting', requiredFreeBytes=required,
            controllerOnly=True, jvmStarted=False, locksHeld=False,
            sameOriginalDeadline=True, caller=base.record(__file__)))
        while shutil.disk_usage(output).free < required:
            clock.check_work()
            time.sleep(min(.5, max(.000001, clock.work_deadline - time.monotonic())))
        clock.check_work()
        base.supervisor.atomic(output / 'space-gate-acquired.json', dict(
            freeBytes=shutil.disk_usage(output).free, requiredFreeBytes=required,
            acquiredAtEpochMs=int(time.time()*1000), caller=base.record(__file__)))
        return export(repository, commit, budget_root, output, clock)

    base.export_control = await_space


if __name__ == '__main__':
    install()
    raise SystemExit(previous.exporter.previous.main())
