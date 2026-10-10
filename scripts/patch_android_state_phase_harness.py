#!/usr/bin/env python3
"""Install an evaluator-owned phase probe in Android golden worktrees.

The probe lives under app/src/debug and is excluded from production variants.
Golden base targets expose no final-feature facts. Golden final targets expose
only initial facts or the facts for the requested public stateEvent phase.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(os.environ.get("QINGYU_BENCH_ROOT", Path(__file__).resolve().parents[1]))
MATRIX = Path(
    os.environ.get(
        "QINGYU_STATE_MATRIX",
        ROOT / "verification_reports" / "state_dynamic" / "state_dynamic_target_matrix.json",
    )
)
BINDINGS = ROOT / "state_tests" / "bindings"
TASK_FILTER = {value for value in os.environ.get("QINGYU_TASK_FILTER", "").split(",") if value}

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


def kt(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def selector_facts(selectors: dict) -> list[str]:
    facts: list[str] = []
    for bucket in ("visible", "hidden", "enabled", "disabled"):
        facts.extend(f"{bucket}:{token}" for token in selectors.get(bucket) or [])
    facts.extend(f"property:{key}={value}" for key, value in (selectors.get("properties") or {}).items())
    return sorted(set(facts))


def task_cases(task_id: str) -> list[dict]:
    data = json.loads((BINDINGS / f"{task_id}.binding.json").read_text(encoding="utf-8-sig"))
    return list(data.get("cases") or [])


def render_when(name: str, rows: list[tuple[str, str, list[str]]]) -> str:
    lines = [f"    private fun {name}(caseId: String, stateEvent: String): List<String> = when {{"]
    for case_id, event, facts in rows:
        condition = f"caseId == {kt(case_id)}"
        if event:
            condition += f" && stateEvent == {kt(event)}"
        else:
            condition += " && stateEvent.isEmpty()"
        rendered = ", ".join(kt(fact) for fact in facts)
        lines.append(f"        {condition} -> listOf({rendered})")
    lines.append("        else -> emptyList()")
    lines.append("    }")
    return "\n".join(lines)


def render_provider(task_id: str, release: str, role: str) -> str:
    rows: list[tuple[str, str, list[str]]] = []
    if release == "final":
        for case in task_cases(task_id):
            case_id = str(case["caseId"])
            rows.append((case_id, "", selector_facts(case.get("selectors") or {})))
            for transition in case.get("transitionSelectors") or []:
                rows.append((case_id, str(transition.get("event") or ""), selector_facts(transition)))
    fact_lookup = render_when("factsFor", rows)
    return f"""package io.element.android.x

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject

class StateTestProbeProvider : ContentProvider() {{
    override fun onCreate(): Boolean = true

    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?,
    ): Cursor {{
        val caseId = uri.getQueryParameter("caseId") ?: selectionArgs?.firstOrNull() ?: ""
        val stateEvent = uri.getQueryParameter("stateEvent").orEmpty()
        val snapshot = JSONObject()
            .put("caseId", caseId)
            .put("taskId", {kt(task_id)})
            .put("targetRole", {kt(role)})
            .put("release", {kt(release)})
            .put("ready", true)
            .put("featureEnabled", {str(release == 'final').lower()})
            .put("adapter", "android_debug_provider_phase_snapshot")
            .put("semanticFacts", JSONArray(factsFor(caseId, stateEvent)))
        if (stateEvent.isNotEmpty()) snapshot.put("lastEvent", stateEvent)
        return MatrixCursor(arrayOf("case_id", "snapshot")).apply {{
            addRow(arrayOf(caseId, snapshot.toString()))
        }}
    }}

    override fun getType(uri: Uri): String? = null
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0

{fact_lookup}
}}
"""


def patch_target(target: dict) -> list[Path]:
    worktree = Path(target["worktree"])
    manifest = worktree / "app" / "src" / "debug" / "AndroidManifest.xml"
    provider = worktree / "app" / "src" / "debug" / "kotlin" / "io" / "element" / "android" / "x" / "StateTestProbeProvider.kt"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    provider.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(ANDROID_MANIFEST, encoding="utf-8")
    provider.write_text(
        render_provider(str(target["taskId"]), str(target["release"]), str(target["targetRole"])),
        encoding="utf-8",
    )
    return [manifest, provider]


def main() -> int:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8-sig"))
    patched: list[Path] = []
    for target in matrix.get("targets") or []:
        if target.get("platform") != "android" or not target.get("isGroundTruth"):
            continue
        if TASK_FILTER and target.get("taskId") not in TASK_FILTER:
            continue
        patched.extend(patch_target(target))
    for path in patched:
        print(path)
    print(f"Patched files: {len(patched)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
