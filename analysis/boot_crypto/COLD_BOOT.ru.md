# Прямой старт Linux 7 из NOR: аппаратно подтверждено

## Результат 2026-11-13

После аппаратного watchdog-reset штатный NOR-загрузчик прочитал наш encrypted
`advapi32.dll`, восстановил исходный SD-файл и передал управление напрямую
`Linux 7.2.0-rc5-r36lab`. Новое ядро запустило свой PID1 и записало свежий proof
на SD. В этом цикле до Linux7 штатный Linux4.4 не запускался; RAM-handoff модуль
не использовался. Watchdog затем автоматически вернул обычный stock4.4/MTP.

Область проверки: старт через NOR после hardware reset. Полное отключение и
повторное включение питания отдельно не испытывалось (`power_cycle_verified=false`).

Основные receipts:

- `kernel_cold_early_restore_v1_trial.json` — полный аппаратный протокол.
- `kernel_cold_early_restore_v1_trial_VERIFIED.json` — независимая повторная
  проверка сохранённых kernel/DTB bytes, trace, restore stamp и PID1 proof.
- `kernel_loader_stock_fallback_probe_v1_trial.json` — аппаратная проверка
  загрузки stock backup через native decrypt/bootm при аварийном пути.

## Идентификация и proof

- Candidate: `payload/kernel_cold_early_restore_v1`.
- Encrypted image SHA256:
  `2da0c4016a9aa356bc6ddc2d195dd5866707c6378bc85f0b23e2ae99c839948b`.
- Исходное замороженное kernel binary SHA256:
  `fb6552de75904ae38aef46c1df119a22bbf865d9e20bf208f58f65d46c2e35be`.
- Fresh run_id: `aa8961f5e8fd47cdabb0a2dc3081efa7`.
- Trace tag: `0xc5d28f11`, stage6 (PID1 reached).
- Kernel entry: `0x804e5898`, UHI a0=`0xfffffffe`, a1/FDT=`0x806f1000`.
- PID1 proof: Linux, release `7.2.0-rc5-r36lab`, build
  `#12 Thu Nov 12 12:12:13 UTC 2026`, mips, pid1, тот же свежий run_id.
- Был запрошен ровно один hardware reset; повторного boot в этом испытании нет.

Старый proof сохранён отдельно перед удалением с SD. Поэтому новый proof не
является остатком RAM-handoff теста. Контроль entry/tag и отдельный restore stamp
дополнительно связывают его с установленным encrypted-кандидатом.

## Цепочка запуска

Нормальный путь:

`NOR -> decrypt/gzip -> shim0x80010000 -> native restore/CRC -> Linux7 -> /init`

Кандидат содержит замороженные kernel и initramfs boot-профиля, неизменённый DTB,
наш shim и защитный терминальный stub. Исполняемых байтов stock Linux4.4 в payload
нет. Резервный encrypted stock-файл читается до Linux7 как данные для восстановления.

Ошибка восстановителя:

`NOR file API -> R36STOCK.ENC -> CRC -> native decrypt -> native bootm -> stock4.4`

Новый `loader_fallback.py` повторно читает backup, проверяет точную длину и CRC,
вызывает оригинальный decrypt wrapper0x89dab188 и bootm0x89daa840 с исходным
loader FDT. Этот путь аппаратно далstage208/tag0xb7b7c950 и нормальный stock/MTP.
Он не прыгает по старому kernel entry в память, уже занятую Linux7.

При неожиданном возврате bootm управление уходит в отдельный stub0x80f00000,
который находится вне stock decompression destination и ставит watchdog5с.

## Восстановление до нового ядра

`advapi32.dll` восстановлен до Linux7:3954299B, source/readback CRC32c3693b14.
После автоматического возврата все6 boot hashes уже совпадали с исходными;
`host_cleanup_wrote_boot_file=false`.

Отдельный64-байтный restore receipt хранится по physical0x02f91e00, сразу после
кольцевого журнала0xe00. Конец receipt0x02f91e40 остаётся ниже границы AVP0x02f91e50.
Последняя partial RAM page не входит в allocator range (в логе конец Normal zone
0x02f90fff). Builder проверяет геометрию замороженного DTB и4KiB pages.
Запись magic выполняется последней. Журнал ядра обернулся (4001B при capacity3520),
а receipt сохранился и подтвердил восстановление, tag, CRC и будущий kernel entry.

Полное сохранение питания во время in-place записи отдельно не испытывалось.

## Проверенная минимальная функциональность

- Встроенный PID1/initramfs запускается, SD обнаруживается и монтируется, proof
  с новым run_id записывается и переживает возврат в stock.
- MIPS clocksource и sched_clock594MHz работают; snapshot timer IRQ155, ERR0.
- MMC найден по1884c000, версия270a, internal DMA, картаSDXC, доступенmmcblk0p1.
- MemTotal42648KiB, MemAvailable36104KiB в snapshot.
- Перед стартом SD aliases переведеныRO, swap отключён. После возврата исходные
  Linux/AVP/DTB и их реальные aliases проверены.

В kernel log есть dirty-volume warning. Это наблюдение, не доказательство
повреждения файловой системы; fsck на активном томе не выполнялся. Для длительных
испытаний остаётся улучшение чистого завершения loader FAT-сессии.

Boot-профиль не создаёт driver-test proof: загрузка `.ko` в этом конкретном
прямом NOR-испытании не проверена. Экран, звук, кнопки, AVP RPC и TreeFrogUI под
Linux7 также не приняты. После теста консоль снова работает на штатном ядре.

## Инструменты и проверки

- `loader_fallback.py` — native backup/CRC/decrypt/bootm и terminal watchdog stub.
- `build_restored_cold_candidate.py` — только локальная сборка, без установки.
- `emulate_loader_fs_probe.py` — нормальный путь с реальным kernel head до
  start_kernel, ошибки восстановителя, pending reset, плохой/missing backup,
  возврат bootm; отдельно исполняется оригинальная расшифровка полного backup.
- `run_restored_cold_trial.py` — одна установка/один аппаратный reset, read-back
  proof/trace/receipt, обязательная итоговая проверка stock.
- `audit_restored_cold_trial.py` — проверяет сохранённое испытание без доступа
  к устройству и без нового перезапуска.
-14 crypto pytest PASS. Эмуляция сама по себе не считается аппаратным успехом.

Не повторять `run_restored_cold_trial.py` с тем же каталогом/receipt: он намеренно
отказывается затирать старый протокол. Для нового эксперимента нужен новый candidate.
Не изменять frozen `payload/kernel_ready`; аппаратный статус хранить внешними receipts.

Неуспешный прежний SD-root/glibc/BusyBox кандидат не получил однозначного диагноза
по утраченному RAM-следу. Рабочий путь использует ранее проверенный встроенный
initramfs, раннее восстановление и нулевой low-RAM prefix вместо shim в physical0.
