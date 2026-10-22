"""Freeze the approved Task13 base repair against the complete pre-edit archive."""

import argparse
import hashlib
from pathlib import Path
import shutil
import tarfile

from . import task12_13_formal_core as core
from .task13_formal_agent import SPEC


def verify_before(path):
    before = core.load(path)
    if before["androidBaseCommit"] != "232f1db645b5710d1eee451c9c8cee1525dc38d6":
        raise ValueError("Task13 immutable Android base reference differs")
    snapshot = core.source_inventory(Path(before["snapshot"]["source"]))
    if snapshot["files"] != before["baseSource"]["files"]:
        raise ValueError("Task13 complete original snapshot changed")
    archive = before["archive"]
    if core.file_record(Path(archive["path"])) != archive:
        raise ValueError("Task13 complete original archive changed")
    with tarfile.open(archive["path"], "r:gz") as source:
        prefix = Path(before["baseSource"]["source"]).name + "/"
        files = {member.name.removeprefix("./").removeprefix(prefix): member
                 for member in source.getmembers() if member.isfile()}
        if set(files) != {item["path"] for item in snapshot["files"]}:
            raise ValueError("Task13 original archive file coverage differs")
        for item in snapshot["files"]:
            data = source.extractfile(files[item["path"]]).read()
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("Task13 original archived file changed")
    for item in before["androidSourceEvidence"]:
        if not item["gitObject"].startswith(before["androidBaseCommit"] + ":"):
            raise ValueError("Android source evidence is not the immutable base")
        if core.file_record(Path(item["record"]["path"])) != item["record"]:
            raise ValueError("Android source evidence changed")
    for field, path in (("canonicalBefore", SPEC.contract),
                        ("activeBindingBefore", core.ROOT / "migrations/13_user_verification/arkts/bindings.json")):
        if core.file_record(path) != before[field]:
            raise ValueError("Task13 contract/binding changed during production repair")
    return before


def freeze(*, before_manifest, source, output):
    before = verify_before(before_manifest)
    if output.exists():
        raise ValueError("Refusing to overwrite a Task13 migration revision")
    inventory = core.source_inventory(source)
    old = {item["path"]: item for item in before["baseSource"]["files"]}
    current = {item["path"]: item for item in inventory["files"]}
    changed = sorted(path for path in set(old) | set(current) if old.get(path) != current.get(path))
    allowed = {"entry/src/main/ets/features/RoomIdentityFeature.ets",
               "entry/src/main/ets/features/UserProfileFeature.ets", "entry/src/main/ets/pages/Index.ets"}
    if set(changed) != allowed:
        raise ValueError("Task13 repair changed files outside the approved migration boundary")
    destination = output / "source"
    for item in inventory["files"]:
        target = destination / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / item["path"], target)
    archive = output / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as result:
        for item in inventory["files"]:
            result.add(destination / item["path"], arcname=item["path"], recursive=False)
    manifest = {"taskId": SPEC.task_id, "revision": "base-migration-repair-v1",
                "before": core.file_record(before_manifest), "androidBaseCommit": before["androidBaseCommit"],
                "sourceInventory": inventory, "snapshot": core.source_inventory(destination),
                "archive": core.file_record(archive), "changedFiles": changed,
                "canonicalUnchanged": core.file_record(SPEC.contract),
                "activeBindingUnchanged": before["activeBindingBefore"],
                "status": "production_revision_frozen_runtime_calibration_required",
                "boundary": {
                    "inputs": "SDK session, encrypted-room sync, member stream, identity stream",
                    "production": "Original page owns presenters and subscribes to the room stream; timeline warning and old acknowledge action restored",
                    "excludedFinalOnly": "No enabled Verify user, user-SAS navigation, profile violation/withdrawal or member violation badge",
                    "externalService": "Encryption service delegates to its connected SDK port; absent backend throws, no optimistic trust update or fake success"}}
    core.write(output / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("before-manifest", "source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    result = freeze(**vars(parser.parse_args()))
    print({"files": result["sourceInventory"]["fileCount"], "changedFiles": result["changedFiles"],
           "status": result["status"]})


if __name__ == "__main__":
    main()
