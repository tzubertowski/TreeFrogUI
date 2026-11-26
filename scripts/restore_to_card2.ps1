# Write the console-native stock backup image onto card2 (Disk 2), then verify.
# Image (14.72 GiB) fits within card2's REAL ~15.6 GiB flash. Disk must be raw/offline.
param([int]$DiskNumber=2,[string]$Image='D:\r36s-\backup\r36s_sd_16gb.img',
      [string]$Result='D:\r36s-\card2_backup\restore_result.txt')
$ErrorActionPreference='Stop'
function Say($m){ $l="[{0}] {1}" -f (Get-Date -Format HH:mm:ss),$m; Add-Content $Result $l; Write-Host $l }
Set-Content $Result "restore_to_card2 start"
try{
  $disk=Get-Disk -Number $DiskNumber
  if($disk.FriendlyName -notmatch 'CardReader' -or $disk.IsBoot -or $disk.IsSystem){ throw "wrong/boot disk" }
  $img=Get-Item $Image; $len=$img.Length
  if($len -gt $disk.Size){ throw "image larger than disk" }
  if($len/1GB -gt 15.3){ throw ("image {0:N2} GiB exceeds safe real capacity" -f ($len/1GB)) }
  Say ("target Disk $DiskNumber $($disk.FriendlyName); image $len bytes ({0:N2} GiB)" -f ($len/1GB))
  # wipe partition table so Windows stops protecting the region, then offline for raw write
  Set-Disk -Number $DiskNumber -IsOffline $false -EA SilentlyContinue; Start-Sleep 1
  try { Clear-Disk -Number $DiskNumber -RemoveData -RemoveOEM -Confirm:$false -EA Stop }
  catch { "rescan`nselect disk $DiskNumber`nclean`nexit" | diskpart | Out-Null }
  Start-Sleep 1
  Set-Disk -Number $DiskNumber -IsOffline $true -EA SilentlyContinue
  Set-Disk -Number $DiskNumber -IsReadOnly $false -EA SilentlyContinue
  Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;using Microsoft.Win32.SafeHandles;
public static class RawR{ [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)]
 public static extern SafeFileHandle CreateFile(string n,uint a,uint s,IntPtr sec,uint d,uint f,IntPtr t);}
'@
  function OpenDev(){ $h=[RawR]::CreateFile("\\.\PhysicalDrive$DiskNumber",[uint32]3221225472,3,[IntPtr]::Zero,3,[uint32]2147483648,[IntPtr]::Zero); if($h.IsInvalid){throw "CreateFile err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}; New-Object IO.FileStream($h,[IO.FileAccess]::ReadWrite,1048576,$false) }
  $expected=((Get-Content "$Image.sha256") -split ' ')[0]
  Say "expected image sha256=$expected"
  # WRITE
  $src=[IO.File]::OpenRead($Image); $dev=OpenDev
  $sha=[Security.Cryptography.SHA256]::Create(); $buf=New-Object byte[] (4*1024*1024); $pos=[long]0; $sw=[Diagnostics.Stopwatch]::StartNew(); $last=0
  while($pos -lt $len){
    $n=$src.Read($buf,0,[Math]::Min([long]$buf.Length,$len-$pos)); if($n -le 0){break}
    $dev.Write($buf,0,$n); [void]$sha.TransformBlock($buf,0,$n,$null,0); $pos+=$n
    if($sw.Elapsed.TotalSeconds-$last -ge 15){ $last=$sw.Elapsed.TotalSeconds; Set-Content 'D:\r36s-\card2_backup\restore_progress.txt' ("{0:N1}% {1:N0}/{2:N0} MB {3:N1} MB/s" -f (100*$pos/$len),($pos/1MB),($len/1MB),(($pos/1MB)/$sw.Elapsed.TotalSeconds)) }
  }
  [void]$sha.TransformFinalBlock($buf,0,0); $wsha=([BitConverter]::ToString($sha.Hash) -replace '-','').ToLower()
  $dev.Flush(); $dev.Close(); $src.Close()
  Say ("written {0} bytes in {1:N0}s; write-stream sha256={2} {3}" -f $pos,$sw.Elapsed.TotalSeconds,$wsha,$(if($wsha -eq $expected){'MATCH'}else{'DIFF'}))
  # VERIFY read-back
  Say "verifying (reading back)..."
  $dev=OpenDev; $sha=[Security.Cryptography.SHA256]::Create(); $pos=[long]0
  while($pos -lt $len){ $want=[int][Math]::Min([long]$buf.Length,$len-$pos); $got=0; while($got -lt $want){ $r=$dev.Read($buf,$got,$want-$got); if($r -le 0){break}; $got+=$r }; [void]$sha.TransformBlock($buf,0,$got,$null,0); $pos+=$got; if($got -lt $want){break} }
  [void]$sha.TransformFinalBlock($buf,0,0); $rsha=([BitConverter]::ToString($sha.Hash) -replace '-','').ToLower()
  $dev.Close()
  Say ("read-back sha256={0} {1}" -f $rsha,$(if($rsha -eq $expected){'VERIFIED OK'}else{'MISMATCH'}))
  Set-Content 'D:\r36s-\card2_backup\restore_DONE' $(if($rsha -eq $expected){'OK'}else{'MISMATCH'})
}catch{ Say "ERROR: $_"; Set-Content 'D:\r36s-\card2_backup\restore_DONE' "ERR: $_" }
