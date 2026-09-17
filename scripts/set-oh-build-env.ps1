$ErrorActionPreference = "Stop"

$devecoRoot = "C:\Program Files\Huawei\DevEco Studio"
$openHarmonySdk = "C:\Users\xiexi\AppData\Local\OpenHarmony\Sdk"
$sdkVersion = "23"

$toolPaths = @(
  "$devecoRoot\tools\ohpm\bin",
  "$devecoRoot\tools\hvigor\bin",
  "$devecoRoot\tools\node",
  "$openHarmonySdk\$sdkVersion\toolchains"
)

foreach ($path in $toolPaths) {
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Required tool path is missing: $path"
  }
}

$env:DEVECO_SDK_HOME = $openHarmonySdk
$env:HOS_SDK_HOME = $openHarmonySdk
$env:OHOS_SDK_HOME = $openHarmonySdk
$env:OHOS_BASE_SDK_HOME = $openHarmonySdk
$env:HARMONYOS_SDK_HOME = "C:\Users\xiexi\AppData\Local\Huawei\Sdk"
$env:JAVA_HOME = Join-Path $devecoRoot "jbr"
$env:NODE_HOME = Join-Path $devecoRoot "tools\node"

$existing = $env:Path -split ';' | Where-Object { $_ }
$prefix = $toolPaths | Where-Object { $existing -notcontains $_ }
$env:Path = (($prefix + $existing) -join ';')

Write-Host "OpenHarmony build environment is ready for SDK $sdkVersion."
Write-Host "ohpm:    $((Get-Command ohpm).Source)"
Write-Host "hvigorw: $((Get-Command hvigorw).Source)"
Write-Host "node:    $((Get-Command node).Source)"
Write-Host "hdc:     $((Get-Command hdc).Source)"
