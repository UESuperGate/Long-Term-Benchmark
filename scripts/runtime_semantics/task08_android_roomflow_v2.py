"""Staged explicit Task08 standalone entry; not integrated into central scoring."""
import importlib.util
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[2] / 'state_tests/runtime/android/08_threads/roomflow_v2/run.py'


def run(source, role, output, timeout=3600, *, execute_runtime=False, application_compile=None):
    spec = importlib.util.spec_from_file_location('task08_android_standalone_v2', ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(source, role, output, timeout, execute_runtime=execute_runtime,
                      application_compile=application_compile)
