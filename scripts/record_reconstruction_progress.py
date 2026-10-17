#!/usr/bin/env python3
"""Record reviewed partial migration evidence without claiming full parity."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "elementx_harmony_full" / "verification" / "migration-map.json"

GROUPS = (
    (
        {"app", "appnav", "services/appnavstate/api", "services/appnavstate/impl"},
        [
            "entry/src/main/ets/appshell/AppShellCoordinator.ets",
            "entry/src/main/ets/pages/ReconstructedRoot.ets",
            "entry/src/main/ets/entryability/EntryAbility.ets",
        ],
        ["AppShellCoordinator", "ReconstructedRoot", "EntryAbility"],
        ["elementx_harmony_full/entry/src/test/AppShellHarness.test.ets"],
        "Production app-shell and navigation state transitions are implemented, but the complete Android navigation graph is not yet ported.",
    ),
    (
        {"features/login/api", "features/login/impl", "libraries/session-storage/api", "libraries/session-storage/impl"},
        [
            "entry/src/main/ets/features/login/PasswordLoginCoordinator.ets",
            "entry/src/main/ets/matrix/production/NativeMatrixAuthenticationService.ets",
            "entry/src/main/ets/session/SessionPersistence.ets",
        ],
        ["PasswordLoginCoordinator", "NativeMatrixAuthenticationService", "SessionPersistence"],
        ["elementx_harmony_full/entry/src/test/ProductionAuthentication.test.ets"],
        "Password authentication and separated credential persistence are implemented; OIDC and full multi-account lifecycle remain incomplete.",
    ),
    (
        {"features/home/api", "features/home/impl", "features/messages/api", "features/messages/impl"},
        [
            "entry/src/main/ets/rooms/RoomListController.ets",
            "entry/src/main/ets/timeline/TimelineController.ets",
            "entry/src/main/ets/matrix/production/NativeRoomListDataSource.ets",
            "entry/src/main/ets/matrix/production/NativeTimelineDataSource.ets",
        ],
        ["RoomListController", "TimelineController", "NativeRoomListDataSource", "NativeTimelineDataSource"],
        [
            "elementx_harmony_full/entry/src/test/RoomTimelineDomain.test.ets",
            "elementx_harmony_full/entry/src/test/ProductionRoomTransport.test.ets",
            "elementx_harmony_full/entry/src/test/ProductionTimelineTransport.test.ets",
        ],
        "Room-list sync, backward timeline pagination, and text sending use the production Matrix SDK bridge; live updates, rich messages, encryption, receipts, and the complete message surface remain incomplete.",
    ),
    (
        {"features/verifysession/api", "features/verifysession/impl", "features/linknewdevice/api", "features/linknewdevice/impl"},
        [
            "entry/src/main/ets/security/VerificationController.ets",
            "entry/src/main/ets/features/linknewdevice/LinkNewDeviceController.ets",
        ],
        ["VerificationController", "LinkNewDeviceController"],
        ["elementx_harmony_full/entry/src/test/SecurityDomain.test.ets"],
        "Verification and device-link transition logic is implemented; SDK-backed SAS/QR protocol execution remains incomplete.",
    ),
    (
        {"features/location/api", "features/location/impl", "libraries/mediaviewer/api", "libraries/mediaviewer/impl", "libraries/matrixmedia/api", "libraries/matrixmedia/impl"},
        [
            "entry/src/main/ets/features/location/LiveLocationController.ets",
            "entry/src/main/ets/media/MediaGalleryController.ets",
            "entry/src/main/ets/media/MediaRepositoryController.ets",
        ],
        ["LiveLocationController", "MediaGalleryController", "MediaRepositoryController"],
        ["elementx_harmony_full/entry/src/test/MediaFeatureDomain.test.ets"],
        "Location and media domain controllers are implemented; production upload/download, map, and viewer integrations remain incomplete.",
    ),
    (
        {"features/roomdetails/api", "features/roomdetails/impl", "features/roomdetailsedit/api", "features/roomdetailsedit/impl", "features/space/api", "features/space/impl"},
        [
            "entry/src/main/ets/features/roommanagement/RoomManagementController.ets",
            "entry/src/main/ets/features/spaces/SpacesController.ets",
        ],
        ["RoomManagementController", "SpacesController"],
        ["elementx_harmony_full/entry/src/test/RoomManagementDomain.test.ets"],
        "Room management and space transition logic is implemented; complete SDK-backed details, moderation, search, and hierarchy flows remain incomplete.",
    ),
    (
        {"libraries/matrix/api", "libraries/matrix/impl"},
        [
            "entry/src/main/ets/nativebridge/AddonNativeMatrixBridge.ets",
            "native/matrix-sdk-bridge/src/lib.rs",
        ],
        ["AddonNativeMatrixBridge", "elementx_matrix_bridge_create_client"],
        ["elementx_harmony_full/entry/src/test/ProductionAuthentication.test.ets"],
        "Matrix Rust SDK 0.16.0 client lifecycle, authentication, room sync, timeline history, and text send bridge are implemented; the full Matrix service surface is not yet exposed.",
    ),
)


def main() -> int:
    payload = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    evidence: dict[str, tuple[list[str], list[str], list[str], str]] = {}
    for modules, target_paths, target_symbols, tests, reason in GROUPS:
        for module in modules:
            evidence[module] = (target_paths, target_symbols, tests, reason)
    updated = 0
    for item in payload.get("mappings", []):
        source_module = str(item.get("source_module", ""))
        if source_module not in evidence:
            continue
        target_paths, target_symbols, tests, reason = evidence[source_module]
        item["disposition"] = "partial"
        item["reason"] = reason
        item["target_modules"] = ["entry"]
        item["target_paths"] = target_paths
        item["target_symbols"] = target_symbols
        item["tests"] = tests
        item["notes"] = "Partial evidence only; strict parity remains fail-closed."
        updated += 1
    MAP_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded partial evidence for {updated} Android modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
