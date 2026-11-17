# Decode an USBPcap capture into a readable MTP timeline for the console
# (VID 18D1 / PID 4E22) and pair each PC request with the console's answer.
#   powershell -File usb_mtp_report.ps1 [-Pcap file.pcap]   (default: newest pcaps)
param([string[]]$Pcap)
$tshark = 'C:\Program Files\Wireshark\tshark.exe'
$out = 'D:\r36s-\usbcap'
if (-not $Pcap) {
    $latest = Get-ChildItem $out -Filter 'usb*_*.pcap' | Sort-Object LastWriteTime -Descending
    if (-not $latest) { 'no pcap files'; exit 1 }
    $stamp = ($latest[0].BaseName -split '_', 2)[1]
    $Pcap = ($latest | Where-Object { $_.BaseName -like "*_$stamp" }).FullName
}

$OPS = @{0x1001='GetDeviceInfo';0x1002='OpenSession';0x1003='CloseSession';0x1004='GetStorageIDs';0x1005='GetStorageInfo';
 0x1006='GetNumObjects';0x1007='GetObjectHandles';0x1008='GetObjectInfo';0x1009='GetObject';0x100A='GetThumb';0x100B='DeleteObject';
 0x100C='SendObjectInfo';0x100D='SendObject';0x1014='GetDevicePropDesc';0x1015='GetDevicePropValue';0x1016='SetDevicePropValue';
 0x101B='GetPartialObject';0x9801='GetObjectPropsSupported';0x9802='GetObjectPropDesc';0x9803='GetObjectPropValue';
 0x9804='SetObjectPropValue';0x9805='GetObjectPropList';0x9810='GetObjectReferences';0x9811='SetObjectReferences'}
$RESP = @{0x2001='OK';0x2002='GeneralError';0x2003='SessionNotOpen';0x2005='OperationNotSupported';0x2009='InvalidObjectHandle';
 0x200C='StoreFull';0x2013='StoreNotAvailable';0x2019='DeviceBusy';0x201D='InvalidParameter';0x201E='SessionAlreadyOpen';0x201F='TransactionCancelled'}
$CLASSREQ = @{0x64='CancelRequest';0x65='GetExtendedEventData';0x66='DeviceReset';0x67='GetDeviceStatus'}
function Hex2Bytes($h) { $h = $h -replace '[:\s]',''; if (-not $h) { return ,@() }; $b = New-Object byte[] ($h.Length/2); for ($i=0;$i -lt $b.Length;$i++) { $b[$i] = [Convert]::ToByte($h.Substring(2*$i,2),16) }; ,$b }

foreach ($file in $Pcap) {
    "=================== $file"
    # 1) which bus/address is the console? (device descriptor with 18d1:4e22)
    $dev = & $tshark -r $file -Y 'usb.idVendor == 0x18d1 && usb.idProduct == 0x4e22' -T fields -e usb.bus_id -e usb.device_address 2>$null | Select-Object -Unique
    if (-not $dev) { '  console (18d1:4e22) not seen in this capture'; continue }
    $addrs = $dev | ForEach-Object { ($_ -split "`t")[1] } | Select-Object -Unique
    "  console bus/address: $($dev -join ', ')"
    $flt = '(' + (($addrs | ForEach-Object { "usb.device_address == $_" }) -join ' || ') + ')'
    $rows = & $tshark -r $file -Y $flt -T fields -E separator='|' `
        -e frame.number -e frame.time_epoch -e usb.irp_info.direction -e usb.transfer_type -e usb.endpoint_address `
        -e usb.usbd_status -e usb.data_len -e usb.setup.bRequest -e usb.bmRequestType -e usb.capdata 2>$null
    $t0 = $null; $pending = @{}; $lastCmd = $null
    foreach ($r in $rows) {
        $f = $r -split '\|'
        $t = [double]$f[1]; if ($null -eq $t0) { $t0 = $t }
        $ts = '{0,9:N3}s' -f ($t - $t0)
        $dirToHost = $f[2] -match '^(0x0*)?1$'   # 1/0x01 = completion (PDO->FDO)
        $xfer = $f[3]; $ep = $f[4]; $st = $f[5]; $len = $f[6]
        if ($xfer -eq '0x02' -and $f[7] -and -not $dirToHost) {
            $bt = [Convert]::ToInt32($f[8],16)
            if (($bt -band 0x60) -eq 0x20) {   # class request on control pipe
                $rq = [Convert]::ToInt32($f[7]); $nm = $CLASSREQ[$rq]; if (-not $nm) { $nm = "class req 0x{0:X2}" -f $rq }
                "  $ts  PC -> console   CONTROL $nm"
            }
            continue
        }
        if ($xfer -ne '0x03') { continue }    # bulk only from here
        $epn = [Convert]::ToInt32($ep,16); $isIn = ($epn -band 0x80) -ne 0
        $b = Hex2Bytes $f[9]
        if (-not $isIn -and -not $dirToHost) {          # bulk OUT submit = PC sends
            if ($b.Length -ge 12) {
                $type = [BitConverter]::ToUInt16($b,4); $code = [BitConverter]::ToUInt16($b,6); $tid = [BitConverter]::ToUInt32($b,8)
                if ($type -eq 1) { $nm = $OPS[[int]$code]; if (-not $nm) { $nm = '0x{0:X4}' -f $code }
                    "  $ts  PC -> console   COMMAND  $nm  (tid $tid)"; $pending[$tid] = @{t=$t;n=$nm}; $lastCmd = $tid }
                elseif ($type -eq 2) { "  $ts  PC -> console   data phase {0} bytes (tid $tid)" -f $b.Length }
            } elseif ($b.Length -gt 0) { "  $ts  PC -> console   bulk OUT $($b.Length) bytes" }
        } elseif ($isIn -and $dirToHost) {              # bulk IN completion = console answered
            if ($st -and $st -ne '0x00000000') { "  $ts  console -> PC   bulk IN ended with status $st (no data: cancelled/failed)"; continue }
            if ($b.Length -ge 12) {
                $type = [BitConverter]::ToUInt16($b,4); $code = [BitConverter]::ToUInt16($b,6); $tid = [BitConverter]::ToUInt32($b,8)
                if ($type -eq 3) { $nm = $RESP[[int]$code]; if (-not $nm) { $nm = '0x{0:X4}' -f $code }
                    $lat = ''; if ($pending.ContainsKey($tid)) { $lat = ' after {0:N0} ms for {1}' -f (($t - $pending[$tid].t)*1000), $pending[$tid].n; $pending.Remove($tid) }
                    "  $ts  console -> PC   RESPONSE $nm (tid $tid)$lat" }
                elseif ($type -eq 2) { "  $ts  console -> PC   data {0} bytes (tid $tid)" -f $b.Length }
                elseif ($type -eq 4) { "  $ts  console -> PC   EVENT 0x{0:X4}" -f $code }
            } elseif ($b.Length -gt 0) { "  $ts  console -> PC   bulk IN $($b.Length) bytes" }
        }
    }
    if ($pending.Count) {
        '  ---- requests that NEVER got a response from the console:'
        foreach ($k in $pending.Keys) { '    tid {0}  {1}  sent at {2:N3}s' -f $k, $pending[$k].n, ($pending[$k].t - $t0) }
    } else { '  ---- every PC request got a response' }
}

# Windows MTP driver log (exported by usb_capture.ps1)
$ev = Get-ChildItem $out -Filter 'evt_*MTPClassDriver*.evtx' | Sort-Object LastWriteTime -Descending | Select-Object -First 2
foreach ($e in $ev) {
    "=================== $($e.Name)"
    Get-WinEvent -Path $e.FullName -Oldest -ErrorAction SilentlyContinue | Select-Object -Last 80 |
        ForEach-Object { '  {0:HH:mm:ss.fff} [{1}] {2}' -f $_.TimeCreated, $_.Id, (($_.Message -replace '\s+',' ') -replace '^(.{0,200}).*','$1') }
}
