"""Versioned evaluator JVM wiring only; frozen v2 process protocol unchanged."""
from pathlib import Path
import sys
import tarfile

from . import task11_android_sdk_leaf_launcher_v2 as v2

MODULE = 'scripts.runtime_semantics.task11_android_sdk_leaf_worker_v3'


def install():
    original_implementation = v2.implementation
    modules = v2.fixture.runtime_modules

    def implementation():
        return original_implementation() + [v2.fixture.record(__file__)]

    def runtime_modules():
        runtime, resources, mechanics, core = modules()
        dependencies = runtime.candidate_dependencies

        def jvm_dependencies(candidate, config):
            value = dependencies(candidate, config)
            selected = []
            audit = []
            for coordinate in value['dependencies']:
                actual = list(coordinate)
                if actual[:2] == ['org.jetbrains.kotlinx', 'kotlinx-serialization-json']:
                    actual[1] = 'kotlinx-serialization-json-jvm'
                if actual[:2] == ['io.mockk', 'mockk']:
                    # Evaluator-owned mocking tool, not a production dependency.
                    actual[1:3] = ['mockk-jvm', '1.14.0']
                if actual != coordinate:
                    audit.append(dict(declared=coordinate, evaluatorJvm=actual))
                selected.append(actual)
            candidate.provenance['evaluatorJvmVariantSelection'] = audit
            return dict(value, dependencies=selected)

        runtime.candidate_dependencies = jvm_dependencies
        return runtime, resources, mechanics, core

    v2.implementation = implementation
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
