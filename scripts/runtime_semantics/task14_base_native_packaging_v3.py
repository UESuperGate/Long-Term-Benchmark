"""Package Task14 base evaluation with prepared-foreground page acquisition."""
from pathlib import Path
import json
import subprocess
import types

from . import task14_base_native_packaging_v2 as previous

old = previous.old
ROOT, TASK, CONTRACT = previous.ROOT, previous.TASK, previous.CONTRACT
core, artifacts, snapshot = previous.core, previous.artifacts, previous.snapshot
PROTOCOL = "task14.base-entry-absence.v3"
DIRECTORY = Path(__file__).with_name("task14_base_native_v3")
CASES = previous.CASES
NODE = previous.NODE


def clone(function, **overrides):
    result = types.FunctionType(function.__code__, {**function.__globals__, **overrides},
        name=function.__name__, argdefs=function.__defaults__, closure=function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


def expected_fixtures():
    command = "const i=require(process.argv[1]);process.stdout.write(JSON.stringify(i.expectedFixtures()));"
    result = subprocess.run([NODE, "-e", command, str(DIRECTORY / "install.cjs")],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10)
    return sorted(json.loads(result.stdout), key=lambda item: item["name"])


def implementation():
    files = {item["path"]: item for item in previous.implementation()["files"]}
    own = [Path(__file__)] + [path for path in DIRECTORY.iterdir() if path.is_file()]
    for path in own:
        files[str(path)] = {"path": str(path), "bytes": path.stat().st_size, "sha256": core.sha256(path)}
    records = [files[name] for name in sorted(files)]
    return {"protocol": PROTOCOL, "files": records, "sha256": artifacts.row_digest(records)}


def derive_builder(contract, epoch):
    return old.replace_once(previous.derive_builder(contract, epoch),
        "require(" + json.dumps(str(previous.DIRECTORY / "install.cjs")) + ")",
        "require(" + json.dumps(str(DIRECTORY / "install.cjs")) + ")")


def prepare(*, source, output, deadline, case_ids=None):
    return clone(old.prepare, CASES=CASES, derive_builder=derive_builder,
        implementation=implementation, expected_fixtures=expected_fixtures,
        guard=types.SimpleNamespace(PROTOCOL=PROTOCOL))(source=source, output=output,
            deadline=deadline, case_ids=case_ids)
