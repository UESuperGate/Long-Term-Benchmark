param(
  [string]$JavaHome = ""
)

$ErrorActionPreference = "Continue"
$root = "C:\Users\xiexi\qingyu"
$outDir = Join-Path $root "verification_reports\state_dynamic"
$androidSdk = "C:\Users\xiexi\AppData\Local\Android\Sdk"
$adb = Join-Path $androidSdk "platform-tools\adb.exe"
$reportPath = Join-Path $outDir "android_build_env_report.json"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

if ($JavaHome.Length -gt 0) {
  $env:JAVA_HOME = $JavaHome
  $env:PATH = (Join-Path $JavaHome "bin") + ";" + $env:PATH
}

$javaPath = (where.exe java 2>$null | Select-Object -First 1)
$javaVersion = if ($javaPath) { (& cmd.exe /c "`"$javaPath`" -version 2>&1" | Out-String).Trim() } else { "missing" }
$sdkPlatforms = if (Test-Path -LiteralPath (Join-Path $androidSdk "platforms")) {
  Get-ChildItem (Join-Path $androidSdk "platforms") -Directory | Select-Object -ExpandProperty Name
} else {
  @()
}

$report = [ordered]@{
  generatedAt = (Get-Date).ToString("s")
  javaHome = $env:JAVA_HOME
  javaPath = $javaPath
  javaVersion = $javaVersion
  java21Detected = ($javaVersion -match 'version "21\.')
  androidSdk = $androidSdk
  adbExists = Test-Path -LiteralPath $adb
  sdkPlatforms = $sdkPlatforms
  notes = @(
    "Element X Android Gradle toolchains request Java 21 for these tags.",
    "If java21Detected is false, install JDK 21 or pass -JavaHome <JDK21> to run-state-dynamic-matrix.ps1.",
    "The first attempted v26.07.0 build also hit a Maven Central TLS handshake failure while resolving Kotlin compiler artifacts."
  )
}

$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
$report | ConvertTo-Json -Depth 5
