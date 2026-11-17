# RESTORE a raw image back onto an SD card. DESTROYS everything on the target disk.
# Run as Administrator:  powershell -ExecutionPolicy Bypass -File restore_sd.ps1 -DiskNumber N
param(
    [Parameter(Mandatory)][int]$DiskNumber,
    [string]$Image = 'D:\r36s-\backup\r36s_sd_16gb.img'
)
$ErrorActionPreference = 'Stop'
$img = Get-Item $Image
$disk = Get-Disk -Number $DiskNumber
if ($disk.IsBoot -or $disk.IsSystem -or $disk.BusType -notin @('SD','USB','SCSI','MMC')) { throw "Disk $DiskNumber looks like a system/internal disk. Refusing." }
if ($disk.Size -lt $img.Length) { throw "Target ($($disk.Size)) is smaller than the image ($($img.Length))." }

$expected = (Get-Content "$Image.sha256").Split(' ')[0]
Write-Host "Checking image SHA256..."
if ((Get-FileHash -Algorithm SHA256 $Image).Hash.ToLower() -ne $expected) { throw "Image hash does not match $Image.sha256 - image is damaged." }

Write-Host "TARGET: Disk $DiskNumber  $($disk.FriendlyName)  $($disk.Size) bytes" -ForegroundColor Yellow
if ((Read-Host "Type the disk number again to ERASE it and write the image") -ne "$DiskNumber") { throw "Cancelled." }

# Dismount volumes and take disk offline so Windows does not interfere
Get-Partition -DiskNumber $DiskNumber -ErrorAction SilentlyContinue | Where-Object DriveLetter | ForEach-Object {
    Remove-PartitionAccessPath -DiskNumber $DiskNumber -PartitionNumber $_.PartitionNumber -AccessPath "$($_.DriveLetter):\" }
Set-Disk -Number $DiskNumber -IsOffline $true
Set-Disk -Number $DiskNumber -IsReadOnly $false

Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices; using Microsoft.Win32.SafeHandles;
public static class RawDiskW {
  [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
  public static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr sec, uint disp, uint flags, IntPtr tmpl);
}
'@
# GENERIC_READ|GENERIC_WRITE, share rw, OPEN_EXISTING, FILE_FLAG_WRITE_THROUGH
$h = [RawDiskW]::CreateFile("\\.\PhysicalDrive$DiskNumber", [uint32]3221225472, 3, [IntPtr]::Zero, 3, [uint32]2147483648, [IntPtr]::Zero)
if ($h.IsInvalid) { throw "CreateFile failed, Win32 error $([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
$dst = New-Object IO.FileStream($h, [IO.FileAccess]::ReadWrite, 1, $false)
$src = [IO.File]::OpenRead($Image)
$buf = New-Object byte[] 4MB; $pos = [long]0; $total = $src.Length
while (($n = $src.Read($buf, 0, $buf.Length)) -gt 0) {
    $dst.Write($buf, 0, $n); $pos += $n
    Write-Progress -Activity "Writing image" -PercentComplete (100.0 * $pos / $total) -Status ("{0:N0} / {1:N0} MB" -f ($pos/1MB), ($total/1MB))
}
$dst.Flush(); $src.Close()

Write-Host "Verifying written data..."
$dst.Position = 0; $sha = [Security.Cryptography.SHA256]::Create(); $pos = [long]0
while ($pos -lt $total) {
    $len = [int][Math]::Min([long]$buf.Length, $total - $pos); $got = 0
    while ($got -lt $len) { $got += $dst.Read($buf, $got, $len - $got) }
    [void]$sha.TransformBlock($buf, 0, $len, $null, 0); $pos += $len
}
[void]$sha.TransformFinalBlock($buf, 0, 0); $dst.Close(); $h.Close()
$got = ([BitConverter]::ToString($sha.Hash) -replace '-', '').ToLower()
Set-Disk -Number $DiskNumber -IsOffline $false
if ($got -eq $expected) { Write-Host "RESTORE OK, SHA256 matches." -ForegroundColor Green } else { Write-Host "VERIFY FAILED: $got" -ForegroundColor Red }
