#!/usr/bin/env python3
"""Fail closed until the full Harmony reconstruction has concrete parity evidence."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "elementx_harmony_full"
VERIFICATION = PROJECT / "verification"
FINAL_DISPOSITIONS = {"ported", "native_bridge", "platform_equivalent", "not_applicable"}
PROGRESS_DISPOSITIONS = {"unmapped", "planned", "partial"}
FIXTURE_PATTERNS = (
    re.compile(r"(?:^|/)Fixture[A-Za-z0-9_]*\.ets$"),
    re.compile(r"(?:^|/)Mock[A-Za-z0-9_]*\.ets$"),
)
FIXTURE_IMPORT = re.compile(r"(?:import|new)\s+[^\n;]*(?:Fixture|Mock)")
CLIENT_CREATE_EXPORT = re.compile(r"elementx_matrix_(?:(?:client|bridge)_)?create(?:_client)?\b")
CLIENT_RELEASE_EXPORT = re.compile(r"elementx_matrix_(?:(?:client|bridge)_)?release(?:_client)?\b")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def source_texts() -> list[tuple[Path, str]]:
    source_root = PROJECT / "entry" / "src" / "main"
    result: list[tuple[Path, str]] = []
    for path in source_root.rglob("*"):
        if path.is_file() and path.suffix in {".ets", ".ts", ".cpp", ".h"}:
            result.append((path, path.read_text(encoding="utf-8", errors="replace")))
    return result


def audit() -> dict:
    inventory_path = VERIFICATION / "android-module-inventory.json"
    map_path = VERIFICATION / "migration-map.json"
    semantic_path = VERIFICATION / "cross-platform-semantic-report.json"
    inventory = load_json(inventory_path)
    mapping = load_json(map_path)
    semantic = load_json(semantic_path)

    failures: list[str] = []
    modules = inventory.get("modules", [])
    mapping_items = mapping.get("mappings", [])
    by_source = {
        item.get("source_module"): item
        for item in mapping_items
        if isinstance(item, dict) and item.get("source_module")
    }

    if not modules:
        failures.append("Android production-module inventory is missing or empty")

    disposition_counts: dict[str, int] = {}
    missing_mappings: list[str] = []
    invalid_mappings: list[str] = []
    missing_evidence: list[str] = []
    for module in modules:
        source_module = module["source_module"]
        item = by_source.get(source_module)
        if item is None:
            missing_mappings.append(source_module)
            continue
        disposition = str(item.get("disposition", "unmapped"))
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        if disposition not in FINAL_DISPOSITIONS | PROGRESS_DISPOSITIONS:
            invalid_mappings.append(f"{source_module}: invalid disposition {disposition}")
            continue
        if disposition in PROGRESS_DISPOSITIONS:
            invalid_mappings.append(f"{source_module}: incomplete disposition {disposition}")
            continue
        reason = str(item.get("reason", "")).strip()
        target_paths = item.get("target_paths", [])
        target_symbols = item.get("target_symbols", [])
        tests = item.get("tests", [])
        if disposition == "not_applicable" and len(reason) < 20:
            missing_evidence.append(f"{source_module}: not_applicable requires a reviewed reason")
        if disposition != "not_applicable" and not target_paths:
            missing_evidence.append(f"{source_module}: no target paths")
        if disposition != "not_applicable" and not target_symbols:
            missing_evidence.append(f"{source_module}: no target symbols")
        if not tests:
            missing_evidence.append(f"{source_module}: no tests")
        combined_text = ""
        for target in target_paths:
            path = PROJECT / str(target)
            if not path.exists():
                missing_evidence.append(f"{source_module}: missing target {target}")
                continue
            if path.is_file():
                combined_text += path.read_text(encoding="utf-8", errors="replace") + "\n"
        for symbol in target_symbols:
            if str(symbol) not in combined_text:
                missing_evidence.append(f"{source_module}: target symbol not found: {symbol}")
        for test in tests:
            path = ROOT / str(test)
            if not path.exists():
                missing_evidence.append(f"{source_module}: missing test evidence {test}")

    if missing_mappings:
        failures.append(f"{len(missing_mappings)} Android modules have no migration mapping")
    if invalid_mappings:
        failures.append(f"{len(invalid_mappings)} migration mappings are incomplete or invalid")
    if missing_evidence:
        failures.append(f"{len(missing_evidence)} migration evidence checks failed")

    production_fixture_files: list[str] = []
    production_fixture_imports: list[str] = []
    for path, text in source_texts():
        relative = path.relative_to(PROJECT).as_posix()
        if any(pattern.search(relative) for pattern in FIXTURE_PATTERNS):
            production_fixture_files.append(relative)
        if FIXTURE_IMPORT.search(text):
            production_fixture_imports.append(relative)
    if production_fixture_files or production_fixture_imports:
        failures.append("Production source set contains fixture/mock code or imports")

    cargo_text = (PROJECT / "native" / "matrix-sdk-bridge" / "Cargo.toml").read_text(
        encoding="utf-8", errors="replace"
    )
    rust_text = (PROJECT / "native" / "matrix-sdk-bridge" / "src" / "lib.rs").read_text(
        encoding="utf-8", errors="replace"
    )
    addon_path = PROJECT / "entry" / "src" / "main" / "cpp" / "matrix_native_addon.cpp"
    addon_text = addon_path.read_text(encoding="utf-8", errors="replace")
    sdk_dependency = bool(re.search(r"matrix-sdk\s*=|matrix_sdk\s*=", cargo_text))
    sdk_reports_linked = (
        "elementx_matrix_bridge_sdk_linked" in rust_text
        and "matrix_sdk::Client::builder" in rust_text
        and bool(re.search(r"cfg\(feature\s*=\s*\"matrix-sdk\"\).*?\b(?:1|true)\b", rust_text, re.S))
    )

    semantic_total = int(semantic.get("total", 0) or 0)
    semantic_passed = int(semantic.get("passed", 0) or 0)
    semantic_platforms = set(semantic.get("platforms", []))
    semantic_ready = (
        semantic_total > 0
        and semantic_passed == semantic_total
        and semantic_platforms == {"android", "arkts"}
    )
    if not semantic_ready:
        failures.append("Cross-platform semantic report is missing or not all-pass on Android and ArkTS")

    hap_files = sorted((PROJECT / "entry" / "build").glob("**/*.hap"))
    if not hap_files:
        failures.append("No built Harmony HAP artifact exists")
    native_library_packaged = False
    for hap_path in hap_files:
        try:
            with zipfile.ZipFile(hap_path) as archive:
                if "libs/arm64-v8a/libmatrix_native.so" in archive.namelist():
                    native_library_packaged = True
                    break
        except zipfile.BadZipFile:
            continue
    sdk_linked = sdk_dependency and sdk_reports_linked and native_library_packaged
    if not sdk_linked:
        failures.append("Matrix Rust SDK is not linked and packaged in the OpenHarmony native bridge")

    client_runtime_exports = (
        "createClient" in addon_text
        and "releaseClient" in addon_text
        and bool(CLIENT_CREATE_EXPORT.search(rust_text))
        and bool(CLIENT_RELEASE_EXPORT.search(rust_text))
    )
    native_runtime_ready = sdk_linked and client_runtime_exports
    if sdk_linked and not client_runtime_exports:
        failures.append("Matrix SDK is linked, but the production client handle lifecycle is not implemented")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures else "FAIL",
        "source_tag": inventory.get("android_tag"),
        "source_commit": inventory.get("android_commit"),
        "module_count": len(modules),
        "mapped_count": len(modules) - len(missing_mappings),
        "disposition_counts": disposition_counts,
        "missing_mappings": missing_mappings,
        "invalid_mappings": invalid_mappings,
        "missing_evidence": missing_evidence,
        "production_fixture_files": sorted(set(production_fixture_files)),
        "production_fixture_imports": sorted(set(production_fixture_imports)),
        "native_sdk_linked": sdk_linked,
        "native_library_packaged": native_library_packaged,
        "native_client_lifecycle_ready": client_runtime_exports,
        "native_runtime_ready": native_runtime_ready,
        "semantic_ready": semantic_ready,
        "semantic_total": semantic_total,
        "semantic_passed": semantic_passed,
        "hap_files": [str(path.relative_to(ROOT)) for path in hap_files],
        "failures": failures,
    }


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# Full Reconstruction Audit",
        "",
        f"- Status: **{report['status']}**",
        f"- Android source: `{report['source_tag']}` / `{report['source_commit']}`",
        f"- Production modules: {report['module_count']}",
        f"- Mapped modules: {report['mapped_count']}",
        f"- Matrix native runtime ready: {report['native_runtime_ready']}",
        f"- Cross-platform semantic suite: {report['semantic_passed']}/{report['semantic_total']}",
        "",
        "## Blocking Failures",
        "",
    ]
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Dispositions", "", f"`{report['disposition_counts']}`", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=VERIFICATION / "full-reconstruction-audit.json")
    parser.add_argument("--markdown", type=Path, default=VERIFICATION / "full-reconstruction-audit.md")
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    report = audit()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown)
    print(json.dumps({key: report[key] for key in ("status", "module_count", "mapped_count", "failures")}, indent=2))
    return 0 if report["status"] == "PASS" or args.allow_incomplete else 1


if __name__ == "__main__":
    raise SystemExit(main())
