[CmdletBinding()]
param(
    [string]$ServiceName = 'ChatLensRealEstateTaskWorker',
    [string]$NssmPath = '',
    [string]$PythonPath = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'NssmServiceControl.ps1')
$repoRoot = Split-Path -Parent $PSScriptRoot
$logRoot = Join-Path $repoRoot 'logs\services'
if (-not $PythonPath) {
    $parentRoot = Split-Path -Parent $repoRoot
    $PythonPath = @(
        (Join-Path $repoRoot 'venv\Scripts\python.exe'),
        (Join-Path $parentRoot 'venv\Scripts\python.exe')
    ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}

if (-not $NssmPath) {
    $nssmCommand = Get-Command nssm.exe -ErrorAction SilentlyContinue
    $NssmPath = @(
        $env:NSSM_PATH,
        $(if ($nssmCommand) { $nssmCommand.Source }),
        'C:\ProgramData\chocolatey\bin\nssm.exe',
        'C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe',
        'C:\tools\nssm\nssm.exe'
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
}

if (-not (Test-Path -LiteralPath $NssmPath -PathType Leaf)) {
    throw 'NSSM was not found. Install it with "choco install nssm -y", pass -NssmPath, or set NSSM_PATH.'
}
if ([string]::IsNullOrWhiteSpace($PythonPath) -or -not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw 'Python was not found in a repository or sibling venv. Pass -PythonPath explicitly.'
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'manage.py') -PathType Leaf)) {
    throw "manage.py was not found under '$repoRoot'."
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$queues = @(
    'real_estate_gate',
    'real_estate_extract',
    'real_estate_match',
    'real_estate_maintenance',
    'real_estate_embeddings',
    'real_estate_imports'
)
$queueArguments = ($queues | ForEach-Object { "--queue $_" }) -join ' '
$arguments = "manage.py run_background_tasks --no-ui --worker-id chatlens-real-estate-worker $queueArguments"
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq 'Running') {
    $currentArguments = (& $NssmPath get $ServiceName AppParameters | Out-String).Trim()
    if ($currentArguments -eq $arguments) {
        Write-Host "$ServiceName is already running with the correct Real Estate queues."
        exit 0
    }
    throw "$ServiceName is running with outdated parameters. Stop it safely, then run this script again to apply the Real Estate queue list."
}
if ($service) {
    Stop-NssmServiceForConfiguration -NssmPath $NssmPath -ServiceName $ServiceName
}
if (-not $service) {
    & $NssmPath install $ServiceName $PythonPath $arguments
    if ($LASTEXITCODE -ne 0) { throw "NSSM could not install $ServiceName." }
}

$settings = @(
    @('Application', $PythonPath),
    @('AppDirectory', $repoRoot),
    @('AppParameters', $arguments),
    @('DisplayName', 'ChatLens Real Estate Task Worker'),
    @('Description', 'Dedicated durable worker for ChatLens Real Estate queues.'),
    @('Start', 'SERVICE_AUTO_START'),
    @('AppExit', 'Default', 'Restart'),
    @('AppRestartDelay', '5000'),
    @('AppStopMethodSkip', '0'),
    @('AppStopMethodConsole', '30000'),
    @('AppStopMethodWindow', '30000'),
    @('AppStopMethodThreads', '30000'),
    @('AppStdout', (Join-Path $logRoot 'real-estate-task-worker.out.log')),
    @('AppStderr', (Join-Path $logRoot 'real-estate-task-worker.err.log')),
    @('AppRotateFiles', '1'),
    @('AppRotateOnline', '1'),
    @('AppRotateBytes', '10485760')
)
foreach ($setting in $settings) {
    & $NssmPath set $ServiceName @setting | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to configure NSSM setting '$($setting[0])'." }
}

Start-NssmServiceSafely -NssmPath $NssmPath -ServiceName $ServiceName | Out-Null
Write-Host "$ServiceName is running and serving: $($queues -join ', ')."
