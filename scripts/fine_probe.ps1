# Fine probe to pin the real flash boundary (disk must be raw/offline).
param([int]$DiskNumber=2,[string]$Result='D:\r36s-\card2_backup\fine_result.txt')
$ErrorActionPreference='Stop'
function Say($m){ Add-Content $Result $m; Write-Host $m }
Set-Content $Result "fine probe $(Get-Date -Format HH:mm:ss)"
try{
  Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;using Microsoft.Win32.SafeHandles;
public static class RawF{
 [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)]
 public static extern SafeFileHandle CreateFile(string n,uint a,uint s,IntPtr sec,uint d,uint f,IntPtr t);}
'@
  function Open(){ $h=[RawF]::CreateFile("\\.\PhysicalDrive$DiskNumber",[uint32]3221225472,3,[IntPtr]::Zero,3,[uint32]2147483648,[IntPtr]::Zero); if($h.IsInvalid){throw "err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}; New-Object IO.FileStream($h,[IO.FileAccess]::ReadWrite,1,$false) }
  $BS=4096; $gib=1073741824L; $magic=[Text.Encoding]::ASCII.GetBytes('FINEPRB1'); $runid=[uint32]((New-Object Random).Next() -band 0x7fffffff)
  $offs=@(); $m=14.5; while($m -le 16.25){ $offs+=[long]([Math]::Floor($m*$gib/$BS)*$BS); $m+=0.1 }
  function Blk([long]$o){ $b=New-Object byte[] $BS; $r=New-Object byte[] 20; [Array]::Copy($magic,0,$r,0,8); [BitConverter]::GetBytes([int64]$o).CopyTo($r,8); [BitConverter]::GetBytes([uint32]$runid).CopyTo($r,16); for($p=0;$p -lt $BS;$p+=20){[Array]::Copy($r,0,$b,$p,[Math]::Min(20,$BS-$p))}; $b }
  $dev=Open; foreach($o in $offs){ $dev.Position=$o; $dev.Write((Blk $o),0,$BS) }; $dev.Flush(); $dev.Close()
  $dev=Open; $lastGood=0L
  foreach($o in $offs){ $buf=New-Object byte[] $BS; $dev.Position=$o; $x=0; while($x -lt $BS){$n=$dev.Read($buf,$x,$BS-$x); if($n-le0){break}; $x+=$n}
    $ok=((Compare-Object $buf[0..7] $magic -SyncWindow 0) -eq $null) -and ([BitConverter]::ToInt64($buf,8) -eq $o) -and ([BitConverter]::ToUInt32($buf,16) -eq $runid)
    Say ("{0:N2} GiB ({1} bytes): {2}" -f ($o/$gib),$o,$(if($ok){'OK'}else{'BAD'}))
    if($ok){ $lastGood=$o }
  }
  $dev.Close()
  Say ("REAL CAPACITY boundary: last good = {0:N3} GiB = {1} bytes" -f ($lastGood/$gib),$lastGood)
  Set-Content 'D:\r36s-\card2_backup\fine_DONE' "$lastGood"
}catch{ Say "ERROR: $_"; Set-Content 'D:\r36s-\card2_backup\fine_DONE' "ERR" }
