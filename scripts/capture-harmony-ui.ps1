param(
  [string]$Root = "C:\Users\xiexi\qingyu",
  [string]$Device = "Pura 90 Pro Max",
  [string]$OutDir = "C:\Users\xiexi\qingyu\verification_reports\harmony_dynamic_ui"
)

$ErrorActionPreference = "Stop"

$hdc = "C:\Users\xiexi\AppData\Local\OpenHarmony\Sdk\23\toolchains\hdc.exe"
$emulator = "C:\Program Files\Huawei\DevEco Studio\tools\emulator\Emulator.exe"
$layout = "C:\Users\xiexi\AppData\Local\Huawei\Emulator\deployed\$Device\uiLayout\analysis.md"

function Read-BundleName {
  param([string]$ProjectDir)

  $appJson = Join-Path $ProjectDir "AppScope\app.json5"
  $content = Get-Content -LiteralPath $appJson -Raw
  $match = [regex]::Match($content, '"bundleName"\s*:\s*"([^"]+)"')
  if (-not $match.Success) {
    throw "bundleName not found in $appJson"
  }
  return $match.Groups[1].Value
}

function Capture-CurrentScreen {
  param(
    [string]$ProjectOutDir,
    [string]$Name
  )

  $captureOutput = & $emulator -instance $Device -uiLayout -a 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host ($captureOutput -join "`n")
    throw "uiLayout capture failed for $Name"
  }
  Copy-Item -LiteralPath $layout -Destination (Join-Path $ProjectOutDir "$Name.ui.md") -Force
}

function Wait-For-AppContent {
  param([string]$ProjectName)

  for ($attempt = 1; $attempt -le 8; $attempt++) {
    $captureOutput = & $emulator -instance $Device -uiLayout -a 2>&1
    if ($LASTEXITCODE -ne 0) {
      Write-Host ($captureOutput -join "`n")
      throw "uiLayout readiness capture failed for $ProjectName"
    }
    $content = Get-Content -LiteralPath $layout -Raw
    if ($content.Contains("base ") -and $content.Contains("final ")) {
      return
    }
    Start-Sleep -Milliseconds 900
  }
  throw "App content did not become visible for $ProjectName"
}

function Open-Tab {
  param([int]$X)

  $clickOutput = & $hdc shell uitest uiInput click $X 811 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host ($clickOutput -join "`n")
    throw "uiInput click failed at x=$X"
  }
  Start-Sleep -Milliseconds 900
}

function Capture-Project {
  param(
    [string]$ProjectDir,
    [string]$Kind
  )

  $name = Split-Path -Leaf $ProjectDir
  $hap = Join-Path $ProjectDir "entry\build\default\outputs\default\entry-default-unsigned.hap"
  if (-not (Test-Path -LiteralPath $hap)) {
    throw "HAP missing for $name at $hap"
  }

  $bundle = Read-BundleName -ProjectDir $ProjectDir
  $projectOutDir = Join-Path $OutDir $name
  New-Item -ItemType Directory -Force -Path $projectOutDir | Out-Null

  Write-Host "=== install $name ==="
  $installOutput = & $hdc install -r $hap 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host ($installOutput -join "`n")
    throw "Install failed for $name"
  }

  Write-Host "=== launch $name ==="
  $launchOutput = & $hdc shell aa start -a EntryAbility -b $bundle 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host ($launchOutput -join "`n")
    throw "Launch failed for $name"
  }
  Start-Sleep -Seconds 2
  Wait-For-AppContent -ProjectName $name

  Capture-CurrentScreen -ProjectOutDir $projectOutDir -Name "timeline"
  Open-Tab -X 491
  Capture-CurrentScreen -ProjectOutDir $projectOutDir -Name "settings"
  Open-Tab -X 818
  Capture-CurrentScreen -ProjectOutDir $projectOutDir -Name "security"
  Open-Tab -X 1145
  Capture-CurrentScreen -ProjectOutDir $projectOutDir -Name "contract"

  return [pscustomobject]@{
    name = $name
    kind = $Kind
    bundle = $bundle
    projectDir = $ProjectDir
    outputDir = $projectOutDir
    captured = @("timeline.ui.md", "settings.ui.md", "security.ui.md", "contract.ui.md")
  }
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$baseProjects = Get-ChildItem -LiteralPath $Root -Directory |
  Where-Object { $_.Name -match '^\d\d_' } |
  Sort-Object Name |
  ForEach-Object { @{ path = $_.FullName; kind = "base" } }

$finalRoot = Join-Path $Root "final_dev_nodes"
$finalProjects = Get-ChildItem -LiteralPath $finalRoot -Directory |
  Where-Object { $_.Name -match '^\d\d_' } |
  Sort-Object Name |
  ForEach-Object { @{ path = $_.FullName; kind = "final" } }

$results = @()
foreach ($project in @($baseProjects + $finalProjects)) {
  $results += Capture-Project -ProjectDir $project.path -Kind $project.kind
}

$manifestPath = Join-Path $OutDir "manifest.json"
$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Host "Wrote $manifestPath"
