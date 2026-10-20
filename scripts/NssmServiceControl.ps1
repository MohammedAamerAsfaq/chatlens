function Wait-NssmServiceState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$ServiceName,
        [Parameter(Mandatory)] [string]$DesiredStatus,
        [int]$TimeoutSeconds = 60
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $service = Get-Service -Name $ServiceName -ErrorAction Stop
        if ($service.Status.ToString() -eq $DesiredStatus) {
            return $service
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)

    $service = Get-Service -Name $ServiceName -ErrorAction Stop
    throw "Service '$ServiceName' did not reach $DesiredStatus within $TimeoutSeconds seconds; current status is $($service.Status)."
}

function Wait-NssmServiceSettled {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$ServiceName,
        [int]$TimeoutSeconds = 60
    )

    $pendingStatuses = @('StartPending', 'StopPending', 'PausePending', 'ContinuePending')
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $service = Get-Service -Name $ServiceName -ErrorAction Stop
        if ($service.Status.ToString() -notin $pendingStatuses) {
            return $service
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)

    $service = Get-Service -Name $ServiceName -ErrorAction Stop
    throw "Service '$ServiceName' remained in transitional state $($service.Status) for $TimeoutSeconds seconds."
}

function Stop-NssmServiceForConfiguration {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$NssmPath,
        [Parameter(Mandatory)] [string]$ServiceName,
        [int]$TimeoutSeconds = 60
    )

    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $service -or $service.Status -eq 'Stopped') { return }

    $service = Wait-NssmServiceSettled -ServiceName $ServiceName -TimeoutSeconds $TimeoutSeconds
    if ($service.Status -eq 'Stopped') { return }

    & $NssmPath stop $ServiceName | Out-Null
    Wait-NssmServiceState -ServiceName $ServiceName -DesiredStatus 'Stopped' -TimeoutSeconds $TimeoutSeconds | Out-Null
}

function Start-NssmServiceSafely {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string]$NssmPath,
        [Parameter(Mandatory)] [string]$ServiceName,
        [int]$TimeoutSeconds = 60,
        [int]$StableSeconds = 2
    )

    $startOutput = & $NssmPath start $ServiceName 2>&1
    $startExitCode = $LASTEXITCODE
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $runningSince = $null

    do {
        $service = Get-Service -Name $ServiceName -ErrorAction Stop
        if ($service.Status -eq 'Running') {
            if (-not $runningSince) { $runningSince = [DateTime]::UtcNow }
            if (([DateTime]::UtcNow - $runningSince).TotalSeconds -ge $StableSeconds) {
                return $service
            }
        } else {
            $runningSince = $null
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)

    $service = Get-Service -Name $ServiceName -ErrorAction Stop
    $detail = ($startOutput | Out-String).Trim()
    throw "Service '$ServiceName' did not remain Running within $TimeoutSeconds seconds. NSSM exit code: $startExitCode. Final status: $($service.Status). NSSM output: $detail"
}
