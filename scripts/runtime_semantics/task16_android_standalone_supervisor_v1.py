"""Task16 standalone diagnostic: reviewed owned supervisor, OFFLINE by default.

No Android work occurs on import or without explicit execute-after-release.
Current queue scheduling remains external; a receipt/flag is not human approval.
Parent prepare/finalize NEVER acquire Android locks: only the child owns both.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid

from . import tasks16_17_native_controller_v3 as owned
from . import task16_android_standalone_worker_v3 as worker
from . import task16_android_full_raw_guard_v1 as guard

ROOT = Path(__file__).resolve().parents[2]


def implementation():
    paths = list(worker.load_plan().EVALUATORS) + [Path(__file__), Path(worker.__file__), Path(guard.__file__),
                                               Path(owned.__file__), Path(owned.timer.__file__),
                                               ROOT / "benchmark_tasks/16_identity_reset/transitions.json"]
    return [worker.record(path) for path in sorted(set(paths))]


def validate_review(reviewed):
    if not reviewed or reviewed != implementation():
        raise ValueError("Current Android evaluator/worker/supervisor closure differs from independent reviewed bytes")


def run_coordinated(source, output, *, reviewed_sources, execute_after_release=False,
                    timeout=3600, binary_proof_scope="retained_tiny_classes"):
    if execute_after_release is not True:
        raise ValueError("Offline queue only: explicit new resource release/root required; no worker started")
    if not 0 < timeout <= 3600 or binary_proof_scope not in {"retained_tiny_classes", "binary_free_predeclared"}:
        raise ValueError("Invalid single overall budget or predeclared class proof scope")
    validate_review(reviewed_sources)
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    if output.exists() or source == output or source in output.parents or output in source.parents:
        raise ValueError("New disjoint run root required; no resume/reset/overwrite")

    def prepare(root, clock):
        # This phase contains metadata only: no locks, dependency resolution,
        # subprocesses, input copies, Gradle, Kotlin, device or nested leases.
        clock.check_work()
        validate_review(reviewed_sources)
        return {"requestId": "android16-standalone-" + uuid.uuid4().hex,
                "supervisorPid": os.getpid(),
                "source": str(source), "worker": worker.record(worker.__file__),
                "fixtureSources": [worker.record(path) for path in sorted(worker.FIXTURE.iterdir()) if path.is_file()],
                "implementation": reviewed_sources,
                "canonicalContract": worker.record(ROOT / "benchmark_tasks/16_identity_reset/transitions.json"),
                "deadlineEpochMs": int((time.time() + clock.deadline - time.monotonic()) * 1000),
                "originalRepairBudgetReused": False,
                "resourceSchedule": "new_root_after_coordinator_release",
                "binaryProofScope": binary_proof_scope, "formalStatus": "not_scored",
                "parentAndroidLocks": "never_acquired", "childAndroidLocks": "both_canonical_nonblocking"}

    def command(request_path):
        return [sys.executable, "-B", "-m", "scripts.runtime_semantics.task16_android_standalone_supervisor_v1",
                "--worker", str(request_path), "--expected-request-sha256", worker.record(request_path)["sha256"]]

    def finalize(root, request, clock):
        clock.check_work()
        validate_review(reviewed_sources)
        proof = guard.verify_bundle(root, expected_request_sha256=worker.record(root / "request.json")["sha256"],
                                    reviewed_sources=reviewed_sources, require_completed=False)
        clock.check_work()
        owned.atomic(root / "full10-independent-diagnostic.json", proof)
        return proof

    # The already-reviewed supervisor owns leader/descendants and ONE timer.
    # No acquire callback: specifically NO parent Android lock/device lease.
    return owned._supervise(output, timeout, prepare, command, finalize)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--expected-request-sha256")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reviewed-sources", type=Path)
    parser.add_argument("--execute-after-release", action="store_true")
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--binary-proof-scope", choices=["retained_tiny_classes", "binary_free_predeclared"], default="retained_tiny_classes")
    args = parser.parse_args()
    if args.worker:
        if not args.expected_request_sha256:
            parser.error("owned child requires caller-pinned request SHA")
        worker.execute_prepared(args.worker, expected_request_sha256=args.expected_request_sha256)
        return
    if not args.execute_after_release:
        parser.error("offline queue; no Android worker/lock/build started")
    if not all((args.source, args.output, args.reviewed_sources)):
        parser.error("new source/root and independent reviewed implementation records required")
    result = run_coordinated(args.source, args.output,
        reviewed_sources=json.loads(args.reviewed_sources.read_text()), execute_after_release=True,
        timeout=args.timeout, binary_proof_scope=args.binary_proof_scope)
    if result is None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
