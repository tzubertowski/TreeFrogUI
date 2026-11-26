# Move the user's ROMs from the stock root folders into TreeFrogUI's roms/<system>/.
# Same-volume moves = fast renames, no extra space, nothing deleted (move only).
# Box-art PNGs (stock IMAGES/) and FILELIST.CSV are left behind (TreeFrogUI uses
# its own .rgb565 art). MAME is skipped (arcade romsets depend on the exact core).
param([string]$Drive='E:', [string]$Log='D:\r36s-\dumpcard\migrate_result.txt')
$ErrorActionPreference='Stop'
Set-Content $Log "migrate start $(Get-Date -Format HH:mm:ss)"
function Say($m){ Add-Content $Log $m; Write-Host $m }

$map = @(
 @{src='FC';   dst='FC';    ext=@('*.zip')},                               # NES (alias)
 @{src='SFC';  dst='SFC';   ext=@('*.zip')},                               # SNES (alias)
 @{src='GBA';  dst='GBA';   ext=@('*.zip','*.gba')},                       # GBA (alias)
 @{src='GB';   dst='gb';    ext=@('*.zip','*.gb')},                        # Game Boy
 @{src='GBC';  dst='gb';    ext=@('*.zip','*.gbc')},                       # GBC -> gambatte (merged)
 @{src='GG';   dst='GG';    ext=@('*.zip')},                               # Game Gear (alias)
 @{src='MD';   dst='MD';    ext=@('*.zip','*.md','*.gen','*.smd','*.bin')},# Mega Drive (alias) - dummy.md is kept (not matched: .md filter would catch it, so exclude by name below)
 @{src='SMS';  dst='SMS';   ext=@('*.zip','*.sms')},                       # Master System (alias)
 @{src='NGPC'; dst='ngpc';  ext=@('*.zip','*.ngp','*.ngc')},
 @{src='PCE';  dst='pce';   ext=@('*.zip','*.pce')},
 @{src='WSC';  dst='wswan'; ext=@('*.zip','*.ws','*.wsc')},
 @{src='ATARI';dst='a26';   ext=@('*.a26','*.zip')},
 @{src='PS';   dst='ps1';   ext=@('*.pbp','*.img','*.iso','*.cue','*.bin','*.chd')}
)

$grandMoved=0
foreach($m in $map){
  $srcPath = Join-Path $Drive $m.src
  $dstPath = Join-Path (Join-Path $Drive 'roms') $m.dst
  if(-not (Test-Path -LiteralPath $srcPath)){ Say ("{0,-6} -> roms/{1,-7} : source missing, skip" -f $m.src,$m.dst); continue }
  New-Item -ItemType Directory -Force -Path $dstPath | Out-Null
  $moved=0
  foreach($pat in $m.ext){
    $items = Get-ChildItem -LiteralPath $srcPath -File -Filter $pat -ErrorAction SilentlyContinue
    foreach($f in $items){
      if($m.src -eq 'MD' -and $f.Name -ieq 'dummy.md'){ continue }   # keep autorun trigger
      $target = Join-Path $dstPath $f.Name
      if(Test-Path -LiteralPath $target){ continue }                 # don't clobber
      Move-Item -LiteralPath $f.FullName -Destination $target
      $moved++
    }
  }
  $remain = (Get-ChildItem -LiteralPath $srcPath -File -ErrorAction SilentlyContinue).Count
  $nowIn  = (Get-ChildItem -LiteralPath $dstPath -File -ErrorAction SilentlyContinue).Count
  Say ("{0,-6} -> roms/{1,-7} : moved {2,5}, now in target {3,5}, left at source {4,5}" -f $m.src,$m.dst,$moved,$nowIn,$remain)
  $grandMoved += $moved
}
Say "MAME   -> (skipped: arcade, needs per-core sorting)"
Say "TOTAL moved: $grandMoved"
# flush
try{ Write-VolumeCache -DriveLetter ($Drive.TrimEnd(':')) -ErrorAction SilentlyContinue }catch{}
Set-Content 'D:\r36s-\dumpcard\migrate_DONE' "OK moved=$grandMoved"
Say "DONE"
