# Temporarily write a valid MBR to the card so Windows can mount the FAT32 at LBA 32,
# or restore the original (console) sector 0 from the backup image.
#   mbr_tool.ps1 fix       -> back up sector0, write valid MBR, rescan, mount, print letter
#   mbr_tool.ps1 restore   -> write backup's original sector 0 back to the card
param(
    [Parameter(Mandatory)][ValidateSet('fix','restore')][string]$Mode,
    [int]$DiskNumber = 2,
    [long]$ExpectedSize = 15806234624,
    [string]$Backup = 'D:\r36s-\backup\r36s_sd_16gb.img',
    [string]$SavedSector0 = 'D:\r36s-\dumpcard\card_sector0_orig.bin',
    [string]$Result = 'D:\r36s-\dumpcard\mbr_result.txt'
)
$ErrorActionPreference='Stop'
function Say($m){ $l="[{0}] {1}" -f (Get-Date -Format HH:mm:ss),$m; Add-Content $Result $l; Write-Host $l }
Set-Content $Result "mbr_tool $Mode"
try {
    $disk=Get-Disk -Number $DiskNumber
    if($disk.Size -ne $ExpectedSize -or $disk.FriendlyName -notmatch 'CardReader'){ throw "Disk $DiskNumber not expected card (size=$($disk.Size), $($disk.FriendlyName))" }
    if($disk.IsBoot -or $disk.IsSystem){ throw "refusing boot/system disk" }

    Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;using Microsoft.Win32.SafeHandles;
public static class RawM{
 [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)]
 public static extern SafeFileHandle CreateFile(string n,uint a,uint s,IntPtr sec,uint d,uint f,IntPtr t);}
'@
    $h=[RawM]::CreateFile("\\.\PhysicalDrive$DiskNumber",[uint32]3221225472,3,[IntPtr]::Zero,3,[uint32]2147483648,[IntPtr]::Zero)
    if($h.IsInvalid){ throw "CreateFile err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
    $dev=New-Object IO.FileStream($h,[IO.FileAccess]::ReadWrite,1,$false)
    $sec=New-Object byte[] 512

    if($Mode -eq 'fix'){
        # read & save current sector 0
        $dev.Position=0; [void]$dev.Read($sec,0,512)
        [IO.File]::WriteAllBytes($SavedSector0,$sec)
        Say "saved current sector0 -> $SavedSector0 (sig $('{0:X2}{1:X2}' -f $sec[510],$sec[511]))"
        # build a fresh MBR: one FAT32-LBA partition, start LBA 32, size = FAT32 total sectors
        $mbr=New-Object byte[] 512
        $startLBA=32; $numSectors=30719744   # from FAT32 BSD (tot32) seen in image
        $p=446
        $mbr[$p+0]=0x00                      # not bootable
        $mbr[$p+1]=0xFE;$mbr[$p+2]=0xFF;$mbr[$p+3]=0xFF   # start CHS filler
        $mbr[$p+4]=0x0C                      # type FAT32 LBA
        $mbr[$p+5]=0xFE;$mbr[$p+6]=0xFF;$mbr[$p+7]=0xFF   # end CHS filler
        [BitConverter]::GetBytes([uint32]$startLBA).CopyTo($mbr,$p+8)
        [BitConverter]::GetBytes([uint32]$numSectors).CopyTo($mbr,$p+12)
        $mbr[510]=0x55;$mbr[511]=0xAA
        $dev.Position=0; $dev.Write($mbr,0,512); $dev.Flush()
        Say "wrote valid MBR (part type 0x0C start=$startLBA size=$numSectors)"
        $dev.Close(); $h.Close()
        # rescan so Windows sees the partition
        Say "rescanning..."
        "rescan" | diskpart | Out-Null
        Start-Sleep 2
        try { Set-Disk -Number $DiskNumber -IsOffline $false -ErrorAction SilentlyContinue } catch {}
        try { Set-Disk -Number $DiskNumber -IsReadOnly $false -ErrorAction SilentlyContinue } catch {}
        Update-Disk -Number $DiskNumber -ErrorAction SilentlyContinue
        Start-Sleep 2
        $part=Get-Partition -DiskNumber $DiskNumber -ErrorAction SilentlyContinue | Where-Object { $_.Size -gt 1GB } | Select-Object -First 1
        if(-not $part){ throw "no partition appeared after rescan" }
        if(-not $part.DriveLetter){
            $used=(Get-Volume).DriveLetter
            $free=[char[]](70..90) | Where-Object { $_ -notin $used } | Select-Object -First 1
            Add-PartitionAccessPath -DiskNumber $DiskNumber -PartitionNumber $part.PartitionNumber -AccessPath "${free}:\"
            Start-Sleep 1; $part=Get-Partition -DiskNumber $DiskNumber -PartitionNumber $part.PartitionNumber
        }
        $letter=(Get-Partition -DiskNumber $DiskNumber -PartitionNumber $part.PartitionNumber).DriveLetter
        $vol=Get-Volume -DriveLetter $letter -ErrorAction SilentlyContinue
        Say "MOUNTED at ${letter}: fs=$($vol.FileSystem) free=$([math]::Round($vol.SizeRemaining/1GB,2))GB"
        Set-Content 'D:\r36s-\dumpcard\mbr_DONE' "FIXED ${letter}"
    } else {
        # restore original console sector 0 from backup
        $bk=[IO.File]::OpenRead($Backup); $orig=New-Object byte[] 512; [void]$bk.Read($orig,0,512); $bk.Close()
        # dismount any mounted volume on this disk first
        $dev.Position=0; $dev.Write($orig,0,512); $dev.Flush(); $dev.Close(); $h.Close()
        Say "restored original sector0 from backup (sig $('{0:X2}{1:X2}' -f $orig[510],$orig[511]))"
        "rescan" | diskpart | Out-Null
        Set-Content 'D:\r36s-\dumpcard\mbr_DONE' "RESTORED"
    }
    Say "OK"
} catch {
    Say "ERROR: $_"; Set-Content 'D:\r36s-\dumpcard\mbr_DONE' "ERROR: $_"
}
