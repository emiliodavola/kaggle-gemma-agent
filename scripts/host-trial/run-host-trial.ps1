#Requires -Version 5.1
<#
.SYNOPSIS
    Runnable port of docs/host-trial-runbook.md, sections 1-7.

.DESCRIPTION
    Same trial as the POSIX script: two tasks (fastapi_15661, fastapi_15588)
    against an OpenAI-compatible cloud backend, archived under runs/.

    SECURITY: the backend key is read ONLY from the OPENAI_API_KEY environment
    variable. It is never accepted as an argument, echoed, or written to disk.
    Set it in this session first (runbook sec. 5):

        $env:OPENAI_API_KEY = "<your-backend-key>"
        $env:OPENAI_BASE_URL = "https://opencode.ai/zen/go/v1"   # optional

    Values are sourced from docs/host-trial-runbook.md (facts table, sections
    1-7) and data/raw/models-trial.yaml (the --models-yaml story).

.PARAMETER ResultsName
    Names results\<ResultsName>. The only parameter. Default: run_01.
#>
[CmdletBinding()]
param(
    [string]$ResultsName = "run_01"
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# --- fixed trial parameters (runbook facts table + sections 4/6) -------------
$DataRaw        = Join-Path $RepoRoot 'data/raw'
$TasksFile      = Join-Path $RepoRoot 'data/raw/tasks.jsonl'
$SnapshotsDir   = Join-Path $RepoRoot 'data/raw/snapshots'
$WheelhouseDir  = Join-Path $RepoRoot 'data/raw/wheelhouse'
$DockerContext  = Join-Path $RepoRoot 'data/raw/docker'
$SubmissionDir  = Join-Path $RepoRoot 'submission'
$ModelsYaml     = Join-Path $RepoRoot 'data/raw/models-trial.yaml'
$ResultsDir     = Join-Path $RepoRoot ("results/{0}" -f $ResultsName)
$JunitDir       = Join-Path $RepoRoot 'junit'
$Competition    = 'gemma-4-developer-agent'
$WheelhouseData = 'metric/gemma-4-developer-agent-wheelhouse'
$TaskIds        = @('fastapi_15661', 'fastapi_15588')
$BackendAlias   = 'deepseek-trial'

function Write-Phase {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=== {0} ===" -f $Text) -ForegroundColor Cyan
}

function Write-Note {
    param([string]$Text)
    Write-Host ("  {0}" -f $Text)
}

function Stop-Trial {
    param([string]$Message)
    Write-Host ("ERROR: {0}" -f $Message) -ForegroundColor Red
    exit 1
}

function Assert-Exit {
    param([string]$What)
    if ($LASTEXITCODE -ne 0) {
        Stop-Trial ("{0} failed (exit {1})" -f $What, $LASTEXITCODE)
    }
}

function Require-Command {
    param([string]$Name, [string]$Hint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Stop-Trial ("missing prerequisite '{0}'. {1}" -f $Name, $Hint)
    }
}

function Get-CompFile {
    param([string]$RemoteFile, [string]$DestDir)
    $name = Split-Path -Leaf $RemoteFile
    $dest = Join-Path $DestDir $name
    if (Test-Path $dest) {
        Write-Note ("skip (exists): {0}" -f $dest)
        return
    }
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    & kaggle competitions download -c $Competition -f $RemoteFile -p $DestDir
    Assert-Exit ("kaggle download {0}" -f $RemoteFile)
}

# --- Phase 1 (runbook section 1): prerequisites ------------------------------
Write-Phase "Phase 1/7 (runbook sec. 1): prerequisites"

Require-Command 'git'    'Install git first.'
Require-Command 'uv'     'Install uv first: https://astral.sh/uv'
Require-Command 'docker' 'Install Docker Desktop and start it.'
Require-Command 'kaggle' 'Install the Kaggle CLI: uv tool install kaggle'

$dockerOs = (& docker info --format '{{.OSType}}' 2>$null)
Assert-Exit 'docker info'
if ($dockerOs -ne 'linux') {
    Stop-Trial ("Docker engine is not reachable in Linux mode (got '{0}'). Start Docker Desktop and confirm the Linux engine (runbook sec. 1.1)." -f $dockerOs)
}

$kaggleToken = Join-Path $HOME '.kaggle/kaggle.json'
if (-not (Test-Path $kaggleToken)) {
    Stop-Trial ("Kaggle token not found at {0}. Download it from your Kaggle account (runbook sec. 1.4)." -f $kaggleToken)
}

& git --version; Assert-Exit 'git --version'
& uv --version; Assert-Exit 'uv --version'
& kaggle --version; Assert-Exit 'kaggle --version'
Write-Note 'Docker engine OSType: linux'

# --- Phase 2 (runbook section 2): repository + harness branch ----------------
Write-Phase "Phase 2/7 (runbook sec. 2): repository and harness branch"

Set-Location $RepoRoot
& git fetch origin; Assert-Exit 'git fetch origin'

$hasContract = Test-Path (Join-Path $RepoRoot 'docs/harness-logging-contract.md')
$hasArchiver = Test-Path (Join-Path $RepoRoot 'src/kaggle_gemma_agent/harness_runs.py')
if (-not $hasContract -or -not $hasArchiver) {
    & git show origin/main:docs/harness-logging-contract.md *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Note 'harness code absent on this branch; switching to main'
        & git checkout main; Assert-Exit 'git checkout main'
        & git pull --ff-only origin main; Assert-Exit 'git pull --ff-only origin main'
    }
    else {
        Stop-Trial 'harness code (docs/harness-logging-contract.md, harness_runs.py) is not available. Check out main or exp/harness-trial-1 (runbook sec. 2).'
    }
}

if (-not (Test-Path (Join-Path $RepoRoot 'docs/harness-logging-contract.md'))) {
    Stop-Trial 'docs/harness-logging-contract.md still missing after update.'
}
if (-not (Test-Path (Join-Path $RepoRoot 'src/kaggle_gemma_agent/harness_runs.py'))) {
    Stop-Trial 'src/kaggle_gemma_agent/harness_runs.py still missing after update.'
}

# --- Phase 3 (runbook section 4): data - wheelhouse + small fixtures ONLY ----
# Bulk snapshots/ and embeddings/ are intentionally NOT pulled (approx. 20.9 GiB).
Write-Phase "Phase 3/7 (runbook sec. 4): fetch wheelhouse + small fixtures (NO bulk)"

$wheels = @(Get-ChildItem -Path $WheelhouseDir -Filter *.whl -ErrorAction SilentlyContinue)
if ($wheels.Count -gt 0) {
    Write-Note 'skip (exists): runtime wheelhouse already extracted'
}
else {
    New-Item -ItemType Directory -Force -Path $WheelhouseDir | Out-Null
    & kaggle datasets download -d $WheelhouseData -p $WheelhouseDir
    Assert-Exit 'kaggle datasets download wheelhouse'
    $zips = @(Get-ChildItem -Path $WheelhouseDir -Filter *.zip -ErrorAction SilentlyContinue)
    foreach ($zip in $zips) {
        Expand-Archive -Path $zip.FullName -DestinationPath $WheelhouseDir -Force
    }
}

Get-CompFile 'tasks.jsonl' $DataRaw
Get-CompFile 'HARNESS_README.md' $DataRaw
Get-CompFile 'sandbox/setup.py' (Join-Path $DataRaw 'sandbox')
Get-CompFile 'docker/Dockerfile.sandbox' $DockerContext
Get-CompFile 'docker/Dockerfile.public' $DockerContext

Write-Note 'fetching only the two trial snapshots (never the whole snapshots/ tree)'
Get-CompFile 'snapshots/fastapi_15661.tgz' $SnapshotsDir
Get-CompFile 'snapshots/fastapi_15588.tgz' $SnapshotsDir

# --- Phase 4 (runbook section 3): build the sandbox image --------------------
Write-Phase "Phase 4/7 (runbook sec. 3): build sandbox image"

$dockerfile = Join-Path $DockerContext 'Dockerfile.sandbox'
if (-not (Test-Path $dockerfile)) {
    Stop-Trial ("missing {0} (fetched in phase 3)." -f $dockerfile)
}
& docker build -t swebench-sandbox:latest -f $dockerfile $DockerContext
Assert-Exit 'docker build swebench-sandbox:latest'

# --- Phase 5 (runbook section 5): backend key - env only ---------------------
Write-Phase "Phase 5/7 (runbook sec. 5): backend key (environment only)"

if ([string]::IsNullOrEmpty($env:OPENAI_API_KEY)) {
    Stop-Trial 'OPENAI_API_KEY is empty. Set it in this session before running (never pass it as an argument): $env:OPENAI_API_KEY = "<key>" (runbook sec. 5).'
}
if ([string]::IsNullOrEmpty($env:OPENAI_BASE_URL)) {
    $env:OPENAI_BASE_URL = 'https://opencode.ai/zen/go/v1'
    Write-Note 'OPENAI_BASE_URL defaulted to https://opencode.ai/zen/go/v1'
}
if (-not (Test-Path $ModelsYaml)) {
    Stop-Trial ("missing {0} (the --models-yaml mapping; runbook sec. 6 / data/raw/models-trial.yaml)." -f $ModelsYaml)
}
Write-Note ("OPENAI_API_KEY is set (value not shown); base URL: {0}" -f $env:OPENAI_BASE_URL)

# --- Phase 6 (runbook section 6): run the trial, two tasks -------------------
Write-Phase "Phase 6/7 (runbook sec. 6): swegemma eval (2 tasks, competition budgets)"

if (-not (Get-Command 'swegemma' -ErrorAction SilentlyContinue)) {
    Stop-Trial 'swegemma is not on PATH. Install it from the wheelhouse dataset (runbook sec. 4.1; install command is an open TODO in the runbook).'
}

New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
$evalArgs = @(
    'eval',
    '--tasks', $TasksFile,
    '--snapshots-dir', $SnapshotsDir,
    '--submission-dir', $SubmissionDir,
    '--task-ids', $TaskIds[0], $TaskIds[1],
    '--results-dir', $ResultsDir,
    '--sandbox', 'docker',
    '--max-tool-calls', '100',
    '--max-time-minutes', '60',
    '--concurrency', '1',
    '--display', 'auto',
    '--models-yaml', $ModelsYaml
)
& swegemma @evalArgs
Assert-Exit 'swegemma eval'

# --- Phase 7 (runbook sections 7-9): archive into runs/ ----------------------
Write-Phase "Phase 7/7 (runbook sec. 7-9): archive + report under runs/"

Write-Note 'JUnit note (runbook sec. 8): the harness writes JUnit XML only inside Container B'
Write-Note 'at /tmp/_swegemma_junit_<id>.xml and warm-pooled containers are wiped. If a'
Write-Note 'container is still alive, copy it out before teardown:'
Write-Note '  docker ps'
Write-Note ("  docker cp <container>:/tmp/_swegemma_junit_fastapi_15661.xml {0}/" -f $JunitDir)
Write-Note 'If it is already gone, pass/fail is still readable from task_results.jsonl.'

New-Item -ItemType Directory -Force -Path $JunitDir | Out-Null
$archiveArgs = @(
    'run', 'python', '-m', 'kaggle_gemma_agent.harness_runs', 'archive', $ResultsDir,
    '--junit-dir', $JunitDir,
    '--tasks', $TasksFile,
    '--backend', $BackendAlias
)
& uv @archiveArgs
Assert-Exit 'harness_runs archive'

$runsRoot = Join-Path $RepoRoot 'runs'
$latestRun = Get-ChildItem -Path $runsRoot -Directory -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latestRun) {
    Stop-Trial 'archiver produced no runs/<UTC>/ directory.'
}

& uv run python -m kaggle_gemma_agent.harness_runs report $latestRun.FullName
Assert-Exit 'harness_runs report'

Write-Host ""
Write-Host ("Trial complete. Archived under {0} (report: {1})." -f $latestRun.FullName, (Join-Path $latestRun.FullName 'report.json'))
