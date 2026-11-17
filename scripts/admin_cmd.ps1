# Job: bring up WPD/MTP so the console's card surfaces, then restart the device node.
$r='D:\r36s-\card2_backup\wpd_fix.txt'; Set-Content $r "wpd fix $(Get-Date -Format HH:mm:ss)"
try { Start-Service WpdBusEnum -ErrorAction Stop; Add-Content $r "WpdBusEnum started" } catch { Add-Content $r "start err: $($_.Exception.Message)" }
Start-Sleep 2
$id = (Get-PnpDevice -PresentOnly -Class WPD | Where-Object InstanceId -match 'VID_18D1&PID_4E22').InstanceId
Add-Content $r "device: $id"
try { Restart-PnpDevice -InstanceId $id -Confirm:$false -ErrorAction Stop; Add-Content $r "restarted" } catch { Add-Content $r "restart err: $($_.Exception.Message)" }
Start-Sleep 3
pnputil /scan-devices | Out-Null
Start-Sleep 2
Add-Content $r ("status: " + ((Get-PnpDevice -PresentOnly | Where-Object InstanceId -match 'VID_18D1&PID_4E22' | Select-Object -Expand Status) -join ','))
Add-Content $r ("WpdBusEnum: " + (Get-Service WpdBusEnum).Status)
