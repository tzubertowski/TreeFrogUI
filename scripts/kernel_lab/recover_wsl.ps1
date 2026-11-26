# Run elevated; touches only the dedicated LxssManager service process.
$ErrorActionPreference = 'Stop'
$log = Join-Path $PSScriptRoot '../../analysis/wsl_recovery.log'
Start-Transcript -Path $log -Append
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Administrator rights are required.'
    }
    $service = Get-CimInstance Win32_Service -Filter "Name='LxssManager'"
    $service | Format-List Name, State, ProcessId
    if ($service.State -eq 'Stop Pending') {
        $servicePid = $service.ProcessId
        if (-not $servicePid) { throw 'No LxssManager process to recover.' }
        $siblings = @(Get-CimInstance Win32_Service -Filter "ProcessId=$servicePid")
        if ($siblings.Count -ne 1 -or $siblings[0].Name -ne 'LxssManager') {
            throw 'Refusing to stop a service process shared with another service.'
        }
        & taskkill.exe /PID $servicePid /F
        if ($LASTEXITCODE -ne 0) { throw "taskkill failed: $LASTEXITCODE" }
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
