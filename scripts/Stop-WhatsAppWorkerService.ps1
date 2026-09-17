[CmdletBinding()]
param(
    [string]$ServiceName = 'ChatLensWorker',
    [string]$NssmPath = '',
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
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
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $service) { throw "Service '$ServiceName' is not installed." }
if ($service.Status -eq 'Stopped') {
    Write-Host "$ServiceName is already stopped."
    exit 0
}

Write-Host "Requesting graceful stop for $ServiceName..."
& $NssmPath stop $ServiceName
if ($LASTEXITCODE -ne 0) { throw "NSSM could not request a stop for $ServiceName." }
$service = Get-Service -Name $ServiceName
try {
    $service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds($TimeoutSeconds))
} catch {
    throw "$ServiceName did not stop within $TimeoutSeconds seconds. It was not force-killed; inspect its service logs."
}
Write-Host "$ServiceName stopped gracefully."
