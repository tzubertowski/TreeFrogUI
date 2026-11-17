$ErrorActionPreference = 'Stop'
Start-Transcript -Path (Join-Path $PSScriptRoot '../../analysis/wsl_system_task_cleanup.log') -Append
try {
    $task = Get-ScheduledTask -TaskName 'R36-Recover-WSL-System'
    $task | Format-List TaskName, State, Description
    $task.Actions | Format-List Execute, Arguments
    if ($task.State -eq 'Running') { throw 'Recovery task is still running.' }
    if ($task.Description -ne 'One-shot recovery of the stuck dedicated LxssManager process; no startup trigger.' -or
        @($task.Actions).Count -ne 1 -or
        $task.Actions[0].Arguments -notlike '*scripts\kernel_lab\recover_wsl_system.ps1*') {
        throw 'Task identity differs; refusing to remove it.'
    }
    Unregister-ScheduledTask -TaskName $task.TaskName -Confirm:$false
    'One-shot SYSTEM task removed.'
} catch {
    Write-Warning $_.Exception.Message
    exit 1
} finally {
    Stop-Transcript
}
