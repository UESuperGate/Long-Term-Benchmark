#!/usr/bin/env python3
"""Live multi-slice Android strict runtime evaluator for Task13 revision 5."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import time

try:
    from . import android_robolectric, android_runner
    from .android_robolectric_ui_resources import compile_resources
    from . import task12_13_formal_core as formal
    from . import task12_13_runtime_support as support
    from . import task13_android_entry_validation as entry_validation
    from .task12_13_android_slice import run_slice
    from .task14_15_formal_core import bounded_file_lock, filesystem_closure
except ImportError:
    import android_robolectric
    import android_runner
    from android_robolectric_ui_resources import compile_resources
    import task12_13_formal_core as formal
    import task12_13_runtime_support as support
    import task13_android_entry_validation as entry_validation
    from task12_13_android_slice import run_slice
    from task14_15_formal_core import bounded_file_lock, filesystem_closure


ROOT = formal.ROOT
TASK_ID = "13_user_verification"
ASSETS = ROOT / "state_tests/runtime/android/13_user_verification"
BASE = ASSETS / "revision5_base"
FINAL = ASSETS / "revision5_final"
ROOM_MEMBER = ASSETS / "room_member"
USER_REQUEST_INVARIANT = "the active request is type user for @alice:example.org throughout the transition"
VIOLATION_UI_INVARIANT = (
    "verification-violation UI offers withdrawal instead of starting a new verification request"
)


def _prepare(source: Path, adapter: Path, evaluator: Path, target: Path,
             *, keys: list[str] | None = None, test_class: str | None = None,
             entrypoints: list[str] | None = None) -> Path:
    config = json.loads(adapter.read_text(encoding="utf-8"))
    if keys is not None:
        config["keys"] = keys
    if test_class is not None:
        config["testClass"] = test_class
    if entrypoints is not None:
        config["entrypoints"] = entrypoints
    config["dependencyCatalog"] = {
        "path": "gradle/libs.versions.toml", "libraries": ["androidx_core", "androidx_corektx"]
    }
    config["evaluatorSources"] = [str(evaluator.resolve())]
    catalog = (source / "gradle/libs.versions.toml").read_text(encoding="utf-8")
    match = re.search(r'^coil\s*=\s*"([^"]+)"', catalog, re.MULTILINE)
    if not match:
        raise ValueError("Candidate version catalog does not define versions.coil")
    coil = match.group(1)
    config["dependencies"] = [
        item[:2] + [coil] + item[3:] if item[0] == "io.coil-kt.coil3" else item
        for item in config.get("dependencies", [])
    ]
    config["alignedGroups"] = [
        [group, coil if group == "io.coil-kt.coil3" else version]
        for group, version in config.get("alignedGroups", [])
    ]
    config["sourceClosure"] = False
    config["sources"] = filesystem_closure(source, config["entrypoints"])
    resources = []
    modules = sorted({item.split("/src/main/")[0] for item in config["sources"]})
    for module in modules:
        resource_root = source / module / "src/main/res"
        gradle = source / module / "build.gradle.kts"
        if not resource_root.is_dir() or not gradle.is_file():
            continue
        match = re.search(r'namespace\s*=\s*"([^"]+)"', gradle.read_text(encoding="utf-8"))
        if not match:
            continue
        files = [
            path.relative_to(source).as_posix()
            for path in sorted(resource_root.rglob("*"))
            if path.is_file() and ("values" in path.relative_to(resource_root).parts or
                                   "drawable" in path.relative_to(resource_root).parts)
        ]
        if files:
            resources.append({"package": match.group(1), "files": files})
    config["resources"] = resources
    formal.write(target, config)
    return target


def _run_slice(source: Path, role: str, adapter_dir: Path, config: Path,
               output: Path, deadline: float) -> dict:
    report = run_slice(
        TASK_ID, role, source, adapter_dir, config, output,
        deadline,
    )
    if report.get("runtimeCompile", {}).get("status") != "passed":
        raise RuntimeError(f"Task13 slice {output.stem} did not compile: {report.get('error')}")
    return report


def _row(report: dict, key: str) -> dict:
    rows = report.get("observations") or report.get("semantic", {}).get("cases", [])
    value = next((copy.deepcopy(item) for item in rows if item.get("key") == key), None)
    if value is None:
        raise RuntimeError(f"Task13 live slice omitted {key}")
    return value


def _base_rows(contract: dict, entry: dict, violation: dict, entry_path: Path) -> list[dict]:
    rows = []
    for spec in contract["cases"][:9]:
        row = entry_validation.entry_row(spec, _row(entry, spec["key"]), entry_path)
        rows.append(row)
    spec = contract["cases"][9]
    row = _row(violation, spec["key"])
    if row.get("status") not in {"pass", "fail"}:
        raise RuntimeError("Task13 base violation slice did not produce a semantic verdict")
    row.update(caseId=spec["caseId"], key=spec["key"], traceDigest=spec["traceDigest"],
               transitionExecuted=True)
    names = {item.get("description", item.get("invariant")) for item in row.get("invariantChecks", [])}
    if VIOLATION_UI_INVARIANT not in names:
        observed = row.get("observed", {})
        passed = (observed.get("withdrawVerificationActionVisible") is True and
                  observed.get("verifyActionVisible") is False and
                  observed.get("profileWarningVisible") is True)
        row.setdefault("invariantChecks", []).append({
            "description": VIOLATION_UI_INVARIANT,
            "passed": passed,
            "status": "pass" if passed else "fail",
            "observed": copy.deepcopy(observed),
        })
    rows.append(row)
    return rows


def _final_rows(contract: dict, route: dict, domain: dict, completion: dict,
                violation: dict) -> list[dict]:
    reports = {case["key"]: domain for case in contract["cases"]}
    reports["profile_routes_user_request"] = route
    reports["finish_clears_violation"] = completion
    reports["identity_violation_surfaces"] = violation
    route_row = _row(route, "profile_routes_user_request")
    request_evidence = {
        "routeObserved": route_row.get("observed"),
        "conjunction": "fresh route slice plus fresh state-machine slice from the same candidate",
    }
    result = []
    for spec in contract["cases"]:
        row = _row(reports[spec["key"]], spec["key"])
        row.update(caseId=spec["caseId"], key=spec["key"], traceDigest=spec["traceDigest"],
                   transitionExecuted=True)
        names = {item.get("description", item.get("invariant")) for item in row.get("invariantChecks", [])}
        if spec["key"] == "finish_clears_violation" and USER_REQUEST_INVARIANT not in names:
            before = next((point["state"] for point in row.get("checkpoints", [])
                           if point.get("name") == "before_canonical_event"), {})
            request_evidence["completionBefore"] = copy.deepcopy(before)
            passed = (route_row.get("status") == "pass" and
                      route_row.get("observed", {}).get("request") ==
                      {"type": "user", "userId": "@alice:example.org"} and
                      before.get("request") == "User(userId=@alice:example.org)")
            row.setdefault("invariantChecks", []).append({
                "description": USER_REQUEST_INVARIANT, "passed": passed,
                "status": "pass" if passed else "fail",
                "observed": copy.deepcopy(request_evidence),
            })
        result.append(row)
    return result


def _canonical_rows(contract: dict, rows: list[dict], role: str) -> list[dict]:
    normalized = support.canonical_rows(
        contract,
        rows,
        role=role,
        base_entry_failure=role == "base",
    )
    for row, original in zip(normalized, rows):
        if original.get("entryFailureEvidence", {}).get("policyId") == entry_validation.POLICY_ID:
            row["entryFailureEvidence"] = original["entryFailureEvidence"]
    return normalized


def evaluate(*, task, platform: str, source: Path, role: str, output: Path,
             deadline: float, device_serial: str | None = None) -> dict:
    del device_serial
    if platform != "android":
        raise ValueError("Task13 Android evaluator received another platform")
    source = source.resolve()
    if not (source / "gradlew").is_file():
        raise ValueError("Task13 runtime requires a materialized standalone source; ref reconstruction is forbidden")
    if (formal.sha256(task.contract) != formal.sha256(task.audited_contract) or
            formal.sha256(task.contract) != task.expected_contract_sha256):
        raise ValueError("Task13 canonical contract differs from its pinned audited revision5")
    contract = formal.load(task.contract)
    evidence = output.with_suffix(".android-evidence")
    evidence.mkdir(parents=True, exist_ok=False)
    original_prepare = android_robolectric.prepare
    original_resources = android_robolectric.compile_resources

    def prepare(configuration, work):
        environment = original_prepare(configuration, work)
        environment["jars"].append(android_runner.cached("com.freeletics.flowredux", "compose-jvm", "1.2.2"))
        environment["jvmArgs"].append(f"-Druntime.contract.path={task.contract}")
        return environment

    android_robolectric.prepare = prepare
    android_robolectric.compile_resources = compile_resources
    reports = {}
    try:
        with bounded_file_lock(ROOT / "state_tests/runtime/android/.build.lock", deadline,
                               "Task13 Android exact multi-slice lock"):
            entry_config = _prepare(
                source, BASE / "adapter.json", ASSETS / "formal/Task13CommonEntryProbeTest.kt",
                evidence / "base-entry.config.json", test_class="runtime.Task13CommonEntryProbeTest",
            )
            reports["entry"] = _run_slice(source, role, ASSETS / "formal", entry_config,
                                           evidence / "base-entry.json", deadline)
            prefix_rows = reports["entry"].get("observations", [])
            prefix_missing = len(prefix_rows) == 9 and all(
                row.get("observed", {}).get("prefixStatus") == "missing_verify_user_action" for row in prefix_rows)
            prefix_available = len(prefix_rows) == 9 and all(
                row.get("status") == "pass" and row.get("observed", {}).get("prefixStatus") == "entry_available"
                for row in prefix_rows)
            if not (prefix_missing or prefix_available):
                raise RuntimeError("Task13 common production UI prefix was not established")
            if prefix_missing:
                violation_config = _prepare(
                    source, BASE / "violation_adapter.json", BASE / "BaseViolationSurfacesTest.kt",
                    evidence / "base-violation.config.json",
                )
                reports["violation"] = _run_slice(source, role, BASE, violation_config,
                                                   evidence / "base-violation.json", deadline)
                rows = _base_rows(contract, reports["entry"], reports["violation"],
                                  evidence / "base-entry.json")
            else:
                route_config = _prepare(source, ROOM_MEMBER / "adapter.json",
                                        ROOM_MEMBER / "RoomMemberNavigationTest.kt",
                                        evidence / "route.config.json",
                                        keys=["profile_routes_user_request"])
                completion_config = _prepare(source, ROOM_MEMBER / "adapter.json",
                                             ROOM_MEMBER / "RoomMemberNavigationTest.kt",
                                             evidence / "completion.config.json",
                                             keys=["finish_clears_violation"])
                violation_config = _prepare(source, FINAL / "adapter.json",
                                            FINAL / "FinalViolationSurfacesTest.kt",
                                            evidence / "violation.config.json")
                reports["route"] = _run_slice(source, role, ROOM_MEMBER, route_config,
                                               evidence / "route.json", deadline)
                domain_config = _prepare(
                    source, ROOM_MEMBER / "adapter.json", ASSETS / "formal/Task13FormalDomainTest.kt",
                    evidence / "domain.config.json", test_class="runtime.Task13FormalDomainTest",
                    keys=[case["key"] for case in contract["cases"]
                          if case["key"] not in {"profile_routes_user_request", "finish_clears_violation",
                                                "identity_violation_surfaces"}],
                    entrypoints=[
                        "features/roomdetails/impl/src/main/kotlin/io/element/android/features/roomdetails/impl/members/details/RoomMemberDetailsPresenter.kt",
                        "features/userprofile/impl/src/main/kotlin/io/element/android/features/userprofile/impl/root/UserProfilePresenter.kt",
                        "features/verifysession/impl/src/main/kotlin/io/element/android/features/verifysession/impl/outgoing/VerifySelfSessionPresenter.kt",
                    ],
                )
                reports["domain"] = _run_slice(source, role, ASSETS / "formal", domain_config,
                                                evidence / "domain.json", deadline)
                reports["completion"] = _run_slice(source, role, ROOM_MEMBER, completion_config,
                                                    evidence / "completion.json", deadline)
                reports["violation"] = _run_slice(source, role, FINAL, violation_config,
                                                   evidence / "violation.json", deadline)
                rows = _final_rows(contract, reports["route"], reports["domain"],
                                   reports["completion"], reports["violation"])
    finally:
        android_robolectric.prepare = original_prepare
        android_robolectric.compile_resources = original_resources
    rows = _canonical_rows(contract, rows, "base" if prefix_missing else role)
    lineage = formal.calibrator_lineage(task, "android")
    evidence_records = {
        name: formal.file_record(evidence / f"{name}.json")
        for name in reports if (evidence / f"{name}.json").is_file()
    }
    return support.strict_report(
        task=task, platform="android", source=source, role=role, rows=rows,
        runtime_compile={"passed": True, "status": "passed",
                         "scope": "four exact candidate production Robolectric slices"},
        lineage=lineage, runtime_kind="android robolectric original production multi-slice",
        transport="host_runtime_completed", evidence=evidence_records, output=output,
    )


def main() -> int:
    args = support.parse_args(__doc__ or "Task13 Android strict runtime")
    try:
        from .task13_formal_agent import SPEC
    except ImportError:
        from task13_formal_agent import SPEC
    report = evaluate(task=SPEC, platform="android", source=args.source, role=args.role,
                      output=args.output, deadline=time.monotonic() + args.deadline_seconds)
    print(json.dumps({"output": str(args.output), "semantic": report["semantic"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
