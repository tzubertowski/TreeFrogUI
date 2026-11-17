# Raw READ-ONLY image of an SD card (\\.\PhysicalDriveN) to a file + SHA256.
# Unreadable sectors are zero-filled and logged (bad_sectors.txt).
param(
    [int]$DiskNumber = 2,
    [long]$ExpectedSize = 15806234624,
    [string]$OutFile = 'D:\r36s-\backup\r36s_sd_16gb.img'
)
$ErrorActionPreference = 'Stop'
$outDir = Split-Path $OutFile
New-Item -ItemType Directory -Force $outDir | Out-Null
$log = Join-Path $outDir 'backup_log.txt'
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; Add-Content -Path $log -Value $l -Encoding utf8; Write-Host $l }

try {
    $disk = Get-Disk -Number $DiskNumber
    if ($disk.Size -ne $ExpectedSize -or $disk.FriendlyName -notmatch 'CardReader') {
        throw "Disk $DiskNumber is not the expected card (size=$($disk.Size), name=$($disk.FriendlyName)). Aborting."
    }
    Log "Disk $DiskNumber : $($disk.FriendlyName) $($disk.Size) bytes, $($disk.PartitionStyle)"

    Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices; using Microsoft.Win32.SafeHandles;
public static class RawDisk {
  [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
  public static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr sec, uint disp, uint flags, IntPtr tmpl);
}
'@
    # GENERIC_READ only, share read|write, OPEN_EXISTING
    $h = [RawDisk]::CreateFile("\\.\PhysicalDrive$DiskNumber", [uint32]2147483648, 3, [IntPtr]::Zero, 3, 0, [IntPtr]::Zero)
    if ($h.IsInvalid) { throw "CreateFile failed, Win32 error $([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
    $src = New-Object IO.FileStream($h, [IO.FileAccess]::Read, 1, $false)
    $dst = New-Object IO.FileStream($OutFile, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::Read, 1048576)
    $sha = [Security.Cryptography.SHA256]::Create()

    $total = $ExpectedSize; $chunk = 4MB; $sector = 512
    $buf = New-Object byte[] $chunk
    $pos = [long]0; $bad = New-Object Collections.Generic.List[long]
    $sw = [Diagnostics.Stopwatch]::StartNew(); $lastReport = 0
    while ($pos -lt $total) {
        $len = [int][Math]::Min([long]$chunk, $total - $pos)
        $ok = $true
        try {
            $src.Position = $pos
            $got = 0
            while ($got -lt $len) { $n = $src.Read($buf, $got, $len - $got); if ($n -le 0) { throw "short read" }; $got += $n }
        } catch { $ok = $false }
        if (-not $ok) {
            Log "Read error in chunk at $pos, retrying per sector"
            for ($o = 0; $o -lt $len; $o += $sector) {
                $read = $false
                for ($try = 0; $try -lt 3 -and -not $read; $try++) {
                    try { $src.Position = $pos + $o; $n = $src.Read($buf, $o, $sector); if ($n -eq $sector) { $read = $true } } catch {}
                }
                if (-not $read) { [Array]::Clear($buf, $o, $sector); $bad.Add(($pos + $o) / $sector) }
            }
        }
        $dst.Write($buf, 0, $len)
        [void]$sha.TransformBlock($buf, 0, $len, $null, 0)
        $pos += $len
        if ($sw.Elapsed.TotalSeconds - $lastReport -ge 5) {
            $lastReport = $sw.Elapsed.TotalSeconds
            $mbs = ($pos / 1MB) / $sw.Elapsed.TotalSeconds
            $eta = [TimeSpan]::FromSeconds(($total - $pos) / 1MB / [Math]::Max($mbs, 0.01))
            Set-Content -Path (Join-Path $outDir 'progress.txt') -Value ("{0:N1}% {1:N0}/{2:N0} MB {3:N1} MB/s ETA {4:hh\:mm\:ss} bad={5}" -f (100.0*$pos/$total), ($pos/1MB), ($total/1MB), $mbs, $eta, $bad.Count)
        }
    }
    [void]$sha.TransformFinalBlock($buf, 0, 0)
    $hash = ([BitConverter]::ToString($sha.Hash) -replace '-', '').ToLower()
    $dst.Flush(); $dst.Close(); $src.Close(); $h.Close()
    Log ("Copied {0} bytes in {1:N0} s, unreadable sectors: {2}" -f $pos, $sw.Elapsed.TotalSeconds, $bad.Count)
    if ($bad.Count) { $bad | Set-Content (Join-Path $outDir 'bad_sectors.txt') }
    Log "SHA256 (card stream): $hash"

    Log "Verifying image file hash..."
    $fileHash = (Get-FileHash -Algorithm SHA256 $OutFile).Hash.ToLower()
    Log "SHA256 (image file):  $fileHash"
    $match = ($fileHash -eq $hash) -and ((Get-Item $OutFile).Length -eq $total)
    "$hash *$(Split-Path $OutFile -Leaf)" | Set-Content -Encoding ascii "$OutFile.sha256"
    Log ("VERIFY: " + $(if ($match) { 'OK' } else { 'MISMATCH' }))
    Set-Content (Join-Path $outDir 'DONE') $(if ($match) { 'OK' } else { 'MISMATCH' })
} catch {
    Log "ERROR: $_"
    Set-Content (Join-Path $outDir 'DONE') "ERROR: $_"
}
