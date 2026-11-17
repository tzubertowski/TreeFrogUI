$ErrorActionPreference = 'Stop'
$name = 'R36-Recover-WSL-System'
$log = Join-Path $PSScriptRoot '../../analysis/wsl_system_task_setup.log'
Start-Transcript -Path $log -Append
try {
    $existing = Get-ScheduledTask | Where-Object { $_.TaskName -eq $name }
    if ($existing) { throw 'Recovery task already exists; inspect it before replacing.' }
    $script = Join-Path $PSScriptRoot 'recover_wsl_system.ps1'
    $action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script`""
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Description 'One-shot recovery of the stuck dedicated LxssManager process; no startup trigger.'
    Start-ScheduledTask -TaskName $name
} catch {
    Write-Warning $_.Exception.Message
    exit 1
} finally {
    Stop-Transcript
}
