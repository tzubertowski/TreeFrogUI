# Elevated dispatcher run by the "ClaudeAdmin" scheduled task (RunLevel Highest).
# Each job: I overwrite admin_cmd.ps1, delete admin_job.done, then `schtasks /run`.
# This runs admin_cmd.ps1 elevated and writes admin_job.done when finished.
$ErrorActionPreference='Continue'
$base='D:\r36s-\scripts'
try { & "$base\admin_cmd.ps1" *>> "$base\admin_cmd.log" }
catch { "DISPATCH ERROR: $_" | Add-Content "$base\admin_cmd.log" }
Set-Content "$base\admin_job.done" ("done {0}" -f (Get-Date -Format o))
