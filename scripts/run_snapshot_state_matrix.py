#!/usr/bin/env python3
"""Run evaluator-owned state tests across Android and ArkTS targets.

ArkTS execution uses a phase protocol: launch the fixture, poll for readiness,
capture initial state, inject each transition through the stateEvent Want
parameter, and capture a fresh layout after every transition.
"""

from __future__ import annotations

import argparse
import html
import json
import locale
import os
import re
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(os.environ.get("QINGYU_BENCH_ROOT", r"C:\Users\xiexi\qingyu"))
ANDROID_SDK = Path(os.environ.get("ANDROID_HOME", r"C:\Users\xiexi\AppData\Local\Android\Sdk"))
ADB = ANDROID_SDK / "platform-tools" / "adb.exe"
HDC = Path(os.environ.get("QINGYU_HDC", r"C:\Users\xiexi\AppData\Local\OpenHarmony\Sdk\23\toolchains\hdc.exe"))
BINDINGS = ROOT / "state_tests" / "bindings"


def decode_process_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    for encoding in ("utf-8-sig", "utf-8", locale.getpreferredencoding(False), "gbk"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        process = subprocess.run(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return process.returncode, decode_process_output(process.stdout)
    except subprocess.TimeoutExpired as exc:
        return 124, decode_process_output(exc.stdout) + f"\nTIMEOUT after {timeout}s"


def ps_safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:140]


def selector_facts(selectors: dict[str, Any], prefix: str = "") -> list[str]:
    out: list[str] = []
    for bucket in ("visible", "hidden", "enabled", "disabled"):
        out.extend(f"{prefix}{bucket}:{token}" for token in selectors.get(bucket) or [])
    for key, value in (selectors.get("properties") or {}).items():
        out.append(f"{prefix}property:{key}={value}")
    return sorted(set(out))


def transition_facts(transition: dict[str, Any]) -> list[str]:
    ordinal = transition.get("ordinal")
    event = str(transition.get("event") or "")
    prefix = f"transition:{ordinal}:"
    out = selector_facts(transition, prefix)
    if ordinal and event:
        out.append(f"{prefix}{event}")
    return sorted(set(out))


def expected_facts(case: dict[str, Any]) -> list[str]:
    out = selector_facts(case.get("selectors") or {})
    for transition in case.get("transitionSelectors") or []:
        out.extend(transition_facts(transition))
    return sorted(set(out))


def parse_snapshot_payload(value: str) -> dict[str, Any] | None:
    raw = html.unescape(value).strip()
    for prefix in ("state_probe_snapshot:", "snapshot="):
        if prefix in raw:
            raw = raw.split(prefix, 1)[1].strip()
    raw = raw.rstrip('\",')
    decoder = json.JSONDecoder()
    candidates = [raw]
    if '\\"' in raw:
        candidates.append(raw.replace('\\"', '"'))
    for candidate in candidates:
        start = candidate.find("{")
        if start < 0:
            continue
        try:
            parsed, _ = decoder.raw_decode(candidate[start:])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def walk_layout_values(node: Any) -> list[str]:
    values: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("text", "originalText", "Content") and isinstance(value, str):
                values.append(value)
            else:
                values.extend(walk_layout_values(value))
    elif isinstance(node, list):
        for item in node:
            values.extend(walk_layout_values(item))
    return values


def extract_snapshot_from_text(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
        for value in walk_layout_values(parsed):
            if "state_probe_snapshot:" in value or "snapshot=" in value:
                snapshot = parse_snapshot_payload(value)
                if snapshot:
                    return snapshot
    except Exception:
        pass
    patterns = [r"state_probe_snapshot:(\{.*?\})(?:[\"<\r\n]|$)", r"snapshot=(\{.*\})"]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            snapshot = parse_snapshot_payload(match.group(1))
            if snapshot:
                return snapshot
    for prefix in ("state_probe_snapshot:", "snapshot="):
        if prefix in text:
            snapshot = parse_snapshot_payload(text.split(prefix, 1)[1])
            if snapshot:
                return snapshot
    return None


def load_binding_cases() -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for path in sorted(BINDINGS.glob("*.binding.json")):
        if path.name == "state_binding_manifest_index.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for source in data.get("cases", []):
            case = dict(source)
            case["expectedInitialFacts"] = selector_facts(case.get("selectors") or {})
            case["expectedFacts"] = expected_facts(case)
            cases[case["caseId"]] = case
    return cases


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    return default


def iter_layout_attributes(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        attrs = node.get("attributes")
        if isinstance(attrs, dict):
            yield attrs | {"_extraAttrs": node.get("extraAttrs") or {}}
        for child in node.get("children") or []:
            yield from iter_layout_attributes(child)
    elif isinstance(node, list):
        for item in node:
            yield from iter_layout_attributes(item)


def parse_layout_nodes(text: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(text)
    except Exception:
        return []
    return list(iter_layout_attributes(parsed))


def node_matches(node: dict[str, Any], token: str) -> bool:
    values = [
        node.get("id"),
        node.get("key"),
        node.get("description"),
        node.get("text"),
        node.get("originalText"),
        (node.get("_extraAttrs") or {}).get("Content"),
    ]
    return any(str(value) == token for value in values if value not in (None, ""))


def node_values(node: dict[str, Any]) -> set[str]:
    return {
        str(value)
        for value in (
            node.get("text"),
            node.get("originalText"),
            node.get("description"),
            (node.get("_extraAttrs") or {}).get("Content"),
        )
        if value not in (None, "")
    }


def tree_selector_facts(layout_text: str, selectors: dict[str, Any]) -> set[str]:
    nodes = parse_layout_nodes(layout_text)
    facts: set[str] = set()
    for token in selectors.get("visible") or []:
        matches = [node for node in nodes if node_matches(node, str(token))]
        if any(as_bool(node.get("visible"), True) for node in matches):
            facts.add(f"visible:{token}")
    for token in selectors.get("hidden") or []:
        matches = [node for node in nodes if node_matches(node, str(token))]
        if not any(as_bool(node.get("visible"), True) for node in matches):
            facts.add(f"hidden:{token}")
    for token in selectors.get("enabled") or []:
        matches = [node for node in nodes if node_matches(node, str(token))]
        if any(as_bool(node.get("visible"), True) and as_bool(node.get("enabled"), False) for node in matches):
            facts.add(f"enabled:{token}")
    for token in selectors.get("disabled") or []:
        matches = [node for node in nodes if node_matches(node, str(token))]
        if any(not as_bool(node.get("enabled"), True) for node in matches):
            facts.add(f"disabled:{token}")
    for key, value in (selectors.get("properties") or {}).items():
        matches = [node for node in nodes if node_matches(node, str(key))]
        if any(str(value) in node_values(node) for node in matches):
            facts.add(f"property:{key}={value}")
    return facts


def snapshot_facts(snapshot: dict[str, Any] | None) -> set[str]:
    if not snapshot:
        return set()
    return {str(value) for value in snapshot.get("semanticFacts", []) or []}


def normalize_event(value: Any) -> str:
    return str(value or "").split("#", 1)[0]


def phase_observed_facts(
    snapshot: dict[str, Any] | None,
    layout_text: str,
    selectors: dict[str, Any],
    ordinal: int | None = None,
    event: str = "",
) -> set[str]:
    raw = snapshot_facts(snapshot)
    tree = tree_selector_facts(layout_text, selectors)
    if ordinal is None:
        return raw | tree
    prefix = f"transition:{ordinal}:"
    observed = {fact for fact in raw if fact.startswith(prefix)}
    observed.update(prefix + fact for fact in tree)
    observed.update(
        prefix + fact
        for fact in raw
        if fact.startswith(("visible:", "hidden:", "enabled:", "disabled:", "property:"))
    )
    acknowledged = any(
        normalize_event(snapshot.get(key) if snapshot else "") == event
        for key in ("lastEvent", "appliedEvent", "stateEvent")
    )
    if event and acknowledged:
        observed.add(prefix + event)
    return observed


def score_case(capture: dict[str, Any], expected: str, case: dict[str, Any], transition_mode: str) -> dict[str, Any]:
    initial = capture.get("initial") or {}
    initial_snapshot = initial.get("snapshot")
    initial_expected = case.get("expectedInitialFacts") or []
    initial_observed = phase_observed_facts(
        initial_snapshot,
        str(initial.get("layoutText") or ""),
        case.get("selectors") or {},
    )
    initial_missing = [fact for fact in initial_expected if fact not in initial_observed]
    phase_results: list[dict[str, Any]] = [{
        "phase": "initial",
        "expectedFacts": initial_expected,
        "observedFacts": sorted(initial_observed),
        "missingFacts": initial_missing,
        "readyObserved": bool(initial.get("readyObserved")),
        "captureStatus": initial.get("status"),
    }]
    all_missing = list(initial_missing)
    aggregate = snapshot_facts(initial_snapshot)
    transitions = case.get("transitionSelectors") or []
    captured_transitions = capture.get("transitions") or []
    for index, transition in enumerate(transitions):
        ordinal = int(transition.get("ordinal") or index + 1)
        event = str(transition.get("event") or "")
        expected_transition = transition_facts(transition)
        phase = captured_transitions[index] if index < len(captured_transitions) else {}
        observed = phase_observed_facts(
            phase.get("snapshot"),
            str(phase.get("layoutText") or ""),
            transition,
            ordinal,
            event,
        )
        legacy_fallback = False
        if transition_mode == "compatible":
            legacy = {fact for fact in aggregate if fact.startswith(f"transition:{ordinal}:")}
            if legacy:
                observed |= legacy
                legacy_fallback = True
        missing = [fact for fact in expected_transition if fact not in observed]
        all_missing.extend(missing)
        phase_results.append({
            "phase": f"transition_{ordinal}",
            "ordinal": ordinal,
            "event": event,
            "expectedFacts": expected_transition,
            "observedFacts": sorted(observed),
            "missingFacts": missing,
            "eventLaunchExit": phase.get("eventLaunchExit"),
            "readyObserved": bool(phase.get("readyObserved")),
            "captureStatus": phase.get("status"),
            "legacyAggregateFallback": legacy_fallback,
        })
    has_snapshot = isinstance(initial_snapshot, dict)
    ready = bool(initial.get("readyObserved"))
    observed = "pass" if has_snapshot and ready and bool(initial_expected or transitions) and not all_missing else "fail"
    if not has_snapshot or not ready:
        semantic_status = "not_scored"
        reason = "snapshot_or_ready_marker_missing"
        strict_status = "matched" if observed == expected else "protocolFail"
    else:
        semantic_status = "passed" if observed == "pass" else "failed"
        reason = "phase_semantic_facts"
        strict_status = "matched" if observed == expected else "mismatch"
    return {
        "observedPolarity": observed,
        "strictStatus": strict_status,
        "semanticStatus": semantic_status,
        "missingFacts": sorted(set(all_missing)),
        "reason": reason,
        "transitionMode": transition_mode,
        "phaseResults": phase_results,
    }


class Runner:
    def __init__(
        self,
        matrix: dict[str, Any],
        out_dir: Path,
        android_serial: str = "",
        ready_timeout: float = 12.0,
        transition_timeout: float = 6.0,
        poll_interval: float = 0.5,
        transition_mode: str = "strict",
    ) -> None:
        self.matrix = matrix
        self.out_dir = out_dir
        self.android_serial = android_serial
        self.ready_timeout = ready_timeout
        self.transition_timeout = transition_timeout
        self.poll_interval = poll_interval
        self.transition_mode = transition_mode
        self.case_bindings = load_binding_cases()
        self.installed_android_target = ""
        self.installed_arkts_target = ""

    def adb(self, args: list[str], timeout: int = 60) -> tuple[int, str]:
        cmd = [str(ADB)]
        if self.android_serial:
            cmd += ["-s", self.android_serial]
        return run(cmd + args, timeout=timeout)

    def hdc(self, args: list[str], timeout: int = 60) -> tuple[int, str]:
        return run([str(HDC)] + args, timeout=timeout)

    def android_capture(self, target: dict[str, Any], case_id: str, target_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        apk = Path(target["apk"])
        detail: dict[str, Any] = {"artifactExists": apk.exists(), "installed": False, "queryExit": None}
        if not apk.exists():
            return {"initial": {"status": "apk_missing"}, "transitions": []}, detail | {"status": "apk_missing"}
        if self.installed_android_target != target["targetId"]:
            self.adb(["uninstall", target["package"]], timeout=30)
            code, text = self.adb(["install", "-r", str(apk)], timeout=180)
            detail["installText"] = text
            if "Success" not in text:
                return {"initial": {"status": "install_failed"}, "transitions": []}, detail | {"status": "install_failed"}
            self.installed_android_target = target["targetId"]
        detail["installed"] = True
        uri = f"content://{target['package']}.state-test-probe/probe?caseId={case_id}"
        code, text = self.adb(["shell", "content", "query", "--uri", uri], timeout=30)
        (target_dir / "provider_query.txt").write_text(text, encoding="utf-8")
        snapshot = extract_snapshot_from_text(text)
        initial = {
            "status": "queried" if snapshot else "snapshot_missing",
            "snapshot": snapshot,
            "layoutText": text,
            "readyObserved": bool(snapshot and snapshot.get("caseId") == case_id),
        }
        detail["queryExit"] = code
        return {"initial": initial, "transitions": []}, detail | {"status": initial["status"]}

    def capture_arkts_layout(self, target: dict[str, Any], case_id: str, phase: str, phase_dir: Path) -> dict[str, Any]:
        phase_dir.mkdir(parents=True, exist_ok=True)
        remote = f"/data/local/tmp/qingyu_{ps_safe(case_id)}_{ps_safe(phase)}.json"
        layout = phase_dir / "layout.json"
        if layout.exists():
            layout.unlink()
        dump_exit, dump_text = self.hdc(
            ["shell", "uitest", "dumpLayout", "-p", remote, "-a", "-b", target["bundle"]],
            timeout=60,
        )
        recv_exit, recv_text = self.hdc(["file", "recv", remote, str(layout)], timeout=60)
        layout_text = layout.read_text(encoding="utf-8", errors="ignore") if layout.exists() else ""
        snapshot = extract_snapshot_from_text(layout_text)
        ready = f"state_test_ready:{case_id}" in layout_text and bool(snapshot and snapshot.get("caseId") == case_id)
        return {
            "status": "captured" if layout.exists() else "capture_failed",
            "snapshot": snapshot,
            "layoutText": layout_text,
            "layout": str(layout),
            "readyObserved": ready,
            "dumpExit": dump_exit,
            "dumpText": dump_text[:1000],
            "recvExit": recv_exit,
            "recvText": recv_text[:1000],
        }

    def wait_for_arkts_phase(
        self,
        target: dict[str, Any],
        case_id: str,
        phase: str,
        phase_dir: Path,
        timeout_seconds: float,
        selectors: dict[str, Any] | None = None,
        ordinal: int | None = None,
        event: str = "",
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        attempts = 0
        while True:
            attempts += 1
            latest = self.capture_arkts_layout(target, case_id, phase, phase_dir)
            satisfied = bool(latest.get("readyObserved"))
            if satisfied and selectors is not None and ordinal is not None:
                observed = phase_observed_facts(
                    latest.get("snapshot"),
                    str(latest.get("layoutText") or ""),
                    selectors,
                    ordinal,
                    event,
                )
                satisfied = all(fact in observed for fact in transition_facts(selectors))
            if satisfied or time.monotonic() >= deadline:
                latest["pollSatisfied"] = satisfied
                latest["pollAttempts"] = attempts
                return latest
            time.sleep(self.poll_interval)

    def arkts_capture(
        self,
        target: dict[str, Any],
        case_id: str,
        case: dict[str, Any],
        target_dir: Path,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        hap = Path(target["hap"])
        detail: dict[str, Any] = {"artifactExists": hap.exists(), "installed": False, "launched": False, "captured": False}
        if not hap.exists():
            return {"initial": {"status": "hap_missing"}, "transitions": []}, detail | {"status": "hap_missing"}
        if self.installed_arkts_target != target["targetId"]:
            self.hdc(["shell", "aa", "force-stop", target["bundle"]], timeout=30)
            code, text = self.hdc(["install", "-r", str(hap)], timeout=180)
            detail["installText"] = text
            if code != 0:
                return {"initial": {"status": "install_failed"}, "transitions": []}, detail | {"status": "install_failed"}
            self.installed_arkts_target = target["targetId"]
        detail["installed"] = True
        uri = f"elementx://state-test?caseId={case_id}"
        code, text = self.hdc(
            ["shell", "aa", "start", "-b", target["bundle"], "-a", "EntryAbility", "-U", uri, "--ps", "caseId", case_id],
            timeout=60,
        )
        detail["launchText"] = text
        detail["launched"] = code == 0
        initial = self.wait_for_arkts_phase(target, case_id, "initial", target_dir / "initial", self.ready_timeout)
        phases: list[dict[str, Any]] = []
        for index, transition in enumerate(case.get("transitionSelectors") or [], start=1):
            ordinal = int(transition.get("ordinal") or index)
            event = str(transition.get("event") or "")
            event_code, event_text = self.hdc(
                [
                    "shell", "aa", "start", "-b", target["bundle"], "-a", "EntryAbility", "-U", uri,
                    "--ps", "caseId", case_id, "--ps", "stateEvent", shlex.quote(event),
                ],
                timeout=60,
            )
            phase = self.wait_for_arkts_phase(
                target,
                case_id,
                f"transition_{ordinal}_{event}",
                target_dir / f"transition_{ordinal:02d}_{ps_safe(event)}",
                self.transition_timeout,
                transition,
                ordinal,
                event,
            )
            phase["eventLaunchExit"] = event_code
            phase["eventLaunchText"] = event_text[:2000]
            phases.append(phase)
        detail["captured"] = initial.get("status") == "captured"
        detail["readyObserved"] = bool(initial.get("readyObserved"))
        detail["transitionCount"] = len(case.get("transitionSelectors") or [])
        detail["transitionCaptureCount"] = len(phases)
        return {"initial": initial, "transitions": phases}, detail | {"status": initial.get("status")}

    def run(self, platform: str, target_role: str, task_id: str = "", case_limit: int = 0) -> dict[str, Any]:
        targets = self.matrix["targets"]
        if platform != "both":
            targets = [target for target in targets if target["platform"] == platform]
        if target_role != "both":
            targets = [target for target in targets if target.get("targetRole") == target_role]
        if task_id:
            targets = [target for target in targets if target["taskId"] == task_id]
        target_ids = {target["targetId"] for target in targets}
        rows = sorted(
            [row for row in self.matrix["caseTargets"] if row["targetId"] in target_ids],
            key=lambda row: (str(row["targetId"]), str(row["caseId"])),
        )
        if case_limit > 0:
            counts: dict[str, int] = {}
            limited = []
            for row in rows:
                count = counts.get(row["targetId"], 0)
                if count < case_limit:
                    limited.append(row)
                    counts[row["targetId"]] = count + 1
            rows = limited
        target_map = {target["targetId"]: target for target in targets}
        results = []
        for index, row in enumerate(rows, start=1):
            target = target_map[row["targetId"]]
            case_id = row["caseId"]
            case = self.case_bindings.get(case_id, {})
            target_dir = self.out_dir / "snapshot_probe" / ps_safe(f"{target['targetId']}__{case_id}")
            target_dir.mkdir(parents=True, exist_ok=True)
            print(f"[snapshot] {index}/{len(rows)} {target['targetId']} {case_id}", flush=True)
            if target["platform"] == "android":
                capture, detail = self.android_capture(target, case_id, target_dir)
                mode = "compatible"
            else:
                capture, detail = self.arkts_capture(target, case_id, case, target_dir)
                mode = self.transition_mode
            serializable_capture = json.loads(json.dumps(capture))
            for phase in [serializable_capture.get("initial") or {}, *(serializable_capture.get("transitions") or [])]:
                phase.pop("layoutText", None)
            (target_dir / "capture.json").write_text(
                json.dumps(serializable_capture, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            score = score_case(capture, row["expected"], case, mode)
            results.append({
                "targetId": row["targetId"],
                "taskId": row["taskId"],
                "platform": row["platform"],
                "targetRole": row.get("targetRole"),
                "caseId": case_id,
                "expectedPolarity": row["expected"],
                "snapshot": capture.get("initial", {}).get("snapshot"),
                "probe": detail,
                **score,
            })
        summary = {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "root": str(ROOT),
            "platformFilter": platform,
            "targetRoleFilter": target_role,
            "taskFilter": task_id,
            "caseLimitPerTarget": case_limit,
            "transitionMode": self.transition_mode,
            "readyTimeoutSeconds": self.ready_timeout,
            "transitionTimeoutSeconds": self.transition_timeout,
            "targetCount": len(targets),
            "caseTargetCount": len(rows),
            "statusCounts": {},
            "semanticStatusCounts": {},
            "targetRoleCounts": {},
            "results": results,
        }
        for key in ("strictStatus", "semanticStatus", "targetRole"):
            counts: dict[str, int] = {}
            for item in results:
                value = str(item.get(key) or "unspecified")
                counts[value] = counts.get(value, 0) + 1
            out_key = {"strictStatus": "statusCounts", "semanticStatus": "semanticStatusCounts", "targetRole": "targetRoleCounts"}[key]
            summary[out_key] = counts
        return summary


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Snapshot State Matrix Run Report",
        "",
        f"- Generated: {summary['generatedAt']}",
        f"- Targets: {summary['targetCount']}",
        f"- Case-target rows: {summary['caseTargetCount']}",
        f"- Platform filter: `{summary['platformFilter']}`",
        f"- Target role filter: `{summary['targetRoleFilter']}`",
        f"- Transition mode: `{summary['transitionMode']}`",
        f"- Status counts: `{json.dumps(summary['statusCounts'], ensure_ascii=False)}`",
        f"- Semantic status counts: `{json.dumps(summary['semanticStatusCounts'], ensure_ascii=False)}`",
        "",
        "## Notes",
        "",
        "- ArkTS cases poll for a case-specific ready marker instead of using a fixed sleep.",
        "- Every declared transition is delivered through the stateEvent Want parameter and captured separately.",
        "- Scoring combines independently observed ArkUI node ids/states with runtime semantic facts.",
        "- Compatible mode may accept aggregate transition facts from legacy golden targets; strict mode does not.",
        "",
        "## Non-Matched Rows",
    ]
    mismatches = [row for row in summary["results"] if row["strictStatus"] != "matched"]
    for row in mismatches[:200]:
        lines.append(
            f"- `{row['targetId']}` `{row['caseId']}` expected `{row['expectedPolarity']}` "
            f"observed `{row['observedPolarity']}` status `{row['strictStatus']}` "
            f"missing `{len(row.get('missingFacts') or [])}`"
        )
    if len(mismatches) > 200:
        lines.append(f"- ... {len(mismatches) - 200} more")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default=str(ROOT / "verification_reports" / "state_dynamic" / "state_dynamic_target_matrix.json"))
    parser.add_argument("--out", default=str(ROOT / "verification_reports" / "snapshot_state_dynamic"))
    parser.add_argument("--platform", choices=["both", "android", "arkts"], default="both")
    parser.add_argument("--target-role", choices=["both", "base", "groundtruth_final", "agent_result"], default="both")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--case-limit-per-target", type=int, default=0)
    parser.add_argument("--android-serial", default="")
    parser.add_argument("--transition-mode", choices=["strict", "compatible"], default="strict")
    parser.add_argument("--ready-timeout", type=float, default=12.0)
    parser.add_argument("--transition-timeout", type=float, default=6.0)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix = json.loads(Path(args.matrix).read_text(encoding="utf-8-sig"))
    summary = Runner(
        matrix,
        out_dir,
        args.android_serial,
        args.ready_timeout,
        args.transition_timeout,
        args.poll_interval,
        args.transition_mode,
    ).run(args.platform, args.target_role, args.task_id, args.case_limit_per_target)
    json_path = out_dir / "snapshot_state_matrix_run_report.json"
    markdown_path = out_dir / "snapshot_state_matrix_run_report.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary, markdown_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
