"""Record Task11 temporary resource JAR hashes before the compiler deletes them."""
from contextlib import contextmanager
from pathlib import Path

import android_robolectric
from task10_11_android_strict_common import record, write_json


@contextmanager
def record_slice_resources():
    original_run = android_robolectric.run_slice

    def run_slice(*args, **kwargs):
        output = Path(args[5] if len(args) > 5 else kwargs["output"])
        manifest = output.with_suffix(".resource-artifacts.json")
        original_compile = android_robolectric.compile_resources
        artifacts = []

        def capture(*compile_args, **compile_kwargs):
            artifact = original_compile(*compile_args, **compile_kwargs)
            if artifact:
                artifacts.append(record(Path(artifact)))
                write_json(manifest, {"stage": "hash_recorded_before_temporary_directory_deletion",
                                      "binaryArtifacts": artifacts})
            return artifact

        android_robolectric.compile_resources = capture
        try:
            result = original_run(*args, **kwargs)
            if artifacts:
                result["resourceArtifactAudit"] = {"manifest": record(manifest), "binaryArtifacts": artifacts,
                    "hashesRecordedBeforeDelete": True,
                    "binaryArtifactsDeleted": all(not Path(item["path"]).exists() for item in artifacts)}
                write_json(output, result)
            return result
        finally:
            android_robolectric.compile_resources = original_compile

    android_robolectric.run_slice = run_slice
    try:
        yield
    finally:
        android_robolectric.run_slice = original_run
