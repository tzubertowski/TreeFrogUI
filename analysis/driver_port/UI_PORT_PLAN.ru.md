# Перенос TreeFrogUI и периферии на Linux 7

## Аппаратный cold trial единого ядра PROFILE=full (`kernel_cold_full_v1`) — PASS

- После перевода `PROFILE=full` на `CONFIG_CC_OPTIMIZE_FOR_SIZE=y` (`-Os`) и модульных `HID`/`RFKILL` образ `vmlinux.bin + r36-lab.dtb` (`3 725 249` Б в `gzip -9`) прошёл эмуляцию (`8/8` + `native_fallback`) и реальный холодный запуск на R36S (`analysis/boot_crypto/kernel_cold_full_v1_trial.json`): `cold_boot_verified=true`, `native_restore_verified=true`, `stock_restored=true`, `7.2.0-rc5-r36full #24`, `usb1` + `usb2` MUSB hubs, `r36-direct-keys` (`input0`) + `r36-serial-keys` (`input1`), `display_inspection=PASS`.
- WSL (`ubmips`, Ubuntu 22.04, 8 ядер) подготовлен (`clang-15`, `lld-15`, `llvm-15`, `curl`, `rsync`, `cpio`) для быстрых последующих сборок.

## VM-сборка PROFILE=full и driver_r36_combined_v1.so (офлайн, без hardware)

- `analysis/driver_port/driver_r36_combined_v1.so` (`sha256: 5ae91af8a61ee70d216b02467db2c763ff1cf2660ed2f92d61bc750de0595328`, 21516 Б) пересобран в QEMU build VM против `/work/console_runtime_20261115_v1/{libpthread.so.0,libc.so.6}` (`NEEDED`: `libpthread.so.0`, `libc.so.6`, `ld.so.1`; `GLIBC<=2.4`), все 7 символов (`video_driver*` + `sound_driver*`) прошли `RTLD_NOW` `dlopen` под `qemu-mipsel` (`CONSOLE_RUNTIME_DLOPEN_COMBINED=PASS`). См. `analysis/driver_port/COMBINED_DRIVER_MIPS_v1_RESULT.json`.
- Полное ядро `PROFILE=full` (`7.2.0-rc5-r36full`) собрано в QEMU build VM и извлечено в `payload/kernel_full_vm_v1/` (gitignored): `vmlinux.bin`, `r36-lab.dtb` (после фикса порядка `#include "r36-audio.dts"` в `r36-full.dts` / `vm_build_kernel.sh`), `r36_hc16xx_drm.ko`, `r36_hc16xx_i2s.ko` и `modules.tar.gz` с 66 `.ko` модулями (Wi-Fi/BT/USB-net). См. `analysis/driver_port/FULL_KERNEL_BUILD_v1_RESULT.json`.
- Hardware-проверка не выполнялась.

## DRM flip support verified + double-buffer backend fix (offline, без hardware)

- Доказано статически по payload/display_driver_source_v4/r36_hc16xx_drm.c и
  deployed r36_hc16xx_drm.ko: драйвер ПОДДЕРЖИВАЕТ двойную буферизацию и
  синхронный page flip (DRIVER_ATOMIC, drm_atomic_helper_page_flip/commit,
  drm_gem_fb_create_with_dirty, drm_vblank_init, drm_crtc_send_vblank_event по
  hc16xx_latched либо после 4 vblank через flip_timeouts, ping-pong next_desc).
  Ограничение было только в userspace backend. Тест:
  scripts/peripheral_lab/test_drm_flip_support.py (skip без payload).
- video_drm_backend.c переписан: два dumb-буфера; scaler всегда пишет
  неактивный; показ через DRM_IOCTL_MODE_PAGE_FLIP + ожидание
  DRM_EVENT_FLIP_COMPLETE с таймаутом и токеном (устаревшие события
  отсеиваются). Первый кадр и recovery после неудачного flip — SETCRTC +
  WAIT_VBLANK; после неудачного flip следующий кадр обязан сделать modeset
  ДО рендера, поэтому активный буфер никогда не перезаписывается. Формат лога
  submitted_frames и экспорт ABI не менялись; trace-заголовок не менялся
  (pixels = front).
- Верификация офлайн: mock video_backend_test.c хэширует активный
  scanout-буфер на каждой активации и падает, если CPU его перезаписал;
  покрыты отказ flip ioctl, таймаут flip-события и drain устаревшего
  события. REAL_BACKEND_MOCK_DRM=PASS и SHARED_LIB_CONTRACT=PASS в QEMU build
  VM (-Wall -Wextra -Werror, trace-сборка отдельно). Полный pytest Windows:
  262 passed/14 skipped. Результат: analysis/driver_port/DRM_FLIP_OFFLINE_v1_RESULT.json.

## MIPS-артефакты пересобраны; candidate flip готов; flip-trial выполнен, evidence неполон

- Тулчейн: mipsel-linux-gnu-gcc (Ubuntu 10.3.0-1ubuntu1 — та же версия, что в
  историческом .so) из D:/wsl/ubmips/rootfs, извлечён в QEMU build VM в
  абсолютные пути. Потребовались фиксы: битые Windows-симлинки (0 байт),
  +x на PT_INTERP ld-linux, PATH-шим /opt/mipsbin на glibc cross-binutils
  (gcc вызывает непрефиксный `as`, Alpine musl ломался о glibc-каталог).
- Собрано (analysis/driver_port/): driver_r36_drm_ui_test.so (trace,
  sha256 74012f12..., NEEDED libpthread.so.0 + libc.so.6 + ld.so.1 — точный
  паритет с v11; MIPS32r2 hard-float; GLIBC<=2.7; экспорт4 = v11),
  backend_notrace.so, driver_r36_test_mockdrm_v1.so (5 экспортов, mock
  целен в qemu test runtime, не деплоится).
- Контракт с консолью: CONSOLE_RUNTIME_DLOPEN=PASS — RTLD_NOW dlopen нового
  .so с сохранённым консольным ld.so.1/libc (макс. GLIBC_2.19)/libpthread/
  libdl под qemu-mipsel, все4 экспорта резолвятся. Лог-токены и версии
  GLIBC побайтно-сопоставимы с историческим v11 (readelf parity).
- Эмулятор: DRM_FLIP_MOCK_SMOKE_v18/8 PASS (4 реальных MIPS-cores x2 режима,
  harness libretro-smoke-mips-v5, actual_backend_frames в каждом прогоне).
  test_drm_flip_support.py3/3 PASSED; pytest262/14.
- Candidate: payload/kernel_ui_flip_v1 (копия navigation_v1 только с новым
  driver .so, manifest+provenance) -> cold payload/kernel_cold_ui_flip_v1
  (sha256 17ea5104...): native gzip validate PASS, cold_restore_emulation8
  строк PASS, cold_restore_native_fallback1 PASS.
- Hardware trial НЕ запускался: транспорт на preflight ответил «R36S not
  found: put the console in USB (MTP) mode» — ни загрузки, ни NOR-записи,
  ни receipt. Камера не использовалась; квадраты НЕ объявлены исправленными.
  Результат: analysis/driver_port/DRM_FLIP_MIPS_REBUILD_v1_RESULT.json.
- Консоль сейчас подключена и отвечает (stock 4.4.186, WorkerTransport).
  /cubegm полностью бэкаплен: scripts/boot_crypto/backup_cubegm.py (read-only,
  батч-tar, sha256-манифест, resume, keepawake) ->
  analysis/boot_crypto/backups/20261116T161658Z_cubegm, complete=true,
  18035 файлов/1001817323 B, pagefile.sys пропущен; перехеш vs манифест +
  спот-чек с устройства байт-в-байт. Тесты backup9+poweroff7, pytest278/14.
  Poweroff-флаги trial-скрипта (--poweroff-on-completion/--poweroff-after)
  готовы и по умолчанию выключены (включать по команде пользователя).
- Trial kernel_cold_ui_flip_v1 ВЫПОЛНЕН (run_id ebc4735788ad4f398f400a7d996da13a,
  receipt analysis/boot_crypto/kernel_cold_ui_flip_v1_trial.json): механика PASS —
  cold NOR boot (trace stage6, entry 0x805c2e74 == original_entry, session_tag
  0xe364cdd), native restore PASS (стамп R36ST1/crc c3693b14), автовозврат stock
  (uptime 18.14s), все6 hashes, host_cleanup=false, poweroff_requested=false.
- Evidence НЕ полон: r36-own-kernel-proof.txt / r36-ui-probe.txt / r36-ui-child.txt /
  r36-ui-keys.txt на SD нет → cold_boot_verified=false; PID1 не дошёл до записи
  отчётов (remount-rw). В nav-trial при идентичном init.elf/initramfs/vmlinux/
  писателе эти файлы собрались; единственное отличие = новый
  driver_r36_drm_ui_test.so (74012f12… vs 991aa7e…). Гипотеза: UI-дочерний завис
  (ожидание flip-события нового драйвера), init завис в waitpid/reap, watchdog
  отсёк; tmpfs-отчёты потеряны — прямых доказательств нет.
- Камера180 кадров (analysis/boot_crypto/camera_cold_ui_flip_v1_run1..3): в окне
  custom boot экран без видимых изменений (splash не появился, смены кадров нет),
  чёрных квадратов не видно ни в одном кадре; дальше чёрный кадр сброса и
  штатный возврат stock. Квадраты НЕ объявлены исправленными — условие наблюдения
  (смена кадров) не наступило.
- Корневая причина неполного evidence (manifest/receipt): UI-окно PID1=60с
  (R36_UI_WINDOW_TICKS=600, байт addiu $at,$zero,600 в init.elf), а flip cold
  собран с watchdog_seconds=30 (manifest и receipt trace=30) → срез до finish_log
  (~61с) гарантирован; nav-candidate имел watchdog90>60 → отчёты записаны.
  Суб-гипотеза (зависший child, D-state → goto wait_reset) разрешается mark-точками.
- Instrumented candidate ГОТОВ: /dev/kmsg mark-точки в ui_console_init.c
  (retained ring 0x2f91000 → .kernel.log триала; NOR trace header занят, stage-гейты
  не трогаем) — report_open/setup_done/module_loaded/child_forked/window_done/
  reap_child_failed/reaped/notes remount и т.д. Сборка Zig0.17 musleabi/mips32r2/
  soft-float (abiflags fp=3), objcopy без .pdr → slot 33131≤34768; все192 строки
  старого init сохранены. payload/kernel_ui_flip_v2 + cold
  payload/kernel_cold_ui_flip_v2 (watchdog90); эмуляции PASS (8+1), flip3/3,
  pytest278/14.
- Следующее: hardware-trial run_restored_cold_trial.py --deploy
  payload/kernel_cold_ui_flip_v2 с камерой; анализ receipt + .kernel.log mark-строк
  + кадров. Новый candidate ID и новый receipt (тот же ID запрещён — receipt
  существует). Консоль в stock; keepawake перезапущен (авто-выключение отключено
  по указанию пользователя).
- Hardware-trials `kernel_cold_ui_flip_v2` (run_id 9739eb57ed6d4ba78a00d3286f01abef)
  и `kernel_cold_ui_flip_v3` (run_id bcb4e228a6ec4cd788071d984ec01aba) выполнены:
  watchdog90 позволил PID1 дойти до `finish_log` и записать `proof.txt`
  (`cold_boot_verified=true`, `native_restore_verified=true`, `stock_restored=true`),
  но метки в `.kernel.log` (`stage=nav_starting key=1627586579 ->
  stage=nav_incomplete pid=24 keys=0 ready1=0 ready0=0 -> stage=report_sizes ui=0`)
  показали отказ `navigation_start` по таймауту 3 с при живом `r36-navigation-keys`
  (`pid=24`) и пустых `ui-report.txt`/`ui-keys.txt`.
- Найдена и устранена точная причина регрессии `v2`/`v3`: ядро запускает `/init`
  без `/dev/console` (`Warning: unable to open an initial console.`), с закрытыми
  `fd 0..2`. Добавленный в `v2` вызов `kfd = open("/dev/kmsg", ...)` занимал `fd = 0`,
  сдвигая `fd = open("/tmp/ui-report.txt", ...)` на `fd = 1`, после чего
  `dup2(1, 1); dup2(1, 2); close(1);` закрывал `stdout` (`fd = 1`) в `PID 1` и
  аналогично закрывал `fd = 1` (`log = 1`) в дочернем процессе `navigation_start`,
  где `/dev/input/event0` (`O_RDONLY`) занимал `fd = 1` и ломал
  `dprintf(1, "keys_diagnostic_ready=1\n")` (`EBADF`).
- В `ui_console_init.c` после монтирования `devtmpfs` дескрипторы `0..2`
  резервируются на `/dev/null`, `kfd` переводится на `fd >= 3` (`F_DUPFD_CLOEXEC`),
  добавлена защита `if(fd>2)close(fd);` и тест
  `test_stdio_fds_reserved_before_kmsg_and_report_dup2` (`279 passed, 14 skipped`).
  Собраны и проверены офлайн `payload/kernel_ui_flip_v4` (`initramfs 34521 <= 34768`)
  и `payload/kernel_cold_ui_flip_v4` (`watchdog_seconds=90`, эмуляции 8+1 PASS).
  Следующий шаг — hardware-trial `payload/kernel_cold_ui_flip_v4` с камерой.
- Пока консоль выключена до вечера, подготовлены и верифицированы офлайн следующие
  модули порта (`311 passed, 14 skipped`):
  - `scripts/peripheral_lab/usb_ffs_mtp_adb.h` + `usb_mtp_adb_service.c` +
    `test_usb_ffs_mtp_adb.py`: дескрипторы `FunctionFS` v2 для композитного `MTP + ADB`
    (`0x18d1:0x4e22`, `3 TX + 2 RX <= 5 TX + 5 RX` в `hc16xx_fifo_cfg`), полный стек
    файловых операций `tfmtp` (`GetStorageInfo`/`GetObjectHandles`/`GetObjectInfo`/
    `GetObject`/`GetPartialObject`/`SendObjectInfo`/`SendObject`/`DeleteObject`/
    `OP_TF_Info`), авто-выбор `FunctionFS`/legacy `/dev/mtp_usb` и одновременный `ADB`
    (`CNXN`, `shell:`, `sync:`).
  - `scripts/peripheral_lab/prepare_ui_gameplay_input.py` + `test_ui_gameplay_input.py`:
    валидатор полной 12-кнопочной игровой карты из `INPUT_PHYSICAL_v3_RESULT.json`
    и сквозной тест `legacy_keys -> SysV -> r36_legacy_to_libretro` + MIPS-сборка.
  - `scripts/peripheral_lab/audio_alsa_backend.c` + `test_audio_alsa_backend.py`:
    ALSA-реализация `sound_driver_init`/`sound_driver_playframe`/`sound_driver_deinit`/
    `sound_driver_flush` под проверенный 12-словный UAPI `r36_hc16xx_i2s` с учётом
    двойного прогрева `init -> deinit -> init` в `picoarch` (`0x42ce80..0x42cfb8`).
  - `scripts/peripheral_lab/driver_r36_combined_backend.c` +
    `test_combined_driver_backend.py`: объединённый `PICOARCH_DRIVER` (неизменённый
    `video_drm_backend.c` + `audio_alsa_backend.c`), проверенный интерлив-циклом DRM
    page flip + ALSA warmup/playframe + `zig cc` MIPS32r2.
  - `scripts/kernel_lab/ports/hc16xx-adc-ro.c` + `adc_battery_osd.h` +
    `scripts/kernel_lab/tests/test_hc16xx_adc_ro.py`: char-узлы `miscdevice`
    `/dev/check_adc1` и `/dev/check_adc5` (calibrated `(sample * 241) / ref`, чтение
    без EOF на открытом fd, сохранение IIO) и R36S-кривая `{64, 153, 180} -> {0, 50, 100}%`
    + порог зарядки `>= 64`.
  - `scripts/peripheral_lab/direct_keys_policy.h` + `test_direct_keys_policy.py`:
    политика прямых кнопок `r36-direct-keys` (`L2=109, R2=104, FN=59, VOL+=115,
    VOL-=114, POWER=116`: громкость, `FN`+`VOL+/-` яркость, short/long `POWER`) и
    правило `GPIO19` speaker PA по `GPIO15` headphone-detect.
  - `scripts/kernel_lab/usb_overlay.py` (`patch_musb_host_otg_support`) +
    `r36-usb-otg.dts` + `vm_build_kernel.sh` (`R36_OTG_WIFI_BT=1`) +
    `usb_otg_wifi_bt_probe.h` + `test_usb_otg_wifi_bt.py`: исправление 4 ошибок
    `hc16xx` MUSB для Host/OTG (`USB_O_UTMI` byte R/W, `role_mode`, `MUSB_DEVCTL_SESSION`,
    `pdata.mode` из `dr_mode`), конфиг модулей Wi-Fi/BT (`CFG80211`/`MAC80211`/`RTL8XXXU`/
    `RTW88`/`MT7601U`/`BT_HCIBTUSB`) и userspace-зонд ролей / `READ_BD_ADDR` / `wlan0`;
  - `scripts/peripheral_lab/audit_cubegm_elf_deps.py` + `test_cubegm_deps_audit.py`:
    проверены 155 ELF в бэкапе `/cubegm` (`23/23` `DT_NEEDED` библиотек найдены локально).
  - `scripts/peripheral_lab/r36_sysd.c` + `test_r36_sysd.py`: единый системный демон
    (кнопки, PA `GPIO19`/`GPIO15`, подсветка `/sys/class/backlight`, батарея ADC и
    чистое выключение `swapoff`/`umount`/`RB_POWER_OFF`) + MIPS32r2 ELF.
  - `scripts/kernel_lab/r36_chkdsk_console.c` + `r36_chkdsk_console.h` + `r36_screen_status.h` +
    `scripts/kernel_lab/tests/test_r36_chkdsk_console.py`: консольный «чек-диск»
    с детектором ошибок ФС/носителя в `/dev/kmsg` (`--if-kernel-error`), экранным RGB565
    прогресс-выводом на `/dev/fb0`, безопасным `swapoff` + `umount2`, снимком метаданных,
    ремонтом `r36-fsck-cp437-v2` и проверкой.
  - `scripts/peripheral_lab/audit_cubegm_runtime.py`, `prepare_otg_firmware.py`,
    `r36_session_init.c`: аудит скриптов/ядер `/cubegm` (`113` ядер), проверщик
    `/lib/firmware` для OTG Wi-Fi/BT и единый супервизор сессии `PID 1`.
  - `scripts/kernel_lab/r36-full.dts` + `PROFILE=full` (`vm_build_kernel.sh`,
    `start_vm_kernel_build.py --full`) + `prepare_session_initramfs.py`: единый полный
    профиль ядра (display + audio + input + adc + pwm + otg wifi/bt), сохранение
    громкости/яркости на SD в `r36_sysd.conf` и упаковщик статических MIPS32r2 бинарников.
  - **Дорожная карта полного перевода консоли на Linux 7.2 (по порядку после включения):**
    1. Trial `payload/kernel_cold_ui_flip_v4` (проверка UI и смены кадров).
    2. Сборка `PROFILE=full` в VM и `driver_r36_combined_backend.c` `.so`.
    3. Приёмка полного игрового цикла (`UI + игры + звук + GPIO19/15 + кнопки + подсветка + ADC`).
    4. Приёмка `MTP + ADB` и OTG `Wi-Fi / Bluetooth` (с проверкой `/lib/firmware`).
    5. Приёмка консольного `r36-chkdsk`, чистого выключения (`RB_POWER_OFF` / `GPIO1`) и переход на постоянную загрузку без watchdog.

## UI directional navigation v1 accepted; black-square defect open

- UI_NAVIGATION_v1_RESULT.json: user подтверждает отличную работу направлений,
  но сообщает чёрные мелкие квадраты внизу при смене кадра. Rendering-quality FAIL/
  unresolved, не скрывать за navigation PASS. User уточнил: idle clean, квадраты
  исчезают без переключения, видны только при смене кадра. Transient defect.
- Real MIPS publisher masks10/20/40/80 hex,70changes/releases0/graceful stop0;
  video callbacks33/new frame hash, UI child0. Native restore/watchdog stock return/
  6boot и3UIhashes PASS, host boot writes=false. Камеры не использовались.
- Static: single active buffer очищается чёрным, затем копируется source до WAIT_VBLANK.
  Это подтверждённый риск live-scanout race, НЕ доказанная причина именно квадратов.
  Следующее source-vs-output evidence и inactive-buffer/vblank-flip implementation
  при поддержке actual DRM, не blindly declare fixed by pre-copy wait.
- Stock frogui/keymap.txt уже задаёт consumer bits. Physical calibration была
  нужна для code->bit producer path; не меняем stock names/extra bits угадыванием.

## Navigation v1 implementation history

- Новый protected UI bootstrap: publisher exclusively owns SysV4B, starts before
  unchanged UI; ready marker/held-state query, PID1 watches and aborts on publisher
  loss, stop/reap before report-only RW. SDRO/settingsRAM/audiooff preserved.
- Compile-time directions-only publisher validates exactly4unique bits4..7;
  measured map712/715/713/714. Actual stock frogui/keymap.txt matches. A/B/START и
  special buttons unmapped; no game launch by confirmation key in this slice.
- Existing input-enabled kernel/DTB/DRM module reused; only PID1/publisher rebuilt.
 60s UI,90s watchdog. Verified v11 backend+observer reused (single-frame live
  check not navigation oracle once callbacks increase). Raw SysV logs collected.
- Cold8/native fallback PASS;261pytestPASS/10SKIP; real native Linux VM uinput/
  evdev/SysV press/release/ready/zero-cleanup/reject-confirm-map PASS. Actual MIPS
  publisher+UI chain now hardware accepted for4directions only; UI_NAVIGATION_v1_STATUS.json.
- Один hardware trial complete. Дальше artifact investigation, не новый такой же
  interactive test. A/START/game launch, extras и sound остаются unverified.

## Physical input calibration preparation (новее UI acceptance)

- User добавил L2/R2, FN,volume+/-, POWER последней и попросил больше времени.
  План:60s capture/90s watchdog, eighteen physical press/release labels.
- Raw order UP RIGHT DOWN LEFT A B X Y START SELECT L1 R1 L2 R2 FN VOL+ VOL- POWER.
  POWER short tap only; hardware long-hold cutoff не отменяется диагностикой.
- Новый patch-only PID1/candidate kernel_input_calibration_v3 от existing input
  kernel: adds GPIO12/13/14 polled inputs only, no action daemon/output GPIO.
  Kernel code unchanged. prepare_input_calibration.py exact DT delta validated.
- Cold wrapper explicit90s watchdog; default30 прежний. Trace/receipt actual reload
  проверяются эмуляцией; first byte-match failed из-за emulator default30, manifest
  propagation исправлен. Offline cold8/native fallback PASS (actual90s counter,
  trace/receipt checked),244pytestPASS/10SKIP. INPUT_CALIBRATION_v3_STATUS.json.
  **Hardware v3 complete:** INPUT_PHYSICAL_v3_RESULT.json, raw18physical buttons PASS.
- Пользователь получил порядок18кнопок; KMS stripes start cue,
  не менять настройки/не запускать игры. Камеры запрещены. Raw key mapping неизвестен,
  старые tests2evdev/0events/ERR2 не доказывают рабочие кнопки.
- User подтвердил все18по порядку;36events/18unique press-release pairs/dropped0.
  Native restore/watchdog90/stock MTP/6boot и3UIhashes PASS, no host cleanup writes.
  Physical L1/R1 measured serial704/707; L2/R2 direct109/104 — старые DTS labels
  не совпадали с физической маркировкой. Полная карта в INPUT_PHYSICAL_v3_RESULT.json.
- analyze_physical_capture.py whole-sequence validation9tests, full253PASS/10SKIP.
  Existing legacy calibrator создал canonical12 map offline (не installed), extras
  без guessed bits. Volume/power raw keys accepted, actions НЕ tested.
- **Следующее:** protected actual MIPS evdev->SysV->unchanged UI navigation trial
  с measured12map. Перед interactive boot human ready; no camera. Extra L2/R2/FN
  consumer ABI и безопасные volume/power handlers — отдельные задачи.

## Разрешённый повтор v11 для human observation

- User отходил и явно запросил повтор. Один unchanged repeat разрешён именно
  для наблюдения пользователем, не новая гипотеза/сборка. Камеры запрещены.
- payload/kernel_cold_ui_live_scanout_v11_repeat1 — точная копия verified v11,
  hashes+existing cold/fallback PASS проверены; no rebuild, fresh run_id/trial path.
- **Repeat complete / appearance accepted:** UI_LIVE_SCANOUT_v11_REPEAT1_RESULT.json.
  User видел интерфейс с недавней игрой и явно подтвердил, что ДО automatic reboot.
  Human eyewitness acceptance, no camera, не вывод из hashes. First+late digital
  match0f4e3334 at10040ms; watchdog/native restore/6boot и3UI hashes PASS.
- Теперь **appearance прежнего UI на diagnostic Linux7 принят этим срезом**.
  Navigation/buttons/audio/actual game/full power-cycle остаются unverified.
  Следующее physical input calibration/navigation, потом audio/game integration;
  не повторять black-screen experiments без нового отдельного дефекта.

## Live checkpoint v11 2026-11-15 (новее v10)

- Пользователь сам наблюдает экран; **камеры не использовать**. Human observation
  пока PENDING, записывать отдельно от цифровой приёмки и только со слов пользователя.
- R36_UI_LIVE_CHECKPOINT monotonic10s после первого callback, every60 real runs,
  synchronous one-shot backend function через RTLD_NOLOAD. Без новых потоков,
  signal handlers, input overrides или extra video frames.
- Backend r36_scanout_live_checkpoint: late_live read-back под lock, только если
  submitted_frames1. Parser late_live требует marker10..15s и first+late hashes/
  health/raster. Исторический v10 before_cleanup partial не переписывать.
- v11 только backend+observer rebuilt; kernel/PID1/DTB unchanged. Native Linux
  scheduler mock и saved-console-runtime MIPS load/fail-closed/forwarding PASS.
  UI_LIVE_SCANOUT_OFFLINE_VERIFIED.json; cold8/native fallback PASS,237pytestPASS/10SKIP.
  No-trace actual backend mock PASS; только две diagnostic libraries изменены.
- **Hardware v11 PASS digital:** UI_LIVE_SCANOUT_v11_RESULT.json. First+late_live
  hashes source/mapped/uncachedDMA0f4e3334 match, late elapsed10031ms/run8460,
  frames1, same descriptor02f90400/pixel01500000/RGB565640x480/timing1/on1/
  timeouts0/raster progress1. Две выборки подтверждены, не continuous monitoring.
- Stock watchdog/native restore/MTP/6boot и3UIhashes PASS, host boot writes=false.
  User visual report PENDING: предупреждён перед boot, вопрос после опыта задан.
  **Следующее:** дождаться human observation именно v11. Если чёрный экран,
  inspect panel/backlight/layer state read-only; не повторять unchanged trial.
  Камеры не открывать, physical appearance не считать принятым по hashes.

## Scanout read-back 2026-11-15 (новее v9)

- Opt-in diagnostic backend R36_SCANOUT_TRACE: first/before_cleanup
  callback-source -> mapped scaled buffer -> uncached physical DMA hash;
  health/descriptor/pixel bounds guards + raster progress, only read-only RAM access.
  Production no-trace route прежний. Не physical visual acceptance.
- UI_SCANOUT_TRACE_OFFLINE_VERIFIED.json: Linux actual C observation mock PASS
  (match/corruption/bad health/missing devmem/padding). MIPS dlopen on saved console
  runtime/fail-closed PASS; compatible harness explicitly linked old saved libc/libdl.
- v10 only backend library changed from v9, kernel/PID1/DTB/core state observer reused.
  Cold bootm/gzip/cold8/native fallback PASS. Final full pytest235PASS/10SKIP;
  native Linux mock отдельно исполнен, Windows sys/mman test skipped by platform.
- **Hardware v10 PARTIAL:** UI_SCANOUT_TRACE_v10_RESULT.json. Первый callback/
  backend input/mapped/uncachedDMA hashes0f4e3334 совпали, active==programmed02f90400,
  pixel01500000/RGB565640x480/pitch1280/on1/timing1/timeouts0/raster progress1.
  Но before_cleanup в логе отсутствует: first_frame_verified=true,
  digital_chain_verified=false (строгий two-phase). Persistence к концу16s не доказана.
- Stock watchdog/native restore/MTP/6boot hashes и3protected UI hashes PASS,
  host boot cleanup writes=false. Камеры не открывались, visual acceptance false.
- **Следующий distinct experiment:** явный late checkpoint пока child alive,
  не cleanup-dependent. После проверки persistence read-only panel/backlight/layer
  state; не повторять unchanged v10, не утверждать panel visibility по hashes.

## State-trace продолжение 2026-11-15 (новее v8)

- Static analysis actual ELF: существует idle redraw-elision: при unchanged
  signature/animation/transition/toast core делает usleep1000 и возвращается
  без video callback. Нейтральный input + videos1 не доказывает поломку core.
  Отдельно: missing fb errors НЕ доказанная причина чёрного экрана.
- Полного source локально нет; nested FrogUI checkout пуст. Companion repos
  не изменялись. REA Windows/MIPS unavailable; использованы installed ELF/Capstone.
  Raw disassembly/address tables local-only, не в Git.
- Новый opt-in read-only observer R36_UI_STATE_TRACE: generated exact-binary
  profile12fields, /proc/self/mem O_RDONLY/pread, before/after real retro_run.
  FNV64/size file match + loaded code identity samples; offsets bounds/type checked.
  У actual FrogUI нет GNU build ID; fingerprint не cryptographic authentication.
- Synthetic forwarding/state+wrong-profile rejection PASS:
  UI_STATE_TRACE_OFFLINE_VERIFIED.json. Initial empty-fields bug caught in verify_v1,
  corrected verify_v2 PASS. Focused6 tests PASS, final full225PASS/9SKIP.
- v9 source/cold payload: ядро/PID1/DTB/DRM backend byte-identical v8,
  только observer library rebuilt. Native bootm/gzip/cold8/fallback PASS.
- **Hardware v9 завершён:** UI_STATE_TRACE_v9_RESULT.json.44state samples,
  first1->0, last_sig2760972902 stable, idle_ticks increments/wraps,
  transition3/carousel13/animation1; toast/screenshot/USB/migration0.
  Runs/returns до12240, videos1/backend1. Реальная idle redraw-elision согласуется
  со static branch; **single callback не является доказанным дефектом**.
- Native restore/watchdog stock MTP/6boot and3protected UI hashes PASS,
  host boot cleanup writes=false. Камеры не использовались; visual НЕ accepted.
- **Следующий distinct experiment:** matching first-frame read-back из mapped DRM
  buffer и active scanout descriptor/DMA. Не подменять physical visual proof
  цифровыми hashes. Не менять flags/input/time и не force redraw ради счётчика.

## Актуальное продолжение 2026-11-15 (приоритет над историей ниже)

- **Камеры запрещены пользователем.** Не открывать и не заявлять visual UI PASS.
- Git верхнего уровня уже инициализирован; держать sources/plans/acceptance summaries
  актуальными по AGENTS.md. Payload, binary/runtime, raw captures и секреты local-only.
- Hardware accepted slices: DRM scanout (KMS v5 IRQ-fix), silent ALSA DMA v3,
  двусторонний USB CDC v4, headless Gambatte/FCEUmm, glibc video backend v3.
  Это отдельные срезы, НЕ совместная приёмка UI/game/audio/input/MTP.
- UI v7: core loaded, backend frames=1; missing legacy framebuffer errors.
  Причинность не доказана. V6 измерил main nanosleep ~14.5ms: не long-timer stall.
- Существующие ui_core_trace_test_v1/harness, synthetic core и trace-v1 повторно
  исполнены БЕЗ rebuild через actual saved console glibc в QEMU-user. Контроль
  без preload и наблюдение с preload PASS; все runtime/artifact hashes совпали.
  UI_CORE_TRACE_FORWARDING_VERIFIED.json; raw ui_core_trace_verify_v2/result.json.
  Это synthetic forwarding, НЕ выполнение настоящего FrogUI/железная приёмка.
- Новое: opt-in R36_UI_CORE_TRACE, только дочерний LD_PRELOAD, несовместим с
  R36_UI_TIME_TRACE. Нейтральный SysV input, SD RO, settings-copy в RAM, 16s window.
- Новый payload/kernel_ui_core_trace_v8: только PID1 rebuild; initramfs34348B
  в исходном40023B slot kernel_display_kms_vm_v6_irqfix. Патч от v7 отказал
  (34348>34325) без output; использован original verified source, код ядра неизменен.
  DRM backend и trace library переиспользованы. Cold wrapper kernel_cold_ui_core_trace_v8,
  bootm/gzip, cold emulation/native fallback, ELF/flat/hash reversal PASS.
- Офлайн pytest:219 passed,9 skipped (Windows отсутствует native Linux C runtime);
  первый прогон218 passed/1 failed/9 skipped: устаревшая проверка #ifdef заменена
  на equivalent exclusive #elif opt-in, production safety не ослаблена.
- **Hardware trace v8 завершён:** UI_CORE_TRACE_v8_RESULT.json. На реальной
  Linux7 retro_run entry/return до12420, videos=1. Первый callback640x480/RGB565
  непустой:585299bytes, FNV1a0f4e3334; DRM submitted1. В этом instrumented trial
  frontend loop продолжает работать, core не выдаёт следующие callbacks.
  Не считать run count benchmark: preload может влиять на тайминги.
- Watchdog/native restore/stock MTP/6boot hashes PASS, host boot cleanup writes=false;
  picoarch/core/settings hashes до/после совпали. RSS8656kB/swap0, child exit0.
  Камера не использовалась, visual/navigation/audio не приняты.
- **Следующий шаг:** actual FrogUI retro_run draw conditions, initialization/worker
  state и legacy framebuffer path. Missing-fb errors остаются, sole cause не доказана.
  Не повторять unchanged trial, не подменять fb ioctl/dummy success и не clamp timers.

Актуальная единая очередь: REMAINING_AND_TESTS.ru.md — интерфейс, кнопки,
звук, эмуляторы, **USB**, ФС и питание. USB CDC Linux7 принят отдельно;
MTP при возврате в stock не является подтверждением MTP Linux7.

Ниже сохранена история; старые запреты/разрешения доступа и pending-статусы
не перекрывают этот раздел и более поздние измеренные отчёты.

## Offline USB и emulator-backend 2026-11-14

- USB private glue patch: удалены Linux IRQ-depth platform callbacks и trailing
  disable_irq. Core owns request_irq/controller masks; stop calls disable under
  musb->lock, синхронный disable_irq мог ждать ISR на том же lock. Контракт
  optional callbacks и source anchor/idempotence/failure checks проверены.
  Это статический дефект, не подтверждённая причина старого enumeration failure.
- --usb-probe isolated kernel build в owned VM: USB0 peripheral/PIO/PHY/CDC ACM,
  USB1 disabled, нет UART/input/audio/display takeover/host/MTP/mass-storage.
  usb_cdc_init.c ждёт UDC bounded, отказывается выбирать среди нескольких,
  отвечает PING/PONG32hex, через12с unbind и пишет fresh SD report, watchdog не трогает.
- usb_cdc_host.py открывает только explicit COM с exact VID/PID/serial и требует
 3 random challenge replies. Configfs bind/device ping count НЕ заменяют host proof.
  Сам tool офлайн не запускался, устройства/микрофон/камера не открывались.
- fetch_usb_build.py strict allowlist/config/ELF/initramfs/provenance checks ready;
  аппаратная enumeration и двусторонняя передача ещё НЕ приняты.
- emulator_backend_smoke_v1/suite.json PASS:4 real unchanged MIPS cores x2 modes,
 120 frames через libretro1555/8888/565 conversion + real new video backend/scaler.
  Только DRM ioctls/device mocked, production driver library не подменяется.
-186 full pytest PASS на момент первого полного прогона, затем добавлены configfs
  syscall-model setup test и USB result tests; общий прогон повторить.

## Offline input/emulator acceptance 2026-11-14

Пользователь временно не может подключить консоль: звук отложен в
AUDIO_TEST_TODO.ru.md, не опрашивать MTP/не записывать микрофон.

- keys_evdev_sysv_integration_v3.json:8 настоящих Linux uinput/evdev/SysV случаев
  PASS, включая initial held state/2sources/alias/release/disconnect cleanup.
- keys_core_integration_v1.json: native Linux publisher -> actual SysV word ->
  real MIPS Gambatte -> synthetic Game Boy CPU program, press/release PASS.
  MIPS publisher through QEMU-user EVIOCGID returns ENOTTY: do NOT claim end-to-end
  native MIPS input or physical serializer acceptance from the host test.
- emulator_smoke_v3/suite.json:4 unchanged cores (Gambatte/Gearboy/FCEUmm/QuickNES),
 120 frames x2 modes (A press-release/neutral), real video/nonzero PCM/input callbacks,
  ROM RAM flags, save-state/mutate/restore PASS.8 execution cases, not just dlopen.
- Original synthetic GB/NES ROM sources make_synthetic_roms.py; no commercial
  ROM/BIOS copied. Runtime MIPS Debian libraries from existing local sysroot/btbundle,
  not actual console userspace. No speed/real games/hardware claim.
- calibrate_legacy_keys.py requires fresh complete capture and human labels of
  press event ordinals with subsequent release. Never guesses serial bit order.
-173 pytest PASS. Full UI/picoarch launch/new-kernel GPIO still pending device access.

## Frontend/input/audio continuation 2026-11-14

Состояние: FRONTEND_PORT_STATUS.json. Не путать готовые compatibility components
с запуском полного интерфейса.

- Новый video_drm_backend.c собран glibc/MIPS hard-float в
  analysis/driver_port/driver_r36_drm_video_v2.so. Обязательные3 video exports
  подтверждены статическим caller ABI; optional g_render/GE/sound отсутствуют.
  Это реальный DRM submit и RGB565 scaler, не dummy-success. Actual-source mocked
  DRM test и MIPS glibc dlopen/error-path PASS. Hardware library submit/UI НЕ tested.
- legacy_keys.c — новый evdev->SysV4B publisher, явная calibrated mapping,
  exclusive segment и release-on-fault. Конфликты между источниками/alias keys,
  repeat и bounds проверены host C tests. Реальный serial order неизвестен.
- Отдельный r36-display-input.dts исключает power/LCD/amp/audio pins и USB.
  Raw serial positions BTN_TRIGGER_HAPPY1..12, directGPIO2/7/11. Input-probe kernel
  собран и cold rollback проверен. Hardware попытка остановилась на missing MTP
  ДО upload и изменения boot-файлов; ничего не запускалось.
- Native ALSA source staged audio_driver_source_v1: actual PCM/IRQ/DMA logic,
  syscore speaker policy удалена, gain0/mute, explicit allow_takeover и DT disabled.
  GPIO19/15 и единоличное владение AVP audio требуют отдельной проверки.
  VM compilation started with --audio-source; completion receipt required.
- Новые flags --input-probe/--audio-source по умолчанию off. Verified display
  candidate/frozen bundle/companion UI sources не менялись.144 pytest PASS,
  ещё новый audio archive opt-in test добавлен после этого прогона.

Следующие реальные шаги: восстановить MTP, принять input inventory/physical serial
mapping; независимо проверить backend harness на DRM, потом прежний picoarch с
PICOARCH_DRIVER. Audio loader picoarch отдельный: video override не заменяет звук.
Нельзя экспортировать заглушки sound_driver_* ради фиктивного запуска UI.

## Цель и текущая граница

Сохраняется существующий TreeFrogUI: picoarch + frogui_libretro.so, настройки,
шрифты и изображения. Реальный интерфейс под Linux7 пока не запущен. Успех
минимального NOR-старта/PID1/SD не означает готовность экрана, аудио или кнопок.

Пользователь отложил доступ к консоли («Пока без консоли»). После этого новые
образы на устройство не устанавливались; выполняются локальные сборки и проверки.

## Подтверждённый stock ABI

Источник: native read-only probe на stock4.4 #23:
`runtime_20261113T041911Z/inventory.txt`. Программа успешно выполнена на консоли,
все GET-ioctl framebuffer вернули0. Это измерение stock, не драйверный PASS Linux7.

| Объект | Измерение |
|---|---|
| UI | /cubegm/picoarch + /cubegm/cores/frogui_libretro.so |
| Backend | driver_gb350.so; активен также tfshim_gb350.so |
| fb0 |640x480, RGB565, pitch1280, phys0x02f92000,14749264B |
| fb1 |640x480, ARGB8888, pitch2560, phys0x01a00000,1228800B |
| GE | /dev/ge, MMIO18806000; в maps также offset01980000/length3c000 |
| Кнопки | /proc/bus/input/devices пуст; cubevol читает GPIO и публикует SysV shm |
| Звук | штатные /dev/sndC0i2so и /dev/auddec, не ALSA /proc/asound |

FB1 находится внутри обычного Linux RAM-диапазона. В новых диагностических DTB
зарезервированы0x01a00000/0x12c000 и консервативно наблюдавшийся GE mmap-диапазон
0x01980000/0x3c000. Последний ещё требует подтверждения device mmap semantics;
это исключение из allocator, а не запись в неподтверждённые регистры GE.

В минимальном frozen kernel `CONFIG_SYSVIPC` выключен. Для совместимого UI нужны
SysV shm/messages/semaphores; в новом source-build profile этот параметр включён.
В frozen kernel уже включён MIPS_FP_SUPPORT; запуск существующего hard-float UI
всё равно требует собственной аппаратной проверки.

Статический ELF inventory: `UI_ABI.json`. Поиск DWARF-прототипов высокоуровневых
экспортов не дал их типов: `DRIVER_UI_SIGNATURES.json` явно содержит missing.
Три сигнатуры документированы рабочим tfshim.c: video_driver_disp_frame,
sound_driver_init, sound_driver_playframe. Остальные нельзя заменять догадками.

## Первый реализуемый срез: AVP transport

`scripts/kernel_lab/amprpc_driver/r36_amprpc_poll.c` — настоящий исходник
polling-драйвера с coherent DMA packet и sysfs-диагностикой. Это не generic ioctl
proxy и не готовая реализация всех AVP-устройств.

- Probe только проверяет ресурсы, отображает MMIO, выделяет одну страницу;
  обращение к peer не выполняется автоматически.
- DT compatible r36lab,amprpc-poll; два точных ресурса18800800/100 и18866800/100.
  Node в source-build DTB по умолчанию disabled.
- test_roundtrip принимает только1 и посылает один open заведомо отсутствующего
  имени. Запись GPIO/DSI/audio/persistentmem/standby не производится.
- Неподходящая группа pending, чужой packet pointer, неверные state/opcode,
  timeout дают отказ. Callback function pointers не вызываются.
- Диагностика одноразовая. Опубликованная DMA-страница не перерабатывается после
  timeout/unload: peer ещё может держать её адрес. Она сохраняется до reset.
- sysfs last_result показывает состояние NOT_RUN/результат, а не фиктивный успех.

`scripts/peripheral_lab/avp_probe.c` — независимый userspace bring-up клиент.
В stock разрешён только --inspect. Отправка запроса разрешена только в собственном
Linux7 PID1. Anonymous page pinning, pagemap и cacheflush дают общий physical
packet; обращение идёт через uncached /dev/mem mapping. Результат записывается
на SD; packet остаётся закреплённым до watchdog reset.

Первый cold-пробник работает на уже проверенном kernel code с заменённым только
встроенным initramfs: `kernel_avp_probe_profile_v3`, wrapper `kernel_cold_avp_probe_v3`.
Kernel ELF и flat image патчатся согласованно, меняются только gzip blob и его
length word; старые RAM-handoff .ko/ctl и stale compressed kernel не копируются.
Это не полный rebuild kernel и не UI-совместимый kernel: SYSVIPC в нём остаётся
как в frozen baseline. Он нужен для изоляции проверки AVP.

Cold wrapper сохраняет раннее восстановление stock-файла и native backup bootm
при отказе. Все новые кандидаты имеют hardware_verified=false/deployed=false.

## Готовые offline artifacts

| Каталог в payload | Назначение |
|---|---|
| kernel_cold_avp_probe_v3 | Изоляция userspace RPC на прежнем проверенном kernel code; новый init и display reservations |
| kernel_port_avp_vm_v1 | Полный source build7.2.0-rc5-r36port, SYSVIPC=y, userspace test, kernel RPC node disabled |
| kernel_port_avp_module_vm_v1 | Тот же kernel/module ABI; RPC node okay, init argument --kernel-probe, extra SD file r36_amprpc_poll.ko |
| kernel_cold_port_avp_vm_v1 | Зашифрованный NOR wrapper source-build userspace профиля |
| kernel_cold_port_avp_module_vm_v1 | Зашифрованный NOR wrapper kernel-module профиля |

Source-build kernel SHA256990e005eb3035748e6440849ca2dbe178f2c40358da6538017f6cd5ed0f51c2d.
Module SHA256b28ee39a05f9f9a8852227973d605332963c85300045df2787c7bbc2dbcfeeda,
vermagic `7.2.0-rc5-r36port mod_unload MIPS32_R2 32BIT`.
Build receipt: payload/kernel_port_avp_vm_v1/build_receipt.json.

В module-mode PID1 не отображает mailbox MMIO сам: он загружает соответствующий
модуль и работает только через sysfs. Таким образом, userspace и kernel client
не управляют одним mailbox одновременно. После записи log закрываются оба SD
stdout/stderr descriptor, затем SD синхронизируется и размонтируется/переводитсяRO.
PASS userspace/kernel разбираются раздельно по полным строкам, fresh run_id и footer;
старая, обрезанная или смешанная запись не даёт аппаратного PASS.

## Проверки первого среза

- Packet builder `amprpc-open-wire.h` побайтно совпал с исполнением оригинального
  avp_open0x802bad04 в7 сценариях, включая границу4096B и отказ oversized path.
  `amprpc_open_wire_verified.json`. Это wire-construction oracle, не ответ AVP.
- Существующий mailbox planner сверяется с оригинальным ISR, включая wrong-group
  pending. Crypto + planner:48 pytest PASS с отдельным basetemp в analysis.
- Для `kernel_cold_avp_probe_v3` и обоих source-build cold wrappers прошли original bootm/header/CRC/gzip,
  pre-kernel restore + real kernel head до start_kernel и native-decrypt fallback.
- profile_validation.json подтверждает init в newc archive, patch bounds,
  совпадение ELF/flat, framebuffer reservations и неизменность всех frozen hashes.
-4 ELF normalization regression tests и4 acceptance parser tests прошли;
  вместе с crypto/planner это56 pytest checks, плюс7 native open-wire cases.
- Userspace RPC, kernel RPC module и фактический AVP response под Linux7 пока
  не проверены на устройстве.

## Порядок дальнейшего переноса

1. Read-only snapshot mailbox на stock, затем один isolated Linux7 open-negative
   roundtrip, проверка state/ack/coherency и автоматического возврата. После этого
   sysfs-тест kernel module на точно соответствующем kernel build.
2. Экран: наследовать panel/MIPI timings от загрузчика; сверить layer descriptors,
   владение fb0/fb1/GE и read-only framebuffer info. Первый вывод — тестовая
   RGB565-картинка с read-back; затем framebuffer/DRM backend для прежнего UI.
3. Звук: восстановить typed ioctl/kshm/mmz либо адаптировать native I2S/ALSA.
   CS4344/left-justified и GPIO3/4/5 подтверждены нашим DTB. Native reference
   зависит от другого syscore firmware для amplifier: его нельзя подключать
   без адаптации. Speaker GPIO19/headphone15 и mute проверяются отдельно.
4. Кнопки: GPIO data9/clock8, плечевые11/7, volume12/13, FN2, power14. Нужна
   проверка каждого serialized bit и timing на нашей плате. Для прежнего picoarch
   потребуется совместимый publisher ftok(/tmp/joy_key,'a')/4B; B=0x4000 из tfkey.c.
   Evdev сам по себе не заменяет этот consumer ABI.
5. USB: сначала CDC/командный диагностический канал, затем FunctionFS/MTP;
   старые kernel4.4 gadget modules в Linux7 не переносятся бинарно. Host/OTG —
   отдельная реализация, upstream glue поддерживает только peripheral/PIO.
6. Backlight, ADC/battery, headphone/amp, корректные shutdown/sleep и чистая FAT
   handover. Power latchGPIO1 и LCD resetGPIO6 не трогать как часть кнопочного теста.
7. Финальная совместная приёмка прежнего UI, навигации, звука, игр, saves, USB,
   idle/sleep/restart, длительного SD/DMA/IRQ прогона и полного power-off/on.

Нельзя blindly forward ioctl по _IOC_SIZE: вложенные pointers и bare legacy
команды требуют известной схемы. Нельзя возвращать0 из неработающих методов,
чтобы объявить UI портированным.

## Исходники и сборка

Найдена публичная native реализация DRM/GE/I2S/input:
https://github.com/csnewman/gb350-linux, pinned bff93e84fe79c9e67bde284dfe4d58054b62282b.
Reference checkout: analysis/gb350-linux-reference, без правок. BoardGB350 v1.22
имеет256MiB; наша плата128MiB и другие boot aliases. Релиз/DTB/AVP firmware оттуда
на нашу карту не устанавливались. Наличие исходника — не hardware PASS нашей платы.

Сборка userspace доступна напрямую на Windows через Zig0.17, target
mipsel-linux.4.4-musleabi/-march=mips32r2/-msoft-float. Статический inventory
прошёл на настоящем stock. Shared backend для старого glibc UI требует отдельного
согласованного ABI; статические musl tools не являются LD_PRELOAD библиотеками.

WSL ubmips по-прежнему StopPending, её процессы не перезапускались. Отдельная
workspace-owned Alpine/QEMU/WHPX build VM имеет native clang20 и GNU MIPS as2.44.
GNU assembler нужен из-за unsupported forward-immediate expressions genex.S в
LLVM integrated assembler. Изменение kernel exception code для обхода не делалось.
modules_prepare генерирует module.lds перед external module final link.
LLD оставлял PT_LOAD file span поверх trailing NOBITS. Packager проверяет точное
совпадение initialized prefix, отсутствие initialized sections в отбрасываемом
хвосте и корректирует толькоp_filesz; p_memsz/код сохраняются. Четыре regression
tests проверяют этот случай, GNU layout и отказ при несовпадающих/initialized данных.
VM descriptors/ключи/PID: analysis/kernel_build_vm_v1/state.json; SSH только
127.0.0.1:22222. HTTP отдаёт только allowlisted boot resources, не каталог с ключом.

Перенос UI source не выполнялся в пустом detached frogui submodule. Сначала
сохраняется existing binary/asset ABI через новый backend/совместимые сервисы;
изменения самих companion source trees требуют их canonical checkout по AGENTS.md.

## Hardware continuation 2026-11-14

Пользователь разрешил watchdog-опыты и приватную локальную камеру.
Пассивный snapshot аппаратно PASS; cold trials KMS v1/v2/v3/v4 всегда вернули
штатное ядро и MTP,6 boot hashes исходные без host cleanup writes.

- v1: DRM probe отказал на panel-timing. Исправлено DT width-mm/height-mm=0
  (размеры неизвестны, значения не выдумываются) в display_driver_source_v4.
- v2: card0 зарегистрирована, EFAULT userspace. Исправлены props/value arrays
  второго GETCONNECTOR и включён64-bit off_t; added checked_ioctl stage reports.
- v3/v4: SETCRTC и WAIT_VBLANK rc0, active descriptor02f90400, pixels01500000,
  RGB565/640x480/pitch1280, timing stable, flip_timeouts0. V4 камера с exposure-6
  показала цветные полосы и последующий возврат штатного меню. Private evidence:
  display_visual_kms_v4.json. Полный scanout PASS false: IRQ counters0, до hash
  не дошли. Не выдавать изображение за полную UI/DRM приёмку.
- Root cause IRQ accounting статически подтверждён: irq-hc16xx-intc.c использует
  handle_percpu_irq для device lines, tot_count остаётся0; proc.c подавляет counts.
  Overlay изменяет mapping на handle_simple_irq без MMIO/ack изменений.
- Новый отдельный кандидат kernel_display_vm_v6_irqfix / KMS variant и cold
  kernel_cold_display_kms_v5_irqfix **аппаратно PASS**: display IRQ2->18/MMC213/ERR0,
  CPU/DMA pixel hashes8d21d5c5, scanout PASS. Камера подтвердила полосы и возврат
  штатного меню. DISPLAY_HARDWARE_VERIFIED.json; watchdog30с вернул stock/MTP,
 6 boot hashes исходные, host_cleanup_wrote_boot_file=false. Не full UI acceptance.
 137 pytest PASS; actual built irq source SHA256
  356a97acc25f3691b1554a06ec414206dc3e6b8d50ef25932529572863acc16d.

Авто-fsck: новые исходники/статический CP437 fsck, regular-image tests и staged
RAM PID1 готовы частично. Production writer disabled, в kernel не встроено:
analysis/driver_port/fat_boot_guard_STATUS.json. Пользователю не обещать уже
установленное самовосстановление. Watchdog check-only сохраняется, writer нельзя
прерывать таймером; предварительная аппаратная приёмка обязательна.

## Продолжение после последней OpenCode-сессии, 2026-11-13

Сессия OpenCode проверена read-only в локальной opencode.db; последняя работа —
`display_driver_source_v3` и `display_probe.c`. Продолжение довело незавершённые
сборочные проверки до сохранённых результатов, без доступа к консоли:

- Возобновлена существующая QEMU VM, ext4 диск подключён без форматирования.
  WSL теперь отвечает, но сборка использует прежний clang20/GNU as в VM.
- MIPS pattern selftest реально выполнен `qemu-mipsel -cpu 74Kf`: PASS/exit0.
  `analysis/driver_port/display_qemu_selftest_20261113.json`. Это НЕ эмуляция DE/DSI.
- После остановки VM обнаружены zero-length archive/exit/object files. Первое
  пересобранное ядро с пустым DRM .o было отклонено по отсутствию .r36abi.
  `payload/kernel_display_vm_v1/VALIDATION_FAILED.json`: **не использовать**.
- `vm_build_kernel.sh` теперь чистит внешние modules, проверяет gzip и выполняет
  sync до объявления завершения. Чистая повторная сборка exit0.
- `payload/kernel_display_vm_v2/build_receipt.json`: Linux7.2.0-rc5-r36disp #7,
  kernel SHA256b694948abe6fdb75c55507d9358b5dd417dadad97b38d8d944e5b4ac4178d20a,
  DRM module963e2b4c38d4b273a6fa184f680729bd4c82a384eca24d916de7e004131627a8.
 110 module imports найдены в kernel exports, MIPS probe/module ioctl ABI совпали,
  embedded initramfs/ELF/flat/source hashes/DT проверены.
- `kernel_display_vm_v2` пассивный: display/RPC disabled. Отдельный
  `kernel_display_kms_vm_v2`: explicit --display-kms-probe, display okay,
  RPC disabled, extra device file r36_hc16xx_drm.ko. KMS hardware не запускался.
- Новый fetcher `scripts/peripheral_lab/fetch_display_build.py` проверяет архив
  allowlist, hashes, provenance, exports, ioctl ABI и профиль.102 pytest PASS для
  kernel_lab+peripheral_lab с реальными artifacts; отдельно14 crypto tests PASS.
- `payload/kernel_cold_display_passive_v1`: bootm/header/gzip PASS;8 cold
  success/fault scenarios и native-decrypt fallback PASS. Реальный kernel head
  достигает start_kernel в Unicorn; file APIs заменены stubs.
- Все62 frozen bundle artifact hashes неизменны. Ничего не установлено на консоль.

Следующий аппаратный шаг: согласовать доступ к устройству, сначала пассивный
snapshot display в stock/собственном ядре, затем отдельно KMS.
В run_restored_cold_trial.py добавлены очистка stale display report и сбор
r36-display-probe.txt; peripheral_result.display_result проверяет fresh run_id,
полный footer/probe_rc, release, отдельный passive/KMS режим, load/modeset,
совпадение DMA/CPU hash, рост IRQ и raster_progress. Старые/обрезанные/смешанные
результаты отвергаются. Физическое изображение всегда NOT_TESTED без отдельной
визуальной приёмки. Последний общий прогон kernel/peripheral/crypto:130 PASS.
Сам cold boot proof ещё не означает display PASS. Визуальное подтверждение панели
и прежний UI не заменяются совпадением DMA/CPU pixel hash.
