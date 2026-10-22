"""Same v5 evaluator; retain exact 8GiB guard samples, never weaken its floor."""
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import tarfile
import time

from . import task11_android_sdk_leaf_worker_v5 as previous

v2 = previous.v2
MODULE = 'scripts.runtime_semantics.task11_android_sdk_leaf_worker_v6'


def require_floor(output):
    free = shutil.disk_usage(output).free
    with (Path(output) / 'worker-space-checks.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(epochMs=int(time.time()*1000), freeBytes=free,
            requiredBytes=8 * 1024**3, pid=os.getpid(), pgid=os.getpgrp(),
            selfMaxRssBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            childMaxRssBytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
            diagnosticOnly=True)) + '\n')
    v2.require(free >= 8 * 1024**3, '8GiB floor; heavy work refused')


def install():
    previous.install()
    implementation = v2.implementation
    v2.implementation = lambda: implementation() + [v2.fixture.record(__file__)]
    v2.require_floor = require_floor
    v2.MODULE = MODULE


def main():
    install()
    request = Path(sys.argv[sys.argv.index('--worker') + 1]).resolve()
    with tarfile.open(request.parent / 'evaluator-implementation.tar.gz', 'w:gz') as stream:
        for item in v2.implementation():
            path = Path(item['path'])
            stream.add(path, arcname=path.relative_to(v2.ROOT).as_posix(), recursive=False)
    return v2.main()


if __name__ == '__main__':
    raise SystemExit(main())
