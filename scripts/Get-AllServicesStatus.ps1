[CmdletBinding()]
param()

# Same order Start-AllServices.ps1 brings things up in (consumers before producers).
$ServiceNames = @(
    'ChatLensTaskWorker',
    'ChatLensRealEstateTaskWorker',
    'ChatLensWorker',
    'ChatLensTaskScheduler'
)

$rows = foreach ($name in $ServiceNames) {
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if (-not $service) {
        [PSCustomObject]@{
            Service   = $name
            Status    = 'NotInstalled'
            StartType = '-'
            ProcessId = '-'
        }
        continue
    }

    $cim = Get-CimInstance -ClassName Win32_Service -Filter "Name='$name'" -ErrorAction SilentlyContinue
    [PSCustomObject]@{
        Service   = $name
        Status    = $service.Status.ToString()
        StartType = $service.StartType.ToString()
        ProcessId = if ($cim -and $cim.ProcessId -ne 0) { $cim.ProcessId } else { '-' }
    }
}

$rows | Format-Table -AutoSize

$unhealthy = $rows | Where-Object { $_.Status -ne 'Running' }
if ($unhealthy.Count -gt 0) {
    Write-Host ''
    $summary = ($unhealthy | ForEach-Object { "$($_.Service) [$($_.Status)]" }) -join ', '
    Write-Warning "Not fully up: $summary"
    exit 1
}

Write-Host "`nAll ChatLens services are running."
