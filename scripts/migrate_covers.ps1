# Move stock box-art PNGs into TreeFrogUI's per-system .res/ folders.
# TreeFrogUI loads <romname>.png|jpg|bmp from roms/<system>/.res/ (theme.md).
# Stock IMAGES/<name>.png already match the ROM base names -> direct move, no convert.
param([string]$Drive='E:', [string]$Log='D:\r36s-\dumpcard\covers_result.txt')
$ErrorActionPreference='Stop'
Set-Content $Log "covers start $(Get-Date -Format HH:mm:ss)"
function Say($m){ Add-Content $Log $m; Write-Host $m }

$map = @(
 @{src='FC';   dst='FC'},   @{src='SFC'; dst='SFC'}, @{src='GBA'; dst='GBA'},
 @{src='GB';   dst='gb'},   @{src='GBC'; dst='gb'},  @{src='GG';  dst='GG'},
 @{src='MD';   dst='MD'},   @{src='SMS'; dst='SMS'}, @{src='NGPC';dst='ngpc'},
 @{src='PCE';  dst='pce'},  @{src='WSC'; dst='wswan'}, @{src='ATARI';dst='a26'},
 @{src='PS';   dst='ps1'}
)
$grand=0
foreach($m in $map){
  $imgDir = Join-Path (Join-Path $Drive $m.src) 'IMAGES'
  $resDir = Join-Path (Join-Path (Join-Path $Drive 'roms') $m.dst) '.res'
  if(-not (Test-Path -LiteralPath $imgDir)){ Say ("{0,-6} : no IMAGES folder, skip" -f $m.src); continue }
  New-Item -ItemType Directory -Force -Path $resDir | Out-Null
  $moved=0
  foreach($pat in @('*.png','*.jpg','*.jpeg','*.bmp')){
    foreach($f in (Get-ChildItem -LiteralPath $imgDir -File -Filter $pat -ErrorAction SilentlyContinue)){
      $t = Join-Path $resDir $f.Name
      if(Test-Path -LiteralPath $t){ continue }
      Move-Item -LiteralPath $f.FullName -Destination $t
      $moved++
    }
  }
  $now=(Get-ChildItem -LiteralPath $resDir -File -ErrorAction SilentlyContinue).Count
  Say ("{0,-6} -> roms/{1,-7}/.res : moved {2,5}, total {3,5}" -f $m.src,$m.dst,$moved,$now)
  $grand+=$moved
}
Say "TOTAL covers moved: $grand"
try{ Write-VolumeCache -DriveLetter ($Drive.TrimEnd(':')) -ErrorAction SilentlyContinue }catch{}
Set-Content 'D:\r36s-\dumpcard\covers_DONE' "OK moved=$grand"
Say "DONE"
