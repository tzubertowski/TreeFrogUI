param(
    [Parameter(Mandatory=$true)][string]$ReportDirectory,
    [string]$DriveLetter = 'F'
)
$ErrorActionPreference = 'Stop'
$root = 'D:\r36s-'
$utf8 = [Text.UTF8Encoding]::new($true)
$record = @{ success=$false; state='starting'; target=($DriveLetter + ':'); partition_backup_complete=$false }
$output = $ReportDirectory

function Save-State([string]$state) {
    $record.state = $state
    [IO.File]::WriteAllText((Join-Path $output 'status.json'), ($record | ConvertTo-Json -Depth 8), $utf8)
}

function Hash-Md5([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm MD5).Hash.ToLowerInvariant()
}

function Run-Check([string]$arguments, [string]$label) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = Join-Path $env:SystemRoot 'System32\chkdsk.exe'
    $info.Arguments = $arguments
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.RedirectStandardInput = $true
    $oem = [Globalization.CultureInfo]::InstalledUICulture.TextInfo.OEMCodePage
    $info.StandardOutputEncoding = [Text.Encoding]::GetEncoding($oem)
    $info.StandardErrorEncoding = [Text.Encoding]::GetEncoding($oem)
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    if (-not $process.Start()) { throw 'Could not start CHKDSK' }
    # Preserve lost chains if FAT CHKDSK asks whether to save them as files.
    # /X already requests dismount; this is never run against a system volume.
    try { $process.StandardInput.WriteLine('Y') } catch [IO.IOException] { }
    $process.StandardInput.Close()
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    [IO.File]::WriteAllText((Join-Path $output ($label + '.txt')), $stdout.Result, $utf8)
    [IO.File]::WriteAllText((Join-Path $output ($label + '.stderr.txt')), $stderr.Result, $utf8)
    return @{ arguments=$arguments; exit_code=$process.ExitCode; output=($label + '.txt'); error_output=($label + '.stderr.txt') }
}

try {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator token required' }
    if ($DriveLetter -ne 'F') { throw 'Only the identified F: card is allowed' }
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $output))) { throw 'Report parent missing' }
    [IO.Directory]::CreateDirectory($output) | Out-Null
    $logical = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='F:'"
    $partition = Get-Partition -DriveLetter F
    $disk = Get-Disk -Number $partition.DiskNumber
    if ($logical.VolumeSerialNumber -ne '5446089B' -or $logical.FileSystem -ne 'FAT32' -or
        $partition.DiskNumber -ne 2 -or $partition.Offset -ne 16384 -or
        $partition.Size -ne 15728508928 -or $disk.Size -ne 62914560000 -or
        $disk.FriendlyName -notmatch 'Realtek.*CardReader') { throw 'Card identity/geometry changed; refusing writes' }
    $record.geometry = @{ disk_number=$partition.DiskNumber; friendly_name=$disk.FriendlyName;
        serial=$logical.VolumeSerialNumber; partition_offset=$partition.Offset; partition_bytes=$partition.Size;
        reported_disk_bytes=$disk.Size; fake_capacity_tail_ignored=$true }
    $original = Join-Path $root 'analysis\boot_crypto\dtb.live.before.bin'
    $expected = '9492f590fc2db86694d3fdc52a25c3e4'
    if ((Hash-Md5 $original) -ne $expected) { throw 'Trusted original DTB digest mismatch' }
    $target = 'F:\cubegm\dtb.bin'
    [IO.File]::Copy($target, (Join-Path $output 'dtb.card.before.bin'), $false)
    $record.dtb_before_md5 = Hash-Md5 $target
    foreach ($name in @('vmlinux.uImage','avp.uImage')) {
        $record[$name + '_before_md5'] = Hash-Md5 ('F:\cubegm\' + $name)
    }
    Save-State 'identity verified; backing up identified partition only'
    $free = (Get-Volume -DriveLetter D).SizeRemaining
    if ($free -lt ($partition.Size + 1073741824)) { throw 'Insufficient host space for partition backup' }
    Add-Type @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class R36VolumeCtl {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool DeviceIoControl(SafeFileHandle h, uint code, IntPtr i, uint il, IntPtr o, uint ol, out uint count, IntPtr ov);
}
'@
    $source = $null; $destination = $null; $locked = $false
    $backup = Join-Path $output 'partition-before.img'
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $source = [IO.FileStream]::new('\\.\F:', [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite, 512)
        [uint32]$returned = 0
        for ($attempt = 0; $attempt -lt 5 -and -not $locked; $attempt++) {
            $locked = [R36VolumeCtl]::DeviceIoControl($source.SafeFileHandle, 0x00090018, [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$returned, [IntPtr]::Zero)
            if (-not $locked) { Start-Sleep -Milliseconds 300 }
        }
        if (-not $locked) { throw ('Volume lock failed, Win32=' + [Runtime.InteropServices.Marshal]::GetLastWin32Error() + '; close programs using F:') }
        if (-not [R36VolumeCtl]::DeviceIoControl($source.SafeFileHandle, 0x00090083, [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$returned, [IntPtr]::Zero)) {
            throw ('Extended partition read permission failed: ' + [Runtime.InteropServices.Marshal]::GetLastWin32Error())
        }
        $destination = [IO.FileStream]::new($backup, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read, 1048576)
        $buffer = New-Object byte[] (8 * 1024 * 1024)
        [long]$copied = 0; [long]$nextReport = 0
        while ($copied -lt $partition.Size) {
            $wanted = [int][Math]::Min([long]$buffer.Length, [long]($partition.Size - $copied))
            $read = $source.Read($buffer, 0, $wanted)
            if ($read -le 0) { throw ('Unexpected end of partition at ' + $copied) }
            $destination.Write($buffer, 0, $read)
            $null = $sha.TransformBlock($buffer, 0, $read, $buffer, 0)
            $copied += $read
            if ($copied -ge $nextReport) {
                $record.backup_bytes = $copied
                Save-State 'partition backup in progress'
                $nextReport = $copied + 536870912
            }
        }
        $destination.Flush($true)
        $null = $sha.TransformFinalBlock([byte[]]@(), 0, 0)
        $record.partition_backup_complete = $true
        $record.backup_bytes = $copied
        $record.partition_backup_sha256 = ([BitConverter]::ToString($sha.Hash)).Replace('-','').ToLowerInvariant()
        $record.partition_backup_path = $backup
    } finally {
        if ($destination) { $destination.Dispose() }
        if ($locked -and $source) {
            [uint32]$ignored = 0
            $null = [R36VolumeCtl]::DeviceIoControl($source.SafeFileHandle, 0x0009001c, [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$ignored, [IntPtr]::Zero)
        }
        if ($source) { $source.Dispose() }
        $sha.Dispose()
    }
    Save-State 'partition backed up; restoring diagnostic DTB if identified'
    if ($record.dtb_before_md5 -eq '51f7338a3dcf3597819a272473900a55') {
        $staged = 'F:\cubegm\r36-dtb-restore.staged.bin'
        [IO.File]::Copy($original, $staged, $true)
        $stream = [IO.FileStream]::new($staged, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
        try { $stream.Flush($true) } finally { $stream.Dispose() }
        if ((Hash-Md5 $staged) -ne $expected) { throw 'Staged DTB restore digest mismatch' }
        [IO.File]::Copy($staged, $target, $true)
        $stream = [IO.FileStream]::new($target, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
        try { $stream.Flush($true) } finally { $stream.Dispose() }
        $record.dtb_restored = (Hash-Md5 $target) -eq $expected
    } elseif ($record.dtb_before_md5 -eq $expected) {
        $record.dtb_restored = $true
    } else {
        $record.dtb_restored = $false
        $record.dtb_note = 'Unknown DTB content preserved; no automatic overwrite of unrelated changes'
    }
    Save-State 'running CHKDSK F: /F /X (no surface scan)'
    $record.chkdsk_repair = Run-Check 'F: /F /X' 'chkdsk-repair'
    Save-State 'running independent read-only CHKDSK verification'
    $record.chkdsk_verify = Run-Check 'F:' 'chkdsk-verify'
    $record.boot_hashes = @{}
    foreach ($name in @('vmlinux.uImage','avp.uImage','dtb.bin')) {
        $record.boot_hashes[$name] = Hash-Md5 ('F:\cubegm\' + $name)
    }
    $record.success = ($record.chkdsk_repair.exit_code -le 1 -and $record.chkdsk_verify.exit_code -eq 0 -and
        $record.boot_hashes['vmlinux.uImage'] -eq 'f994b5e32dc90c5eec7e4bd965bff8fe' -and
        $record.boot_hashes['avp.uImage'] -eq '36cf812151712a8a1ec01911ac03ab74' -and
        $record.boot_hashes['dtb.bin'] -eq $expected)
    Save-State 'completed'
} catch {
    $record.error = $_.Exception.Message
    if (Test-Path -LiteralPath $output) { Save-State 'failed; inspect report before further changes' }
} finally {
    if (Test-Path -LiteralPath $output) {
        [IO.File]::WriteAllText((Join-Path $output 'done.json'), ($record | ConvertTo-Json -Depth 8), $utf8)
    }
}
if (-not $record.success) { exit 1 }
