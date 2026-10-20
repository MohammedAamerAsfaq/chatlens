[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'NssmServiceControl.ps1')

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw 'This script must be run from an elevated (Administrator) PowerShell session.'
}

# Consumers before producers: bring workers up first so nothing they'd otherwise
# process gets queued while they're still offline.
$ServiceNames = @(
    'ChatLensTaskWorker',
    'ChatLensRealEstateTaskWorker',
    'ChatLensWorker',
    'ChatLensTaskScheduler'
)

$failed = @()
foreach ($name in $ServiceNames) {
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Warning "$name is not installed - skipping. Run scripts\Start-<Service>.ps1 once to install it as a service first."
        continue
    }
    if ($service.Status -eq 'Running') {
        Write-Host "$name is already running."
        continue
    }

    Write-Host "Starting $name (currently $($service.Status))..."
    try {
        if ($service.Status -eq 'Paused') {
            try {
                Resume-Service -Name $name
            } catch {
                # Most NSSM-wrapped services don't implement pause/continue control codes,
                # so Resume-Service fails against them; fall back to a full stop+start.
                Stop-Service -Name $name -Force
                Start-Service -Name $name
            }
        } else {
            Start-Service -Name $name
        }
        Wait-NssmServiceState -ServiceName $name -DesiredStatus 'Running' -TimeoutSeconds $TimeoutSeconds | Out-Null
        Write-Host "$name is running."
    } catch {
        # Write-Warning, not Write-Error: with $ErrorActionPreference = 'Stop' in effect,
        # Write-Error itself becomes a terminating statement and would abort the whole
        # loop after the first failure instead of continuing to the remaining services.
        Write-Warning "Failed to start $name`: $($_.Exception.Message)"
        $failed += $name
    }
}

if ($failed.Count -gt 0) {
    throw "One or more services failed to start: $($failed -join ', '). Check logs\services for details."
}

Write-Host "`nAll ChatLens services are running."
