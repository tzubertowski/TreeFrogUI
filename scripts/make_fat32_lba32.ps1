# Create a FAT32 partition starting at LBA 32 (matching the booting card1 layout),
# sized within the card's REAL ~15.6 GiB flash. Disk 2 only.
param([int]$DiskNumber=2,[long]$PartSectors=31457248,[string]$Label='R36S',
      [string]$Result='D:\r36s-\card2_backup\mk_result.txt')
$ErrorActionPreference='Stop'
function Say($m){ Add-Content $Result $m; Write-Host $m }
Set-Content $Result "make_fat32_lba32 $(Get-Date -Format HH:mm:ss)"
try{
  $disk=Get-Disk -Number $DiskNumber
  if($disk.FriendlyName -notmatch 'CardReader' -or $disk.IsBoot -or $disk.IsSystem){ throw "wrong/boot disk" }
  # 1) wipe
  Set-Disk -Number $DiskNumber -IsOffline $false -EA SilentlyContinue; Start-Sleep 1
  try{ Clear-Disk -Number $DiskNumber -RemoveData -RemoveOEM -Confirm:$false -EA Stop }catch{ "rescan`nselect disk $DiskNumber`nclean`nexit" | diskpart | Out-Null }
  Start-Sleep 1
  Say "disk cleaned"
  # 2) raw-write MBR with one FAT32-LBA partition at LBA 32
  Set-Disk -Number $DiskNumber -IsOffline $true -EA SilentlyContinue
  Set-Disk -Number $DiskNumber -IsReadOnly $false -EA SilentlyContinue
  Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;using Microsoft.Win32.SafeHandles;
public static class RawMk{ [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)]
 public static extern SafeFileHandle CreateFile(string n,uint a,uint s,IntPtr sec,uint d,uint f,IntPtr t);}
'@
  $h=[RawMk]::CreateFile("\\.\PhysicalDrive$DiskNumber",[uint32]3221225472,3,[IntPtr]::Zero,3,[uint32]2147483648,[IntPtr]::Zero)
  if($h.IsInvalid){ throw "CreateFile err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
  $dev=New-Object IO.FileStream($h,[IO.FileAccess]::ReadWrite,1,$false)
  $mbr=New-Object byte[] 512
  $p=446
  $mbr[$p]=0x00; $mbr[$p+1]=0xFE;$mbr[$p+2]=0xFF;$mbr[$p+3]=0xFF; $mbr[$p+4]=0x0C; $mbr[$p+5]=0xFE;$mbr[$p+6]=0xFF;$mbr[$p+7]=0xFF
  [BitConverter]::GetBytes([uint32]32).CopyTo($mbr,$p+8)
  [BitConverter]::GetBytes([uint32]$PartSectors).CopyTo($mbr,$p+12)
  $mbr[510]=0x55; $mbr[511]=0xAA
  $dev.Position=0; $dev.Write($mbr,0,512); $dev.Flush(); $dev.Close(); $h.Close()
  Say "MBR written: part 0x0C start=LBA32 sectors=$PartSectors ($([math]::Round($PartSectors*512/1GB,2)) GiB)"
  # 3) online + rescan so Windows sees the partition
  Set-Disk -Number $DiskNumber -IsOffline $false -EA SilentlyContinue
  "rescan" | diskpart | Out-Null; Start-Sleep 2
  Update-Disk -Number $DiskNumber -EA SilentlyContinue; Start-Sleep 1
  $part=Get-Partition -DiskNumber $DiskNumber -EA SilentlyContinue | Where-Object { $_.Size -gt 1GB } | Select-Object -First 1
  if(-not $part){ throw "partition not seen after rescan" }
  if(-not $part.DriveLetter){
    $used=(Get-Volume).DriveLetter; $free=[char[]](70..90) | Where-Object { $_ -and ($_ -notin $used) } | Select-Object -First 1
    Add-PartitionAccessPath -DiskNumber $DiskNumber -PartitionNumber $part.PartitionNumber -AccessPath "${free}:\" -EA SilentlyContinue
    Start-Sleep 1; $part=Get-Partition -DiskNumber $DiskNumber -PartitionNumber $part.PartitionNumber
  }
  $letter=$part.DriveLetter
  Say "partition at offset=$($part.Offset) (LBA $($part.Offset/512)) letter=$letter"
  # 4) format FAT32
  Format-Volume -DriveLetter $letter -FileSystem FAT32 -NewFileSystemLabel $Label -Confirm:$false -Force | Out-Null
  $v=Get-Volume -DriveLetter $letter
  Say ("FORMATTED {0}: fs={1} size={2:N2}GiB free={3:N2}GiB" -f $letter,$v.FileSystem,($v.Size/1GB),($v.SizeRemaining/1GB))
  Set-Content 'D:\r36s-\card2_backup\mk_DONE' "OK $letter"
}catch{ Say "ERROR: $_"; Set-Content 'D:\r36s-\card2_backup\mk_DONE' "ERR" }
