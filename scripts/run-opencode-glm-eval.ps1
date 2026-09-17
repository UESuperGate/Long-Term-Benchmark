param(
  [string]$Root = "C:\Users\xiexi\qingyu",
  [string]$RunId = "",
  [string]$Model = "bigmodel-glm/glm-5.3",
  [string]$BaseUrl = "https://open.bigmodel.cn/api/coding/paas/v4",
  [string]$HarmonyInstance = "Custom Screen",
  [string[]]$TaskId = @(),
  [int]$AgentTimeoutSeconds = 900,
  [int]$ModelContextLimit = 200000,
  [int]$ModelOutputLimit = 131072,
  [ValidateSet("enabled", "adaptive", "disabled")]
  [string]$ThinkingType = "enabled",
  [int]$ThinkingBudgetTokens = 65536,
  [int]$ProviderTimeoutMs = 10800000,
  [int]$ProviderHeaderTimeoutMs = 900000,
  [int]$ProviderChunkTimeoutMs = 900000,
  [switch]$UseOpencodeFileConfig,
  [switch]$SkipDynamicProbe
)

$ErrorActionPreference = "Stop"

if (-not $env:OPENCODE_GLM_API_KEY -and -not $UseOpencodeFileConfig) {
  throw "OPENCODE_GLM_API_KEY is required. Set it for this process; do not write it into the script."
}

$opencode = (Get-Command opencode.cmd -ErrorAction Stop).Source
. (Join-Path $Root "scripts\set-oh-build-env.ps1")

if ($RunId.Length -eq 0) {
  $RunId = "opencode_glm53_" + (Get-Date -Format "yyyyMMdd_HHmmss")
}

$runRoot = Join-Path $Root "eval_runs\$RunId"
$candidateRoot = Join-Path $runRoot "arkts_agent_results"
$logRoot = Join-Path $runRoot "logs"
$reportRoot = Join-Path $runRoot "verification_reports\state_dynamic_strict_contract"
$bindingRoot = Join-Path $Root "state_tests\bindings"

New-Item -ItemType Directory -Force -Path $candidateRoot, $logRoot, $reportRoot | Out-Null

python (Join-Path $Root "scripts\generate_state_binding_manifests.py") | Out-Host

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
  },
  [pscustomobject]@{
    id = "04_live_location"
    spec = "elementx-spec4-live-location.md"
    state = "elementx-state-test4-live-location.yaml"
    baseDir = "04_live_location_base_26_04_0"
    finalDir = "04_live_location_final_26_05_1"
  },
  [pscustomobject]@{
    id = "05_link_new_device"
    spec = "elementx-spec5-link-new-device.md"
    state = "elementx-state-test5-link-new-device.yaml"
    baseDir = "05_link_new_device_base_26_05_0"
    finalDir = "05_link_new_device_final_26_08_2"
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

function Write-TaskPrompt {
  param($Task, [string]$ProjectDir, [string]$InputDir)
  $promptPath = Join-Path $InputDir "opencode_prompt.md"
  $specPath = Join-Path $InputDir $Task.spec
  $statePath = Join-Path $InputDir $Task.state
  $bindingPath = Join-Path $Root "state_tests\bindings\$($Task.id).binding.json"
  $text = @"
IMPORTANT: Implement the task now. Do not stop after project orientation, and do not ask what to do next. Your answer is only acceptable after you have edited the ArkTS source and attempted a build.

You are running inside a copied ArkTS/HarmonyOS SDK 23 Element X benchmark base project.

Task id: $($Task.id)
Project directory: $ProjectDir
Requirement spec: $specPath
State-test YAML: $statePath

Implement the requested long-horizon task in this ArkTS project only.

Rules:
- Treat the requirement spec and state-test YAML as the public task contract.
- Evaluator binding manifests and oracle facts are hidden evaluator inputs. Do not search for, read, copy, or recreate state_tests/bindings/*.json.
- Do not read or copy from any ArkTS final answer directory outside this project.
- Do not modify Android source.
- Preserve SDK 23 compatibility and the existing project structure.
- Keep the implementation constrained to behavior described by the spec/state tests.
- First read entry/src/main/ets/pages/Index.ets and any local project files you need.
- Update the real ArkTS implementation, not only README or benchmark notes.
- Preserve the existing state-test harness entrypoints if present, including StateTestPanel, stateTestCaseId, stateTestFeatureEnabled, stateTestRequiredFeature, and handleStateTestCaseChanged. You may extend a semantic-fact adapter only when its facts are derived from the current runtime state/model/view state.
- Do not hardcode state_test_result, strict_state_assertion:final_feature_available, version checks, feature_available=true, or a case-id switch that renders expected tokens without implementing the underlying feature state.
- Do not emit strict_state_fact:* unless each fact is computed from actual app state after the testcase's given_state and transitions are applied.
- The app must expose real UI/state semantics that can satisfy per-case given_state, expect_ui, transitions, and properties; target-level smoke markers are not sufficient.
- If a state-test deeplink is already present, use it only to route to or apply legitimate feature state. Do not turn it into a self-scoring harness.
- After editing, run ohpm install if needed and hvigorw assembleHap --no-daemon.
- Fix build errors before finishing. If build still fails, leave the source in your best attempted state and summarize the blocker.

When done, summarize changed files, build result, which functional areas from the state-test YAML are implemented, and any remaining blockers.
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
  foreach ($arg in @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $helper,
    "-OpencodeCommand", $OpencodeExe,
    "-SelectedModel", $SelectedModel,
    "-ProjectDir", $ProjectDir,
    "-Title", $Title,
    "-PromptPath", $PromptPath,
    "-AgentLog", $AgentLog
  )) {
    [void]$psi.ArgumentList.Add($arg)
  }
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
    $taskInputDir = Join-Path $candidateDir "_benchmark_inputs"
    New-Item -ItemType Directory -Force -Path $taskInputDir | Out-Null
    Copy-Item -LiteralPath (Join-Path $Root "specs\$($task.spec)") -Destination (Join-Path $taskInputDir $task.spec) -Force
    Copy-Item -LiteralPath (Join-Path $Root "state_tests\$($task.state)") -Destination (Join-Path $taskInputDir $task.state) -Force
    Copy-Item -LiteralPath (Join-Path $Root "state_tests\README.md") -Destination (Join-Path $taskInputDir "state_tests_README.md") -Force
    Copy-Item -LiteralPath (Join-Path $Root "state_tests\state-test-schema.json") -Destination (Join-Path $taskInputDir "state-test-schema.json") -Force
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
      & ohpm install *> $buildLog
      $ohpmExit = $LASTEXITCODE
      if ($ohpmExit -eq 0) {
        & hvigorw assembleHap --no-daemon *>> $buildLog
        $buildExit = $LASTEXITCODE
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
      evaluatorBinding = Join-Path $bindingRoot "$($task.id).binding.json"
      stateReadme = Join-Path $taskInputDir "state_tests_README.md"
      stateSchema = Join-Path $taskInputDir "state-test-schema.json"
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
}
$manifestPath = Join-Path $runRoot "eval_manifest.json"
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Host "[manifest] $manifestPath"

if (-not $SkipDynamicProbe) {
  $previousAgentRoot = $env:QINGYU_ARKTS_AGENT_ROOT
  $previousReportDir = $env:QINGYU_STATE_REPORT_DIR
  $env:QINGYU_ARKTS_AGENT_ROOT = $candidateRoot
  $env:QINGYU_STATE_REPORT_DIR = $reportRoot
  try {
    $matrixArgs = @{
      Root = $Root
      Platform = "ArkTS"
      Release = "Both"
      TargetRole = "Both"
      HarmonyInstance = $HarmonyInstance
      ReportDir = $reportRoot
    }
    if ($TaskId.Count -eq 1) {
      $matrixArgs.TaskId = $TaskId[0]
    }
    $matrixScript = Join-Path $Root "scripts\run-state-strict-matrix.ps1"
    & $matrixScript @matrixArgs
  } finally {
    if ($null -eq $previousAgentRoot) {
      Remove-Item Env:QINGYU_ARKTS_AGENT_ROOT -ErrorAction SilentlyContinue
    } else {
      $env:QINGYU_ARKTS_AGENT_ROOT = $previousAgentRoot
    }
    if ($null -eq $previousReportDir) {
      Remove-Item Env:QINGYU_STATE_REPORT_DIR -ErrorAction SilentlyContinue
    } else {
      $env:QINGYU_STATE_REPORT_DIR = $previousReportDir
    }
  }
}

Write-Host "[done] $runRoot"
