# Apply card.patch (list of [u64 offset][u32 len][data]) to the SD card raw device,
# with pre-write safety gate and post-write read-back verification.
# READ-ONLY until the gate passes. Full backup exists; any mistake is restorable.
param(
    [int]$DiskNumber = 2,
    [long]$ExpectedSize = 15806234624,
    [string]$Patch  = 'D:\r36s-\dumpcard\card.patch',
    [string]$Backup = 'D:\r36s-\backup\r36s_sd_16gb.img',
    [string]$Result = 'D:\r36s-\dumpcard\apply_result.txt'
)
$ErrorActionPreference = 'Stop'
function Say($m){ $l="[{0}] {1}" -f (Get-Date -Format HH:mm:ss),$m; Add-Content $Result $l; Write-Host $l }
Set-Content $Result "apply_patch start"

try {
    $disk = Get-Disk -Number $DiskNumber
    if ($disk.Size -ne $ExpectedSize -or $disk.FriendlyName -notmatch 'CardReader') { throw "Disk $DiskNumber not the expected card (size=$($disk.Size), name=$($disk.FriendlyName))" }
    if ($disk.IsBoot -or $disk.IsSystem) { throw "refusing: disk is boot/system" }
    Say "target: Disk $DiskNumber $($disk.FriendlyName) $($disk.Size)"

    Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;using Microsoft.Win32.SafeHandles;
public static class Raw{
 [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)]
 public static extern SafeFileHandle CreateFile(string n,uint a,uint s,IntPtr sec,uint d,uint f,IntPtr t);}
'@
    # GENERIC_READ|WRITE=0xC0000000, share R|W=3, OPEN_EXISTING=3, WRITE_THROUGH=0x80000000
    $h = [Raw]::CreateFile("\\.\PhysicalDrive$DiskNumber",[uint32]3221225472,3,[IntPtr]::Zero,3,[uint32]2147483648,[IntPtr]::Zero)
    if ($h.IsInvalid){ throw "CreateFile failed err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
    $dev = New-Object IO.FileStream($h,[IO.FileAccess]::ReadWrite,1,$false)

    # ---- SAFETY GATE: boot sector (offset 16384) must match backup, i.e. our pristine card ----
    $bk = [IO.File]::OpenRead($Backup)
    function ReadAt($stream,[long]$off,[int]$len){ $b=New-Object byte[] $len; $stream.Position=$off; $r=0; while($r -lt $len){$n=$stream.Read($b,$r,$len-$r); if($n-le0){break}; $r+=$n}; return $b }
    $cardBS = ReadAt $dev 16384 512
    $bkBS   = ReadAt $bk  16384 512
    if (-not ([Linq.Enumerable]::SequenceEqual([byte[]]$cardBS,[byte[]]$bkBS))) { throw "SAFETY GATE FAILED: card boot sector != backup; aborting without writing" }
    Say "safety gate OK: card FAT boot sector matches backup"

    # ---- apply patch ----
    $fs = [IO.File]::OpenRead($Patch)
    $hdr = New-Object byte[] 12
    $applied=0; $bytes=0
    while ($true) {
        $got=0; while($got -lt 12){ $n=$fs.Read($hdr,$got,12-$got); if($n-le0){break}; $got+=$n }
        if ($got -eq 0) { break }
        if ($got -lt 12) { throw "truncated patch header" }
        $off=[BitConverter]::ToUInt64($hdr,0); $len=[BitConverter]::ToInt32($hdr,8)
        $data=New-Object byte[] $len; $got=0; while($got -lt $len){ $n=$fs.Read($data,$got,$len-$got); if($n-le0){throw "truncated patch data"}; $got+=$n }
        $dev.Position=[long]$off; $dev.Write($data,0,$len)
        $applied++; $bytes+=$len
    }
    $fs.Close(); $dev.Flush()
    Say "applied $applied blocks, $bytes bytes"

    # ---- read-back verify every block ----
    $fs=[IO.File]::OpenRead($Patch); $ok=0; $bad=0
    while ($true) {
        $got=0; while($got -lt 12){ $n=$fs.Read($hdr,$got,12-$got); if($n-le0){break}; $got+=$n }
        if ($got -eq 0){ break }
        $off=[BitConverter]::ToUInt64($hdr,0); $len=[BitConverter]::ToInt32($hdr,8)
        $data=New-Object byte[] $len; $g=0; while($g -lt $len){ $g+=$fs.Read($data,$g,$len-$g) }
        $rb = ReadAt $dev ([long]$off) $len
        if ([Linq.Enumerable]::SequenceEqual([byte[]]$rb,[byte[]]$data)) { $ok++ } else { $bad++; Say "MISMATCH at $off" }
    }
    $fs.Close(); $dev.Close(); $h.Close(); $bk.Close()
    Say "verify: $ok ok, $bad bad"
    Set-Content 'D:\r36s-\dumpcard\apply_DONE' $(if($bad -eq 0){'OK'}else{"BAD:$bad"})
    Say $(if($bad -eq 0){'RESULT OK'}else{'RESULT MISMATCH'})
} catch {
    Say "ERROR: $_"
    Set-Content 'D:\r36s-\dumpcard\apply_DONE' "ERROR: $_"
}
