#!/usr/bin/env python3
"""Run evaluator-owned snapshot state tests across Android and ArkTS targets."""

from __future__ import annotations

import argparse
import html
import json
import locale
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any


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
        p = subprocess.run(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, decode_process_output(p.stdout)
    except subprocess.TimeoutExpired as exc:
        return 124, decode_process_output(exc.stdout) + f"\nTIMEOUT after {timeout}s"


def ps_safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:140]


def expected_facts(case: dict[str, Any]) -> list[str]:
    out: list[str] = []
    selectors = case.get("selectors") or {}
    for bucket in ("visible", "hidden", "enabled", "disabled"):
        out.extend(f"{bucket}:{token}" for token in selectors.get(bucket) or [])
    for key, value in (selectors.get("properties") or {}).items():
        out.append(f"property:{key}={value}")
    for transition in case.get("transitionSelectors") or []:
        ordinal = transition.get("ordinal")
        event = transition.get("event")
        if ordinal and event:
            out.append(f"transition:{ordinal}:{event}")
        for bucket in ("visible", "hidden", "enabled", "disabled"):
            out.extend(f"transition:{ordinal}:{bucket}:{token}" for token in transition.get(bucket) or [])
        for key, value in (transition.get("properties") or {}).items():
            out.append(f"transition:{ordinal}:property:{key}={value}")
    return sorted(set(out))


def parse_snapshot_payload(value: str) -> dict[str, Any] | None:
    raw = html.unescape(value).strip()
    for prefix in ("state_probe_snapshot:", "snapshot="):
        if prefix in raw:
            raw = raw.split(prefix, 1)[1].strip()
    raw = raw.rstrip('",')
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


def load_binding_cases() -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for path in sorted(BINDINGS.glob("*.binding.json")):
        if path.name == "state_binding_manifest_index.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for case in data.get("cases", []):
            case = dict(case)
            case["expectedFacts"] = expected_facts(case)
            cases[case["caseId"]] = case
    return cases


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
    patterns = [
        r"state_probe_snapshot:(\{.*?\})(?:[\"<\r\n]|$)",
        r"snapshot=(\{.*\})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            continue
        snapshot = parse_snapshot_payload(match.group(1))
        if snapshot:
            return snapshot
    for prefix in ("state_probe_snapshot:", "snapshot="):
        if prefix in text:
            snapshot = parse_snapshot_payload(text.split(prefix, 1)[1])
            if snapshot:
                return snapshot
    return None


def score_snapshot(snapshot: dict[str, Any] | None, expected: str, facts: list[str]) -> dict[str, Any]:
    if not snapshot:
        observed = "fail"
        return {
            "observedPolarity": observed,
            "strictStatus": "matched" if observed == expected else "protocolFail",
            "semanticStatus": "not_scored",
            "missingFacts": facts,
            "reason": "snapshot_missing",
        }
    observed_facts = set(str(x) for x in snapshot.get("semanticFacts", []) or [])
    missing = [fact for fact in facts if fact not in observed_facts]
    observed = "pass" if not missing and facts else "fail"
    return {
        "observedPolarity": observed,
        "strictStatus": "matched" if observed == expected else "mismatch",
        "semanticStatus": "passed" if observed == "pass" else "failed",
        "missingFacts": missing,
        "reason": "snapshot_semantic_facts",
    }


class Runner:
    def __init__(self, matrix: dict[str, Any], out_dir: Path, android_serial: str = "") -> None:
        self.matrix = matrix
        self.out_dir = out_dir
        self.android_serial = android_serial
        self.case_bindings = load_binding_cases()
        self.installed_android_target = ""
        self.installed_arkts_target = ""

    def adb(self, args: list[str], timeout: int = 60) -> tuple[int, str]:
        cmd = [str(ADB)]
        if self.android_serial:
            cmd += ["-s", self.android_serial]
        cmd += args
        return run(cmd, timeout=timeout)

    def hdc(self, args: list[str], timeout: int = 60) -> tuple[int, str]:
        return run([str(HDC)] + args, timeout=timeout)

    def android_snapshot(self, target: dict[str, Any], case_id: str, target_dir: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        apk = Path(target["apk"])
        detail: dict[str, Any] = {"artifactExists": apk.exists(), "installed": False, "queryExit": None, "queryText": ""}
        if not apk.exists():
            return None, detail | {"status": "apk_missing"}
        if self.installed_android_target != target["targetId"]:
            self.adb(["uninstall", target["package"]], timeout=30)
            code, text = self.adb(["install", "-r", str(apk)], timeout=180)
            detail["installText"] = text
            if "Success" not in text:
                return None, detail | {"status": "install_failed"}
            self.installed_android_target = target["targetId"]
        detail["installed"] = True
        uri = f"content://{target['package']}.state-test-probe/probe?caseId={case_id}"
        code, text = 1, ""
        for attempt in range(1, 4):
            code, text = self.adb(["shell", "content", "query", "--uri", uri], timeout=30)
            if extract_snapshot_from_text(text):
                break
            if "Could not find provider" in text or "cannot connect to daemon" in text or "daemon still not running" in text:
                time.sleep(1.5 * attempt)
                continue
            break
        (target_dir / "provider_query.txt").write_text(text, encoding="utf-8")
        detail["queryExit"] = code
        detail["queryText"] = text[:2000]
        return extract_snapshot_from_text(text), detail | {"status": "queried"}

    def arkts_snapshot(self, target: dict[str, Any], case_id: str, target_dir: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        hap = Path(target["hap"])
        detail: dict[str, Any] = {"artifactExists": hap.exists(), "installed": False, "launched": False, "captured": False}
        if not hap.exists():
            return None, detail | {"status": "hap_missing"}
        if self.installed_arkts_target != target["targetId"]:
            self.hdc(["shell", "aa", "force-stop", target["bundle"]], timeout=30)
            code, text = self.hdc(["install", "-r", str(hap)], timeout=180)
            detail["installText"] = text
            if code != 0:
                return None, detail | {"status": "install_failed"}
            self.installed_arkts_target = target["targetId"]
        detail["installed"] = True
        uri = f"elementx://state-test?caseId={case_id}"
        code, text = self.hdc(["shell", "aa", "start", "-b", target["bundle"], "-a", "EntryAbility", "-U", uri, "--ps", "caseId", case_id], timeout=60)
        detail["launchText"] = text
        detail["launched"] = code == 0
        time.sleep(1.2)
        remote = f"/data/local/tmp/qingyu_snapshot_{ps_safe(case_id)}.json"
        layout = target_dir / "layout.json"
        self.hdc(["shell", "uitest", "dumpLayout", "-p", remote, "-a", "-b", target["bundle"]], timeout=60)
        self.hdc(["file", "recv", remote, str(layout)], timeout=60)
        if layout.exists():
            detail["captured"] = True
            text = layout.read_text(encoding="utf-8", errors="ignore")
            return extract_snapshot_from_text(text), detail | {"status": "captured"}
        return None, detail | {"status": "capture_failed"}

    def run(self, platform: str, target_role: str, task_id: str = "", case_limit: int = 0) -> dict[str, Any]:
        targets = self.matrix["targets"]
        if platform != "both":
            targets = [t for t in targets if t["platform"] == platform]
        if target_role != "both":
            targets = [t for t in targets if t.get("targetRole") == target_role]
        if task_id:
            targets = [t for t in targets if t["taskId"] == task_id]
        target_ids = {t["targetId"] for t in targets}
        rows = [r for r in self.matrix["caseTargets"] if r["targetId"] in target_ids]
        rows = sorted(rows, key=lambda r: (str(r["targetId"]), str(r["caseId"])))
        if case_limit > 0:
            by_target: dict[str, int] = {}
            limited = []
            for row in rows:
                count = by_target.get(row["targetId"], 0)
                if count < case_limit:
                    limited.append(row)
                    by_target[row["targetId"]] = count + 1
            rows = limited

        target_map = {t["targetId"]: t for t in targets}
        results = []
        for idx, row in enumerate(rows, start=1):
            target = target_map[row["targetId"]]
            case_id = row["caseId"]
            case = self.case_bindings.get(case_id, {})
            facts = case.get("expectedFacts", [])
            target_dir = self.out_dir / "snapshot_probe" / ps_safe(f"{target['targetId']}__{case_id}")
            target_dir.mkdir(parents=True, exist_ok=True)
            print(f"[snapshot] {idx}/{len(rows)} {target['targetId']} {case_id}", flush=True)
            if target["platform"] == "android":
                snapshot, detail = self.android_snapshot(target, case_id, target_dir)
            else:
                snapshot, detail = self.arkts_snapshot(target, case_id, target_dir)
            (target_dir / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n" if snapshot else "null\n", encoding="utf-8")
            score = score_snapshot(snapshot, row["expected"], facts)
            results.append({
                "targetId": row["targetId"],
                "taskId": row["taskId"],
                "platform": row["platform"],
                "targetRole": row.get("targetRole"),
                "caseId": case_id,
                "expectedPolarity": row["expected"],
                "snapshot": snapshot,
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
        f"- Status counts: `{json.dumps(summary['statusCounts'], ensure_ascii=False)}`",
        f"- Semantic status counts: `{json.dumps(summary['semanticStatusCounts'], ensure_ascii=False)}`",
        f"- Target role counts: `{json.dumps(summary['targetRoleCounts'], ensure_ascii=False)}`",
        "",
        "## Notes",
        "",
        "- Scoring is evaluator-side: raw `state_probe_snapshot` JSON is compared with binding manifests.",
        "- Android transport uses exported debug `StateTestProbeProvider` query, not UIAutomator.",
        "- ArkTS transport uses hidden `state_probe_snapshot` from `uitest dumpLayout`.",
        "",
        "## Non-Matched Rows",
    ]
    mismatches = [r for r in summary["results"] if r["strictStatus"] != "matched"]
    for row in mismatches[:200]:
        lines.append(f"- `{row['targetId']}` `{row['caseId']}` expected `{row['expectedPolarity']}` observed `{row['observedPolarity']}` status `{row['strictStatus']}` missing `{len(row.get('missingFacts') or [])}`")
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
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix = json.loads(Path(args.matrix).read_text(encoding="utf-8-sig"))
    summary = Runner(matrix, out_dir, args.android_serial).run(args.platform, args.target_role, args.task_id, args.case_limit_per_target)
    json_path = out_dir / "snapshot_state_matrix_run_report.json"
    md_path = out_dir / "snapshot_state_matrix_run_report.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary, md_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
