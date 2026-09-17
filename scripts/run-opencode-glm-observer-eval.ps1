param(
  [string]$Root = "C:\Users\xiexi\qingyu",
  [string]$RunId = "",
  [string]$Model = "bigmodel-glm/glm-5.3",
  [string]$BaseUrl = "https://open.bigmodel.cn/api/coding/paas/v4",
  [string[]]$TaskId = @("01_user_status", "02_gallery_messages", "03_timeline_protection_rich_events"),
  [int]$AgentTimeoutSeconds = 10800,
  [int]$ModelContextLimit = 200000,
  [int]$ModelOutputLimit = 131072,
  [ValidateSet("enabled", "adaptive", "disabled")]
  [string]$ThinkingType = "enabled",
  [int]$ThinkingBudgetTokens = 65536,
  [int]$ProviderTimeoutMs = 10800000,
  [int]$ProviderHeaderTimeoutMs = 900000,
  [int]$ProviderChunkTimeoutMs = 900000,
  [switch]$UseOpencodeFileConfig
)

$ErrorActionPreference = "Stop"

if (-not $env:OPENCODE_GLM_API_KEY -and -not $UseOpencodeFileConfig) {
  throw "OPENCODE_GLM_API_KEY is required. Set it for this process; do not write it into the script."
}

$TaskId = @($TaskId | ForEach-Object { $_ -split "," } | Where-Object { $_.Trim().Length -gt 0 } | ForEach-Object { $_.Trim() })

$opencode = (Get-Command opencode.cmd -ErrorAction Stop).Source
. (Join-Path $Root "scripts\set-oh-build-env.ps1")

if ($RunId.Length -eq 0) {
  $RunId = "opencode_glm53_observer_" + (Get-Date -Format "yyyyMMdd_HHmmss")
}

$runRoot = Join-Path $Root "eval_runs\$RunId"
$candidateRoot = Join-Path $runRoot "arkts_agent_results"
$logRoot = Join-Path $runRoot "logs"
New-Item -ItemType Directory -Force -Path $candidateRoot, $logRoot | Out-Null

$tasks = @(
  [pscustomobject]@{
    id = "01_user_status"
    spec = "elementx-spec1-user-status.md"
    state = "elementx-state-test1-user-status.yaml"
    baseDir = "01_user_status_base_26_07_0"
    finalDir = "01_user_status_final_26_08_4"
  },
  [pscustomobject]@{
    id = "02_gallery_messages"
    spec = "elementx-spec2-gallery-messages.md"
    state = "elementx-state-test2-gallery-messages.yaml"
    baseDir = "02_gallery_messages_base_26_06_1"
    finalDir = "02_gallery_messages_final_26_08_1"
  },
  [pscustomobject]@{
    id = "03_timeline_protection_rich_events"
    spec = "elementx-spec3-active-call-timeline.md"
    state = "elementx-state-test3-timeline-protection-rich-events.yaml"
    baseDir = "03_active_call_timeline_base_26_07_1"
    finalDir = "03_active_call_timeline_final_26_08_0"
  }
)

if ($TaskId.Count -gt 0) {
  $wanted = @{}
  foreach ($id in $TaskId) {
    $wanted[$id] = $true
  }
  $tasks = @($tasks | Where-Object { $wanted.ContainsKey($_.id) })
}

function New-OpencodeConfigContent {
  param(
    [string]$ProviderBaseUrl,
    [string]$SelectedModel,
    [int]$ContextLimit,
    [int]$OutputLimit,
    [string]$ThinkingMode,
    [int]$ThinkingBudget,
    [int]$TimeoutMs,
    [int]$HeaderTimeoutMs,
    [int]$ChunkTimeoutMs
  )
  $providerId, $modelId = $SelectedModel.Split("/", 2)
  $modelMap = @{}
  $modelMap[$modelId] = @{
    name = "GLM 5.3"
    tool_call = $true
    limit = @{ context = $ContextLimit; output = $OutputLimit }
    options = @{
      thinking = @{
        type = $ThinkingMode
        budgetTokens = $ThinkingBudget
      }
    }
  }
  $providers = @{}
  $providers[$providerId] = @{
    npm = "@ai-sdk/openai-compatible"
    name = "BigModel GLM"
    options = @{
      baseURL = $ProviderBaseUrl
      apiKey = "{env:OPENCODE_GLM_API_KEY}"
      timeout = $TimeoutMs
      headerTimeout = $HeaderTimeoutMs
      chunkTimeout = $ChunkTimeoutMs
    }
    models = $modelMap
  }
  return (@{
    provider = $providers
    model = $SelectedModel
    small_model = $SelectedModel
    share = "disabled"
    autoupdate = $false
    permission = @{
      read = "allow"
      edit = "allow"
      write = "allow"
      bash = "allow"
      list = "allow"
      grep = "allow"
      glob = "allow"
      webfetch = "deny"
      websearch = "deny"
    }
  } | ConvertTo-Json -Depth 20 -Compress)
}

function Copy-ProjectBase {
  param([string]$Source, [string]$Destination)
  if (Test-Path -LiteralPath $Destination) {
    Remove-Item -LiteralPath $Destination -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  $args = @(
    $Source,
    $Destination,
    "/E",
    "/XD",
    ".hvigor",
    "build",
    "oh_modules",
    "node_modules",
    ".git",
    "/XF",
    "*.hap",
    "*.app",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP"
  )
  & robocopy @args | Out-Null
  if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed from $Source to $Destination with exit code $LASTEXITCODE"
  }
}

function ConvertTo-SanitizedAgentInput {
  param([string]$ProjectDir)

  $replacements = [ordered]@{
    "strict_state_fact" = "debug_state_fact"
    "state_probe_snapshot" = "debug_state_snapshot"
    "state_test_result" = "debug_state_result"
    "final_feature_available" = "debug_feature_available"
    "strict_state_" = "debug_state_"
    "stateTestSemanticFacts" = "debugSemanticFacts"
    "stateProbeSnapshot" = "debugStateSnapshot"
  }

  $files = Get-ChildItem -LiteralPath $ProjectDir -Recurse -File -Include *.ets,*.ts,*.json5,*.md -ErrorAction SilentlyContinue |
    Where-Object {
      $_.FullName -notmatch "\\(oh_modules|node_modules|build|\.git|_benchmark_inputs)\\"
    }

  foreach ($file in $files) {
    $text = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
    $updated = $text
    foreach ($key in $replacements.Keys) {
      $updated = $updated.Replace($key, $replacements[$key])
    }
    if ($updated -ne $text) {
      Set-Content -LiteralPath $file.FullName -Value $updated -Encoding UTF8
    }
  }

  $scan = & rg -n "strict_state_fact|state_probe_snapshot|state_test_result|final_feature_available|strict_state_" "$ProjectDir\entry\src\main\ets" 2>$null
  if ($LASTEXITCODE -eq 0) {
    throw "Sanitized agent input still contains evaluator marker strings:`n$scan"
  }
}

function Write-TaskPrompt {
  param($Task, [string]$ProjectDir, [string]$InputDir)
  $promptPath = Join-Path $InputDir "opencode_prompt.md"
  $specPath = Join-Path $InputDir $Task.spec
  $statePath = Join-Path $InputDir $Task.state
  $text = @"
IMPORTANT: Implement the task now. Do not stop after project orientation, and do not ask what to do next. Your answer is only acceptable after you have edited the ArkTS source and attempted a build.

You are running inside a copied ArkTS/HarmonyOS SDK 23 Element X benchmark base project.

Task id: $($Task.id)
Project directory: $ProjectDir
Requirement spec: $specPath
State-test YAML: $statePath

Implement the requested long-horizon task in this ArkTS project only.

Public development contract:
- Treat the requirement spec and state-test YAML as the public task contract.
- Do not read or copy from evaluator binding manifests, oracle facts, generated reports, or ArkTS final answer directories outside this project.
- Do not modify Android source.
- Preserve SDK 23 compatibility and the existing project structure.
- Keep the implementation constrained to behavior described by the spec/state tests.
- Prefer extending the existing state model, view model, service interfaces, fixtures, and declarative UI flow rather than replacing them with unrelated structures.
- New feature behavior should be expressed through stable declarative state and observable UI semantics: accessible labels, enabled/disabled state, route/state transitions, meaningful ids on real UI nodes when the base already uses ids, and service/mock boundaries.
- Do not add evaluator-only marker protocols, self-scoring outputs, hidden answer lists, or case-id switches that render expected facts without implementing the underlying feature behavior.
- Do not add strings such as strict_state_fact, state_probe_snapshot, state_test_result, or final_feature_available.
- If a testcase id/deeplink entrypoint already exists in the base, use it only to select legitimate fixture state or navigation state. Do not turn it into an oracle.
- Do not create verification-only files such as verification/behavior_contract.json as a substitute for implementation.
- Before spending time on summaries, edit the real feature files under entry/src/main/ets: model, service, viewmodel, and pages as needed.
- The state-test YAML exposes the public semantic nodes expected from the feature. Implement the actual feature behavior that makes those nodes naturally appear; do not merely print every expected token from a switch.
- First read entry/src/main/ets/pages/Index.ets and local model/viewmodel/service files you need.
- Update the real ArkTS implementation, not only README or benchmark notes.
- After editing, run ohpm install if needed and hvigorw assembleHap --no-daemon.
- Fix build errors before finishing. If build still fails, leave the source in your best attempted state and summarize the blocker.

When done, summarize changed files, build result, implemented functional areas, and remaining blockers.
"@
  Set-Content -LiteralPath $promptPath -Value $text -Encoding UTF8
  return $promptPath
}

function Invoke-OpencodeRunWithTimeout {
  param(
    [string]$OpencodeExe,
    [string]$SelectedModel,
    [string]$ProjectDir,
    [string]$Title,
    [string]$PromptPath,
    [string]$AgentLog,
    [int]$TimeoutSeconds
  )

  $stderrLog = "$AgentLog.stderr.log"
  Remove-Item -LiteralPath $AgentLog, $stderrLog -Force -ErrorAction SilentlyContinue
  $helper = Join-Path $Root "scripts\invoke-opencode-run.ps1"
  $psi = [System.Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = "powershell.exe"
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $argv = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $helper,
    "-OpencodeCommand", $OpencodeExe,
    "-SelectedModel", $SelectedModel,
    "-ProjectDir", $ProjectDir,
    "-Title", $Title,
    "-PromptPath", $PromptPath,
    "-AgentLog", $AgentLog
  )
  $psi.Arguments = ($argv | ForEach-Object {
    if ($_ -match '[\s"]') {
      '"' + ($_ -replace '"', '\"') + '"'
    } else {
      $_
    }
  }) -join " "
  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $psi
  [void]$process.Start()

  if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    & taskkill.exe /PID $process.Id /T /F *> $stderrLog
    Add-Content -LiteralPath $AgentLog -Encoding UTF8 -Value (@{
      type = "runner_timeout"
      timeoutSeconds = $TimeoutSeconds
      timestamp = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
    } | ConvertTo-Json -Compress)
    return 124
  }

  $process.StandardOutput.ReadToEnd() | Add-Content -LiteralPath $stderrLog -Encoding UTF8
  $process.StandardError.ReadToEnd() | Add-Content -LiteralPath $stderrLog -Encoding UTF8
  return [int]$process.ExitCode
}

$manifestTasks = @()
$previousConfigContent = $env:OPENCODE_CONFIG_CONTENT
if ($UseOpencodeFileConfig) {
  Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
} else {
  $env:OPENCODE_CONFIG_CONTENT = New-OpencodeConfigContent `
    -ProviderBaseUrl $BaseUrl `
    -SelectedModel $Model `
    -ContextLimit $ModelContextLimit `
    -OutputLimit $ModelOutputLimit `
    -ThinkingMode $ThinkingType `
    -ThinkingBudget $ThinkingBudgetTokens `
    -TimeoutMs $ProviderTimeoutMs `
    -HeaderTimeoutMs $ProviderHeaderTimeoutMs `
    -ChunkTimeoutMs $ProviderChunkTimeoutMs
}

try {
  foreach ($task in $tasks) {
    $sourceDir = Join-Path $Root $task.baseDir
    $candidateDir = Join-Path $candidateRoot $task.finalDir
    Write-Host "[prepare] $($task.id)"
    Copy-ProjectBase -Source $sourceDir -Destination $candidateDir
    ConvertTo-SanitizedAgentInput -ProjectDir $candidateDir
    $taskInputDir = Join-Path $candidateDir "_benchmark_inputs"
    New-Item -ItemType Directory -Force -Path $taskInputDir | Out-Null
    Copy-Item -LiteralPath (Join-Path $Root "specs\$($task.spec)") -Destination (Join-Path $taskInputDir $task.spec) -Force
    Copy-Item -LiteralPath (Join-Path $Root "state_tests\$($task.state)") -Destination (Join-Path $taskInputDir $task.state) -Force
    $promptPath = Write-TaskPrompt -Task $task -ProjectDir $candidateDir -InputDir $taskInputDir

    $agentLog = Join-Path $logRoot "$($task.id)_opencode.jsonl"
    $buildLog = Join-Path $logRoot "$($task.id)_build.log"

    Write-Host "[opencode] $($task.id)"
    $agentExit = Invoke-OpencodeRunWithTimeout `
      -OpencodeExe $opencode `
      -SelectedModel $Model `
      -ProjectDir $candidateDir `
      -Title "$RunId $($task.id)" `
      -PromptPath $promptPath `
      -AgentLog $agentLog `
      -TimeoutSeconds $AgentTimeoutSeconds

    Write-Host "[build] $($task.id)"
    Push-Location $candidateDir
    try {
      $ohpmOutput = & cmd.exe /d /c "ohpm install 2>&1"
      $ohpmExit = $LASTEXITCODE
      Set-Content -LiteralPath $buildLog -Encoding UTF8 -Value $ohpmOutput
      if ($ohpmExit -eq 0) {
        $hvigorOutput = & cmd.exe /d /c "hvigorw assembleHap --no-daemon 2>&1"
        $buildExit = $LASTEXITCODE
        Add-Content -LiteralPath $buildLog -Encoding UTF8 -Value $hvigorOutput
      } else {
        $buildExit = -1
      }
    } finally {
      Pop-Location
    }

    $hap = Get-ChildItem -LiteralPath $candidateDir -Recurse -File -Filter "*.hap" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1

    $manifestTasks += [pscustomobject]@{
      id = $task.id
      baseDir = $task.baseDir
      agentResultDir = $candidateDir
      spec = Join-Path $taskInputDir $task.spec
      state = Join-Path $taskInputDir $task.state
      model = $Model
      modelContextLimit = $ModelContextLimit
      modelOutputLimit = $ModelOutputLimit
      thinkingType = $ThinkingType
      thinkingBudgetTokens = $ThinkingBudgetTokens
      agentExit = $agentExit
      buildExit = $buildExit
      hap = if ($hap) { $hap.FullName } else { "" }
      agentLog = $agentLog
      buildLog = $buildLog
    }
  }
} finally {
  if ($null -eq $previousConfigContent) {
    Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
  } else {
    $env:OPENCODE_CONFIG_CONTENT = $previousConfigContent
  }
}

$manifest = [pscustomobject]@{
  runId = $RunId
  createdAt = (Get-Date).ToString("o")
  runner = "opencode"
  model = $Model
  configMode = if ($UseOpencodeFileConfig) { "opencode_file" } else { "env_generated" }
  modelContextLimit = $ModelContextLimit
  modelOutputLimit = $ModelOutputLimit
  thinkingType = $ThinkingType
  thinkingBudgetTokens = $ThinkingBudgetTokens
  providerTimeoutMs = $ProviderTimeoutMs
  providerHeaderTimeoutMs = $ProviderHeaderTimeoutMs
  providerChunkTimeoutMs = $ProviderChunkTimeoutMs
  baseUrl = $BaseUrl
  root = $runRoot
  agentResultRoot = $candidateRoot
  tasks = $manifestTasks
  publicDevelopmentContract = "No evaluator marker protocol; preserve observable state/UI semantics."
}
$manifestPath = Join-Path $runRoot "eval_manifest.json"
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Host "[manifest] $manifestPath"
Write-Host "[done] $runRoot"
