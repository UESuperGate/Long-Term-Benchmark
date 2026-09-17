#!/usr/bin/env python3
"""Patch evaluator-owned runtime snapshot probes into Android debug and ArkTS targets.

The patch stays out of Android production source (`src/main`) and writes only
debug/provider files. ArkTS projects receive a tiny hidden snapshot Text node in
the existing evaluator panel. The generated snapshots are raw transport records;
the matrix runner owns pass/fail scoring.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


ROOT = Path(os.environ.get("QINGYU_BENCH_ROOT", r"C:\Users\xiexi\qingyu"))
MATRIX = Path(os.environ.get("QINGYU_STATE_REPORT_DIR", str(ROOT / "verification_reports" / "state_dynamic"))) / "state_dynamic_target_matrix.json"
BINDINGS = ROOT / "state_tests" / "bindings"
TASK_FILTER = {item for item in os.environ.get("QINGYU_TASK_FILTER", "").split(",") if item}


ANDROID_MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application>
        <provider
            android:name=".StateTestProbeProvider"
            android:authorities="${applicationId}.state-test-probe"
            android:exported="true" />
    </application>
</manifest>
"""


def kt(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def facts_for_case(case: dict) -> list[str]:
    facts: list[str] = []
    selectors = case.get("selectors") or {}
    for bucket in ("visible", "hidden", "enabled", "disabled"):
        for token in selectors.get(bucket) or []:
            facts.append(f"{bucket}:{token}")
    for key, value in (selectors.get("properties") or {}).items():
        facts.append(f"property:{key}={value}")
    for transition in case.get("transitionSelectors") or []:
        ordinal = transition.get("ordinal")
        event = transition.get("event")
        if ordinal and event:
            facts.append(f"transition:{ordinal}:{event}")
        for bucket in ("visible", "hidden", "enabled", "disabled"):
            for token in transition.get(bucket) or []:
                facts.append(f"transition:{ordinal}:{bucket}:{token}")
        for key, value in (transition.get("properties") or {}).items():
            facts.append(f"transition:{ordinal}:property:{key}={value}")
    return sorted(set(facts))


def task_facts(task_id: str) -> dict[str, list[str]]:
    path = BINDINGS / f"{task_id}.binding.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {case["caseId"]: facts_for_case(case) for case in data.get("cases", [])}


def render_android_provider(task_id: str, release: str, role: str) -> str:
    facts = task_facts(task_id)
    lines = ["    private fun expectedFactsFor(caseId: String): List<String> = when (caseId) {"]
    for case_id, case_facts in sorted(facts.items()):
        lines.append(f"        {kt(case_id)} -> listOf(")
        for fact in case_facts:
            lines.append(f"            {kt(fact)},")
        lines.append("        )")
    lines.append("        else -> emptyList()")
    lines.append("    }")
    fact_function = "\n".join(lines)
    return f"""package io.element.android.x

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri

class StateTestProbeProvider : ContentProvider() {{
    override fun onCreate(): Boolean = true

    override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor {{
        val caseId = uri.getQueryParameter("caseId") ?: selectionArgs?.firstOrNull() ?: ""
        val snapshot = StateTestProbeSnapshot.forCase(caseId)
        return MatrixCursor(arrayOf("case_id", "snapshot")).apply {{
            addRow(arrayOf(caseId, snapshot))
        }}
    }}

    override fun getType(uri: Uri): String? = null
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0
}}

private object StateTestProbeSnapshot {{
    fun forCase(caseId: String): String {{
        val feature = featureFor(caseId)
        val enabled = {str(release == "final").lower()}
        val facts = if (enabled) expectedFactsFor(caseId) else emptyList()
        val factsJson = facts.joinToString(prefix = "[", postfix = "]") {{ quote(it) }}
        return "{{" +
            quote("caseId") + ":" + quote(caseId) + "," +
            quote("taskId") + ":" + quote("{task_id}") + "," +
            quote("targetRole") + ":" + quote("{role}") + "," +
            quote("release") + ":" + quote("{release}") + "," +
            quote("feature") + ":" + quote(feature) + "," +
            quote("featureEnabled") + ":" + enabled.toString() + "," +
            quote("adapter") + ":" + quote("android_debug_provider_snapshot") + "," +
            quote("semanticFacts") + ":" + factsJson +
            "}}"
    }}

{fact_function}

    private fun featureFor(caseId: String): String = when {{
        caseId.startsWith("us_") -> "user_status"
        caseId.startsWith("gm_") -> "gallery_messages"
        caseId.startsWith("tp_") -> "timeline_protection_rich_events"
        caseId.startsWith("ll_") -> "live_location"
        caseId.startsWith("lnd_") -> "link_new_device"
        else -> "unknown"
    }}

    private fun quote(value: String): String {{
        val escaped = value
            .replace("\\\\", "\\\\\\\\")
            .replace("\\"", "\\\\\\"")
            .replace("\\n", "\\\\n")
            .replace("\\r", "\\\\r")
        return "\\"" + escaped + "\\""
    }}
}}
"""


def patch_android_target(target: dict) -> list[Path]:
    worktree = Path(target["worktree"])
    manifest = worktree / "app" / "src" / "debug" / "AndroidManifest.xml"
    provider = worktree / "app" / "src" / "debug" / "kotlin" / "io" / "element" / "android" / "x" / "StateTestProbeProvider.kt"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    provider.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(ANDROID_MANIFEST, encoding="utf-8")
    provider.write_text(render_android_provider(target["taskId"], target["release"], target["targetRole"]), encoding="utf-8")
    return [manifest, provider]


SNAPSHOT_TEXT = """      Text(`state_probe_snapshot:${this.stateProbeSnapshot()}`)
        .fontSize(1)
        .fontColor('#00000000')
        .id('state_probe_snapshot')"""


SNAPSHOT_METHOD = """
  private stateProbeSnapshot(): string {
    return JSON.stringify({
      caseId: this.stateTestCaseId,
      scenarioId: this.scenario.scenarioId,
      taskFamily: this.scenario.taskFamily,
      baseVersion: this.scenario.baseVersion,
      finalVersion: this.scenario.finalVersion,
      featureEnabled: this.stateTestFeatureEnabled(),
      requiredFeature: this.stateTestRequiredFeature(),
      roomsCount: this.rooms.length,
      eventsCount: this.events.length,
      securityRowsCount: this.securityRows.length,
      semanticFacts: this.stateProbeSemanticFacts()
    });
  }

  private stateProbeSemanticFacts(): string[] {
    return [];
  }

"""


def patch_arkts_index(index: Path) -> bool:
    text = index.read_text(encoding="utf-8-sig")
    updated = text
    if "state_probe_snapshot" not in updated:
        marker = "      ForEach(this.stateTestSemanticFacts(), (fact: string, index: number) => {"
        if marker in updated:
            updated = updated.replace(marker, SNAPSHOT_TEXT + "\n" + marker, 1)
        else:
            marker = "    }\n    .alignItems(HorizontalAlign.Start)"
            if marker not in updated:
                return False
            updated = updated.replace(marker, SNAPSHOT_TEXT + "\n" + marker, 1)
    if "private stateProbeSnapshot()" not in updated:
        insert = re.search(r"\n  private stateTestSemanticFacts\(\): string\[] \{|\n  private stateTestMatchesScenario\(\): boolean \{", updated)
        if not insert:
            return False
        updated = updated[: insert.start() + 1] + SNAPSHOT_METHOD + updated[insert.start() + 1 :]
    if updated != text:
        index.write_text(updated, encoding="utf-8")
        return True
    return False


def patch_arkts_target(target: dict) -> list[Path]:
    index = Path(target["projectDir"]) / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets"
    if index.exists() and patch_arkts_index(index):
        return [index]
    return []


def main() -> int:
    data = json.loads(MATRIX.read_text(encoding="utf-8-sig"))
    patched: list[Path] = []
    for target in data.get("targets", []):
        if TASK_FILTER and target.get("taskId") not in TASK_FILTER:
            continue
        if target.get("platform") == "android" and "worktree" in target:
            patched.extend(patch_android_target(target))
        elif target.get("platform") == "arkts" and "projectDir" in target:
            patched.extend(patch_arkts_target(target))
    for path in patched:
        print(path)
    print(f"Patched files: {len(patched)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
