"""Exact-version JVM evaluator plus bounded generated-resource packaging."""
from pathlib import Path
import sys
import tarfile

from . import task11_android_sdk_leaf_worker_v4 as previous
from . import task11_android_resource_batches_v1 as batches

v2 = previous.v2
MODULE = 'scripts.runtime_semantics.task11_android_sdk_leaf_worker_v5'


def install():
    previous.install()
    implementation = v2.implementation
    modules = v2.fixture.runtime_modules

    def bindings():
        return implementation() + [v2.fixture.record(__file__), v2.fixture.record(batches.__file__)]

    def runtime_modules():
        runtime, resources, mechanics, core = modules()
        resources.compile_resources = batches.compile_resources
        return runtime, resources, mechanics, core

    v2.implementation = bindings
    v2.fixture.runtime_modules = runtime_modules
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
