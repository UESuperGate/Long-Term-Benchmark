"""Prune unreferenced JVM extractions, never original cached dependencies."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "state_tests/runtime/android"
CACHE = ASSETS / "08_threads/.dependencies"


def referenced_paths():
    paths = set()

    def visit(value):
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            for item in value.split(":"):
                if item.startswith(str(CACHE)):
                    paths.add(Path(item))

    for directory in (ASSETS, ROOT / "experiment_results/runtime_transition_20261019"):
        for path in directory.rglob("*.json"):
            if ".dependencies" in path.parts:
                continue
            try:
                visit(json.loads(path.read_text()))
            except (ValueError, UnicodeError):
                continue
    for path in ASSETS.rglob("*classpath*.txt"):
        visit(path.read_text())
    return paths


def prune(apply=False):
    references = referenced_paths()
    removed = []
    repository = CACHE / "maven-repository"
    for jar in repository.rglob("*.jar"):
        if jar.is_symlink() or jar in references:
            continue
        aar = jar.with_suffix(".aar")
        if not aar.exists():
            continue
        with zipfile.ZipFile(aar) as archive:
            if "classes.jar" not in archive.namelist():
                continue
            data = jar.read_bytes()
            if data != archive.read("classes.jar"):
                continue
        removed.append({"path": str(jar), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        if apply:
            jar.unlink()
    return {"applied": apply, "files": len(removed), "bytes": sum(item["bytes"] for item in removed), "artifacts": removed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with (ASSETS / ".build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = prune(args.apply)
    print(json.dumps(result))
