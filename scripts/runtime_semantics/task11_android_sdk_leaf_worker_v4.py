"""Exact-version JVM variants; allow official small dependency resolution."""
from pathlib import Path
import sys
import tarfile

from . import task11_android_sdk_leaf_worker_v3 as previous

v2 = previous.v2
MODULE = 'scripts.runtime_semantics.task11_android_sdk_leaf_worker_v4'


def install():
    previous.install()
    implementation = v2.implementation
    modules = v2.fixture.runtime_modules

    def bindings():
        return implementation() + [v2.fixture.record(__file__)]

    def runtime_modules():
        runtime, resources, mechanics, core = modules()
        resolve = runtime.candidate_dependencies

        def exact_jvm(candidate, config):
            value = resolve(candidate, config)
            selected = []
            for coordinate in value['dependencies']:
                actual = list(coordinate)
                if actual[:2] == ['io.mockk', 'mockk-jvm']:
                    # Immutable candidate test-library version, not cached 1.14.0.
                    actual[2] = candidate.provenance['catalogDependencies']['test_mockk'][2]
                selected.append(actual)
            audit = candidate.provenance.get('evaluatorJvmVariantSelection', [])
            for item in audit:
                item['evaluatorJvm'][2] = item['declared'][2]
            candidate.provenance['evaluatorDependencyPolicy'] = dict(
                exactDeclaredVersions=True, productionSdkVersionUnchanged=True,
                officialPomRepositoriesAllowed=True, variantOnly=True)
            return dict(value, dependencies=selected, offlineDependencies=False)

        runtime.candidate_dependencies = exact_jvm
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
