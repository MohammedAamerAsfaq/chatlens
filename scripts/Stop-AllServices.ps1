[CmdletBinding()]
param(
    [string]$NssmPath = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'NssmServiceControl.ps1')

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw 'This script must be run from an elevated (Administrator) PowerShell session.'
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

# Producers before consumers: stop anything that could enqueue new work before the
# workers that process it, so each worker only has to drain what's already queued.
$ServicesInOrder = @(
    @{ Name = 'ChatLensTaskScheduler';        TimeoutSeconds = 60  },
    @{ Name = 'ChatLensWorker';               TimeoutSeconds = 60  },
    @{ Name = 'ChatLensRealEstateTaskWorker'; TimeoutSeconds = 360 },
    @{ Name = 'ChatLensTaskWorker';           TimeoutSeconds = 360 }
)

$failed = @()
foreach ($entry in $ServicesInOrder) {
    $name = $entry.Name
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Host "$name is not installed - skipping."
        continue
    }
    if ($service.Status -eq 'Stopped') {
        Write-Host "$name is already stopped."
        continue
    }

    Write-Host "Stopping $name (up to $($entry.TimeoutSeconds)s to drain active work)..."
    try {
        Stop-NssmServiceForConfiguration -NssmPath $NssmPath -ServiceName $name -TimeoutSeconds $entry.TimeoutSeconds
        Write-Host "$name stopped."
    } catch {
        # Write-Warning, not Write-Error: with $ErrorActionPreference = 'Stop' in effect,
        # Write-Error itself becomes a terminating statement and would abort the loop
        # after the first failure instead of continuing to the remaining services.
        Write-Warning "Failed to stop $name`: $($_.Exception.Message)"
        $failed += $name
    }
}

if ($failed.Count -gt 0) {
    throw "One or more services failed to stop cleanly: $($failed -join ', '). They were NOT force-killed; investigate before retrying or restarting."
}

Write-Host "`nAll ChatLens services are stopped."
