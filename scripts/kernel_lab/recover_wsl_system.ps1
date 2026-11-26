# One-shot SYSTEM recovery, invoked by the Windows Task Scheduler.
$ErrorActionPreference = 'Stop'
$log = Join-Path $PSScriptRoot '../../analysis/wsl_system_recovery.log'
Start-Transcript -Path $log -Append
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if ($identity.User.Value -ne 'S-1-5-18') {
        throw 'This recovery requires the LocalSystem identity.'
    }
    $service = Get-CimInstance Win32_Service -Filter "Name='LxssManager'"
    $service | Format-List Name, State, ProcessId
    if ($service.State -eq 'Stop Pending') {
        $servicePid = $service.ProcessId
        if (-not $servicePid) { throw 'No service process to recover.' }
        $siblings = @(Get-CimInstance Win32_Service -Filter "ProcessId=$servicePid")
        if ($siblings.Count -ne 1 -or $siblings[0].Name -ne 'LxssManager') {
            throw 'Refusing to kill a shared service process.'
        }
        & taskkill.exe /PID $servicePid /F
        if ($LASTEXITCODE -ne 0) { throw "SYSTEM taskkill failed: $LASTEXITCODE" }
        (Get-Service LxssManager).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(15))
    }
    Start-Service LxssManager
    (Get-Service LxssManager).WaitForStatus('Running', [TimeSpan]::FromSeconds(15))
    Get-Service LxssManager
} catch {
    Write-Warning $_.Exception.Message
    exit 1
} finally {
    Stop-Transcript
}
