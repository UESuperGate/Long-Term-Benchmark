"""Source-parameterized Task14 candidate evaluator using physical ArkUI and the real SDK/provider chain."""
from pathlib import Path
import json
import subprocess
import types

from . import task14_actual_routes_packaging_v4 as old

ROOT, TASK, CONTRACT = old.ROOT, old.TASK, old.CONTRACT
core, artifacts, snapshot = old.core, old.artifacts, old.snapshot
PROTOCOL = "task14.candidate-native.v19"
DIRECTORY = Path(__file__).with_name("task14_candidate_native_v19")
CASES = {item["caseId"] for item in json.loads(CONTRACT.read_text())["cases"]}
NODE = "/Applications/DevEco-Studio.app/Contents/tools/node/bin/node"


def clone(function, **overrides):
    result = types.FunctionType(function.__code__, {**function.__globals__, **overrides},
        name=function.__name__, argdefs=function.__defaults__, closure=function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def expected_fixtures():
    command = "const i=require(process.argv[1]);process.stdout.write(JSON.stringify(i.expectedFixtures()));"
    result = subprocess.run([NODE, "-e", command, str(DIRECTORY / "install.cjs")],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10)
    return json.loads(result.stdout)


def implementation():
    paths = [Path(__file__)] + [path for path in DIRECTORY.iterdir() if path.is_file()]
    paths += [ROOT / "state_tests/runtime/arkts/native" / name for name in (
        "Task14DeviceUi.install.cjs", "Task14DeviceUi.js", "Task14DeviceUi.core.js",
        "CandidateApiBindings.cjs")]
    paths += [Path(__file__).with_name(name) for name in (
        "task14_matrix_provider_v2.cjs", "task14_matrix_provider_host_v2.cjs")]
    records = [{"path": str(path), "bytes": path.stat().st_size, "sha256": core.sha256(path)}
               for path in sorted(set(paths))]
    return {"protocol": PROTOCOL, "files": records, "sha256": artifacts.row_digest(records)}


def derive_builder(contract, epoch):
    return old.replace_once(old.derive_builder(contract, epoch),
        "require(" + json.dumps(str(old.DIRECTORY / "install.cjs")) + ")",
        "require(" + json.dumps(str(DIRECTORY / "install.cjs")) + ")")


def prepare(*, source, output, deadline, case_ids=None):
    return clone(old.prepare, CASES=CASES, derive_builder=derive_builder,
        implementation=implementation, expected_fixtures=expected_fixtures,
        guard=types.SimpleNamespace(PROTOCOL=PROTOCOL))(source=source, output=output,
            deadline=deadline, case_ids=case_ids)
