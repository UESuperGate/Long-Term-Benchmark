"""V4 exact control exporter: suppress machine LFS filters, preserve v3 attempt."""
import os
from pathlib import Path

from . import task11_android_sdk_leaf_control_v3 as previous


def install():
    git = previous.git_command
    export = previous.export_control

    def raw_git(repository, args, target, clock, output):
        return git(repository, ['-c', 'filter.lfs.process=', '-c', 'filter.lfs.smudge=',
                               '-c', 'filter.lfs.required=false', *args], target, clock, output)

    def control(repository, commit, budget_root, output, clock):
        clock.check_work()
        stale = budget_root / 'original-control.tar.gz'
        receipt = budget_root / 'control-export.json'
        if stale.exists() and not receipt.exists():
            failed = budget_root / 'attempt1/original-control.failed.tar.gz'
            previous.v2.require(not failed.exists(), 'Never overwrite original failed archive')
            original = previous.record(stale)
            os.replace(stale, failed)
            previous.supervisor.atomic(failed.with_suffix('.preservation.json'), dict(
                original=original, retained=previous.record(failed), complete=False,
                recoverableClaimed=False, reason='machine LFS filter ran; export failed before raw blob verification'))
        value = export(repository, commit, budget_root, output, clock)
        previous.supervisor.atomic(output / 'control-export-caller-v4.json', dict(
            caller=previous.record(__file__), baseCaller=previous.record(previous.__file__),
            controlExport=previous.record(receipt), lfsFiltersDisabled=True))
        return value

    previous.git_command, previous.export_control = raw_git, control


if __name__ == '__main__':
    install()
    raise SystemExit(previous.main())
