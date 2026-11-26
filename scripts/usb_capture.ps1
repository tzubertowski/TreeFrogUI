# Elevated: raw USB capture on every USB root hub (USBPcap) until a stop file
# appears or 2 hours pass. One pcap per root hub in D:\r36s-\usbcap\.
#   start: Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File','D:\r36s-\scripts\usb_capture.ps1'
#   stop : New-Item D:\r36s-\usbcap\capture.stop
$out  = 'D:\r36s-\usbcap'
$cmd  = 'C:\Program Files\USBPcap\USBPcapCMD.exe'
$stop = Join-Path $out 'capture.stop'
$log  = Join-Path $out 'capture.log'
New-Item -ItemType Directory -Force $out | Out-Null
Remove-Item $stop -ErrorAction SilentlyContinue
function L($m) { "$(Get-Date -Format 'HH:mm:ss.fff') $m" | Out-File -FilePath $log -Append -Encoding utf8 }

L '==== capture start ===='
$ifs = & $cmd --extcap-interfaces 2>&1 | ForEach-Object {
    if ($_ -match 'value=(\\\\\.\\USBPcap\d+)') { $Matches[1] }
} | Select-Object -Unique
if (-not $ifs) { L 'NO USBPcap interfaces - reboot the PC after installing USBPcap'; exit 1 }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$procs = @()
foreach ($i in $ifs) {
    $n = $i -replace '.*USBPcap', ''
    $f = Join-Path $out "usb${n}_$stamp.pcap"
    # -A: capture all devices on the hub, including ones connected later.
    # --inject-descriptors: put device/config descriptors at the start of the file.
    $p = Start-Process -FilePath $cmd -WindowStyle Hidden -PassThru -ArgumentList @('-d', $i, '-o', "`"$f`"", '-A', '--inject-descriptors', '-b', '8388608')
    $procs += $p
    L "capturing $i -> $f (pid $($p.Id))"
}
$deadline = (Get-Date).AddHours(2)
while (-not (Test-Path $stop) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
foreach ($p in $procs) { try { Stop-Process -Id $p.Id -Force -ErrorAction Stop } catch {} }
Remove-Item $stop -ErrorAction SilentlyContinue
L '==== capture stopped ===='
# Export Windows' MTP/WPD/WUDF driver logs next to the pcaps (readable without admin).
foreach ($n in 'Microsoft-Windows-WPD-MTPClassDriver/Operational','Microsoft-Windows-WPD-MTPClassDriver/Analytic',
               'Microsoft-Windows-WPD-MTPUS/Analytic','Microsoft-Windows-WPD-API/Analytic',
               'Microsoft-Windows-WPD-CompositeClassDriver/Operational','Microsoft-Windows-WPD-CompositeClassDriver/Analytic',
               'Microsoft-Windows-DriverFrameworks-UserMode/Operational','Microsoft-Windows-Kernel-PnP/Configuration') {
    $f = Join-Path $out ("evt_" + ($n -replace '[\\/ ]','_') + "_$stamp.evtx")
    wevtutil epl $n $f /ow:true 2>&1 | Out-Null
    L "exported $n -> $(Test-Path $f)"
}
L '==== export done ===='
