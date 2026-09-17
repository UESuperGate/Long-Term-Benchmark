param(
  [string]$AndroidPackage = "",
  [string]$AndroidLaunchActivity = "",
  [string]$HarmonyInstance = "Pura 90 Pro Max"
)

$ErrorActionPreference = "Continue"
$root = "C:\Users\xiexi\qingyu"
$outDir = Join-Path $root "verification_reports\ui_dynamic"
$androidSdk = "C:\Users\xiexi\AppData\Local\Android\Sdk"
$hdc = "C:\Users\xiexi\AppData\Local\OpenHarmony\Sdk\23\toolchains\hdc.exe"
$emulator = "C:\Program Files\Huawei\DevEco Studio\tools\emulator\Emulator.exe"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$env:Path = "$androidSdk\platform-tools;$androidSdk\emulator;C:\Program Files\Huawei\DevEco Studio\tools\ohpm\bin;C:\Program Files\Huawei\DevEco Studio\tools\hvigor\bin;C:\Program Files\Huawei\DevEco Studio\tools\node;" + $env:Path

$cases = @(
  @{
    Id = "01_user_status_final_26_08_4"
    Bundle = "com.qingyu.elementx.userstatus.final"
    Title = "User Status"
    Expected = @("User Status", "final 26.08.4", "User status")
  },
  @{
    Id = "02_gallery_messages_final_26_08_1"
    Bundle = "com.qingyu.elementx.gallery.final"
    Title = "Gallery Messages"
    Expected = @("Gallery Messages", "final 26.08.1", "Gallery renderer connected")
  },
  @{
    Id = "03_active_call_timeline_final_26_08_0"
    Bundle = "com.qingyu.elementx.activecall.final"
    Title = "Active Call Timeline"
    Expected = @("Active Call Timeline", "final 26.08.0", "Join call")
  },
  @{
    Id = "04_live_location_final_26_05_1"
    Bundle = "com.qingyu.elementx.livelocation.final"
    Title = "Live Location"
    Expected = @("Live Location", "final 26.05.1", "Open live map")
  },
  @{
    Id = "05_link_new_device_final_26_08_2"
    Bundle = "com.qingyu.elementx.linkdevice.final"
    Title = "Link New Device"
    Expected = @("Link New Device", "final 26.08.2", "Function-level Android parity")
  }
)

function Capture-AndroidReference {
  Write-Host "[android] checking device list"
  $devices = adb devices -l | Out-String
  $result = [pscustomobject][ordered]@{
    devices = $devices.Trim()
    package = $AndroidPackage
    status = "skipped:no_android_reference_package"
    screenshot = $null
    uiDump = $null
  }

  if ($AndroidPackage.Length -eq 0) {
    return $result
  }

  Write-Host "[android] checking package $AndroidPackage"
  $packages = adb shell pm list packages | Out-String
  if ($packages.Contains("package:$AndroidPackage")) {
    if ($AndroidLaunchActivity.Length -gt 0) {
      adb shell am start -n "$AndroidPackage/$AndroidLaunchActivity" | Out-Null
    } else {
      adb shell monkey -p $AndroidPackage 1 | Out-Null
    }
    Start-Sleep -Seconds 3
    $shot = Join-Path $outDir "android_reference.png"
    $dump = Join-Path $outDir "android_reference_window.xml"
    adb exec-out screencap -p > $shot
    adb shell uiautomator dump /sdcard/android_reference_window.xml | Out-Null
    adb pull /sdcard/android_reference_window.xml $dump | Out-Null
    $result.status = "captured"
    $result.screenshot = $shot
    $result.uiDump = $dump
  }
  return $result
}

function Get-TextLeft($text, $label) {
  $escaped = [regex]::Escape($label)
  $matches = [regex]::Matches($text, "Text $escaped \[id:\d+\] \[top: \d+, left: (?<left>\d+),")
  if ($matches.Count -eq 0) {
    return $null
  }
  return [int]$matches[0].Groups["left"].Value
}

function Save-HarmonySnapshot($localPath) {
  $remotePath = "/data/local/tmp/" + ([IO.Path]::GetFileName($localPath))
  & $hdc shell snapshot_display -f $remotePath | Out-Null
  & $hdc file recv $remotePath $localPath | Out-Null
}

function Save-HarmonyUiTree($localPath) {
  & $emulator -instance $HarmonyInstance -uiLayout -a | Out-Null
  Copy-Item -LiteralPath "C:\Users\xiexi\AppData\Local\Huawei\Emulator\deployed\$HarmonyInstance\uiLayout\analysis.md" -Destination $localPath -Force
  return (Get-Content -LiteralPath $localPath -Raw)
}

function Get-WidgetCenter($tree, $label) {
  $escaped = [regex]::Escape($label)
  $matches = [regex]::Matches($tree, "$escaped \[id:\d+\] \[top: (?<top>\d+), left: (?<left>\d+), width: (?<width>\d+), height: (?<height>\d+)\]")
  if ($matches.Count -eq 0) {
    return $null
  }
  $m = $matches[0]
  $x = [int]$m.Groups["left"].Value + [math]::Floor([int]$m.Groups["width"].Value / 2)
  $y = [int]$m.Groups["top"].Value + [math]::Floor([int]$m.Groups["height"].Value / 2)
  return "$x $y"
}

function Click-WidgetByLabel($tree, $label) {
  $center = Get-WidgetCenter $tree $label
  if ($null -ne $center) {
    $clickOutput = & $emulator -instance $HarmonyInstance -click $center | Out-String
    Start-Sleep -Seconds 1
    return ($clickOutput -match "success")
  }
  return $false
}

function Test-HarmonyCase($case) {
  Write-Host "[harmony] install/start/capture $($case.Id)"
  $caseDir = Join-Path (Join-Path $root "final_dev_nodes") $case.Id
  $hap = Join-Path $caseDir "entry\build\default\outputs\default\entry-default-unsigned.hap"
  $safeId = $case.Id
  $shotTimeline = Join-Path $outDir "$safeId.timeline.jpeg"
  $shotSettings = Join-Path $outDir "$safeId.settings.jpeg"
  $shotContract = Join-Path $outDir "$safeId.contract.jpeg"
  $treeTimeline = Join-Path $outDir "$safeId.timeline.ui.md"
  $treeSettings = Join-Path $outDir "$safeId.settings.ui.md"
  $treeContract = Join-Path $outDir "$safeId.contract.ui.md"

  & $hdc install -r $hap | Out-Null
  & $hdc shell aa start -b $case.Bundle -a EntryAbility | Out-Null
  Start-Sleep -Seconds 3
  $initialTree = Save-HarmonyUiTree (Join-Path $outDir "$safeId.initial.ui.md")
  [void](Click-WidgetByLabel $initialTree "Timeline")
  Start-Sleep -Seconds 1
  Save-HarmonySnapshot $shotTimeline
  $timelineTree = Save-HarmonyUiTree $treeTimeline

  $settingsClicked = Click-WidgetByLabel $timelineTree "Settings"
  if ($settingsClicked) {
    Save-HarmonySnapshot $shotSettings
    $settingsTree = Save-HarmonyUiTree $treeSettings
  } else {
    $settingsTree = ""
  }

  $contractClicked = Click-WidgetByLabel ($timelineTree + "`n" + $settingsTree) "Contract"
  if ($contractClicked) {
    Save-HarmonySnapshot $shotContract
    $contractTree = Save-HarmonyUiTree $treeContract
  } else {
    $contractTree = ""
  }

  $tree = $timelineTree + "`n" + $settingsTree + "`n" + $contractTree
  $missing = @()
  foreach ($expectedText in $case.Expected) {
    if (-not $tree.Contains($expectedText)) {
      $missing += $expectedText
    }
  }

  $senderLeft = Get-TextLeft $timelineTree "Alice"
  $timeLeft = Get-TextLeft $timelineTree "09:20"
  $timeSeparated = $false
  if ($null -ne $senderLeft -and $null -ne $timeLeft) {
    $timeSeparated = (($timeLeft - $senderLeft) -ge 180)
  }

  return [pscustomobject][ordered]@{
    id = $case.Id
    bundle = $case.Bundle
    status = $(if ($missing.Count -eq 0 -and $timeSeparated) { "passed" } else { "failed" })
    missingTexts = $missing
    senderLeft = $senderLeft
    timeLeft = $timeLeft
    senderTimestampSeparated = $timeSeparated
    screenshots = @($shotTimeline, $shotSettings, $shotContract)
    uiTrees = @($treeTimeline, $treeSettings, $treeContract)
    settingsClicked = $settingsClicked
    contractClicked = $contractClicked
  }
}

$androidResult = Capture-AndroidReference
$targets = & $hdc list targets -v | Out-String
$harmonyResults = @()

if ($targets -match "Connected") {
  foreach ($case in $cases) {
    $harmonyResults += (Test-HarmonyCase $case)
  }
} else {
  foreach ($case in $cases) {
    $harmonyResults += [pscustomobject][ordered]@{
      id = $case.Id
      bundle = $case.Bundle
      status = "blocked:no_hdc_target"
    }
  }
}

$report = [ordered]@{
  generatedAt = (Get-Date).ToString("s")
  android = $androidResult
  harmonyTarget = $targets.Trim()
  harmonyInstance = $HarmonyInstance
  cases = $harmonyResults
}

$jsonPath = Join-Path $outDir "ui_dynamic_report.json"
$mdPath = Join-Path $outDir "ui_dynamic_report.md"
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$md = @()
$md += "# UI Dynamic Test Report"
$md += ""
$md += "- Generated: $($report.generatedAt)"
$md += "- Android: $($androidResult.status)"
$md += "- Harmony target: $($targets.Trim())"
$md += "- Harmony instance: $HarmonyInstance"
$md += ""
$md += "## Cases"
foreach ($item in $harmonyResults) {
  $md += ""
  $md += "### $($item.id)"
  $md += "- Status: $($item.status)"
  $md += "- Bundle: $($item.bundle)"
  if ($null -ne $item.PSObject.Properties["senderTimestampSeparated"]) {
    $md += "- Sender/timestamp separated: $($item.senderTimestampSeparated) (left: $($item.senderLeft) -> $($item.timeLeft))"
  }
  if ($null -ne $item.PSObject.Properties["missingTexts"] -and $item.missingTexts.Count -gt 0) {
    $md += "- Missing texts: $($item.missingTexts -join ', ')"
  }
  if ($null -ne $item.PSObject.Properties["screenshots"]) {
    $md += "- Screenshots: $($item.screenshots -join '; ')"
    $md += "- UI trees: $($item.uiTrees -join '; ')"
    $md += "- Settings clicked: $($item.settingsClicked)"
    $md += "- Contract clicked: $($item.contractClicked)"
  }
}
$md -join "`n" | Set-Content -LiteralPath $mdPath -Encoding UTF8

Write-Host "Wrote $jsonPath"
Write-Host "Wrote $mdPath"
$harmonyResults | Format-Table id,status,senderTimestampSeparated,senderLeft,timeLeft -AutoSize
