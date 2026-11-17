# Elevated one-time setup for deep USB/MTP tracing on the PC.
# 1) installs USBPcap (raw USB packet capture, used with Wireshark/tshark)
# 2) enables Windows' MTP / WPD / WUDF driver logs
# Writes a report to D:\r36s-\usbcap\setup.log
$ErrorActionPreference = 'Continue'
$out = 'D:\r36s-\usbcap'
New-Item -ItemType Directory -Force $out | Out-Null
$log = Join-Path $out 'setup.log'
function L($m) { "$(Get-Date -Format 'HH:mm:ss') $m" | Tee-Object -FilePath $log -Append }

L '==== usb_trace_setup start ===='
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
L "admin=$isAdmin"

# --- 1. USBPcap ---
$cmd = 'C:\Program Files\USBPcap\USBPcapCMD.exe'
if (-not (Test-Path $cmd)) {
    L 'installing USBPcap via winget (desowin.USBPcap)...'
    $r = winget install --id desowin.USBPcap --exact --source winget --silent --accept-package-agreements --accept-source-agreements 2>&1
    $r | Where-Object { $_ -match '\w{3,}' } | ForEach-Object { L "  winget: $_" }
}
L "USBPcapCMD present: $(Test-Path $cmd)"
$svc = Get-Service USBPcap -ErrorAction SilentlyContinue
L "USBPcap service: $($svc.Status)"

# --- 2. Windows MTP / WPD / WUDF logs ---
$logs = @(
  'Microsoft-Windows-WPD-MTPClassDriver/Operational',
  'Microsoft-Windows-WPD-MTPClassDriver/Analytic',
  'Microsoft-Windows-WPD-MTPUS/Analytic',
  'Microsoft-Windows-WPD-API/Analytic',
  'Microsoft-Windows-WPD-CompositeClassDriver/Operational',
  'Microsoft-Windows-WPD-CompositeClassDriver/Analytic',
  'Microsoft-Windows-WPD-ClassInstaller/Operational',
  'Microsoft-Windows-DriverFrameworks-UserMode/Operational'
)
foreach ($n in $logs) {
    # analytic/debug logs must be disabled before their size/retention can change
    wevtutil sl $n /e:false /q:true 2>$null | Out-Null
    wevtutil sl $n /ms:52428800 /q:true 2>&1 | Out-Null
    $o = wevtutil sl $n /e:true /q:true 2>&1
    $en = (wevtutil gl $n 2>&1 | Select-String '^enabled:').Line
    L "log $n -> $en $o"
}
L '==== usb_trace_setup done ===='
