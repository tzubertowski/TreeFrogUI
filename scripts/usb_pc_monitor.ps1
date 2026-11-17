# PC-side USB monitor for the R36S USB-transfer tests.
# Polls every second and logs, with timestamps, every change in:
#   - removable/USB disk volumes (drive letters)  -> and LISTS the files on them
#   - USB / WPD / PortableDevice / DiskDrive PnP devices (incl. our gadget
#     VID/PIDs and any "device malfunctioned" / Unknown USB Device state)
# So even a device that appears for only a moment is captured here.
$ErrorActionPreference = 'SilentlyContinue'
$log  = 'D:\r36s-\usb_pc_monitor.log'
$stop = 'D:\r36s-\usb_pc_monitor.stop'
$maxMinutes = 720

$enc = New-Object System.Text.UTF8Encoding($false)
function W($m){
  $t = (Get-Date).ToString('HH:mm:ss.fff')
  $line = "$t  $m`r`n"
  [System.IO.File]::AppendAllText($log, $line, $enc)
}

# our gadget identities (from usb_diag.sh)
$known = @{
  'VID_1209&PID_3000' = 'TreeFrogUI MASS-STORAGE gadget'
  'VID_18D1&PID_4E22' = 'TreeFrogUI MTP gadget'
}
function Annotate($id){
  foreach($k in $known.Keys){ if($id -match $k){ return " <== $($known[$k])" } }
  if($id -match 'VID_1209' -or $id -match 'VID_18D1'){ return ' <== TreeFrogUI gadget' }
  return ''
}

function Get-VolMap {
  $m = @{}
  Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=2 OR DriveType=3' |
    ForEach-Object {
      $dt = if($_.DriveType -eq 2){'removable'}else{'fixed'}
      $m[$_.DeviceID] = ('{0}|{1}|{2}|{3}' -f $dt, $_.VolumeName, $_.Size, $_.FileSystem)
    }
  return $m
}

function Get-PnpMap {
  $m = @{}
  Get-PnpDevice -PresentOnly |
    Where-Object { $_.InstanceId -match 'USB\\' -or $_.Class -in @('USB','WPD','DiskDrive','PortableDevice') } |
    ForEach-Object {
      $m[$_.InstanceId] = ('{0}|{1}|{2}' -f $_.Class, $_.Status, $_.FriendlyName)
    }
  return $m
}

function ListDrive($id){
  $root = $id + '\'
  try {
    $items = Get-ChildItem -LiteralPath $root -Force -ErrorAction Stop
    if(-not $items){ W ("    [$id] is EMPTY (no files/folders at root)"); return }
    $n = ($items | Measure-Object).Count
    W ("    [$id] root has $n entries:")
    $items | Select-Object -First 60 | ForEach-Object {
      $tag = if($_.PSIsContainer){'<DIR> '}else{''}
      W ("      $tag$($_.Name)")
    }
    if($n -gt 60){ W ("      ... (+$($n-60) more)") }
  } catch {
    W ("    [$id] could NOT be read: $($_.Exception.Message)")
  }
}

W '================ USB PC monitor START ================'
W "watching every 1s; drop file $stop to end, or auto-stops after $maxMinutes min"
$vol  = Get-VolMap
$pnp  = Get-PnpMap
W ("baseline drives: " + (($vol.Keys | Sort-Object) -join ', '))
W ("baseline USB/WPD devices: " + $pnp.Count)
$pnp.GetEnumerator() | Sort-Object Name | ForEach-Object {
  $a = Annotate $_.Key
  if($a){ W ("  baseline* $($_.Value)  [$($_.Key)]$a") }
}

$deadline = (Get-Date).AddMinutes($maxMinutes)
while($true){
  if(Test-Path $stop){ W 'STOP file found - exiting'; Remove-Item $stop -Force; break }
  if((Get-Date) -gt $deadline){ W 'max runtime reached - exiting'; break }
  Start-Sleep -Milliseconds 1000

  $v2 = Get-VolMap
  foreach($k in $v2.Keys){ if(-not $vol.ContainsKey($k)){ W ("DRIVE + $k  ($($v2[$k]))"); ListDrive $k } }
  foreach($k in $v2.Keys){ if($vol.ContainsKey($k) -and $vol[$k] -ne $v2[$k]){ W ("DRIVE ~ $k  ($($vol[$k]))  ->  ($($v2[$k]))"); ListDrive $k } }
  foreach($k in $vol.Keys){ if(-not $v2.ContainsKey($k)){ W ("DRIVE - $k  (removed)") } }
  $vol = $v2

  $p2 = Get-PnpMap
  foreach($k in $p2.Keys){
    if(-not $pnp.ContainsKey($k)){ W ("DEV   + $($p2[$k])  [$k]" + (Annotate $k)) }
    elseif($pnp[$k] -ne $p2[$k]){ W ("DEV   ~ $($pnp[$k])  ->  $($p2[$k])  [$k]" + (Annotate $k)) }
  }
  foreach($k in $pnp.Keys){ if(-not $p2.ContainsKey($k)){ W ("DEV   - $($pnp[$k])  [$k]" + (Annotate $k)) } }
  $pnp = $p2
}
W '================ USB PC monitor END ================'
