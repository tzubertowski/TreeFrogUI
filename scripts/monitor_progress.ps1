$ErrorActionPreference='SilentlyContinue'
$prog='D:\r36s-\card2_backup\restore_progress.txt'
$done='D:\r36s-\card2_backup\restore_DONE'
$res ='D:\r36s-\card2_backup\restore_result.txt'
$Host.UI.RawUI.WindowTitle='card2: запись образа — прогресс'
function Num($s){ ($s -replace '[^\d,.]','') -replace ',','.' }
$start=Get-Date
while(-not (Test-Path $done)){
  Clear-Host
  Write-Host "=== Запись стокового образа на card2 (с проверкой) ===" -ForegroundColor Cyan
  Write-Host ("прошло: {0:hh\:mm\:ss}" -f ((Get-Date)-$start))
  $line=(Get-Content $prog -Tail 1)
  if($line){
    $m=[regex]::Match($line,'([\d  .,]+)%\s+([\d  ]+)/([\d  ]+)\s*MB\s+([\d  .,]+)\s*MB/s')
    if($m.Success){
      $pct=[double](Num $m.Groups[1].Value); $cur=[double](Num $m.Groups[2].Value); $tot=[double](Num $m.Groups[3].Value); $spd=[double](Num $m.Groups[4].Value)
      $barLen=40; $fill=[int]($barLen*$pct/100); $bar=('#'*$fill)+('-'*($barLen-$fill))
      $etaSec = if($spd -gt 0){ ($tot-$cur)/$spd } else { 0 }
      $eta=[TimeSpan]::FromSeconds($etaSec)
      $finish=(Get-Date).AddSeconds($etaSec)
      Write-Host ""
      Write-Host ("[{0}] {1:N1}%" -f $bar,$pct) -ForegroundColor Green
      Write-Host ("записано: {0:N0} / {1:N0} МБ   скорость: {2:N1} МБ/с" -f $cur,$tot,$spd)
      Write-Host ("осталось: ~{0:hh\:mm\:ss}   ориентир. конец: {1:HH\:mm\:ss}" -f $eta,$finish) -ForegroundColor Yellow
    } else { Write-Host "ждём данные прогресса..." }
  } else {
    $tail=(Get-Content $res -Tail 2) -join "`n"
    Write-Host "подготовка (очистка диска / старт)..."; if($tail){ Write-Host $tail -ForegroundColor DarkGray }
  }
  Write-Host "`n(после записи идёт сверка по SHA256 — тогда шкала остановится, это нормально)"
  Start-Sleep 3
}
Clear-Host
Write-Host "=== ГОТОВО ===" -ForegroundColor Cyan
Write-Host ("результат: {0}" -f (Get-Content $done)) -ForegroundColor Green
Write-Host "--- лог ---"; Get-Content $res -Tail 8
Write-Host "`nМожно закрыть это окно."
