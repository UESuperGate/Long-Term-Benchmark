"""Run independent Android slices and merge only verified canonical case rows.

Call run_supplemental only after releasing the primary Android build lock. Child
runners acquire that lock themselves. This module never replaces app compilation
or a whole primary report. Adapter, identity and evidence gaps remain not_scored.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

if __package__:
    from .android11_reviewed_navigation import validate_reviewed_predecessor
else:
    from android11_reviewed_navigation import validate_reviewed_predecessor

ROOT = Path(__file__).resolve().parents[2]
RECIPES = {
    "09_spaces_lifecycle": ("rendered", True),
    "10_media_upload_quality": ("preview", True),
    "11_room_upgrade_navigation": ("rendered", False),
    "12_report_room": ("rendered", True),
    "14_join_room_by_address": ("rendered", True),
    "15_account_deactivation": ("rendered", True),
}
EXTRA_RECIPES = {
    "10_media_upload_quality": (("rendered", True),),
    "11_room_upgrade_navigation": (("roomlist", True),),
}
# These audited gaps are independent of a slice's claimed PASS. Remove only after
# reviewing actual lifecycle/artifact or navigator/backstack execution evidence.
UNPROVEN_BOUNDARIES = {
    ("10_media_upload_quality", "failure_cancel_retry"):
        "Retained composition and scripted codec cleanup do not establish reachable retry or prepared artifact survival.",
    ("11_room_upgrade_navigation", "open_predecessor"):
        "View callback delivery does not establish actual navigator/backstack success.",
}


def file_record(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _sha(value, lengths=(64,)):
    return isinstance(value, str) and len(value) in lengths and all(c in "0123456789abcdef" for c in value)


def _contract_hash(report):
    provenance = report.get("provenance", {})
    return report.get("contractSha256") or provenance.get("contractSha256") or provenance.get("canonicalContract", {}).get("sha256")


def _identity_errors(report, task_id, role, contract_sha256, reference=None):
    errors = []
    provenance = report.get("provenance", {})
    if report.get("taskId") != task_id or report.get("role") != role:
        errors.append("Task/role identity mismatch")
    if report.get("platform", "android") != "android":
        errors.append("Not an Android report")
    if provenance.get("role", role) != role:
        errors.append("Provenance role mismatch")
    if not _sha(contract_sha256) or _contract_hash(report) != contract_sha256:
        errors.append("Missing or mismatched canonical contract hash")
    declared_hashes = [report.get("contractSha256"), provenance.get("contractSha256"),
                       provenance.get("canonicalContract", {}).get("sha256")]
    if any(value is not None and value != contract_sha256 for value in declared_hashes):
        errors.append("Conflicting declared contract hashes")
    if not _sha(provenance.get("tree"), (40, 64)):
        errors.append("Missing immutable candidate tree")
    if role == "agent" and not _sha(provenance.get("patchSha256")):
        errors.append("Missing archived agent patch hash")
    if reference is not None:
        other = reference.get("provenance", {})
        for field in ("tree", "patchSha256", "commit"):
            if provenance.get(field) != other.get(field):
                errors.append(f"Candidate {field} mismatch")
    return errors


def _compare(expected, observed, path=""):
    missing, mismatches = [], []
    if isinstance(expected, dict) and isinstance(observed, dict):
        for key, value in expected.items():
            field = f"{path}.{key}" if path else key
            if key not in observed:
                missing.append(field)
            else:
                absent, wrong = _compare(value, observed[key], field)
                missing.extend(absent)
                mismatches.extend(wrong)
    elif isinstance(expected, list) and isinstance(observed, list) and len(expected) == len(observed):
        for index, value in enumerate(expected):
            absent, wrong = _compare(value, observed[index], f"{path}[{index}]")
            missing.extend(absent)
            mismatches.extend(wrong)
    elif type(expected) is not type(observed) or expected != observed:
        mismatches.append({"field": path, "expected": expected, "observed": observed})
    return missing, mismatches


def _validate_artifacts(report):
    """Verify persisted runtime/evaluator bytes and candidate source hashes."""
    errors = []
    provenance = report.get("provenance", {})
    sources = provenance.get("productionSources", [])
    evaluators = provenance.get("evaluatorSources", [])
    if not sources or not evaluators:
        return ["Missing production/evaluator source manifest"]
    records = list(evaluators)
    log = report.get("log") or report.get("diagnostics", {}).get("log")
    if not log:
        errors.append("Missing runtime log hash")
    else:
        records.append(log)
    for field in ("runtimeEvidence", "reportArtifact"):
        if report.get(field):
            records.append(report[field])
    for field in ("canonicalContract", "previewRunner", "renderedRunner", "previewConfiguration"):
        if provenance.get(field):
            records.append(provenance[field])
    records.extend(provenance.get("packagingSources", []))
    for record in records:
        try:
            if not _sha(record.get("sha256")) or file_record(record["path"])["sha256"] != record["sha256"]:
                errors.append(f"Artifact hash mismatch: {record.get('path')}")
        except (KeyError, OSError, TypeError):
            errors.append(f"Artifact unavailable: {record.get('path')}")
    source = provenance.get("source")
    tree = provenance.get("tree")
    if not source or not _sha(tree, (40, 64)):
        return errors + ["Missing immutable production source location/tree"]
    for record in sources:
        path = record.get("path", "")
        if not path or Path(path).is_absolute() or ".." in Path(path).parts or not _sha(record.get("sha256")):
            errors.append("Invalid production source hash/path")
            continue
        try:
            data = subprocess.check_output(["git", "-C", str(source), "show", f"{tree}:{path}"],
                                           stderr=subprocess.PIPE, timeout=15)
            if hashlib.sha256(data).hexdigest() != record["sha256"]:
                errors.append(f"Production source hash mismatch: {path}")
        except (OSError, subprocess.SubprocessError):
            errors.append(f"Production source unavailable in candidate tree: {path}")
    return errors


def _unscored(row, reasons):
    row["reportedStatus"] = row.get("status")
    row["status"] = "not_scored"
    row["reason"] = "; ".join(dict.fromkeys(reasons))
    return row


def normalize_slice(report, contract, *, contract_sha256):
    """Validate canonical rows without adding observations from the contract.

    Missing IDs/digests/hashes are not synthesized. Prefer semantic.cases over raw
    JUnit observations so a runner's exclusions cannot be bypassed by raw PASSes.
    """
    normalized = copy.deepcopy(report)
    task_id = contract["taskId"]
    role = report.get("role")
    errors = _identity_errors(report, task_id, role, contract_sha256)
    if report.get("observationMode", "runtime_state_transition") != "runtime_state_transition":
        errors.append("Not runtime state-transition evidence")
    if role not in ("base", "final", "agent"):
        errors.append("Unsupported candidate role")
    cases = {case["key"]: case for case in contract["cases"]}
    rows = copy.deepcopy(report.get("semantic", {}).get("cases", report.get("observations", [])))
    keys = [row.get("key") for row in rows]
    if len(set(keys)) != len(keys):
        errors.append("Duplicate supplemental case keys")
    scored = any(row.get("status") in ("pass", "fail") for row in rows)
    if scored and not errors:
        errors.extend(_validate_artifacts(report))
    for row in rows:
        reasons = list(errors)
        spec = cases.get(row.get("key"))
        if spec is None:
            _unscored(row, reasons + ["Unknown canonical case key"])
            continue
        if row.get("caseId") != spec["caseId"] or row.get("traceDigest") != spec["traceDigest"]:
            reasons.append("Canonical case identity/digest mismatch")
        for field in ("taskId", "role"):
            if field in row and row[field] != report.get(field):
                reasons.append(f"Row {field} mismatch")
        provenance = report.get("provenance", {})
        if "provenance" in row:
            for field in ("tree", "patchSha256", "commit", "role", "canonicalContract", "productionSources", "evaluatorSources"):
                if row["provenance"].get(field) != provenance.get(field):
                    reasons.append(f"Row provenance {field} mismatch")
        if "productionSources" in row and row["productionSources"] != provenance.get("productionSources"):
            reasons.append("Row production source manifest mismatch")
        policy = UNPROVEN_BOUNDARIES.get((task_id, row["key"]))
        if policy:
            if (task_id, row["key"], role) == ("11_room_upgrade_navigation", "open_predecessor", "final") and not reasons:
                review_errors = validate_reviewed_predecessor(report, row, contract, contract_sha256=contract_sha256)
                if review_errors:
                    reasons.extend([policy, *review_errors])
            else:
                reasons.append(policy)
        if row.get("scoringExclusion") or row.get("unsupported") or row.get("unsupportedInvariants"):
            reasons.append("Explicit unsupported observation/invariant or scoring exclusion")
        if row.get("status") not in ("pass", "fail"):
            _unscored(row, reasons + [row.get("reason") or "No scored runtime observation"])
            continue
        if report.get("runtimeCompile", {}).get("status") != "passed":
            reasons.append("Production slice/evaluator compilation not established")
        checkpoints = row.get("checkpoints", [])
        if len(checkpoints) < 2 or any(not isinstance(point, dict) or not point for point in checkpoints):
            reasons.append("Missing before/after runtime checkpoints")
        missing, mismatches = _compare(spec["expected"], row.get("observed", {}))
        checks = row.get("invariantChecks", [])
        invariant_rows = {}
        for check in checks:
            description = check.get("invariant", check.get("description"))
            if description in invariant_rows:
                reasons.append("Duplicate invariant evidence")
            passed = check.get("passed")
            if check.get("status") in ("pass", "fail"):
                if "passed" in check and (type(passed) is not bool or passed != (check["status"] == "pass")):
                    reasons.append("Conflicting invariant status/passed fields")
                passed = check["status"] == "pass"
            invariant_rows[description] = dict(check, description=description, passed=passed,
                                               observed=check.get("evidence", check.get("observed")))
        absent = [description for description in spec.get("invariants", [])
                  if description not in invariant_rows or
                  type(invariant_rows[description].get("passed")) is not bool or
                  invariant_rows[description].get("observed") is None or
                  isinstance(invariant_rows[description].get("observed"), (str, list, dict)) and
                  not invariant_rows[description]["observed"]]
        row["coverage"] = {"missingExpectedFields": missing, "missingInvariants": absent, "mismatches": mismatches}
        if missing or absent:
            reasons.append("Incomplete canonical expected fields/invariant evidence")
        if reasons:
            _unscored(row, reasons)
            continue
        failed = bool(mismatches) or any(not invariant_rows[name]["passed"] for name in spec.get("invariants", []))
        if row["status"] == "fail" and not failed:
            _unscored(row, ["JUnit failure does not establish a canonical observation/invariant violation"])
            continue
        row["status"] = "fail" if failed else "pass"
        row["invariantChecks"] = list(invariant_rows.values())
        row["productionSources"] = copy.deepcopy(provenance["productionSources"])
        row["provenance"] = copy.deepcopy(provenance)
        row["supplementalEvidence"] = {
            "log": report.get("log") or report.get("diagnostics", {}).get("log"),
            "report": report.get("reportArtifact", report.get("runtimeEvidence")),
            "runtimeCompile": copy.deepcopy(report["runtimeCompile"]),
        }
    normalized["semantic"] = {"cases": rows}
    normalized["validationErrors"] = errors
    return normalized


def _projection(expected, observed):
    if isinstance(expected, dict) and isinstance(observed, dict):
        return {key: _projection(value, observed[key]) for key, value in expected.items() if key in observed}
    if isinstance(expected, list) and isinstance(observed, list):
        return [_projection(value, item) for value, item in zip(expected, observed)] if len(expected) == len(observed) else observed
    return observed


def merge_supplemental(primary, supplements, contract, *, contract_sha256):
    """Return a copy; promote rows individually and retain conflicts unscored."""
    merged = copy.deepcopy(primary)
    diagnostics = merged.setdefault("diagnostics", {}).setdefault("supplemental", [])
    primary_errors = _identity_errors(primary, contract["taskId"], primary.get("role"), contract_sha256)
    specs = {case["key"]: case for case in contract["cases"]}
    rows = merged.setdefault("semantic", {}).setdefault("cases", [])
    by_key = {row.get("key"): row for row in rows}
    if len(by_key) != len(rows):
        primary_errors.append("Duplicate primary case keys")
    for row in rows:
        spec = specs.get(row.get("key"))
        if not spec or row.get("caseId") != spec["caseId"] or row.get("traceDigest") != spec["traceDigest"]:
            primary_errors.append("Primary case identity/digest mismatch")
    for supplement in supplements:
        errors = primary_errors + _identity_errors(supplement, contract["taskId"], primary.get("role"),
                                                  contract_sha256, primary)
        entry = {"taskId": supplement.get("taskId"), "role": supplement.get("role"),
                 "report": supplement.get("reportArtifact"), "promoted": [], "conflicts": [],
                 "rejected": [], "identityErrors": errors,
                 "runtimeCompile": copy.deepcopy(supplement.get("runtimeCompile"))}
        diagnostics.append(entry)
        if errors:
            continue
        normalized = normalize_slice(supplement, contract, contract_sha256=contract_sha256)
        entry["validationErrors"] = normalized["validationErrors"]
        for incoming in normalized["semantic"]["cases"]:
            key = incoming.get("key")
            if incoming["status"] == "not_scored":
                entry["rejected"].append({"key": key, "reason": incoming["reason"]})
                continue
            previous = by_key.get(key)
            if previous is not None and previous.get("supplementalConflict"):
                entry["conflicts"].append(key)
                continue
            if previous is not None and previous.get("status") in ("pass", "fail"):
                expected = specs[key]["expected"]
                same = previous["status"] == incoming["status"] and _projection(expected, previous.get("observed", {})) == _projection(expected, incoming["observed"])
                if not same:
                    conflict = copy.deepcopy(previous)
                    conflict.update(status="not_scored", reason="Conflicting primary/supplemental runtime observations; review required.",
                                    supplementalConflict={"primary": copy.deepcopy(previous), "supplemental": incoming})
                    rows[rows.index(previous)] = conflict
                    by_key[key] = conflict
                    entry["conflicts"].append(key)
                continue
            if previous is None:
                rows.append(incoming)
            else:
                rows[rows.index(previous)] = incoming
            by_key[key] = incoming
            entry["promoted"].append(key)
    merged["semantic"].update(total=len(rows), passed=sum(row["status"] == "pass" for row in rows),
                              failed=sum(row["status"] == "fail" for row in rows),
                              notScored=sum(row["status"] == "not_scored" for row in rows))
    return merged


def run_supplemental(task_id, role, source, *, output_dir, timeout=300, lock_timeout=300, root=ROOT, slice_name=None):
    """Run the allowlisted slice after primary lock release; never reuse stale output."""
    root, source, output_dir = Path(root).resolve(), Path(source).resolve(), Path(output_dir).resolve()
    if task_id not in RECIPES or role not in ("base", "final", "agent"):
        raise ValueError("Unsupported supplemental task/role")
    lock_path = root / "state_tests/runtime/android/.build.lock"
    with lock_path.open("a") as lock:
        deadline = time.monotonic() + lock_timeout
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Android build lock is still busy; release the caller's primary lock or retry after the active build") from None
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        fcntl.flock(lock, fcntl.LOCK_UN)
    recipes = (RECIPES[task_id],) + EXTRA_RECIPES.get(task_id, ())
    selected = [recipe for recipe in recipes if slice_name is None or recipe[0] == slice_name]
    if not selected:
        raise ValueError("Unsupported supplemental slice")
    directory, controlled_output = selected[0]
    script = root / "state_tests/runtime/android" / task_id / directory / "run.py"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"android_{task_id}_{role}.json"
    actual = target if controlled_output else script.parent / "results" / f"{role}.json"
    command = [sys.executable, str(script), "--role", role, "--source", str(source), "--timeout", str(timeout)]
    if controlled_output:
        command += ["--output", str(target)]
    previous = actual.stat().st_mtime_ns if actual.exists() else None
    start = time.monotonic()
    attempt = {"command": command, "runner": file_record(script), "output": str(actual)}
    try:
        process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout + 60)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            raise
        attempt.update(exitCode=process.returncode, stdout=stdout, stderr=stderr)
        if not actual.exists() or actual.stat().st_mtime_ns == previous:
            raise ValueError("Supplemental runner produced no fresh report")
        report = json.loads(actual.read_text())
        if report.get("taskId") != task_id or report.get("role") != role:
            raise ValueError("Supplemental output task/role mismatch")
        report["reportArtifact"] = file_record(actual)
    except (OSError, ValueError, subprocess.SubprocessError) as failure:
        attempt["error"] = f"{type(failure).__name__}: {failure}"
        report = {"taskId": task_id, "role": role, "platform": "android", "semantic": {"cases": []},
                  "status": "not_scored", "reason": attempt["error"]}
    attempt["durationSeconds"] = round(time.monotonic() - start, 3)
    report["supplementalRun"] = attempt
    return report
