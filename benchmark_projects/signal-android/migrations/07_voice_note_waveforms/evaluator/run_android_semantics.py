#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

ADB = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))) / "platform-tools/adb"
SERIAL = os.environ.get("ANDROID_SERIAL", "emulator-5554")
RUNNER = "org.signal.benchmark.waveform.evaluator.VoiceWaveformInstrumentation"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def adb(*parts: str, timeout: int = 90, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(ADB), "-s", SERIAL, *parts], text=True, capture_output=True, timeout=timeout, check=check)


def encode(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def app_id(project: Path) -> str:
    for relative in ("app/build.gradle.kts", "app/build.gradle"):
        source = project / relative
        if not source.is_file():
            continue
        match = re.search(r"applicationId\s*(?:=\s*)?['\"]([^'\"]+)['\"]", source.read_text())
        if match:
            return match.group(1)
    raise RuntimeError("applicationId missing")


def obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def arr(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def near(value: Any, expected: float) -> bool:
    return isinstance(value, (int, float)) and abs(float(value) - expected) < 1e-6


def effect_names(episode: dict[str, Any]) -> list[str]:
    return [str(item.get("name")) for item in arr(obj(episode.get("observed")).get("effects")) if isinstance(item, dict)]


def semantic_checks(key: str, episode: dict[str, Any]) -> list[bool]:
    observed = obj(episode.get("observed"))
    state = obj(observed.get("state"))
    persistence = obj(observed.get("persistence"))
    stored = obj(persistence.get("waveform"))
    effects = arr(observed.get("effects"))
    names = effect_names(episode)
    checkpoint = obj(episode.get("checkpoint"))
    checkpoint_state = obj(checkpoint.get("state"))
    if key == "generate_upload_ready_waveform":
        bars = arr(obj(state.get("storedWaveform")).get("bytes"))
        return [len(bars) == 100 and set(bars) == {255}, obj(state.get("storedWaveform")).get("senderProvided") is False,
                names == ["persistGenerationPlaceholder", "decodeAudio", "persistGeneratedWaveform"]]
    if key == "audio_upload_waits_for_waveform":
        held = obj(checkpoint_state.get("upload"))
        final = obj(state.get("upload"))
        return [held.get("compression") == "complete" and held.get("upload") == "not_started",
                held.get("waveformGeneration") == "running" and final.get("waveformGeneration") == "complete",
                names == ["compressAttachment", "generateWaveform", "uploadAttachment"] and final.get("upload") == "complete"]
    if key == "mixed_uploads_gate_only_audio":
        held = obj(checkpoint_state.get("uploads")); audio = obj(held.get("audio-3")); image = obj(held.get("image-3"))
        return [audio.get("upload") == "not_started" and image.get("upload") == "complete",
                image.get("waveformGeneration") == "not_scheduled" and sum(1 for item in effects if obj(item).get("name") == "generateWaveform" and obj(item).get("attachmentId") == "image-3") == 0,
                obj(obj(state.get("uploads")).get("audio-3")).get("upload") == "complete" and names.count("uploadAttachment") == 2]
    if key == "outgoing_pointer_carries_waveform":
        pointer = obj(state.get("pointer"))
        return [pointer.get("audioWaveform") == [0, 64, 128, 255] and near(pointer.get("audioDurationSeconds"), 12.5),
                pointer.get("cdnKey") == "cdn-key-4" and pointer.get("encryptionDigest") == "digest-4",
                names == ["buildAttachmentPointer"]]
    if key == "reject_oversized_remote_waveform":
        validation = obj(state.get("validation"))
        return [validation.get("accepted") is False and validation.get("reason") == "oversized_audio_waveform",
                "waveform" not in persistence, not any(name in names for name in ("persistAttachment", "renderWaveform"))]
    if key == "persist_valid_sender_waveform":
        persisted = obj(obj(state.get("persistedAttachment")).get("waveform")); reloaded = obj(obj(state.get("reloadedAttachment")).get("waveform"))
        return [persisted.get("bytes") == [0, 64, 128, 255] and near(persisted.get("durationSeconds"), 3.25),
                persisted.get("senderProvided") is True and reloaded == persisted,
                "generateWaveform" not in names and names == ["persistAttachment"]]
    if key == "resample_sender_waveform_without_media":
        bars = arr(state.get("renderWaveform"))
        return [state.get("result") == "success" and len(bars) == 46,
                all(near(value, 0.0) for value in bars[:23]) and all(near(value, 1.0) for value in bars[23:]),
                "generateWaveform" not in names and stored.get("senderProvided") is True]
    if key == "regenerate_stale_local_waveform":
        replacement = obj(state.get("persistedReplacement")); bars = arr(replacement.get("bytes")); render = arr(state.get("renderWaveform"))
        return [len(bars) == 100 and set(bars) == {255} and replacement.get("senderProvided") is False,
                names.count("generateWaveform") == 1 and names.count("persistGeneratedWaveform") == 1,
                len(render) == 46 and all(near(value, 1.0) for value in render)]
    if key == "recover_empty_generation_placeholder":
        replacement = obj(state.get("persistedReplacement")); bars = arr(replacement.get("bytes")); render = arr(state.get("renderWaveform"))
        return [len(bars) == 100 and bars[:50] == [0] * 50 and bars[50:] == [255] * 50,
                names.count("generateWaveform") == 1 and names.count("persistGeneratedWaveform") == 1,
                len(render) == 46 and all(near(value, 0.0) for value in render[:23]) and all(near(value, 1.0) for value in render[23:]) and "uploadAttachment" not in names]
    exported = obj(state.get("exportedFilePointer")); restored = obj(obj(state.get("restoredAttachment")).get("waveform")); rendered = obj(state.get("renderAfterRestore")); bars = arr(rendered.get("bars"))
    return [exported.get("audioWaveform") == [0, 85, 170, 255] and near(exported.get("audioDurationSeconds"), 8.5),
            restored.get("bytes") == [0, 85, 170, 255] and restored.get("senderProvided") is True,
            rendered.get("result") == "success" and len(bars) == 46 and near(bars[0], 0.0) and near(bars[-1], 1.0) and "generateWaveform" not in names]


def run(project: Path, role: str, output: Path) -> int:
    migration = Path(__file__).resolve().parents[1]
    contract = json.loads((migration / "canonical/transitions.json").read_text())
    app_apk = project / "app/build/outputs/apk/debug/app-debug.apk"
    test_apk = project / "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
    package = app_id(project); test_package = package + ".test"
    rows: list[dict[str, Any]] = []; episodes: list[dict[str, Any]] = []
    installed = False; error = ""; api_level: int | None = None
    externally_locked = os.environ.get("LTB_ANDROID_DEVICE_LOCK_HELD") == "1"
    lock_context = contextlib.nullcontext(None) if externally_locked else open("/tmp/long-term-benchmark-android-device.lock", "a+")
    with lock_context as lock:
        if lock is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if not app_apk.is_file() or not test_apk.is_file(): raise RuntimeError("application or instrumentation APK missing")
            api_level = int(adb("shell", "getprop", "ro.build.version.sdk").stdout.strip())
            if api_level != 37: raise RuntimeError(f"expected Android API 37, found {api_level}")
            adb("install", "-r", "-t", str(app_apk), timeout=180); adb("install", "-r", "-t", str(test_apk), timeout=180); installed = True
            for case in contract["cases"]:
                call = adb("shell", "am", "instrument", "-w", "-e", "caseKey", case["key"], "-e", "given", encode(case["given"]), "-e", "event", encode(case["event"]), f"{test_package}/{RUNNER}", timeout=90, check=False)
                if call.returncode != 0 or "INSTRUMENTATION_CODE: 0" not in call.stdout:
                    rows.append({"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": "not_scored", "reason": (call.stdout + call.stderr).strip()})
                    continue
                episode = json.loads(adb("exec-out", "run-as", package, "cat", "files/runtime-episode.json").stdout)
                episodes.append({"caseId": case["caseId"], "episode": episode, "instrumentation": call.stdout})
                values = semantic_checks(case["key"], episode)
                invariant_checks = [{"invariant": text, "passed": values[index], "evidence": {"before": episode.get("before"), "checkpoint": episode.get("checkpoint"), "after": episode.get("after")}} for index, text in enumerate(case["invariants"])]
                bound = episode.get("given") == case["given"] and episode.get("event") == case["event"] and episode.get("givenEstablished") is True and bool(episode.get("pageOwnerId")) and episode.get("transitionExecuted") is True and episode.get("storageReopened") is True and bool(episode.get("productionCalls"))
                passed = bound and all(values) and all(item["passed"] for item in invariant_checks)
                rows.append({"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": "pass" if passed else "fail", "observed": episode.get("observed"), "checkpoints": [{"label": "before", "state": episode.get("before")}, {"label": "held", "state": episode.get("checkpoint")}, {"label": "after", "state": episode.get("after")}], "invariantChecks": invariant_checks, "runtimeBoundaryChecks": {"canonicalInputBound": bound, "pageOwnerId": episode.get("pageOwnerId"), "productionCalls": episode.get("productionCalls")}})
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as failure:
            error = str(failure)
            rows = [{"caseId": case["caseId"], "key": case["key"], "traceDigest": case["traceDigest"], "status": "not_scored", "reason": error} for case in contract["cases"]]
        finally:
            if installed:
                adb("uninstall", test_package, check=False); adb("uninstall", package, check=False)
    raw = output.with_suffix(".raw.json"); raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps({"schemaVersion": 1, "taskId": contract["taskId"], "platform": "android", "role": role, "episodes": episodes}, indent=2) + "\n")
    count = lambda status: sum(row["status"] == status for row in rows)
    artifacts = [{"name": path.name, "sha256": sha256(path), "bytes": path.stat().st_size} for path in (app_apk, test_apk) if path.is_file()]
    report = {"schemaVersion": 1, "taskId": contract["taskId"], "platform": "android", "role": role, "observationMode": "runtime_state_transition", "runtime": "Android API37 Activity page owner plus instrumentation", "compile": {"passed": len(artifacts) == 2, "artifacts": artifacts}, "semantic": {"passed": count("pass"), "failed": count("fail"), "notScored": count("not_scored"), "total": len(rows), "cases": rows}, "diagnostics": {"adapter": "ready" if not error else "unavailable", "transport": "adb_instrumentation", "deviceSerial": SERIAL, "deviceApi": api_level, "sourceObserver": False, "rawEvidence": {"path": raw.name, "sha256": sha256(raw), "bytes": raw.stat().st_size}}}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if not error and count("not_scored") == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--project", type=Path, required=True); parser.add_argument("--role", choices=("base", "final", "agent"), required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    return run(args.project.resolve(), args.role, args.output.resolve())


if __name__ == "__main__": raise SystemExit(main())
