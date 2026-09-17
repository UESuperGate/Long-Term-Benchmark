from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
ANDROID_MATRIX_CLIENT = ROOT / "_sources" / "element-x-android" / "libraries" / "matrix" / "api" / "src" / "main" / "kotlin" / "io" / "element" / "android" / "libraries" / "matrix" / "api" / "MatrixClient.kt"
HARMONY_CLIENT = ROOT / "elementx_harmony_client"
ARKTS_CONTRACT = HARMONY_CLIENT / "entry" / "src" / "main" / "ets" / "services" / "MatrixClientContract.ets"
SERVICE_FILE = HARMONY_CLIENT / "entry" / "src" / "main" / "ets" / "services" / "MatrixClientService.ets"
SERVER_API_FILE = HARMONY_CLIENT / "entry" / "src" / "main" / "ets" / "services" / "MatrixClientServerApi.ets"
SYNC_MAPPER_FILE = HARMONY_CLIENT / "entry" / "src" / "main" / "ets" / "services" / "MatrixSyncMapper.ets"
REPORT_DIR = ROOT / "verification_reports"
JSON_REPORT = REPORT_DIR / "production_readiness.json"
MD_REPORT = REPORT_DIR / "production_readiness.md"


FLOW_SUBSTITUTIONS = {
    "getRoomInfoFlow": "getRoomInfoFlowSnapshot",
    "sendQueueDisabledFlow": "sendQueueDisabledSnapshot",
}

EXPECTED_SERVICE_PROPERTIES = {
    "sessionPaths",
    "userProfile",
    "roomListService",
    "spaceService",
    "sessionVerificationService",
    "pushersService",
    "notificationService",
    "notificationSettingsService",
    "encryptionService",
    "roomDirectoryService",
    "messageSearchService",
    "mediaPreviewService",
    "matrixMediaLoader",
    "sessionCoroutineScope",
    "ignoredUsersFlow",
    "roomMembershipObserver",
    "ownBeaconInfoUpdates",
    "contentScanner",
}

REQUIRED_NATIVE_HINTS = (
    ".so",
    "napi",
    "native",
    "matrix-rust-sdk",
    "rust",
)

REST_CAPABILITIES = {
    "homeserver_discovery": ("/.well-known/matrix/client",),
    "versions": ("/_matrix/client/versions",),
    "password_login": ("/_matrix/client/v3/login", "m.login.password"),
    "sync": ("/_matrix/client/v3/sync",),
    "send_message": ("/send/", "m.room.message"),
    "media_upload": ("/_matrix/media", "upload"),
    "receipts": ("/receipt/", "m.read"),
    "profile": ("/profile/", "displayname"),
    "room_moderation": ("inviteUser", "kickUser", "banUser", "unbanUser", "reportRoom"),
    "account_data": ("/account_data/",),
    "join_room": ("/join/",),
    "create_room": ("/createRoom",),
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def kotlin_interface_body(source: str) -> str:
    match = re.search(r"interface\s+MatrixClient\s*:\s*ClientUrlContentFetcher\s*\{(?P<body>.*)\n\}", source, re.S)
    if not match:
        return source
    body = match.group("body")
    extension_index = body.find("\n/**\n * Returns a room alias")
    if extension_index >= 0:
        return body[:extension_index]
    return body


def arkts_interface_body(source: str) -> str:
    match = re.search(r"export\s+interface\s+MatrixClientContract\s*\{(?P<body>.*?)\n\}", source, re.S)
    if not match:
        return source
    return match.group("body")


def sorted_unique(items: Iterable[str]) -> list[str]:
    return sorted(set(items))


def extract_kotlin_surface(source: str) -> dict[str, list[str]]:
    body = kotlin_interface_body(source)
    props = re.findall(r"^\s*val\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", body, re.M)
    methods = re.findall(r"^\s*(?:suspend\s+)?fun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", body, re.M)
    return {
        "properties": sorted_unique(props),
        "methods": sorted_unique(methods),
    }


def extract_arkts_surface(source: str) -> dict[str, list[str]]:
    body = arkts_interface_body(source)
    props = re.findall(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:", body, re.M)
    methods = re.findall(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*\(", body, re.M)
    return {
        "properties": sorted_unique(props),
        "methods": sorted_unique(methods),
    }


def source_files(root: Path) -> list[Path]:
    ignored_parts = {"build", ".hvigor", "oh_modules", ".preview"}
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ignored_parts.intersection(path.parts):
            continue
        result.append(path)
    return result


def has_native_bridge(files: list[Path]) -> tuple[bool, list[str]]:
    hits: list[str] = []
    for path in files:
        lower_name = path.name.lower()
        lower_path = str(path).lower()
        if any(hint in lower_name or hint in lower_path for hint in REQUIRED_NATIVE_HINTS):
            hits.append(str(path.relative_to(ROOT)))
    return bool(hits), sorted_unique(hits)


def file_contains(path: Path, tokens: Iterable[str]) -> bool:
    if not path.exists():
        return False
    text = read_text(path)
    return all(token in text for token in tokens)


def rest_capability_status() -> dict[str, bool]:
    if not SERVER_API_FILE.exists():
        return {name: False for name in REST_CAPABILITIES}
    text = read_text(SERVER_API_FILE)
    return {
        name: all(token in text for token in tokens)
        for name, tokens in REST_CAPABILITIES.items()
    }


def production_areas(
    missing_service_properties: list[str],
    missing_methods: list[str],
    extra_properties: list[str],
    extra_methods: list[str],
    substituted_flows: dict[str, str],
    native_bridge_present: bool,
    native_bridge_hits: list[str],
    rest_status: dict[str, bool],
) -> list[dict[str, object]]:
    service_file_text = read_text(SERVICE_FILE) if SERVICE_FILE.exists() else ""
    sync_mapper_text = read_text(SYNC_MAPPER_FILE) if SYNC_MAPPER_FILE.exists() else ""

    fixture_tokens = [
        "FixtureMatrixClientAdapter",
        "fixtureRooms",
        "getFixtureTimelineEvents",
        "accessToken.length === 0",
    ]
    fixture_hits = [token for token in fixture_tokens if token in service_file_text]

    crypto_tokens = [
        "encryptionService",
        "Olm",
        "Megolm",
        "cross-signing",
        "key backup",
    ]
    crypto_hits = [
        token
        for token in crypto_tokens
        if token in service_file_text or (ARKTS_CONTRACT.exists() and token in read_text(ARKTS_CONTRACT))
    ]

    sync_tokens = ["m.room.message", "m.room.name", "m.room.topic", "m.receipt"]
    sync_hits = [token for token in sync_tokens if token in sync_mapper_text]

    passed_rest = [name for name, ok in rest_status.items() if ok]
    missing_rest = [name for name, ok in rest_status.items() if not ok]

    return [
        {
            "area": "Android MatrixClient API surface",
            "status": "partial",
            "evidence": {
                "missing_service_properties": missing_service_properties,
                "missing_methods": missing_methods,
                "extra_properties": extra_properties,
                "extra_methods": extra_methods,
                "flow_substitutions": substituted_flows,
            },
            "required_for_production": "Expose the same session-scoped services and live Flow/StateFlow semantics, not only synchronous snapshots.",
        },
        {
            "area": "Matrix Rust SDK binding",
            "status": "missing" if not native_bridge_present else "partial",
            "evidence": {
                "native_bridge_files": native_bridge_hits,
            },
            "required_for_production": "Provide a Harmony native bridge or full ArkTS SDK implementation for sync, crypto, timeline, media, room list, verification, push and storage.",
        },
        {
            "area": "End-to-end encryption and verification",
            "status": "missing" if not crypto_hits else "partial",
            "evidence": {
                "found_tokens": crypto_hits,
            },
            "required_for_production": "Implement Olm/Megolm sessions, cross-signing, secret storage, recovery, key backup, encrypted media and device verification.",
        },
        {
            "area": "Client-Server REST subset",
            "status": "partial",
            "evidence": {
                "implemented_capabilities": passed_rest,
                "missing_checked_capabilities": missing_rest,
            },
            "required_for_production": "Complete Matrix Client-Server coverage used by Element X, with spec-compliant retries, pagination, errors and capability negotiation.",
        },
        {
            "area": "Sync, room list and timeline model",
            "status": "partial",
            "evidence": {
                "sync_mapper_tokens": sync_hits,
                "fixture_tokens": fixture_hits,
            },
            "required_for_production": "Replace fixture rooms/timeline paths with persistent, incremental, encrypted-capable sync and room-list services.",
        },
        {
            "area": "Secure session storage",
            "status": "partial",
            "evidence": {
                "preferences_store": file_contains(HARMONY_CLIENT / "entry" / "src" / "main" / "ets" / "services" / "PersistentSessionStore.ets", ["@ohos.data.preferences"]),
                "secure_store": file_contains(HARMONY_CLIENT / "entry" / "src" / "main" / "ets" / "services" / "PersistentSessionStore.ets", ["keychain", "credential", "keystore", "cryptoFramework"]),
            },
            "required_for_production": "Move access tokens, device ids and cryptographic material into platform-secure storage with migration and wipe behavior.",
        },
        {
            "area": "Push, notification rules and media pipeline",
            "status": "partial",
            "evidence": {
                "missing_service_properties": [
                    item
                    for item in missing_service_properties
                    if item in {"pushersService", "notificationService", "notificationSettingsService", "mediaPreviewService", "matrixMediaLoader"}
                ],
            },
            "required_for_production": "Implement pushers, notification rule editing, event rendering, MXC download/cache, thumbnailing and encrypted media handling.",
        },
        {
            "area": "Production tests",
            "status": "partial",
            "evidence": {
                "existing_dynamic_reports": sorted_unique(
                    str(path.relative_to(ROOT))
                    for path in (ROOT / "verification_reports").glob("full_client_*/*.md")
                ),
            },
            "required_for_production": "Add live homeserver, offline/restore, encrypted room, media, verification, push and migration tests, then make this audit pass.",
        },
    ]


def render_markdown(report: dict[str, object]) -> str:
    lines: list[str] = [
        "# Element X Harmony Production Readiness",
        "",
        f"Overall status: **{report['overall_status']}**",
        "",
        "This audit compares the Android `MatrixClient.kt` surface and expected Matrix Rust SDK-backed behavior with the current ArkTS Harmony client.",
        "",
        "## API surface",
        "",
        f"- Android properties: {report['android_surface']['property_count']}",
        f"- ArkTS properties: {report['arkts_surface']['property_count']}",
        f"- Missing Android service properties in ArkTS: {len(report['api_gaps']['missing_service_properties'])}",
        f"- Extra ArkTS properties not present in Android MatrixClient: {len(report['api_gaps']['extra_properties'])}",
        f"- Android methods: {report['android_surface']['method_count']}",
        f"- ArkTS methods: {report['arkts_surface']['method_count']}",
        f"- Missing Android method names in ArkTS: {len(report['api_gaps']['missing_methods'])}",
        f"- Extra ArkTS method names not present in Android MatrixClient: {len(report['api_gaps']['extra_methods'])}",
        "",
    ]

    if report["api_gaps"]["missing_service_properties"]:
        lines.append("Missing service properties:")
        lines.extend(f"- `{name}`" for name in report["api_gaps"]["missing_service_properties"])
        lines.append("")

    if report["api_gaps"]["missing_methods"]:
        lines.append("Missing method names:")
        lines.extend(f"- `{name}`" for name in report["api_gaps"]["missing_methods"])
        lines.append("")

    if report["api_gaps"]["extra_properties"]:
        lines.append("Extra ArkTS properties:")
        lines.extend(f"- `{name}`" for name in report["api_gaps"]["extra_properties"])
        lines.append("")

    if report["api_gaps"]["extra_methods"]:
        lines.append("Extra ArkTS method names:")
        lines.extend(f"- `{name}`" for name in report["api_gaps"]["extra_methods"])
        lines.append("")

    if report["api_gaps"]["flow_substitutions"]:
        lines.append("Synchronous substitutions that are not production-equivalent to Android Flow/StateFlow:")
        for android_name, arkts_name in report["api_gaps"]["flow_substitutions"].items():
            lines.append(f"- `{android_name}` is represented as `{arkts_name}`")
        lines.append("")

    lines.extend(["## Production areas", ""])
    for area in report["production_areas"]:
        lines.append(f"### {area['area']}")
        lines.append(f"Status: **{area['status']}**")
        lines.append("")
        lines.append(f"Required for production: {area['required_for_production']}")
        lines.append("")

    lines.extend(
        [
            "## Gate result",
            "",
            "This audit intentionally exits non-zero until the Harmony client has a real Matrix SDK/Rust SDK-equivalent implementation and the remaining fixture paths are removed or limited to tests.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    missing_inputs = [path for path in (ANDROID_MATRIX_CLIENT, ARKTS_CONTRACT) if not path.exists()]
    if missing_inputs:
        for path in missing_inputs:
            print(f"Missing required input: {path}", file=sys.stderr)
        return 2

    android_surface = extract_kotlin_surface(read_text(ANDROID_MATRIX_CLIENT))
    arkts_surface = extract_arkts_surface(read_text(ARKTS_CONTRACT))

    missing_service_properties = sorted(
        prop for prop in EXPECTED_SERVICE_PROPERTIES if prop not in set(arkts_surface["properties"])
    )
    missing_methods = sorted(
        method
        for method in android_surface["methods"]
        if method not in set(arkts_surface["methods"]) and method not in FLOW_SUBSTITUTIONS
    )
    extra_properties = sorted(
        prop for prop in arkts_surface["properties"] if prop not in set(android_surface["properties"])
    )
    extra_methods = sorted(
        method for method in arkts_surface["methods"] if method not in set(android_surface["methods"])
    )
    substituted_flows = {
        android_name: arkts_name
        for android_name, arkts_name in FLOW_SUBSTITUTIONS.items()
        if android_name in android_surface["methods"]
        and android_name not in arkts_surface["methods"]
        and arkts_name in arkts_surface["methods"]
    }

    files = source_files(HARMONY_CLIENT)
    native_bridge_present, native_bridge_hits = has_native_bridge(files)
    rest_status = rest_capability_status()

    areas = production_areas(
        missing_service_properties,
        missing_methods,
        extra_properties,
        extra_methods,
        substituted_flows,
        native_bridge_present,
        native_bridge_hits,
        rest_status,
    )

    blockers = [
        area
        for area in areas
        if area["status"] in {"missing", "partial"}
    ]

    report: dict[str, object] = {
        "overall_status": "NOT_PRODUCTION_READY" if blockers else "PRODUCTION_READY",
        "android_source": str(ANDROID_MATRIX_CLIENT),
        "arkts_source": str(ARKTS_CONTRACT),
        "android_surface": {
            "property_count": len(android_surface["properties"]),
            "method_count": len(android_surface["methods"]),
            "properties": android_surface["properties"],
            "methods": android_surface["methods"],
        },
        "arkts_surface": {
            "property_count": len(arkts_surface["properties"]),
            "method_count": len(arkts_surface["methods"]),
            "properties": arkts_surface["properties"],
            "methods": arkts_surface["methods"],
        },
        "api_gaps": {
            "missing_service_properties": missing_service_properties,
            "missing_methods": missing_methods,
            "extra_properties": extra_properties,
            "extra_methods": extra_methods,
            "flow_substitutions": substituted_flows,
        },
        "rest_capabilities": rest_status,
        "production_areas": areas,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MD_REPORT.write_text(render_markdown(report) + "\n", encoding="utf-8")

    print(f"Wrote {JSON_REPORT}")
    print(f"Wrote {MD_REPORT}")
    print(f"Overall status: {report['overall_status']}")
    return 1 if report["overall_status"] != "PRODUCTION_READY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
