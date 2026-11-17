# Fake-capacity test for \\.\PhysicalDrive2 using raw Win32 I/O.
# Writes offset-encoded 4K signatures across the claimed range, then re-reads.
# Mismatches past the real flash reveal fake capacity. Disk should be OFFLINE.
param([int]$DiskNumber=2,[long]$Size=62914560000,[string]$Result='D:\r36s-\card2_backup\capacity_result.txt')
$ErrorActionPreference='Stop'
function Say($m){ Add-Content $Result $m; Write-Host $m }
Set-Content $Result "capacity test start $(Get-Date -Format HH:mm:ss)"
try{
  $disk=Get-Disk -Number $DiskNumber
  if($disk.Size -ne $Size -or $disk.FriendlyName -notmatch 'CardReader'){ throw "disk mismatch size=$($disk.Size) name=$($disk.FriendlyName)" }
  if($disk.IsBoot -or $disk.IsSystem){ throw "refusing boot/system disk" }
  try{ Set-Disk -Number $DiskNumber -IsOffline $true -EA SilentlyContinue }catch{}
  try{ Set-Disk -Number $DiskNumber -IsReadOnly $false -EA SilentlyContinue }catch{}

  Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;using Microsoft.Win32.SafeHandles;
public static class RawC{
 [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)]
 public static extern SafeFileHandle CreateFile(string n,uint a,uint s,IntPtr sec,uint d,uint f,IntPtr t);}
'@
  function Open(){
    # GENERIC_READ|WRITE=0xC0000000, share R|W=3, OPEN_EXISTING=3, WRITE_THROUGH=0x80000000
    $h=[RawC]::CreateFile("\\.\PhysicalDrive$DiskNumber",[uint32]3221225472,3,[IntPtr]::Zero,3,[uint32]2147483648,[IntPtr]::Zero)
    if($h.IsInvalid){ throw "CreateFile err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
    return (New-Object IO.FileStream($h,[IO.FileAccess]::ReadWrite,1,$false))
  }
  $BS=4096
  $magic=[Text.Encoding]::ASCII.GetBytes('FAKECAP1')
  $rng=New-Object Random
  $runid=[uint32]($rng.Next() -band 0x7fffffff)
  # probe offsets (4K aligned), skip first 1 GiB (FS metadata), scan high densely
  $gib=1073741824L
  $offs=New-Object System.Collections.Generic.List[long]
  foreach($g in 1,2,4,8,12,14,15,16){ $offs.Add([long]$g*$gib) }
  $g=16.0
  while($g -lt ($Size/$gib - 0.1)){ $g+=2.0; $offs.Add([long]($g*$gib)) }
  $offs.Add($Size-$BS)
  $offs=$offs | ForEach-Object { $_ - ($_ % $BS) } | Sort-Object -Unique | Where-Object { $_ -gt 0 -and $_ -le ($Size-$BS) }

  function Blk([long]$off){
    $b=New-Object byte[] $BS
    $rec=New-Object byte[] 20
    [Array]::Copy($magic,0,$rec,0,8)
    [BitConverter]::GetBytes([int64]$off).CopyTo($rec,8)
    [BitConverter]::GetBytes([uint32]$runid).CopyTo($rec,16)
    for($p=0;$p -lt $BS;$p+=20){ [Array]::Copy($rec,0,$b,$p,[Math]::Min(20,$BS-$p)) }
    return $b
  }
  Say ("claimed {0} bytes ({1:N2} GiB), runid={2}, {3} probes" -f $Size,($Size/$gib),$runid,$offs.Count)
  $dev=Open
  foreach($o in $offs){ $dev.Position=$o; $dev.Write((Blk $o),0,$BS) }
  $dev.Flush(); $dev.Close()
  Say "written; reopening to read back"
  $dev=Open
  $good=@(); $bad=@()
  foreach($o in $offs){
    $buf=New-Object byte[] $BS; $dev.Position=$o; $r=0; while($r -lt $BS){ $n=$dev.Read($buf,$r,$BS-$r); if($n-le0){break}; $r+=$n }
    $okMagic = (Compare-Object $buf[0..7] $magic -SyncWindow 0) -eq $null
    $gotOff = if($okMagic){ [BitConverter]::ToInt64($buf,8) } else { -1 }
    $gotRun = if($okMagic){ [BitConverter]::ToUInt32($buf,16) } else { 0 }
    if($okMagic -and $gotOff -eq $o -and $gotRun -eq $runid){ $good+=$o }
    else {
      $desc = if($okMagic){ "aliased->{0:N1}GiB run={1}" -f ($gotOff/$gib),$gotRun } else { "garbage/zero" }
      $bad+=,@($o,$desc)
    }
  }
  $dev.Close()
  Say ("GOOD {0}/{1}   BAD {2}" -f $good.Count,$offs.Count,$bad.Count)
  foreach($b in $bad){ Say ("  BAD {0:N2} GiB : {1}" -f ($b[0]/$gib),$b[1]) }
  if($good.Count){ Say ("highest VERIFIED: {0:N2} GiB" -f (($good|Measure-Object -Max).Maximum/$gib)) }
  if($bad.Count){
    $fb=($bad|ForEach-Object{$_[0]}|Measure-Object -Min).Minimum
    Say ("first BAD: {0:N2} GiB" -f ($fb/$gib))
    Say ("VERDICT: FAKE capacity. Real flash ~<= {0:N1} GiB (claimed {1:N1} GiB)" -f ($fb/$gib),($Size/$gib))
  } else { Say "VERDICT: GENUINE (no wraparound at probe points)" }
  Set-Content 'D:\r36s-\card2_backup\capacity_DONE' 'OK'
}catch{ Say "ERROR: $_"; Set-Content 'D:\r36s-\card2_backup\capacity_DONE' "ERR" }
