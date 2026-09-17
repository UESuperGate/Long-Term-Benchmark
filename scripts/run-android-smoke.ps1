param(
  [string]$TaskId = "",
  [ValidateSet("Both", "Base", "Final")]
  [string]$Release = "Both",
  [string]$AndroidSdk = "C:\Users\xiexi\AppData\Local\Android\Sdk",
  [string]$Package = "io.element.android.x.debug",
  [string]$Device = "",
  [switch]$KeepInstalled
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue) {
  $Global:PSNativeCommandUseErrorActionPreference = $false
}
$root = "C:\Users\xiexi\qingyu"
$outDir = Join-Path $root "verification_reports\state_dynamic\android_smoke"
$matrixJson = Join-Path $root "verification_reports\state_dynamic\state_dynamic_target_matrix.json"
$matrixScript = Join-Path $root "scripts\state_target_matrix.py"
$adb = Join-Path $AndroidSdk "platform-tools\adb.exe"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

if (-not (Test-Path -LiteralPath $adb)) {
  throw "adb.exe not found at $adb"
}
if (-not (Test-Path -LiteralPath $matrixJson)) {
  python $matrixScript | Out-Host
}

function Invoke-Adb {
  param([string[]]$AdbArgs)
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    if ($Device.Length -gt 0) {
      return & $adb -s $Device @AdbArgs 2>&1
    }
    return & $adb @AdbArgs 2>&1
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
}

function Get-AdbText {
  param([string[]]$AdbArgs)
  return (Invoke-Adb -AdbArgs $AdbArgs | Out-String).Trim()
}

function Get-InstalledVersion {
  $dump = Get-AdbText -AdbArgs @("shell", "dumpsys", "package", $Package)
  $versionCode = ""
  $versionName = ""
  foreach ($line in ($dump -split "`r?`n")) {
    if ($line -match "versionCode=([0-9]+)") {
      $versionCode = $Matches[1]
    }
    if ($line -match "versionName=([^`r`n ]+)") {
      $versionName = $Matches[1]
    }
  }
  return [pscustomobject][ordered]@{
    versionCode = $versionCode
    versionName = $versionName
  }
}

$devices = Get-AdbText -AdbArgs @("devices", "-l")
if (-not ($devices -match "\bdevice\b")) {
  throw "No Android emulator/device is visible to adb. Output: $devices"
}

$matrix = Get-Content -LiteralPath $matrixJson -Raw -Encoding UTF8 | ConvertFrom-Json
$targets = @($matrix.targets | Where-Object { $_.platform -eq "android" })
if ($TaskId.Length -gt 0) {
  $targets = @($targets | Where-Object { $_.taskId -eq $TaskId })
}
if ($Release -ne "Both") {
  $wantedRelease = $Release.ToLowerInvariant()
  $targets = @($targets | Where-Object { $_.release -eq $wantedRelease })
}

$results = @()
foreach ($target in $targets) {
  $targetId = [string]$target.targetId
  $safeTargetId = $targetId -replace "[^A-Za-z0-9_.-]", "_"
  $apk = [string]$target.apk
  $screenshot = Join-Path $outDir "$safeTargetId.png"
  $xml = Join-Path $outDir "$safeTargetId.xml"
  $remoteXml = "/sdcard/$safeTargetId.xml"

  if (-not (Test-Path -LiteralPath $apk)) {
    $results += [pscustomobject][ordered]@{
      targetId = $targetId
      taskId = $target.taskId
      release = $target.release
      tag = $target.tag
      status = "blocked:apk_missing"
      apk = $apk
      package = $Package
      installedVersionCode = ""
      installedVersionName = ""
      currentActivity = ""
      uiTree = ""
      screenshot = ""
      installOutput = ""
      launchOutput = ""
    }
    continue
  }

  if (-not $KeepInstalled) {
    Invoke-Adb -AdbArgs @("uninstall", $Package) | Out-Null
  }

  $installOutput = Get-AdbText -AdbArgs @("install", $apk)
  if ($LASTEXITCODE -ne 0 -or -not ($installOutput -match "Success")) {
    $results += [pscustomobject][ordered]@{
      targetId = $targetId
      taskId = $target.taskId
      release = $target.release
      tag = $target.tag
      status = "failed:install"
      apk = $apk
      package = $Package
      installedVersionCode = ""
      installedVersionName = ""
      currentActivity = ""
      uiTree = ""
      screenshot = ""
      installOutput = $installOutput
      launchOutput = ""
    }
    continue
  }

  Invoke-Adb -AdbArgs @("shell", "pm", "clear", $Package) | Out-Null
  $launchOutput = Get-AdbText -AdbArgs @("shell", "monkey", "-p", $Package, "-c", "android.intent.category.LAUNCHER", "1")
  Start-Sleep -Seconds 5
  $version = Get-InstalledVersion
  $activity = Get-AdbText -AdbArgs @("shell", "dumpsys", "activity", "activities")
  $currentActivity = ""
  foreach ($line in ($activity -split "`r?`n")) {
    if ($line -match "ResumedActivity|topResumedActivity|mResumedActivity") {
      $currentActivity = $line.Trim()
      break
    }
  }

  if ($Device.Length -gt 0) {
    & $adb -s $Device exec-out screencap -p > $screenshot
  } else {
    & $adb exec-out screencap -p > $screenshot
  }
  Invoke-Adb -AdbArgs @("shell", "uiautomator", "dump", $remoteXml) | Out-Null
  Invoke-Adb -AdbArgs @("pull", $remoteXml, $xml) | Out-Null
  if (-not (Test-Path -LiteralPath $xml)) {
    Invoke-Adb -AdbArgs @("shell", "uiautomator", "dump", "/sdcard/window.xml") | Out-Null
    Invoke-Adb -AdbArgs @("pull", "/sdcard/window.xml", $xml) | Out-Null
  }
  $xmlText = if (Test-Path -LiteralPath $xml) { Get-Content -LiteralPath $xml -Raw -Encoding UTF8 } else { "" }
  $hasScreenshot = (Test-Path -LiteralPath $screenshot) -and ((Get-Item -LiteralPath $screenshot).Length -gt 0)
  $hasUiTree = Test-Path -LiteralPath $xml
  $status = if (($xmlText -match $Package -or $currentActivity -match [regex]::Escape($Package)) -and $hasScreenshot -and $hasUiTree) {
    "launched"
  } elseif ($currentActivity -match [regex]::Escape($Package)) {
    "warning:launched_but_capture_incomplete"
  } else {
    "warning:installed_but_launch_not_confirmed"
  }

  $results += [pscustomobject][ordered]@{
    targetId = $targetId
    taskId = $target.taskId
    release = $target.release
    tag = $target.tag
    status = $status
    apk = $apk
    package = $Package
    installedVersionCode = $version.versionCode
    installedVersionName = $version.versionName
    currentActivity = $currentActivity
    uiTree = $xml
    screenshot = $screenshot
    installOutput = $installOutput
    launchOutput = $launchOutput
  }
}

$summary = [ordered]@{
  generatedAt = (Get-Date).ToString("s")
  adb = $adb
  device = $Device
  package = $Package
  taskFilter = $TaskId
  releaseFilter = $Release
  results = $results
}

$jsonPath = Join-Path $outDir "android_smoke_report.json"
$mdPath = Join-Path $outDir "android_smoke_report.md"
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$lines = @()
$lines += "# Android Smoke Report"
$lines += ""
$lines += ("- Generated: {0}" -f $summary.generatedAt)
$lines += ("- Package: {0}" -f $Package)
$launchedCount = @($results | Where-Object { $_.status -eq "launched" }).Count
$warningCount = @($results | Where-Object { $_.status -like "warning:*" }).Count
$failedCount = @($results | Where-Object { $_.status -like "failed:*" }).Count
$blockedCount = @($results | Where-Object { $_.status -like "blocked:*" }).Count
$lines += ("- Results: launched {0}, warnings {1}, failed {2}, blocked {3}" -f $launchedCount, $warningCount, $failedCount, $blockedCount)
$lines += ""
$lines += "| Target | Tag | Status | Installed | Screenshot | UI Tree |"
$lines += "| --- | --- | --- | --- | --- | --- |"
foreach ($result in $results) {
  $installed = if ($result.installedVersionName.Length -gt 0) { "$($result.installedVersionName) / $($result.installedVersionCode)" } else { "" }
  $shotName = if ($result.screenshot.Length -gt 0) { [System.IO.Path]::GetFileName($result.screenshot) } else { "" }
  $xmlName = if ($result.uiTree.Length -gt 0) { [System.IO.Path]::GetFileName($result.uiTree) } else { "" }
  $lines += ("| {0} | {1} | {2} | {3} | {4} | {5} |" -f $result.targetId, $result.tag, $result.status, $installed, $shotName, $xmlName)
}
$lines | Set-Content -LiteralPath $mdPath -Encoding UTF8

$results | Format-Table targetId,tag,status,installedVersionName,installedVersionCode -AutoSize
