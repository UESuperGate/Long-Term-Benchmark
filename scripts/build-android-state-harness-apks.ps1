param(
    [string]$Root = "C:\Users\xiexi\qingyu",
    [string]$TaskId = "",
    [string]$Release = "",
    [string]$JdkHome = "C:\Users\xiexi\qingyu\.jdks\temurin-21\jdk-21.0.12.1+1",
    [string]$AndroidSdk = "C:\Users\xiexi\AppData\Local\Android\Sdk"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $JdkHome "bin\java.exe"))) {
    throw "Java 21 not found at $JdkHome"
}

if (-not (Test-Path (Join-Path $AndroidSdk "platform-tools\adb.exe"))) {
    throw "Android SDK not found at $AndroidSdk"
}

$matrixPath = Join-Path $Root "verification_reports\state_dynamic\state_dynamic_target_matrix.json"
if (-not (Test-Path $matrixPath)) {
    throw "Missing state matrix: $matrixPath"
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

$uniqueTargets = @{}
foreach ($target in $targets) {
    $uniqueTargets[[string]$target.worktree] = $target
}

$reportDir = Join-Path $Root "verification_reports\state_dynamic\android_state_build"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$previousJavaHome = $env:JAVA_HOME
$previousAndroidHome = $env:ANDROID_HOME
$previousAndroidSdkRoot = $env:ANDROID_SDK_ROOT
$previousPath = $env:PATH

$env:JAVA_HOME = $JdkHome
$env:ANDROID_HOME = $AndroidSdk
$env:ANDROID_SDK_ROOT = $AndroidSdk
$env:PATH = "$JdkHome\bin;$AndroidSdk\platform-tools;$previousPath"

$results = @()

try {
    foreach ($entry in $uniqueTargets.GetEnumerator()) {
        $target = $entry.Value
        $worktree = [string]$target.worktree
        $apk = [string]$target.apk
        $targetId = [string]$target.targetId
        $safeTarget = ($targetId -replace '[^A-Za-z0-9_.-]', '_')
        $logPath = Join-Path $reportDir "$safeTarget.log"

        if (-not (Test-Path $worktree)) {
            $results += [pscustomobject]@{
                targetId = $targetId
                taskId = $target.taskId
                release = $target.release
                status = "blocked"
                exitCode = $null
                apk = $apk
                log = $logPath
                detail = "Worktree not found: $worktree"
            }
            continue
        }

        Push-Location $worktree
        try {
            $previousPreferenceForGradle = $ErrorActionPreference
            try {
                $ErrorActionPreference = "Continue"
                & .\gradlew.bat --no-daemon :app:assembleGplayDebug *> $logPath
                $exitCode = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $previousPreferenceForGradle
            }
        } finally {
            Pop-Location
        }

        $status = if ($exitCode -eq 0 -and (Test-Path $apk)) { "built" } else { "failed" }
        $detail = if ($status -eq "built") { "APK built with debug state harness." } else { "Gradle build failed or APK missing." }

        $results += [pscustomobject]@{
            targetId = $targetId
            taskId = $target.taskId
            release = $target.release
            status = $status
            exitCode = $exitCode
            apk = $apk
            log = $logPath
            detail = $detail
        }
    }
} finally {
    $env:JAVA_HOME = $previousJavaHome
    $env:ANDROID_HOME = $previousAndroidHome
    $env:ANDROID_SDK_ROOT = $previousAndroidSdkRoot
    $env:PATH = $previousPath
}

$summary = [pscustomobject]@{
    generatedAt = (Get-Date).ToString("o")
    root = $Root
    jdkHome = $JdkHome
    androidSdk = $AndroidSdk
    total = $results.Count
    built = @($results | Where-Object { $_.status -eq "built" }).Count
    failed = @($results | Where-Object { $_.status -eq "failed" }).Count
    blocked = @($results | Where-Object { $_.status -eq "blocked" }).Count
    results = $results
}

$jsonPath = Join-Path $Root "verification_reports\state_dynamic\android_state_harness_build_report.json"
$mdPath = Join-Path $Root "verification_reports\state_dynamic\android_state_harness_build_report.md"

$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $jsonPath -Encoding UTF8

$lines = @()
$lines += "# Android State Harness Build Report"
$lines += ""
$lines += "- Generated: $($summary.generatedAt)"
$lines += "- JDK: $JdkHome"
$lines += "- Android SDK: $AndroidSdk"
$lines += "- Total targets: $($summary.total)"
$lines += "- Built: $($summary.built)"
$lines += "- Failed: $($summary.failed)"
$lines += "- Blocked: $($summary.blocked)"
$lines += ""
$lines += "| Target | Status | APK | Log |"
$lines += "| --- | --- | --- | --- |"
foreach ($result in $results) {
    $lines += "| $($result.targetId) | $($result.status) | $($result.apk) | $($result.log) |"
}
$lines | Set-Content -Path $mdPath -Encoding UTF8

Write-Host "Android harness APK build: built=$($summary.built)/$($summary.total), failed=$($summary.failed), blocked=$($summary.blocked)"
Write-Host "Report: $mdPath"
