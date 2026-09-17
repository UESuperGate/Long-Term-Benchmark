$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$finalRoot = Join-Path $repoRoot "final_dev_nodes"
. (Join-Path $PSScriptRoot "set-oh-build-env.ps1")

$finals = Get-ChildItem -LiteralPath $finalRoot -Directory |
  Where-Object { $_.Name -match '^\d\d_' } |
  Sort-Object Name

$results = @()
foreach ($final in $finals) {
  Write-Host ""
  Write-Host "=== $($final.Name): ohpm install ==="
  Push-Location $final.FullName
  try {
    ohpm install
    $ohpmExit = $LASTEXITCODE
    if ($ohpmExit -ne 0) {
      throw "ohpm install failed with exit code $ohpmExit"
    }

    Write-Host "=== $($final.Name): hvigorw assembleHap ==="
    hvigorw assembleHap --no-daemon
    $hvigorExit = $LASTEXITCODE
    if ($hvigorExit -ne 0) {
      throw "hvigorw assembleHap failed with exit code $hvigorExit"
    }

    $hap = Get-ChildItem -LiteralPath $final.FullName -Recurse -File -Filter '*.hap' |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1

    $results += [pscustomobject]@{
      Final = $final.Name
      Ohpm = $ohpmExit
      Build = $hvigorExit
      Hap = if ($hap) { $hap.FullName } else { "" }
    }
  } finally {
    Pop-Location
  }
}

Write-Host ""
$results | Format-Table -AutoSize
