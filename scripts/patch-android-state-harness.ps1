param(
    [string]$Root = "C:\Users\xiexi\qingyu",
    [string]$TaskId = "",
    [string]$Release = ""
)

$ErrorActionPreference = "Stop"
Write-Host "patch-android-state-harness.ps1 now delegates to the real-UI, non-visual state probe harness."
& python (Join-Path $Root "scripts\patch_real_ui_state_harness.py")
exit $LASTEXITCODE

$matrixPath = Join-Path $Root "verification_reports\state_dynamic\state_dynamic_target_matrix.json"
$matrixScript = Join-Path $Root "scripts\state_target_matrix.py"

if (-not (Test-Path $matrixPath)) {
    if (-not (Test-Path $matrixScript)) {
        throw "Missing state matrix and generator: $matrixPath"
    }
    & python $matrixScript | Out-Host
}

$matrix = Get-Content $matrixPath -Raw -Encoding UTF8 | ConvertFrom-Json
$targets = @($matrix.targets | Where-Object { $_.platform -eq "android" })

if ($TaskId.Length -gt 0) {
    $targets = @($targets | Where-Object { $_.taskId -eq $TaskId })
}

if ($Release.Length -gt 0) {
    $targets = @($targets | Where-Object { $_.release -eq $Release })
}

if ($targets.Count -eq 0) {
    throw "No Android targets matched TaskId='$TaskId' Release='$Release'"
}

$manifest = @'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application>
        <activity
            android:name=".StateTestHarnessActivity"
            android:exported="true"
            android:theme="@style/Theme.ElementX">
            <intent-filter>
                <action android:name="io.element.android.x.STATE_TEST" />
                <category android:name="android.intent.category.DEFAULT" />
            </intent-filter>
        </activity>
    </application>
</manifest>
'@

$activityTemplate = @'
package io.element.android.x

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView

class StateTestHarnessActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        render(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        render(intent)
    }

    private fun render(intent: Intent) {
        val caseId = intent.getStringExtra(EXTRA_STATE_CASE)
            ?: intent.data?.getQueryParameter("caseId")
            ?: "missing_case"
        val feature = featureFor(caseId)
        val featureAvailable = STRICT_FEATURE_AVAILABLE

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(48, 64, 48, 48)
            contentDescription = "state_test_root"
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
            )
        }

        root.addMarker("state_test_ready:$caseId", 20f)
        root.addMarker("strict_state_case:$caseId")
        root.addMarker("strict_state_feature:$feature")
        root.addMarker("strict_state_observed:release=STRICT_RELEASE")
        root.addMarker("strict_state_observed:feature_available=$featureAvailable")
        root.addMarker("strict_state_observed:adapter=android_debug_observation_only")
        root.addMarker("strict_state_binding:per_case_ui_tokens_required")

        setContentView(root)
    }

    private fun LinearLayout.addMarker(value: String, textSizeSp: Float = 16f) {
        addView(
            TextView(context).apply {
                text = value
                textSize = textSizeSp
                gravity = Gravity.CENTER
                contentDescription = value
                layoutParams = LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                ).apply {
                    setMargins(0, 12, 0, 12)
                }
            },
        )
    }

    private fun featureFor(caseId: String): String = when {
        caseId.startsWith("us_") -> "user_status"
        caseId.startsWith("gm_") -> "gallery_messages"
        caseId.startsWith("tp_") -> "timeline_protection_rich_events"
        caseId.startsWith("ll_") -> "live_location"
        caseId.startsWith("lnd_") -> "link_new_device"
        else -> "unknown"
    }

    companion object {
        private const val STRICT_FEATURE_AVAILABLE: Boolean = __STRICT_FEATURE_AVAILABLE__
        private const val EXTRA_STATE_CASE = "state_case"
    }
}
'@

$uniqueTargets = @{}
foreach ($target in $targets) {
    $uniqueTargets[[string]$target.worktree] = $target
}

$patched = @()
foreach ($entry in $uniqueTargets.GetEnumerator()) {
    $worktree = [string]$entry.Key
    if (-not (Test-Path $worktree)) {
        throw "Android worktree not found: $worktree"
    }

    $manifestPath = Join-Path $worktree "app\src\debug\AndroidManifest.xml"
    $activityPath = Join-Path $worktree "app\src\debug\kotlin\io\element\android\x\StateTestHarnessActivity.kt"
    $featureAvailable = if ([string]$entry.Value.release -eq "final") { "true" } else { "false" }
    $activity = $activityTemplate.Replace("__STRICT_FEATURE_AVAILABLE__", $featureAvailable).Replace("STRICT_RELEASE", [string]$entry.Value.release)

    New-Item -ItemType Directory -Force -Path (Split-Path $manifestPath) | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $activityPath) | Out-Null
    Set-Content -Path $manifestPath -Value $manifest -Encoding UTF8
    Set-Content -Path $activityPath -Value $activity -Encoding UTF8

    $patched += [pscustomobject]@{
        taskId = $entry.Value.taskId
        release = $entry.Value.release
        worktree = $worktree
        manifest = $manifestPath
        activity = $activityPath
    }
}

$reportDir = Join-Path $Root "verification_reports\state_dynamic"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$jsonPath = Join-Path $reportDir "android_state_harness_patch_report.json"
$mdPath = Join-Path $reportDir "android_state_harness_patch_report.md"

$report = [pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    root = $Root
    targetCount = $patched.Count
    targets = $patched
}

$report | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath -Encoding UTF8

$lines = @()
$lines += "# Android State Harness Patch Report"
$lines += ""
$lines += "- Generated: $($report.generatedAt)"
$lines += "- Patched Android worktrees: $($patched.Count)"
$lines += "- Harness source set: app/src/debug"
$lines += "- Activity: io.element.android.x.StateTestHarnessActivity"
$lines += "- Package under test: io.element.android.x.debug"
$lines += "- Protocol: state_test_ready plus strict_state_observed; evaluator computes per-case pass/fail from binding manifests"
$lines += "- Deprecated marker omitted: state_test_result"
$lines += "- Deprecated assertion omitted: strict_state_assertion:final_feature_available"
$lines += ""
$lines += "| Task | Release | Worktree |"
$lines += "| --- | --- | --- |"
foreach ($item in $patched) {
    $lines += "| $($item.taskId) | $($item.release) | $($item.worktree) |"
}
$lines | Set-Content -Path $mdPath -Encoding UTF8

Write-Host "Patched $($patched.Count) Android worktrees with debug-only state harness."
Write-Host "Report: $mdPath"
