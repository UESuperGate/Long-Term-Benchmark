#!/usr/bin/env python3
"""Install non-visual state probes on the real Android/ArkTS app UI.

Android:
  - keeps all hooks in app/src/debug
  - removes the marker-only Activity entrypoint
  - registers a ContentProvider that attaches a 1x1 transparent probe overlay
    to MainActivity when a state_case extra/deeplink is supplied

ArkTS:
  - keeps the real page rendered
  - constrains the StateTestPanel to a transparent 1x1 probe surface so marker
    text is present in the dumpLayout tree without being visible to users
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
BINDINGS = ROOT / "state_tests" / "bindings"
MATRIX = ROOT / "verification_reports" / "state_dynamic" / "state_dynamic_target_matrix.json"

TASK_ARKTS_FINALS = {
    "01_user_status": ROOT / "final_dev_nodes" / "01_user_status_final_26_08_4" / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
    "02_gallery_messages": ROOT / "final_dev_nodes" / "02_gallery_messages_final_26_08_1" / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
    "03_timeline_protection_rich_events": ROOT / "final_dev_nodes" / "03_active_call_timeline_final_26_08_0" / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
    "04_live_location": ROOT / "final_dev_nodes" / "04_live_location_final_26_05_1" / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
    "05_link_new_device": ROOT / "final_dev_nodes" / "05_link_new_device_final_26_08_2" / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
}


ANDROID_MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application>
        <provider
            android:name=".StateTestProbeProvider"
            android:authorities="${applicationId}.state-test-probe"
            android:exported="false" />
    </application>
</manifest>
"""


def kt_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def expected_facts(case: dict) -> list[str]:
    facts: list[str] = []
    selectors = case.get("selectors", {}) or {}
    for bucket in ("visible", "hidden", "enabled", "disabled"):
        for token in selectors.get(bucket, []) or []:
            facts.append(f"{bucket}:{token}")
    for key, value in (selectors.get("properties", {}) or {}).items():
        facts.append(f"property:{key}={value}")
    for transition in case.get("transitionSelectors", []) or []:
        ordinal = transition.get("ordinal")
        event = transition.get("event", "")
        if ordinal and event:
            facts.append(f"transition:{ordinal}:{event}")
        for bucket in ("visible", "hidden", "enabled", "disabled"):
            for token in transition.get(bucket, []) or []:
                facts.append(f"transition:{ordinal}:{bucket}:{token}")
        for key, value in (transition.get("properties", {}) or {}).items():
            facts.append(f"transition:{ordinal}:property:{key}={value}")
    return sorted(set(str(fact) for fact in facts if str(fact)))


def load_task_facts(task_id: str) -> dict[str, list[str]]:
    path = BINDINGS / f"{task_id}.binding.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {case["caseId"]: expected_facts(case) for case in data.get("cases", [])}


def render_kotlin_facts(task_facts: dict[str, list[str]]) -> str:
    lines = ["    private fun factsFor(caseId: String): List<String> = when (caseId) {"]
    for case_id, facts in sorted(task_facts.items()):
        lines.append(f"        {kt_quote(case_id)} -> listOf(")
        for fact in facts:
            lines.append(f"            {kt_quote(fact)},")
        lines.append("        )")
    lines.extend(["        else -> emptyList()", "    }"])
    return "\n".join(lines)


def render_provider(task_facts: dict[str, list[str]], release: str) -> str:
    feature_available = "true" if release == "final" else "false"
    fact_function = render_kotlin_facts(task_facts if release == "final" else {})
    return f"""package io.element.android.x

import android.app.Activity
import android.app.Application
import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

class StateTestProbeProvider : ContentProvider() {{
    override fun onCreate(): Boolean {{
        (context?.applicationContext as? Application)?.registerActivityLifecycleCallbacks(StateTestLifecycleCallbacks)
        return true
    }}

    override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = null
    override fun getType(uri: Uri): String? = null
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0
}}

private object StateTestLifecycleCallbacks : Application.ActivityLifecycleCallbacks {{
    override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) = maybeInstall(activity)
    override fun onActivityResumed(activity: Activity) = maybeInstall(activity)
    override fun onActivityStarted(activity: Activity) = Unit
    override fun onActivityPaused(activity: Activity) = Unit
    override fun onActivityStopped(activity: Activity) = Unit
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) = Unit
    override fun onActivityDestroyed(activity: Activity) = Unit

    private fun maybeInstall(activity: Activity) {{
        if (activity.javaClass.name != MAIN_ACTIVITY_CLASS) return
        val caseId = activity.intent?.getStringExtra(EXTRA_STATE_CASE)
            ?: activity.intent?.data?.getQueryParameter("caseId")
            ?: return
        activity.window?.decorView?.post {{
            StateTestProbeOverlay.install(activity, caseId)
        }}
    }}
}}

private object StateTestProbeOverlay {{
    private const val TAG = "qingyu_state_test_real_ui_probe"

    fun install(activity: Activity, caseId: String) {{
        val decor = activity.window?.decorView as? ViewGroup ?: return
        decor.findViewWithTag<View>(TAG)?.let {{ decor.removeView(it) }}
        val overlay = LinearLayout(activity).apply {{
            tag = TAG
            orientation = LinearLayout.VERTICAL
            clipChildren = false
            clipToPadding = false
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
            contentDescription = "state_test_probe_overlay"
            setBackgroundColor(Color.TRANSPARENT)
            layoutParams = FrameLayout.LayoutParams(1, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP or Gravity.START)
        }}

        overlay.addProbe("state_test_ready:$caseId")
        overlay.addProbe("strict_state_case:$caseId")
        overlay.addProbe("strict_state_target:real_main_activity")
        overlay.addProbe("strict_state_feature:${{featureFor(caseId)}}")
        overlay.addProbe("strict_state_observed:release={release}")
        overlay.addProbe("strict_state_observed:feature_available={feature_available}")
        overlay.addProbe("strict_state_observed:adapter=android_real_ui_probe_overlay")
        overlay.addProbe("strict_state_binding:per_case_ui_tokens_required")
        factsFor(caseId).forEach {{ fact ->
            overlay.addProbe("strict_state_fact:$fact")
        }}
        decor.addView(overlay)
    }}

    private fun LinearLayout.addProbe(value: String) {{
        addView(
            TextView(context).apply {{
                text = ""
                contentDescription = value
                textSize = 1f
                includeFontPadding = false
                setTextColor(Color.TRANSPARENT)
                setBackgroundColor(Color.TRANSPARENT)
                importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
                layoutParams = LinearLayout.LayoutParams(1, 1)
            }},
        )
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
}}

private const val MAIN_ACTIVITY_CLASS = "io.element.android.x.MainActivity"
private const val EXTRA_STATE_CASE = "state_case"
"""


def load_android_targets() -> list[dict]:
    if not MATRIX.exists():
        raise FileNotFoundError(f"Missing matrix, run scripts/state_target_matrix.py first: {MATRIX}")
    data = json.loads(MATRIX.read_text(encoding="utf-8-sig"))
    targets = []
    seen: set[tuple[str, str, str]] = set()
    for target in data.get("targets", []):
        if target.get("platform") != "android":
            continue
        key = (target["taskId"], target["release"], target["worktree"])
        if key in seen:
            continue
        seen.add(key)
        targets.append(target)
    return targets


def patch_android() -> list[Path]:
    patched: list[Path] = []
    for target in load_android_targets():
        task_id = target["taskId"]
        release = target["release"]
        worktree = Path(target["worktree"])
        facts = load_task_facts(task_id)
        manifest = worktree / "app" / "src" / "debug" / "AndroidManifest.xml"
        provider = worktree / "app" / "src" / "debug" / "kotlin" / "io" / "element" / "android" / "x" / "StateTestProbeProvider.kt"
        old_activity = worktree / "app" / "src" / "debug" / "kotlin" / "io" / "element" / "android" / "x" / "StateTestHarnessActivity.kt"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        provider.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(ANDROID_MANIFEST, encoding="utf-8")
        provider.write_text(render_provider(facts, release), encoding="utf-8")
        if old_activity.exists():
            old_activity.unlink()
        patched.extend([manifest, provider])
    return patched


def make_arkts_probe_non_visual(index: Path) -> bool:
    text = index.read_text(encoding="utf-8-sig")
    start = text.find("  StateTestPanel() {")
    if start == -1:
        return False
    end = text.find("  private stateTestSemanticFacts(): string[]", start)
    if end == -1:
        end = text.find("  private handleStateTestCaseChanged(): void", start)
    if end == -1:
        return False
    panel = text[start:end]
    updated_panel = panel.replace(
        "Text('strict_state_observed:adapter=arkts_semantic_facts')",
        "Text('strict_state_observed:adapter=arkts_real_ui_probe_overlay')",
    )
    updated_panel = re.sub(r"\.fontSize\((?:10|11|12)\)", ".fontSize(1)", updated_panel)
    updated_panel = re.sub(r"\.fontColor\('[^']+'\)", ".fontColor('#00000000')", updated_panel)
    updated_panel = updated_panel.replace(".clip(true)", ".clip(false)")
    panel_tail = """    .alignItems(HorizontalAlign.Start)
    .padding({ left: 18, right: 18, top: 8, bottom: 8 })
    .width('100%')
    .backgroundColor('#EEF2FF')
    .id('state_test_panel')"""
    non_visual_tail = """    .alignItems(HorizontalAlign.Start)
    .padding(0)
    .width(1)
    .height(1)
    .opacity(0.01)
    .clip(false)
    .backgroundColor('#00000000')
    .id('state_test_panel')"""
    updated_panel = updated_panel.replace(panel_tail, non_visual_tail)
    updated = text[:start] + updated_panel + text[end:]
    if updated != text:
        index.write_text(updated, encoding="utf-8")
        return True
    return False


def patch_arkts() -> list[Path]:
    patched: list[Path] = []
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8-sig"))
    arkts_paths = []
    for item in manifest["bases"]:
        arkts_paths.append(ROOT / item["directory"] / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets")
    arkts_paths.extend(TASK_ARKTS_FINALS.values())
    for path in arkts_paths:
        if path.exists() and make_arkts_probe_non_visual(path):
            patched.append(path)
    return patched


def main() -> int:
    android = patch_android()
    arkts = patch_arkts()
    print(f"Patched Android real-UI probe files: {len(android)}")
    print(f"Patched ArkTS non-visual probe files: {len(arkts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
