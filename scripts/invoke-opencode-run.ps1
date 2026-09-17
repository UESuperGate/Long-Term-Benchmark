param(
  [Parameter(Mandatory = $true)][string]$OpencodeCommand,
  [Parameter(Mandatory = $true)][string]$SelectedModel,
  [Parameter(Mandatory = $true)][string]$ProjectDir,
  [Parameter(Mandatory = $true)][string]$Title,
  [Parameter(Mandatory = $true)][string]$PromptPath,
  [Parameter(Mandatory = $true)][string]$AgentLog
)

$ErrorActionPreference = "Stop"
$promptText = Get-Content -LiteralPath $PromptPath -Raw -Encoding UTF8
& $OpencodeCommand run --model $SelectedModel --format json --auto --dir $ProjectDir --title $Title $promptText *> $AgentLog
exit $LASTEXITCODE
