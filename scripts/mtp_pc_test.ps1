# Automated MTP test against the console (must be in USB/MTP mode).
#  1) time listing of SD card\roms\FC (big folder)
#  2) upload a 24 MB random file to SD card\roms (time it)
#  3) download it back to the PC and compare SHA-256
# Report: D:\r36s-\usbcap\mtp_pc_test.log
param([int]$SizeMB = 24, [string]$BigFolder = 'roms\FC', [string]$UploadFolder = 'roms')
$out = 'D:\r36s-\usbcap'; $log = Join-Path $out 'mtp_pc_test.log'
function L($m) { $s = "$(Get-Date -Format 'HH:mm:ss.fff') $m"; $s; $s | Out-File $log -Append -Encoding utf8 }

$sh = New-Object -ComObject Shell.Application
$pc = $sh.NameSpace(17)
$dev = $pc.Items() | Where-Object { -not $_.IsFileSystem -and $_.IsFolder } | Select-Object -First 1
if (-not $dev) { L 'console not found under This PC'; exit 1 }
L "device: [$($dev.Name)] type=$($dev.Type)"
$stor = @($dev.GetFolder.Items()) | Select-Object -First 1
L "storage: [$($stor.Name)]"
function Open-Sub($folderItem, $rel) {
    $f = $folderItem.GetFolder
    foreach ($part in ($rel -split '\\')) {
        $it = @($f.Items()) | Where-Object { $_.Name -eq $part } | Select-Object -First 1
        if (-not $it) { return $null }
        $f = $it.GetFolder
    }
    return $f
}

# 1) big folder listing
$sw = [Diagnostics.Stopwatch]::StartNew()
$big = Open-Sub $stor $BigFolder
$n = if ($big) { @($big.Items()).Count } else { -1 }
L ("listing {0}: {1} items in {2:N1} s" -f $BigFolder, $n, $sw.Elapsed.TotalSeconds)

# 2) upload
$src = Join-Path $out "mtp_test_${SizeMB}MB.bin"
if (-not (Test-Path $src) -or (Get-Item $src).Length -ne $SizeMB * 1MB) {
    $buf = New-Object byte[] (1MB); $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $fs = [IO.File]::Create($src); for ($i = 0; $i -lt $SizeMB; $i++) { $rng.GetBytes($buf); $fs.Write($buf, 0, $buf.Length) }; $fs.Close()
}
$hash = (Get-FileHash $src -Algorithm SHA256).Hash
$name = Split-Path $src -Leaf
$up = Open-Sub $stor $UploadFolder
if (-not $up) { L "upload folder $UploadFolder not found"; exit 1 }
L "upload $name ($SizeMB MB) -> $UploadFolder ..."
$sw.Restart()
$up.CopyHere($src, 0x10 + 0x4 + 0x400)
$item = $null
while ($sw.Elapsed.TotalSeconds -lt 600) {
    Start-Sleep -Milliseconds 500
    $item = @($up.Items()) | Where-Object { $_.Name -eq $name -or $_.Name -eq [IO.Path]::GetFileNameWithoutExtension($name) } | Select-Object -First 1
    if ($item) { $sz = $item.ExtendedProperty('System.Size'); if ($sz -eq $SizeMB * 1MB) { break } }
}
$t = $sw.Elapsed.TotalSeconds
if (-not $item) { L ("upload: file did not appear after {0:N0} s" -f $t); exit 1 }
L ("upload done in {0:N1} s (~{1:N2} MB/s, PC-side estimate)" -f $t, ($SizeMB / $t))

# 3) download back
$dl = Join-Path $out 'download'; New-Item -ItemType Directory -Force $dl | Out-Null
$dst = Join-Path $dl $name; Remove-Item $dst -ErrorAction SilentlyContinue
$sw.Restart()
$sh.NameSpace($dl).CopyHere($item, 0x10 + 0x4 + 0x400)
while ($sw.Elapsed.TotalSeconds -lt 600) {
    Start-Sleep -Milliseconds 300
    if ((Test-Path $dst) -and (Get-Item $dst).Length -eq $SizeMB * 1MB) {
        try { $fs = [IO.File]::Open($dst, 'Open', 'Read', 'None'); $fs.Close(); break } catch {}
    }
}
$t = $sw.Elapsed.TotalSeconds
$ok = (Test-Path $dst) -and ((Get-FileHash $dst -Algorithm SHA256).Hash -eq $hash)
L ("download done in {0:N1} s (~{1:N2} MB/s), SHA-256 match: {2}" -f $t, ($SizeMB / $t), $ok)
