"""Offline immutable task17 empty-list Presenter/View slice, never a full app build."""
import argparse
import copy
import fcntl
import json
from pathlib import Path
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / "scripts/runtime_semantics"))
import android_robolectric
import android_robolectric_dependencies
from android_robolectric_ui_resources import compile_resources
from android_supplemental import file_record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    output = args.output.resolve()
    if any(p.exists() for p in (output, output.with_suffix(".log"), output.with_suffix(".config.json"), output.with_suffix(""))):
        raise FileExistsError("Evidence output must be new")
    output.parent.mkdir(parents=True, exist_ok=True)
    template = ROOT / "experiment_results/runtime_transition_20261019/android_base_followup/task12-presenter/base-v4.config.json"
    config = json.loads(template.read_text())
    prefix = "features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/"
    config.update(scope="original_pinned_provider_factory_presenter_view_empty_success", testClass="runtime.PinnedEmptyUiTest",
                  keys=["empty_success"], entrypoints=[prefix + path for path in (
                      "pinned/list/PinnedMessagesListView.kt", "pinned/list/PinnedMessagesListPresenter.kt",
                      "pinned/DefaultIsPinnedMessagesFeatureEnabled.kt")],
                  evaluatorSources=[str(HERE / "PinnedEmptyUiTest.kt"), str(HERE / "Annotations.kt"),
                                    str(HERE.parents[1] / "common/Anvil.kt")])
    config["resources"] = [item for item in config["resources"] if item["package"] in (
        "io.element.android.libraries.ui.strings", "io.element.android.libraries.designsystem", "io.element.android.libraries.matrix.ui")]
    config["dependencies"] = [item for item in config["dependencies"] if item[0] != "io.coil-kt.coil3"]
    # Preserve the old source's windowInsets/ripple APIs without rewriting code.
    for item in config["dependencies"]:
        if item[0] == "androidx.compose.material":
            item[2] = "1.6.8"
        elif item[0] == "androidx.compose.material3":
            item[2] = "1.2.1"
    config["alignedGroups"] += [["androidx.compose.material", "1.6.8"], ["androidx.compose.material3", "1.2.1"]]
    config["dependencyCatalog"]["libraries"] += ["coil_compose", "jsoup", "sigpwned_emoji4j",
        "androidx_constraintlayout_compose", "matrix_richtexteditor", "matrix_richtexteditor_compose", "androidx_recyclerview"]
    config["dependencies"].append(["androidx.media3", "media3-common", "1.4.1"])
    for item in config["resources"]:
        if item["package"] == "io.element.android.libraries.designsystem":
            item["files"] += [f"libraries/designsystem/src/main/res/drawable/{name}.xml"
                              for name in ("pin", "ic_developer_options", "ic_winner")]
    config["resources"] += [
        {"package": "io.element.android.features.messages.impl", "files": ["features/messages/impl/src/main/res/values/localazy.xml"]},
        {"package": "io.element.android.features.location.api", "files": ["features/location/api/src/main/res/drawable/blurred_map.png",
            "_evaluator_generated/res/values/location_defaults.xml"]}]
    configuration = output.with_suffix(".config.json")
    configuration.write_text(json.dumps(config, indent=2) + "\n")
    contract_path = ROOT / "benchmark_tasks/17_pinned_messages/transitions.json"
    contract = json.loads(contract_path.read_text())
    defaults = HERE / "res/values/location_defaults.xml"

    def resources(candidate, configuration, work, java_home):
        read_original = candidate.read
        # Only evaluator-generated build metadata is supplied here. Every
        # candidate source/resource still comes unchanged from its immutable tree.
        candidate.read = lambda path: defaults.read_bytes() if path == "_evaluator_generated/res/values/location_defaults.xml" else read_original(path)
        try:
            read_original("features/location/api/build.gradle.kts")
            return compile_resources(candidate, configuration, work, java_home)
        finally:
            candidate.read = read_original

    android_robolectric.compile_resources = resources
    closure_original = android_robolectric.closure
    android_robolectric.closure = lambda repository, ref, seeds: closure_original(repository, ref, seeds) + [
        "appconfig/src/main/kotlin/io/element/android/appconfig/TimelineConfig.kt",
        "appconfig/src/main/kotlin/io/element/android/appconfig/OnBoardingConfig.kt"]
    prepare_original = android_robolectric.prepare
    metadata_records = []

    def seed_metadata(repository):
        seed_original(repository)
        coordinates = [("androidx.compose.material", name, "1.6.8") for name in
                       ("material", "material-ripple", "material-icons-core")]
        coordinates.append(("androidx.compose.material3", "material3", "1.2.1"))
        for group, name, version in coordinates:
            relative = Path(group.replace(".", "/")) / name / version / f"{name}-{version}.jar"
            target = HERE / ".dependencies" / relative
            if not target.exists():
                with urllib.request.urlopen("https://dl.google.com/dl/android/maven2/" + relative.as_posix(), timeout=20) as response:
                    data = response.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024 or not data.startswith(b"PK"):
                    raise ValueError("Refusing oversized/non-JAR Compose metadata")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            metadata_records.append(file_record(target))
            linked = repository / relative
            if not linked.exists():
                linked.parent.mkdir(parents=True, exist_ok=True)
                linked.symlink_to(target)

    seed_original = android_robolectric_dependencies.seed_repository
    android_robolectric_dependencies.seed_repository = seed_metadata

    def prepare(configuration, work):
        environment = prepare_original(configuration, work)
        environment["jvmArgs"] += [f"-Druntime.rendered.output={output.with_suffix('')}", f"-Druntime.contract.path={contract_path}"]
        return environment

    android_robolectric.prepare = prepare
    with (ROOT / "state_tests/runtime/android/.build.lock").open("a") as lock:
        deadline = time.monotonic() + args.timeout
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Shared build lock held; no competing build started")
                time.sleep(0.5)
        result = android_robolectric.run_slice("17_pinned_messages", "final", ROOT / "_sources/element-x-android",
                                               HERE, configuration, output, args.timeout)
    raw = {row["key"]: row for row in result.get("observations", [])}
    rows = []
    for case in contract["cases"]:
        row = copy.deepcopy(raw.get(case["key"], {"status": "not_scored", "observed": None, "checkpoints": [],
            "invariantChecks": [], "reason": "Not executed in this independent empty-list slice."}))
        row.update(caseId=case["caseId"], key=case["key"], traceDigest=case["traceDigest"])
        rows.append(row)
    result.update(platform="android", observationMode="runtime_state_transition", canonicalSemanticScore=False,
        executionEnvironment="host_jvm_robolectric_rendered_compose", semantic={"cases": rows},
        compile={"passed": None, "status": "not_run", "scope": "android_application"},
        contractSha256=file_record(contract_path)["sha256"])
    result.setdefault("provenance", {}).update(canonicalContract=file_record(contract_path), renderedRunner=file_record(__file__),
        packagingSources=[file_record(configuration), file_record(template), file_record(defaults),
                          file_record(ROOT / "scripts/runtime_semantics/android_robolectric_ui_resources.py")],
        supplementalMetadataArtifacts=metadata_records)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"raw": {key: row["status"] for key, row in raw.items()}, "error": result.get("error"), "output": str(output)}))


if __name__ == "__main__":
    main()
