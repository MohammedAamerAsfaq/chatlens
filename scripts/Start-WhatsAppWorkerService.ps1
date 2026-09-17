[CmdletBinding()]
param(
    [string]$ServiceName = 'ChatLensWorker',
    [string]$NssmPath = '',
    [string]$NodePath = ''
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$workerRoot = Join-Path $repoRoot 'whatsapp-worker'
$logRoot = Join-Path $repoRoot 'logs\services'

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
if (-not (Test-Path -LiteralPath (Join-Path $workerRoot 'index.js') -PathType Leaf)) {
    throw "WhatsApp worker entry point was not found under '$workerRoot'."
}
if (-not $NodePath) {
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { throw 'node.exe was not found in PATH. Pass -NodePath explicitly.' }
    $NodePath = $nodeCommand.Source
}
if (-not (Test-Path -LiteralPath $NodePath -PathType Leaf)) {
    throw "node.exe was not found at '$NodePath'."
}

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq 'Running') {
    Write-Host "$ServiceName is already running."
    exit 0
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
if (-not $service) {
    & $NssmPath install $ServiceName $NodePath 'index.js'
    if ($LASTEXITCODE -ne 0) { throw "NSSM could not install $ServiceName." }
}

$settings = @(
    @('Application', $NodePath),
    @('AppDirectory', $workerRoot),
    @('AppParameters', 'index.js'),
    @('DisplayName', 'ChatLens WhatsApp Worker'),
    @('Description', 'Baileys WhatsApp session and message transport worker for ChatLens.'),
    @('Start', 'SERVICE_AUTO_START'),
    @('AppExit', 'Default', 'Restart'),
    @('AppRestartDelay', '5000'),
    @('AppStopMethodSkip', '0'),
    @('AppStopMethodConsole', '30000'),
    @('AppStopMethodWindow', '30000'),
    @('AppStopMethodThreads', '30000'),
    @('AppStdout', (Join-Path $logRoot 'whatsapp-worker.out.log')),
    @('AppStderr', (Join-Path $logRoot 'whatsapp-worker.err.log')),
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
Write-Host "$ServiceName is running from $workerRoot."
