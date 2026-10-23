#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


PAGES_CLASSES = (
    "org.wordpress.android.ui.pages.PagesActivity",
    "org.wordpress.android.ui.pagesrs.PagesRsListViewModel",
    "org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerActivity",
)
SUPPORT_CLASSES = (
    "org.wordpress.android.support.main.ui.SupportViewModel",
    "org.wordpress.android.support.unified.ui.UnifiedSupportViewModel",
    "org.wordpress.android.support.unified.repository.UnifiedSupportRepository",
    "org.wordpress.android.support.unified.model.UnifiedConversation",
    "org.wordpress.android.support.unified.ui.UnifiedConversationDetailScreenKt",
    "org.wordpress.android.support.unified.ui.SupportRuntimeOwnerActivity",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def production_source_digest(project: Path, task_id: str) -> str:
    target = (
        "org/wordpress/android/ui/pagesrs/"
        if task_id == "01_pages_list"
        else "org/wordpress/android/support/unified/"
    )
    target_package = (
        "org.wordpress.android.ui.pagesrs"
        if task_id == "01_pages_list"
        else "org.wordpress.android.support.unified"
    )
    package_pattern = re.compile(
        rf"^\s*package\s+{re.escape(target_package)}(?:\.|\s*$)", re.MULTILINE
    )
    rows: list[str] = []
    for path in sorted(project.rglob("*")):
        if not path.is_file() or path.suffix not in {".kt", ".java"}:
            continue
        relative = path.relative_to(project)
        if any(part in {".benchmark-evaluator", "build", ".gradle", ".kotlin"} for part in relative.parts):
            continue
        if any(part in {"test", "androidTest"} for part in relative.parts):
            continue
        if target in f"{relative.as_posix()}/" or package_pattern.search(path.read_text(encoding="utf-8")):
            rows.append(f"{relative.as_posix()}\0{sha256(path)}")
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def production_source_roots(project: Path, task_id: str) -> list[str]:
    package_path = Path(
        "org/wordpress/android/ui/pagesrs"
        if task_id == "01_pages_list"
        else "org/wordpress/android/support/unified"
    )
    roots: set[str] = set()
    for source in project.rglob("*"):
        if not source.is_file() or source.suffix not in {".kt", ".java"}:
            continue
        relative = source.relative_to(project)
        if any(part in {".benchmark-evaluator", ".benchmark-scaffold", "build", ".gradle", ".kotlin"}
               for part in relative.parts):
            continue
        parts = relative.parts
        needle = package_path.parts
        for index in range(len(parts) - len(needle)):
            if parts[index:index + len(needle)] == needle:
                root = Path(*parts[:index])
                roots.add(root.as_posix() or ".")
                break
    return sorted(roots)


def class_roots(project: Path) -> list[Path]:
    candidates = (
        project / "build/tmp/kotlin-classes/debug",
        project / "build/intermediates/javac/debug/compileDebugJavaWithJavac/classes",
    )
    return [path for path in candidates if path.is_dir()]


def public_methods(javap: Path, roots: list[Path], class_name: str) -> list[str] | None:
    relative = Path(*class_name.split(".")).with_suffix(".class")
    if not any((root / relative).is_file() for root in roots):
        return None
    result = subprocess.run(
        [str(javap), "-public", "-classpath", os.pathsep.join(map(str, roots)), class_name],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"javap failed for {class_name}: {result.stderr.strip()}")
    methods = set()
    for line in result.stdout.splitlines():
        match = re.search(r"\s([A-Za-z_$][A-Za-z0-9_$]*)\([^;]*\);$", line.strip())
        if match:
            methods.add(match.group(1))
    return sorted(methods)


def write_receipt(project: Path, task_id: str, output: Path) -> dict[str, object]:
    roots = class_roots(project)
    if not roots:
        raise RuntimeError("visible Android build emitted no debug class directory")
    java_home = Path(os.environ.get("JAVA_HOME", "/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home"))
    javap = java_home / "bin/javap"
    if not javap.is_file():
        fallback = shutil.which("javap")
        if fallback is None:
            raise RuntimeError(f"javap is unavailable: {javap}")
        javap = Path(fallback)
    classes = {}
    for class_name in PAGES_CLASSES if task_id == "01_pages_list" else SUPPORT_CLASSES:
        methods = public_methods(javap, roots, class_name)
        if methods is not None:
            classes[class_name] = {"publicMethods": methods}
    receipt = {
        "schemaVersion": 2,
        "taskId": task_id,
        "buildFileSha256": sha256(project / "build.gradle.kts"),
        "productionSourceDigest": production_source_digest(project, task_id),
        "productionSourceRoots": production_source_roots(project, task_id),
        "classes": classes,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", choices=("01_pages_list", "02_unified_support"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    output = args.output.resolve() if args.output else project / ".benchmark-scaffold/visible-abi.json"
    print(json.dumps(write_receipt(project, args.task_id, output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
