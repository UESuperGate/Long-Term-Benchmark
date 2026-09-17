$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "set-oh-build-env.ps1")

$bases = Get-ChildItem -LiteralPath $repoRoot -Directory |
  Where-Object { $_.Name -match '^\d\d_' } |
  Sort-Object Name

$results = @()
foreach ($base in $bases) {
  Write-Host ""
  Write-Host "=== $($base.Name): ohpm install ==="
  Push-Location $base.FullName
  try {
    ohpm install
    $ohpmExit = $LASTEXITCODE
    if ($ohpmExit -ne 0) {
      throw "ohpm install failed with exit code $ohpmExit"
    }

    Write-Host "=== $($base.Name): hvigorw assembleHap ==="
    hvigorw assembleHap --no-daemon
    $hvigorExit = $LASTEXITCODE
    if ($hvigorExit -ne 0) {
      throw "hvigorw assembleHap failed with exit code $hvigorExit"
    }

    $hap = Get-ChildItem -LiteralPath $base.FullName -Recurse -File -Filter '*.hap' |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1

    $results += [pscustomobject]@{
      Base = $base.Name
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
