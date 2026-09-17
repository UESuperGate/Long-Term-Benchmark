param(
  [string]$Root = "C:\Users\xiexi\qingyu",
  [string]$TaskId = "",
  [ValidateSet("Both", "Android", "ArkTS")]
  [string]$Platform = "Both",
  [ValidateSet("Both", "Base", "Final")]
  [string]$Release = "Both",
  [ValidateSet("Both", "Base", "GroundtruthFinal", "AgentResult")]
  [string]$TargetRole = "Both",
  [string]$CaseId = "",
  [string]$AndroidSerial = "",
  [string]$HarmonyInstance = "Custom Screen",
  [string]$AndroidSdk = "C:\Users\xiexi\AppData\Local\Android\Sdk",
  [string]$HdcPath = "C:\Users\xiexi\AppData\Local\OpenHarmony\Sdk\23\toolchains\hdc.exe",
  [string]$HarmonyEmulator = "C:\Program Files\Huawei\DevEco Studio\tools\emulator\Emulator.exe",
  [string]$ReportDir = "",
  [int]$LaunchDelayMs = 1200,
  [switch]$AllowTargetPolaritySmoke,
  [switch]$AllowStateObservationSmoke,
  [switch]$SkipDeviceProbe
)

$ErrorActionPreference = "Stop"

$outDir = if ($ReportDir.Length -gt 0) { $ReportDir } else { Join-Path $Root "verification_reports\state_dynamic" }
$probeDir = Join-Path $outDir "strict_matrix_probe"
$matrixScript = Join-Path $Root "scripts\state_target_matrix.py"
$auditScript = Join-Path $Root "scripts\strict_state_oracle_audit.py"
$bindingScript = Join-Path $Root "scripts\generate_state_binding_manifests.py"
$matrixPath = Join-Path $outDir "state_dynamic_target_matrix.json"
$auditPath = Join-Path $outDir "strict_state_oracle_audit.json"
$reportJson = Join-Path $outDir "strict_state_matrix_run_report.json"
$reportMd = Join-Path $outDir "strict_state_matrix_run_report.md"
$bindingDir = Join-Path $Root "state_tests\bindings"
$adb = Join-Path $AndroidSdk "platform-tools\adb.exe"
$androidHarnessActivity = "io.element.android.x.MainActivity"
$script:InstalledAndroidTargetId = ""

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path $probeDir | Out-Null
$env:QINGYU_STATE_REPORT_DIR = $outDir
if ($TaskId.Length -gt 0) {
  $env:QINGYU_TASK_FILTER = $TaskId
} else {
  Remove-Item Env:QINGYU_TASK_FILTER -ErrorAction SilentlyContinue
}

function Safe-Name {
  param([string]$Value)
  $safe = ($Value -replace '[^A-Za-z0-9_.-]', '_')
  if ($safe.Length -le 96) {
    return $safe
  }
  $md5 = [System.Security.Cryptography.MD5]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($safe)
    $hashBytes = $md5.ComputeHash($bytes)
    $hash = -join ($hashBytes | ForEach-Object { $_.ToString("x2") })
    return "$($safe.Substring(0, 80))_$($hash.Substring(0, 16))"
  } finally {
    $md5.Dispose()
  }
}

function Get-TargetRole {
  param($Target)
  if ($null -ne $Target -and $Target.PSObject.Properties.Name -contains "targetRole" -and [string]$Target.targetRole -ne "") {
    return [string]$Target.targetRole
  }
  if ($null -ne $Target -and [string]$Target.release -eq "base") {
    return "base"
  }
  return "groundtruth_final"
}

function Test-TargetRoleMatch {
  param($Target, [string]$WantedRole)
  if ($WantedRole -eq "Both") {
    return $true
  }
  $role = (Get-TargetRole $Target).ToLowerInvariant()
  if ($WantedRole -eq "Base") {
    return $role -eq "base"
  }
  if ($WantedRole -eq "GroundtruthFinal") {
    return $role -eq "groundtruth_final"
  }
  if ($WantedRole -eq "AgentResult") {
    return $role -eq "agent_result"
  }
  return $false
}

function Invoke-TextCommand {
  param([string]$Exe, [string[]]$CommandArgs)
  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    $output = & $Exe @CommandArgs 2>&1
    return [pscustomobject]@{
      exitCode = $LASTEXITCODE
      text = ($output -join "`n")
    }
  } finally {
    $ErrorActionPreference = $previousPreference
  }
}

function Invoke-AdbCommand {
  param([string[]]$CommandArgs)
  if ($AndroidSerial.Length -gt 0) {
    return Invoke-TextCommand -Exe $adb -CommandArgs (@("-s", $AndroidSerial) + $CommandArgs)
  }
  return Invoke-TextCommand -Exe $adb -CommandArgs $CommandArgs
}

function Test-HdcReady {
  if (-not (Test-Path -LiteralPath $HdcPath)) {
    return $false
  }
  $targets = Invoke-TextCommand -Exe $HdcPath -CommandArgs @("list", "targets", "-v")
  return ($targets.exitCode -eq 0 -and $targets.text.Length -gt 0 -and -not $targets.text.Contains("[Empty]"))
}

function Test-AdbReady {
  if (-not (Test-Path -LiteralPath $adb)) {
    return $false
  }
  if ($AndroidSerial.Length -gt 0) {
    $state = Invoke-AdbCommand -CommandArgs @("get-state")
    return ($state.exitCode -eq 0 -and $state.text.Trim() -eq "device")
  }
  $devices = Invoke-TextCommand -Exe $adb -CommandArgs @("devices", "-l")
  if ($devices.exitCode -ne 0) {
    return $false
  }
  foreach ($line in $devices.text -split "`n") {
    if ($line.Trim() -match "^\S+\s+device\s") {
      return $true
    }
  }
  return $false
}

function Read-TextSafe {
  param([string]$Path)
  if (Test-Path -LiteralPath $Path) {
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8)
  }
  return ""
}

function Capture-HarmonyLayoutForCase {
  param(
    [string]$CaseId,
    [string]$Bundle,
    [string]$LayoutOut
  )
  $readyMarker = "state_test_ready:$CaseId"
  $captureText = ""
  $remoteLayout = "/data/local/tmp/qingyu_strict_$((Safe-Name $CaseId)).json"
  for ($attempt = 1; $attempt -le 3; $attempt += 1) {
    Remove-Item -LiteralPath $LayoutOut -Force -ErrorAction SilentlyContinue
    Invoke-TextCommand -Exe $HdcPath -CommandArgs @("shell", "rm", "-f", $remoteLayout) | Out-Null
    $capture = Invoke-TextCommand -Exe $HdcPath -CommandArgs @("shell", "uitest", "dumpLayout", "-p", $remoteLayout, "-a", "-b", $Bundle)
    $captureText = $capture.text
    Start-Sleep -Milliseconds 500
    $recv = Invoke-TextCommand -Exe $HdcPath -CommandArgs @("file", "recv", $remoteLayout, $LayoutOut)
    if ($recv.exitCode -eq 0 -and (Test-Path -LiteralPath $LayoutOut)) {
      $content = Read-TextSafe $LayoutOut
      if ($content.Length -gt 0) {
        if ($content.Contains($readyMarker)) {
          return [pscustomobject]@{
            captured = $true
            fresh = $true
            content = $content
            detail = "$captureText`n$($recv.text)"
          }
        }
        $captureText = "$captureText`n$($recv.text)"
      }
    }
    Start-Sleep -Milliseconds 700
  }
  $fallbackContent = Read-TextSafe $LayoutOut
  return [pscustomobject]@{
    captured = (Test-Path -LiteralPath $LayoutOut)
    fresh = $false
    content = $fallbackContent
    detail = $captureText
  }
}

function Probe-Key {
  param([string]$TargetId, [string]$CaseId)
  return "$TargetId`u{241F}$CaseId"
}

function Test-CaptureToken {
  param([string]$Content, [string]$Token)
  if ($Token.Length -eq 0) {
    return $true
  }
  return ($Content.Contains($Token))
}

function Get-CaseSemanticFacts {
  param($BindingCase)
  $facts = [System.Collections.Generic.List[string]]::new()
  if ($null -eq $BindingCase) {
    return @()
  }
  $selectors = $BindingCase.selectors
  if ($null -ne $selectors) {
    foreach ($bucket in @("visible", "hidden", "enabled", "disabled")) {
      foreach ($token in @($selectors.$bucket)) {
        if ([string]$token -ne "") {
          $facts.Add("$($bucket):$token")
        }
      }
    }
    $properties = $selectors.properties
    if ($null -ne $properties) {
      foreach ($property in $properties.PSObject.Properties) {
        $facts.Add("property:$($property.Name)=$($property.Value)")
      }
    }
  }
  foreach ($transition in @($BindingCase.transitionSelectors)) {
    $ordinal = [string]$transition.ordinal
    $event = [string]$transition.event
    if ($ordinal.Length -gt 0 -and $event.Length -gt 0) {
      $facts.Add("transition:${ordinal}:$event")
    }
    foreach ($bucket in @("visible", "hidden", "enabled", "disabled")) {
      foreach ($token in @($transition.$bucket)) {
        if ([string]$token -ne "" -and $ordinal.Length -gt 0) {
          $facts.Add("transition:${ordinal}:${bucket}:$token")
        }
      }
    }
    $properties = $transition.properties
    if ($null -ne $properties) {
      foreach ($property in $properties.PSObject.Properties) {
        if ($ordinal.Length -gt 0) {
          $facts.Add("transition:${ordinal}:property:$($property.Name)=$($property.Value)")
        }
      }
    }
  }
  return @($facts | Sort-Object -Unique)
}

function Get-ObservedSemanticFacts {
  param([string]$Content)
  $facts = [System.Collections.Generic.HashSet[string]]::new()
  foreach ($match in [regex]::Matches($Content, "strict_state_fact:([^`"'<>\r\n]+)")) {
    [void]$facts.Add([System.Net.WebUtility]::HtmlDecode($match.Groups[1].Value))
  }
  return @($facts)
}

function Load-StateBindingCases {
  param([string]$BindingDir)
  $cases = @{}
  if (-not (Test-Path -LiteralPath $BindingDir)) {
    return $cases
  }
  foreach ($path in Get-ChildItem -LiteralPath $BindingDir -Filter "*.binding.json" -File | Sort-Object Name) {
    if ($path.Name -eq "state_binding_manifest_index.json") {
      continue
    }
    $manifest = Get-Content -LiteralPath $path.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($case in @($manifest.cases)) {
      $cases[[string]$case.caseId] = $case
    }
  }
  return $cases
}

function Invoke-PerCaseUiScoring {
  param($AuditCase, $BindingCase, $Probe, [string]$ExpectedPolarity)
  $capturePath = ""
  if ($Probe.platform -eq "android") {
    $capturePath = [string]$Probe.xml
  } elseif ($Probe.platform -eq "arkts") {
    $capturePath = [string]$Probe.layout
  }
  $content = Read-TextSafe $capturePath
  $ready = $content.Contains("state_test_ready:$($AuditCase.caseId)")
  $caseMarker = $content.Contains("strict_state_case:$($AuditCase.caseId)")
  $stateObservationAdapter = (
    $content.Contains("strict_state_observed:adapter=") -and
    $content.Contains("_observation_only") -and
    $Probe.strictRuntimeStateObserved
  )
  $tokens = $AuditCase.assertionTokens
  $missingRequired = @()
  $unexpectedForbidden = @()
  $transitionTraceMissing = $false
  $expectedFacts = @(Get-CaseSemanticFacts $BindingCase)
  $observedFacts = Get-ObservedSemanticFacts $content

  if ($expectedFacts.Count -gt 0) {
    foreach ($fact in $expectedFacts) {
      if ($observedFacts -notcontains $fact) {
        $missingRequired += "strict_state_fact:$fact"
      }
    }
    $hasProtocol = ($ready -and $caseMarker)
    if (-not $hasProtocol) {
      $observedPolarity = "fail"
      $status = if ($ExpectedPolarity -eq "pass") { "protocolFail" } else { "matched" }
      $verdict = if ($status -eq "protocolFail") { "excluded" } else { $status }
      return [pscustomobject][ordered]@{
        observedPolarity = $observedPolarity
        strictStatus = $status
        verdict = $verdict
        reason = "Harness protocol failed before semantic scoring. ready=$ready caseMarker=$caseMarker."
        readyMarkerObserved = $ready
        caseMarkerObserved = $caseMarker
        missingRequired = @("state_test_ready:$($AuditCase.caseId)", "strict_state_case:$($AuditCase.caseId)")
        unexpectedForbidden = @()
        transitionTraceMissing = $false
        scoringMode = "strict_harness_protocol"
        harnessComplianceStatus = "protocol_missing_ready_or_case"
        semanticStatus = "not_scored"
      }
    }
    if ($observedFacts.Count -eq 0 -and $ExpectedPolarity -eq "pass") {
      return [pscustomobject][ordered]@{
        observedPolarity = "fail"
        strictStatus = "protocolFail"
        verdict = "excluded"
        reason = "Harness protocol failed: final target reached the case but emitted no strict_state_fact markers, so semantic scoring cannot start."
        readyMarkerObserved = $ready
        caseMarkerObserved = $caseMarker
        missingRequired = $missingRequired
        unexpectedForbidden = @()
        transitionTraceMissing = $false
        scoringMode = "strict_harness_protocol"
        harnessComplianceStatus = "missing_strict_state_facts"
        semanticStatus = "not_scored"
      }
    }
    $hasSemanticOracle = ($missingRequired.Count -eq 0)
    $observedPolarity = if ($hasSemanticOracle) { "pass" } else { "fail" }
    $status = if ($observedPolarity -eq $ExpectedPolarity) { "matched" } else { "mismatch" }
    $reason = if ($hasSemanticOracle) {
      "Strict semantic facts matched the evaluator binding manifest."
    } else {
      "Strict semantic facts missing. ready=$ready caseMarker=$caseMarker missingFacts=$($missingRequired.Count) expectedFacts=$($expectedFacts.Count)."
    }
    return [pscustomobject][ordered]@{
      observedPolarity = $observedPolarity
      strictStatus = $status
      verdict = $status
      reason = $reason
      readyMarkerObserved = $ready
      caseMarkerObserved = $caseMarker
      missingRequired = $missingRequired
      unexpectedForbidden = @()
      transitionTraceMissing = $false
      scoringMode = "strict_semantic_facts"
      harnessComplianceStatus = "passed"
      semanticStatus = if ($hasSemanticOracle) { "passed" } else { "failed" }
    }
  }

  foreach ($bucket in @("visible", "enabled", "properties")) {
    foreach ($token in @($tokens.$bucket)) {
      if (-not (Test-CaptureToken -Content $content -Token ([string]$token))) {
        $missingRequired += "$($bucket):$token"
      }
    }
  }
  foreach ($bucket in @("hidden", "disabled")) {
    foreach ($token in @($tokens.$bucket)) {
      if (Test-CaptureToken -Content $content -Token ([string]$token)) {
        $unexpectedForbidden += "$($bucket):$token"
      }
    }
  }
  if ([int]$AuditCase.transitionCount -gt 0) {
    for ($ordinal = 1; $ordinal -le [int]$AuditCase.transitionCount; $ordinal++) {
      $transitionMarker = "strict_state_transition:$($AuditCase.caseId):$ordinal"
      if (-not $content.Contains($transitionMarker)) {
        $missingRequired += "transition_trace:$transitionMarker"
        $transitionTraceMissing = $true
      }
    }
  }

  if ($stateObservationAdapter -and $AllowStateObservationSmoke) {
    $observedPolarity = if ([string]$Probe.strictFeatureAvailable -eq "true") { "pass" } else { "fail" }
    $status = if (($ready -and $caseMarker) -and $observedPolarity -eq $ExpectedPolarity) { "matched" } else { "mismatch" }
    $reason = if ($status -eq "matched") {
      "State observation adapter matched expected base/final polarity for this case."
    } else {
      "State observation adapter failed. ready=$ready caseMarker=$caseMarker featureAvailable=$($Probe.strictFeatureAvailable)."
    }
    return [pscustomobject][ordered]@{
      observedPolarity = $observedPolarity
      strictStatus = $status
      verdict = $status
      reason = $reason
      readyMarkerObserved = $ready
      caseMarkerObserved = $caseMarker
      missingRequired = @()
      unexpectedForbidden = @()
      transitionTraceMissing = $false
      scoringMode = "$($Probe.platform)_state_observation_adapter"
    }
  }
  if ($stateObservationAdapter -and -not $AllowStateObservationSmoke) {
    $observedPolarity = "fail"
    $status = if ($observedPolarity -eq $ExpectedPolarity) { "matched" } else { "mismatch" }
    return [pscustomobject][ordered]@{
      observedPolarity = $observedPolarity
      strictStatus = $status
      verdict = $status
      reason = "State observation adapter exposed target-level feature availability only. Semantic testcase scoring requires strict_state_fact markers; use -AllowStateObservationSmoke for legacy smoke rescoring."
      readyMarkerObserved = $ready
      caseMarkerObserved = $caseMarker
      missingRequired = @("strict_state_fact:*")
      unexpectedForbidden = @()
      transitionTraceMissing = $false
      scoringMode = "$($Probe.platform)_state_observation_smoke_rejected"
    }
  }

  $hasPerCaseOracle = ($ready -and $caseMarker -and (($missingRequired.Count + $unexpectedForbidden.Count) -eq 0))
  $observedPolarity = if ($hasPerCaseOracle) { "pass" } else { "fail" }
  $status = if ($observedPolarity -eq $ExpectedPolarity) { "matched" } else { "mismatch" }
  $verdict = $status
  $reason = if ($hasPerCaseOracle) {
    "Per-case UI tree assertions matched the binding manifest."
  } else {
    "Per-case assertions failed. ready=$ready caseMarker=$caseMarker missingRequired=$($missingRequired.Count) unexpectedForbidden=$($unexpectedForbidden.Count)."
  }
  return [pscustomobject][ordered]@{
    observedPolarity = $observedPolarity
    strictStatus = $status
    verdict = $verdict
    reason = $reason
    readyMarkerObserved = $ready
    caseMarkerObserved = $caseMarker
    missingRequired = $missingRequired
    unexpectedForbidden = $unexpectedForbidden
    transitionTraceMissing = $transitionTraceMissing
    scoringMode = "per_case_ui_tree_tokens"
  }
}

function Has-LegacyArktsMarker {
  param($Target)
  if (-not $Target.projectDir) {
    return $false
  }
  $index = Join-Path ([string]$Target.projectDir) "entry\src\main\ets\pages\Index.ets"
  $text = Read-TextSafe $index
  return ($text -match "state_test_result" -or $text -match "strict_state_assertion:final_feature_available")
}

function Has-LegacyAndroidMarker {
  param($Target)
  if (-not $Target.worktree) {
    return $false
  }
  $debugHarnessDir = Join-Path ([string]$Target.worktree) "app\src\debug"
  if (-not (Test-Path -LiteralPath $debugHarnessDir)) {
    return $false
  }
  $hits = @(Get-ChildItem -LiteralPath $debugHarnessDir -Recurse -File -Include "*.kt", "*.xml" -ErrorAction SilentlyContinue |
    Select-String -Pattern "state_test_result", "state_test_expected", "state_test_version_name", "state_test_version_code", "strict_state_assertion:final_feature_available" -SimpleMatch -ErrorAction SilentlyContinue |
    Select-Object -First 1)
  return ($hits.Count -gt 0)
}

function Has-MarkerOnlyAndroidHarness {
  param($Target)
  if (-not $Target.worktree) {
    return $false
  }
  $debugHarness = Join-Path ([string]$Target.worktree) "app\src\debug\kotlin\io\element\android\x\StateTestHarnessActivity.kt"
  if (-not (Test-Path -LiteralPath $debugHarness)) {
    return $false
  }
  $text = Read-TextSafe $debugHarness
  return (
    $text -match "class\s+StateTestHarnessActivity\s*:\s*Activity" -and
    $text -match "LinearLayout" -and
    $text -match "addMarker\(" -and
    $text -match "setContentView\(root\)"
  )
}

function Get-FirstCaseForTarget {
  param($Target, $CaseRows)
  $rows = @($CaseRows | Where-Object { $_.targetId -eq $Target.targetId })
  if ($rows.Count -eq 0) {
    return $null
  }
  return $rows[0]
}

function Save-AndroidScreenshot {
  param([string]$Path)
  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    if ($AndroidSerial.Length -gt 0) {
      & $adb -s $AndroidSerial exec-out screencap -p > $Path
    } else {
      & $adb exec-out screencap -p > $Path
    }
    return $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousPreference
  }
}

function Probe-AndroidTarget {
  param($Target, $CaseRows)
  $case = Get-FirstCaseForTarget $Target $CaseRows
  $caseId = if ($null -eq $case) { "" } else { [string]$case.caseId }
  $targetDir = Join-Path $probeDir (Safe-Name ("$($Target.targetId):$caseId"))
  New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
  $apk = [string]$Target.apk
  $probe = [ordered]@{
    targetId = $Target.targetId
    caseId = $caseId
    platform = "android"
    release = $Target.release
    targetRole = Get-TargetRole $Target
    artifact = $apk
    artifactExists = (Test-Path -LiteralPath $apk)
    probed = $false
    installed = $false
    launched = $false
    captured = $false
    legacyMarkerObserved = $false
    strictRuntimeStateObserved = $false
    strictFeatureAvailable = ""
    status = "not_run"
    detail = ""
    xml = ""
    screenshot = ""
  }
  if ($SkipDeviceProbe) {
    $probe.status = "skipped:device_probe_disabled"
    return [pscustomobject]$probe
  }
  if (-not (Test-Path -LiteralPath $adb)) {
    $probe.status = "blocked:adb_missing"
    $probe.detail = $adb
    return [pscustomobject]$probe
  }
  if (-not $probe.artifactExists) {
    $probe.status = "blocked:apk_missing"
    return [pscustomobject]$probe
  }
  if (-not (Test-AdbReady)) {
    $devices = Invoke-TextCommand -Exe $adb -CommandArgs @("devices", "-l")
    $probe.status = "blocked:no_android_device"
    $probe.detail = $devices.text
    return [pscustomobject]$probe
  }
  $probe.probed = $true
  if ($script:InstalledAndroidTargetId -ne [string]$Target.targetId) {
    Invoke-AdbCommand -CommandArgs @("uninstall", [string]$Target.package) | Out-Null
    $install = Invoke-AdbCommand -CommandArgs @("install", "-r", $apk)
    if ($install.text -notmatch "Success") {
      $probe.status = "blocked:android_install_failed"
      $probe.detail = $install.text
      return [pscustomobject]$probe
    }
    $script:InstalledAndroidTargetId = [string]$Target.targetId
  }
  $probe.installed = $true
  $component = "$($Target.package)/$androidHarnessActivity"
  $xmlDevice = "/sdcard/strict_state_probe.xml"
  $xmlPath = Join-Path $targetDir "probe.xml"
  $pngPath = Join-Path $targetDir "probe.png"
  $launch = [pscustomobject]@{ exitCode = 1; text = "not launched" }
  $xml = ""
  for ($launchAttempt = 1; $launchAttempt -le 2; $launchAttempt += 1) {
    Invoke-AdbCommand -CommandArgs @("shell", "am", "force-stop", [string]$Target.package) | Out-Null
    Start-Sleep -Milliseconds 500
    $caseUri = "elementx://state-test?caseId=$caseId"
    $launch = Invoke-AdbCommand -CommandArgs @("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-c", "android.intent.category.DEFAULT", "-n", $component, "-d", $caseUri)
    Start-Sleep -Milliseconds $LaunchDelayMs
    for ($captureAttempt = 1; $captureAttempt -le 6; $captureAttempt += 1) {
      Invoke-AdbCommand -CommandArgs @("shell", "uiautomator", "dump", $xmlDevice) | Out-Null
      Invoke-AdbCommand -CommandArgs @("pull", $xmlDevice, $xmlPath) | Out-Null
      $xml = Read-TextSafe $xmlPath
      if ($xml.Contains("state_test_ready:$caseId") -or $xml.Contains("strict_state_case:$caseId")) {
        break
      }
      if ($xml -match "state_test_ready:[^`"'\s<]+") {
        break
      }
      Start-Sleep -Milliseconds 1000
    }
    if ($xml.Contains("state_test_ready:$caseId") -or $xml.Contains("strict_state_case:$caseId")) {
      break
    }
  }
  Save-AndroidScreenshot $pngPath | Out-Null
  $probe.launched = ($launch.text -notmatch "Error")
  $probe.captured = (Test-Path -LiteralPath $xmlPath)
  $probe.xml = $xmlPath
  $probe.screenshot = $pngPath
  $probe.legacyMarkerObserved = ($xml -match "state_test_result:(pass|fail)" -or $xml -match "strict_state_assertion:final_feature_available")
  $strictMatch = [regex]::Match($xml, "strict_state_observed:feature_available=(true|false)")
  $probe.strictRuntimeStateObserved = $strictMatch.Success
  if ($strictMatch.Success) {
    $probe.strictFeatureAvailable = $strictMatch.Groups[1].Value
  }
  if ($probe.legacyMarkerObserved -and -not $probe.strictRuntimeStateObserved) {
    $probe.status = "contaminated:legacy_version_marker_only"
  } elseif ($probe.strictRuntimeStateObserved) {
    $probe.status = "captured:strict_state"
  } elseif ($probe.launched) {
    $probe.status = "captured:no_state_oracle"
  } else {
    $probe.status = "blocked:android_launch_failed"
    $probe.detail = $launch.text
  }
  return [pscustomobject]$probe
}

function Probe-ArktsTarget {
  param($Target, $CaseRows)
  $case = Get-FirstCaseForTarget $Target $CaseRows
  $caseId = if ($null -eq $case) { "" } else { [string]$case.caseId }
  $targetDir = Join-Path $probeDir (Safe-Name ("$($Target.targetId):$caseId"))
  New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
  $hap = [string]$Target.hap
  $probe = [ordered]@{
    targetId = $Target.targetId
    caseId = $caseId
    platform = "arkts"
    release = $Target.release
    targetRole = Get-TargetRole $Target
    artifact = $hap
    artifactExists = (Test-Path -LiteralPath $hap)
    probed = $false
    installed = $false
    launched = $false
    captured = $false
    legacyMarkerObserved = $false
    strictRuntimeStateObserved = $false
    strictFeatureAvailable = ""
    status = "not_run"
    detail = ""
    layout = ""
  }
  if ($SkipDeviceProbe) {
    $probe.status = "skipped:device_probe_disabled"
    return [pscustomobject]$probe
  }
  if (-not (Test-Path -LiteralPath $HdcPath)) {
    $probe.status = "blocked:hdc_missing"
    $probe.detail = $HdcPath
    return [pscustomobject]$probe
  }
  if (-not (Test-Path -LiteralPath $HarmonyEmulator)) {
    $probe.status = "blocked:harmony_emulator_missing"
    $probe.detail = $HarmonyEmulator
    return [pscustomobject]$probe
  }
  if (-not (Test-HdcReady)) {
    $probe.status = "blocked:no_hdc_target"
    return [pscustomobject]$probe
  }
  if (-not $probe.artifactExists) {
    $probe.status = "blocked:hap_missing"
    return [pscustomobject]$probe
  }
  $probe.probed = $true
  Invoke-TextCommand -Exe $HdcPath -CommandArgs @("shell", "aa", "force-stop", [string]$Target.bundle) | Out-Null
  $install = Invoke-TextCommand -Exe $HdcPath -CommandArgs @("install", "-r", $hap)
  if ($install.exitCode -ne 0) {
    $probe.status = "blocked:arkts_install_failed"
    $probe.detail = $install.text
    return [pscustomobject]$probe
  }
  $probe.installed = $true
  $uri = "elementx://state-test?caseId=$caseId"
  Invoke-TextCommand -Exe $HdcPath -CommandArgs @("shell", "aa", "force-stop", [string]$Target.bundle) | Out-Null
  $launch = Invoke-TextCommand -Exe $HdcPath -CommandArgs @("shell", "aa", "start", "-b", [string]$Target.bundle, "-a", "EntryAbility", "-U", $uri, "--ps", "caseId", $caseId)
  Start-Sleep -Milliseconds $LaunchDelayMs
  $layoutOut = Join-Path $targetDir "layout.json"
  $capture = Capture-HarmonyLayoutForCase -CaseId $caseId -Bundle ([string]$Target.bundle) -LayoutOut $layoutOut
  $probe.launched = ($launch.exitCode -eq 0 -and $launch.text -notmatch "Error")
  $probe.captured = $capture.captured
  $probe.layout = $layoutOut
  $content = $capture.content
  $probe.legacyMarkerObserved = ($content -match "state_test_result:(pass|fail)" -or $content -match "strict_state_assertion:final_feature_available")
  $strictMatch = [regex]::Match($content, "strict_state_observed:feature_available=(true|false)")
  $probe.strictRuntimeStateObserved = $strictMatch.Success
  if ($strictMatch.Success) {
    $probe.strictFeatureAvailable = $strictMatch.Groups[1].Value
  }
  if ($probe.legacyMarkerObserved -and -not $probe.strictRuntimeStateObserved) {
    $probe.status = "contaminated:legacy_feature_marker_only"
  } elseif ($probe.strictRuntimeStateObserved -and $capture.fresh) {
    $probe.status = "captured:strict_state"
  } elseif ($probe.strictRuntimeStateObserved) {
    $probe.status = "captured:stale_or_wrong_case"
    $probe.detail = "Captured layout did not contain state_test_ready:$caseId. $($capture.detail)"
  } elseif ($probe.captured) {
    $probe.status = "captured:no_state_oracle"
  } else {
    $probe.status = "blocked:arkts_ui_capture_failed"
    $probe.detail = $capture.detail
  }
  return [pscustomobject]$probe
}

python $bindingScript | Out-Host
python $matrixScript | Out-Host
python $auditScript | Out-Host

$matrix = Get-Content -LiteralPath $matrixPath -Raw -Encoding UTF8 | ConvertFrom-Json
$audit = Get-Content -LiteralPath $auditPath -Raw -Encoding UTF8 | ConvertFrom-Json

$targets = @($matrix.targets)
if ($TaskId.Length -gt 0) {
  $targets = @($targets | Where-Object { $_.taskId -eq $TaskId })
}
if ($Platform -ne "Both") {
  $wantedPlatform = $Platform.ToLowerInvariant()
  $targets = @($targets | Where-Object { $_.platform -eq $wantedPlatform })
}
if ($Release -ne "Both") {
  $wantedRelease = $Release.ToLowerInvariant()
  $targets = @($targets | Where-Object { $_.release -eq $wantedRelease })
}
if ($TargetRole -ne "Both") {
  $wantedTargetRole = $TargetRole
  $targets = @($targets | Where-Object { Test-TargetRoleMatch $_ $wantedTargetRole })
}

$caseRows = @($matrix.caseTargets)
if ($CaseId.Length -gt 0) {
  $caseRows = @($caseRows | Where-Object { $_.caseId -eq $CaseId })
}

$caseAudit = @{}
foreach ($case in @($audit.cases)) {
  $caseAudit[[string]$case.caseId] = $case
}
$bindingCases = Load-StateBindingCases $bindingDir

$targetProbes = @()
foreach ($target in $targets) {
  $rowsForTarget = @($caseRows | Where-Object { $_.targetId -eq $target.targetId })
  foreach ($rowForTarget in $rowsForTarget) {
    Write-Host "[strict-probe] $($target.targetId) $($rowForTarget.caseId)"
    if ($target.platform -eq "android") {
      $probe = Probe-AndroidTarget $target @($rowForTarget)
      $probe | Add-Member -NotePropertyName legacySourceMarker -NotePropertyValue (Has-LegacyAndroidMarker $target)
      $probe | Add-Member -NotePropertyName markerOnlySourceHarness -NotePropertyValue (Has-MarkerOnlyAndroidHarness $target)
      $targetProbes += $probe
    } elseif ($target.platform -eq "arkts") {
      $probe = Probe-ArktsTarget $target @($rowForTarget)
      $probe | Add-Member -NotePropertyName legacySourceMarker -NotePropertyValue (Has-LegacyArktsMarker $target)
      $probe | Add-Member -NotePropertyName markerOnlySourceHarness -NotePropertyValue $false
      $targetProbes += $probe
    }
  }
}

$probeByTarget = @{}
foreach ($probe in $targetProbes) {
  $probeByTarget[(Probe-Key ([string]$probe.targetId) ([string]$probe.caseId))] = $probe
}

$results = @()
foreach ($row in $caseRows) {
  if (-not ($targets | Where-Object { $_.targetId -eq $row.targetId })) {
    continue
  }
  $auditCase = $caseAudit[[string]$row.caseId]
  $bindingCase = $bindingCases[[string]$row.caseId]
  $probe = $probeByTarget[(Probe-Key ([string]$row.targetId) ([string]$row.caseId))]
  $status = "unsupportedBinding"
  $verdict = "excluded"
  $observedPolarity = ""
  $reason = ""
  $readyMarkerObserved = $false
  $caseMarkerObserved = $false
  $missingRequired = @()
  $unexpectedForbidden = @()
  $transitionTraceMissing = $false
  $scoringMode = ""
  $harnessComplianceStatus = ""
  $semanticStatus = ""
  if ($null -eq $auditCase) {
    $status = "invalid_oracle"
    $reason = "Case is missing from strict oracle audit."
    $harnessComplianceStatus = "not_applicable"
    $semanticStatus = "not_scored"
  } elseif ($auditCase.status -ne "valid_oracle") {
    $status = $auditCase.status
    $reason = (($auditCase.issues | ForEach-Object { $_.message }) -join " ")
    $harnessComplianceStatus = "not_applicable"
    $semanticStatus = "not_scored"
  } elseif ($auditCase.polarityRole -eq "regression_guard") {
    $status = "regression_guard"
    $reason = "Regression guard is not eligible for base-fail/final-pass polarity scoring."
    $harnessComplianceStatus = "not_applicable"
    $semanticStatus = "not_scored"
  } elseif ($null -eq $probe -or -not $probe.probed) {
    $status = "collectorError"
    $reason = if ($null -eq $probe) { "Target probe missing." } else { $probe.status }
    $harnessComplianceStatus = "collector_error"
    $semanticStatus = "not_scored"
  } elseif ($probe.markerOnlySourceHarness) {
    $status = "protocolFail"
    $reason = "Android debug harness renders evaluator markers as the entire Activity instead of launching the real app UI."
    $harnessComplianceStatus = "contaminated_marker_only_harness"
    $semanticStatus = "not_scored"
  } elseif ($probe.status -like "contaminated:*" -or $probe.legacySourceMarker -or $probe.legacyMarkerObserved) {
    $status = "protocolFail"
    $reason = "Only legacy feature/version marker evidence is present; strict runtime state assertions are absent."
    $harnessComplianceStatus = "contaminated_legacy_harness"
    $semanticStatus = "not_scored"
  } else {
    $score = Invoke-PerCaseUiScoring -AuditCase $auditCase -BindingCase $bindingCase -Probe $probe -ExpectedPolarity ([string]$row.expected)
    $observedPolarity = $score.observedPolarity
    $status = $score.strictStatus
    $verdict = $score.verdict
    $reason = $score.reason
    $readyMarkerObserved = $score.readyMarkerObserved
    $caseMarkerObserved = $score.caseMarkerObserved
    $missingRequired = @($score.missingRequired)
    $unexpectedForbidden = @($score.unexpectedForbidden)
    $transitionTraceMissing = $score.transitionTraceMissing
    $scoringMode = $score.scoringMode
    $harnessComplianceStatus = if ($score.PSObject.Properties.Name -contains "harnessComplianceStatus") { $score.harnessComplianceStatus } else { "passed" }
    $semanticStatus = if ($score.PSObject.Properties.Name -contains "semanticStatus") { $score.semanticStatus } else { if ($observedPolarity -eq "pass") { "passed" } else { "failed" } }
    if ($status -eq "mismatch" -and $AllowTargetPolaritySmoke -and $probe.strictRuntimeStateObserved) {
      $smokePolarity = if ([string]$probe.strictFeatureAvailable -eq "true") { "pass" } else { "fail" }
      if ($smokePolarity -eq [string]$row.expected) {
        $status = "matchedTargetPolaritySmokeOnly"
        $verdict = "excluded"
        $reason = "Per-case UI assertions failed, but target-level feature availability matched. This is smoke evidence only."
        $semanticStatus = "not_scored"
      }
    }
  }
  $results += [pscustomobject][ordered]@{
    targetId = $row.targetId
    taskId = $row.taskId
    platform = $row.platform
    release = $row.release
    targetRole = if ($row.PSObject.Properties.Name -contains "targetRole") { $row.targetRole } else { Get-TargetRole $row }
    isGroundTruth = if ($row.PSObject.Properties.Name -contains "isGroundTruth") { $row.isGroundTruth } else { $true }
    caseId = $row.caseId
    expectedPolarity = $row.expected
    observedPolarity = $observedPolarity
    auditStatus = if ($null -eq $auditCase) { "missing" } else { $auditCase.status }
    polarityRole = if ($null -eq $auditCase) { "missing" } else { $auditCase.polarityRole }
    strictStatus = $status
    verdict = $verdict
    reason = $reason
    readyMarkerObserved = $readyMarkerObserved
    caseMarkerObserved = $caseMarkerObserved
    missingRequired = $missingRequired
    unexpectedForbidden = $unexpectedForbidden
    transitionTraceMissing = $transitionTraceMissing
    scoringMode = $scoringMode
    harnessComplianceStatus = $harnessComplianceStatus
    semanticStatus = $semanticStatus
    probeStatus = if ($null -eq $probe) { "" } else { $probe.status }
  }
}

$summary = [ordered]@{
  generatedAt = (Get-Date).ToString("s")
  root = $Root
  taskFilter = $TaskId
  platformFilter = $Platform
  releaseFilter = $Release
  targetRoleFilter = $TargetRole
  caseFilter = $CaseId
  strictPolicy = "No legacy state_test_result marker is counted as pass. Production strict pass requires strict_state_fact markers that satisfy the evaluator binding manifest for the requested semantic testcase. Target-level feature availability is smoke evidence only and is rejected by default; use -AllowStateObservationSmoke only for legacy smoke rescoring."
  targetProbeCount = @($targetProbes | Select-Object -ExpandProperty targetId -Unique).Count
  caseProbeCount = $targetProbes.Count
  caseTargetCount = $results.Count
  targetProbes = $targetProbes
  statusCounts = @{}
  harnessComplianceCounts = @{}
  semanticStatusCounts = @{}
  targetRoleCounts = @{}
  results = $results
}

foreach ($group in ($results | Group-Object strictStatus)) {
  $summary.statusCounts[$group.Name] = $group.Count
}
foreach ($group in ($results | Group-Object harnessComplianceStatus)) {
  $name = if ([string]$group.Name -eq "") { "unspecified" } else { [string]$group.Name }
  $summary.harnessComplianceCounts[$name] = $group.Count
}
foreach ($group in ($results | Group-Object semanticStatus)) {
  $name = if ([string]$group.Name -eq "") { "unspecified" } else { [string]$group.Name }
  $summary.semanticStatusCounts[$name] = $group.Count
}
foreach ($group in ($results | Group-Object targetRole)) {
  $name = if ([string]$group.Name -eq "") { "unspecified" } else { [string]$group.Name }
  $summary.targetRoleCounts[$name] = $group.Count
}

$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportJson -Encoding UTF8

$lines = @()
$lines += "# Strict State Matrix Run Report"
$lines += ""
$lines += "- Generated: $($summary.generatedAt)"
$lines += "- Targets probed: $($summary.targetProbeCount)"
$lines += "- Case probes: $($summary.caseProbeCount)"
$lines += "- Case-target rows assessed: $($summary.caseTargetCount)"
$lines += "- Target role filter: $($summary.targetRoleFilter)"
$lines += "- Strict policy: $($summary.strictPolicy)"
$lines += "- Status counts: $($summary.statusCounts | ConvertTo-Json -Compress)"
$lines += "- Harness compliance counts: $($summary.harnessComplianceCounts | ConvertTo-Json -Compress)"
$lines += "- Semantic status counts: $($summary.semanticStatusCounts | ConvertTo-Json -Compress)"
$lines += "- Target role counts: $($summary.targetRoleCounts | ConvertTo-Json -Compress)"
$lines += ""
$lines += "## Scoring Mode Counts"
foreach ($group in ($results | Group-Object scoringMode | Sort-Object Name)) {
  $name = if ([string]$group.Name -eq "") { "none" } else { [string]$group.Name }
  $lines += "- ``$name``: $($group.Count)"
}
$lines += ""
$lines += "## Probe Status By Target"
foreach ($group in ($targetProbes | Group-Object targetId | Sort-Object Name)) {
  $counts = @{}
  foreach ($statusGroup in ($group.Group | Group-Object status)) {
    $counts[$statusGroup.Name] = $statusGroup.Count
  }
  $first = $group.Group[0]
  $lines += ('- `{0}` role={1}: {2}; artifactExists={3}, legacySourceMarker={4}, markerOnlySourceHarness={5}' -f $group.Name, $first.targetRole, ($counts | ConvertTo-Json -Compress), $first.artifactExists, $first.legacySourceMarker, $first.markerOnlySourceHarness)
}
$lines += ""
$lines += "## Case Status By Target"
foreach ($group in ($results | Group-Object targetId | Sort-Object Name)) {
  $counts = @{}
  foreach ($statusGroup in ($group.Group | Group-Object strictStatus)) {
    $counts[$statusGroup.Name] = $statusGroup.Count
  }
  $first = $group.Group[0]
  $lines += ('- `{0}` role={1} groundtruth={2}: {3}' -f $group.Name, $first.targetRole, $first.isGroundTruth, ($counts | ConvertTo-Json -Compress))
}
$lines += ""
$lines += "## Interpretation"
$lines += ""
$lines += '- `base` and `groundtruth_final` are the golden polarity targets: base must fail final-oriented cases, and groundtruth_final must pass them.'
$lines += '- `agent_result` is scored against the same final-oriented assertions, but it is not used to prove that the testcase has valid base/final polarity.'
$lines += '- `matched` means the selected strict scoring mode matched expected polarity.'
$lines += '- `strict_semantic_facts` means the runner matched evaluator-owned semantic facts, emitted as `strict_state_fact:<fact>`, against the binding manifest.'
$lines += '- `per_case_ui_tree_tokens` means the runner matched evaluator binding tokens directly against the captured UI tree.'
$lines += '- `android_state_observation_adapter` and `arkts_state_observation_adapter` are legacy smoke modes enabled only with `-AllowStateObservationSmoke`.'
$lines += '- `*_state_observation_smoke_rejected` means the app exposed ready/case markers and target-level feature availability, but no semantic facts.'
$lines += '- `mismatch` means the observed per-case UI result did not match base/final polarity.'
$lines += '- `matchedTargetPolaritySmokeOnly` means per-case assertions failed, but the optional target-level feature marker matched; it is excluded from production scoring.'
$lines += '- `contaminatedMarkerOnlyHarness` means the Android debug harness rendered evaluator marker text as the whole Activity instead of testing the real app UI.'
$lines += '- `contaminatedLegacyHarness` means the app ran, but only exposed the old feature/version marker, so the row is not a functional pass.'
$lines += '- `protocolFail` means the app could not enter production semantic scoring because the required strict harness contract was missing or contaminated.'
$lines += '- `invalid_oracle` means the testcase currently contradicts or lacks a reachable final Android oracle and must be fixed before scoring.'
$lines += '- `regression_guard` means the case is useful, but it cannot be used to prove base all-fail/final all-pass polarity.'
$lines += '- `unsupportedBinding` means the current app build lacks evaluator-owned active state bindings for that semantic testcase.'
$lines += '- `insufficientPerCaseOracle` means the app exposed only target-level feature availability; this is smoke evidence and is not counted as a production state-test pass.'
$lines += ""
$lines += "## Mismatch Samples"
$sampleRows = @($results | Where-Object { $_.strictStatus -eq "mismatch" -or $_.strictStatus -eq "unsupportedBinding" -or $_.strictStatus -eq "matchedTargetPolaritySmokeOnly" -or $_.strictStatus -eq "protocolFail" } | Select-Object -First 20)
if ($sampleRows.Count -eq 0) {
  $lines += "- None"
} else {
  foreach ($item in $sampleRows) {
    $lines += ('- `{0}` role={1} `{2}` expected={3} observed={4} status={5} harness={6} semantic={7} missing={8} unexpected={9}' -f $item.targetId, $item.targetRole, $item.caseId, $item.expectedPolarity, $item.observedPolarity, $item.strictStatus, $item.harnessComplianceStatus, $item.semanticStatus, @($item.missingRequired).Count, @($item.unexpectedForbidden).Count)
  }
}
$lines | Set-Content -LiteralPath $reportMd -Encoding UTF8

Write-Host "Wrote $reportJson"
Write-Host "Wrote $reportMd"
$targetProbes | Format-Table targetId,targetRole,status,artifactExists,installed,captured,legacyMarkerObserved,legacySourceMarker,markerOnlySourceHarness -AutoSize
$results | Group-Object strictStatus | Sort-Object Name | Format-Table Name,Count -AutoSize
