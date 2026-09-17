[CmdletBinding()]
param(
    [string]$ServiceName = 'ChatLensTaskWorker',
    [string]$NssmPath = '',
    [string]$PythonPath = ''
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$logRoot = Join-Path $repoRoot 'logs\services'
if (-not $PythonPath) { $PythonPath = Join-Path $repoRoot 'venv\Scripts\python.exe' }

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
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python was not found at '$PythonPath'. Pass -PythonPath explicitly."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'manage.py') -PathType Leaf)) {
    throw "manage.py was not found under '$repoRoot'."
}

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq 'Running') {
    Write-Host "$ServiceName is already running."
    exit 0
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$arguments = 'manage.py run_background_tasks --no-ui'
if (-not $service) {
    & $NssmPath install $ServiceName $PythonPath $arguments
    if ($LASTEXITCODE -ne 0) { throw "NSSM could not install $ServiceName." }
}

$settings = @(
    @('Application', $PythonPath),
    @('AppDirectory', $repoRoot),
    @('AppParameters', $arguments),
    @('DisplayName', 'ChatLens Task Worker'),
    @('Description', 'Durable background task worker for all enabled ChatLens queues.'),
    @('Start', 'SERVICE_AUTO_START'),
    @('AppExit', 'Default', 'Restart'),
    @('AppRestartDelay', '5000'),
    @('AppStopMethodSkip', '0'),
    @('AppStopMethodConsole', '30000'),
    @('AppStopMethodWindow', '30000'),
    @('AppStopMethodThreads', '30000'),
    @('AppStdout', (Join-Path $logRoot 'task-worker.out.log')),
    @('AppStderr', (Join-Path $logRoot 'task-worker.err.log')),
    @('AppRotateFiles', '1'),
    @('AppRotateOnline', '1'),
    @('AppRotateBytes', '10485760')
)
foreach ($setting in $settings) {
    & $NssmPath set $ServiceName @setting | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to configure NSSM setting '$($setting[0])'." }
}

& $NssmPath start $ServiceName
if ($LASTEXITCODE -ne 0) { throw "NSSM could not start $ServiceName." }
(Get-Service -Name $ServiceName).WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
Write-Host "$ServiceName is running and serving all enabled queues."
