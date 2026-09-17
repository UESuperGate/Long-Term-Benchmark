param(
  [string]$Root = "C:\Users\xiexi\qingyu",
  [string]$RunId = "",
  [string]$Model = "aliyun/deepseek-v4-flash",
  [string]$BaseUrl = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
  [string]$HarmonyInstance = "Custom Screen",
  [string[]]$TaskId = @()
)

$ErrorActionPreference = "Stop"

if (-not $env:DEVECO_EVAL_API_KEY) {
  throw "DEVECO_EVAL_API_KEY is required. Set it for this process; do not write it into the script."
}

$deveco = "C:\Users\xiexi\AppData\Roaming\npm\deveco.cmd"
if (-not (Test-Path -LiteralPath $deveco)) {
  throw "DevEco CLI not found at $deveco"
}

. (Join-Path $Root "scripts\set-oh-build-env.ps1")

if ($RunId.Length -eq 0) {
  $RunId = "deveco_deepseek_flash_" + (Get-Date -Format "yyyyMMdd_HHmmss")
}

$runRoot = Join-Path $Root "eval_runs\$RunId"
$candidateRoot = Join-Path $runRoot "arkts_final_candidates"
$logRoot = Join-Path $runRoot "logs"
$reportRoot = Join-Path $runRoot "verification_reports\state_dynamic"
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

function New-DevecoConfigContent {
  param([string]$ApiKey, [string]$ProviderBaseUrl, [string]$SelectedModel)
  $providerId, $modelId = $SelectedModel.Split("/", 2)
  $modelMap = @{}
  $modelMap[$modelId] = @{
    name = $modelId
    tool_call = $true
    attachment = $false
    reasoning = $false
    temperature = $true
    status = "active"
    limit = @{ context = 128000; output = 16000 }
    cost = @{ input = 0; output = 0 }
  }
  $providers = @{}
  $providers[$providerId] = @{
    npm = "@ai-sdk/openai-compatible"
    name = "Aliyun Compatible Mode"
    options = @{
      baseURL = $ProviderBaseUrl
      apiKey = $ApiKey
      timeout = 1800000
      headerTimeout = 300000
      chunkTimeout = 300000
    }
    models = $modelMap
  }
  return (@{
    provider = $providers
    model = $SelectedModel
    small_model = $SelectedModel
    share = "disabled"
    permission = @{
      read = "allow"
      edit = "allow"
      bash = "allow"
      list = "allow"
      grep = "allow"
      glob = "allow"
      webfetch = "allow"
      websearch = "allow"
      external_directory = "deny"
      todowrite = "allow"
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
  $promptPath = Join-Path $InputDir "deveco_prompt.md"
  $specPath = Join-Path $InputDir $Task.spec
  $statePath = Join-Path $InputDir $Task.state
  $bindingPath = Join-Path $InputDir "$($Task.id).binding.json"
  $text = @"
IMPORTANT: Implement the task now. Do not stop after project orientation, and do not ask what to do next. Your answer is only acceptable after you have edited the ArkTS source and attempted a build.

You are running inside a copied ArkTS/HarmonyOS SDK 23 Element X benchmark base project.

Task id: $($Task.id)
Project directory: $ProjectDir
Requirement spec: $specPath
State-test YAML: $statePath
Evaluator binding manifest: $bindingPath

Implement the requested long-horizon task in this ArkTS project only.

Rules:
- Treat the requirement spec, state-test YAML, and evaluator binding manifest as the public task contract.
- Do not read or copy from any ArkTS final answer directory outside this project.
- Do not modify Android source.
- Preserve SDK 23 compatibility and the existing project structure.
- Keep the implementation constrained to behavior described by the spec/state tests.
- First read `entry/src/main/ets/pages/Index.ets` and any local project files you need.
- Update the real ArkTS implementation, not only README or benchmark notes.
- Do not hardcode `state_test_result`, version checks, `feature_available=true`, or a case-id switch that renders expected tokens without implementing the underlying feature state.
- The app must expose real UI/state semantics that can satisfy per-case `given_state`, `expect_ui`, `transitions`, and `properties`; target-level smoke markers are not sufficient.
- If a state-test deeplink is already present, use it only to route to or apply legitimate feature state. Do not turn it into a self-scoring harness.
- After editing, run ``ohpm install`` if needed and ``hvigorw assembleHap --no-daemon``.
- Fix build errors before finishing. If build still fails, leave the source in your best attempted state and summarize the blocker.

When done, summarize changed files, build result, which functional areas from the state-test YAML are implemented, and any remaining blockers.
"@
  Set-Content -LiteralPath $promptPath -Value $text -Encoding UTF8
  return $promptPath
}

$manifestTasks = @()
$env:DEVECO_CONFIG_CONTENT = New-DevecoConfigContent -ApiKey $env:DEVECO_EVAL_API_KEY -ProviderBaseUrl $BaseUrl -SelectedModel $Model

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
    Copy-Item -LiteralPath (Join-Path $bindingRoot "$($task.id).binding.json") -Destination (Join-Path $taskInputDir "$($task.id).binding.json") -Force
    $promptPath = Write-TaskPrompt -Task $task -ProjectDir $candidateDir -InputDir $taskInputDir

    $agentLog = Join-Path $logRoot "$($task.id)_deveco.jsonl"
    $buildLog = Join-Path $logRoot "$($task.id)_build.log"

    Write-Host "[deveco] $($task.id)"
    $promptText = Get-Content -LiteralPath $promptPath -Raw -Encoding UTF8
    & $deveco run --model $Model --format json --dangerously-skip-permissions --dir $candidateDir --title "$RunId $($task.id)" $promptText *> $agentLog
    $agentExit = $LASTEXITCODE

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
      candidateFinalDir = $candidateDir
      spec = Join-Path $taskInputDir $task.spec
      state = Join-Path $taskInputDir $task.state
      binding = Join-Path $taskInputDir "$($task.id).binding.json"
      stateReadme = Join-Path $taskInputDir "state_tests_README.md"
      stateSchema = Join-Path $taskInputDir "state-test-schema.json"
      model = $Model
      agentExit = $agentExit
      buildExit = $buildExit
      hap = if ($hap) { $hap.FullName } else { "" }
      agentLog = $agentLog
      buildLog = $buildLog
    }
  }
} finally {
  Remove-Item Env:DEVECO_CONFIG_CONTENT -ErrorAction SilentlyContinue
}

$manifest = [pscustomobject]@{
  runId = $RunId
  createdAt = (Get-Date).ToString("o")
  model = $Model
  baseUrl = $BaseUrl
  root = $runRoot
  candidateRoot = $candidateRoot
  tasks = $manifestTasks
}
$manifestPath = Join-Path $runRoot "eval_manifest.json"
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Host "[manifest] $manifestPath"

$env:QINGYU_ARKTS_FINAL_ROOT = $candidateRoot
$env:QINGYU_STATE_REPORT_DIR = $reportRoot
try {
  $matrixArgs = @{
    Root = $Root
    Platform = "ArkTS"
    Release = "Both"
    HarmonyInstance = $HarmonyInstance
    ReportDir = $reportRoot
  }
  if ($TaskId.Count -eq 1) {
    $matrixArgs.TaskId = $TaskId[0]
  }
  $matrixScript = Join-Path $Root "scripts\run-state-strict-matrix.ps1"
  & $matrixScript @matrixArgs
} finally {
  Remove-Item Env:QINGYU_ARKTS_FINAL_ROOT -ErrorAction SilentlyContinue
  Remove-Item Env:QINGYU_STATE_REPORT_DIR -ErrorAction SilentlyContinue
}

Write-Host "[done] $runRoot"
