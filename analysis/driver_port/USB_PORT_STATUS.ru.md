# USB Linux7: офлайн-подготовка и аппаратная граница

Актуально 2026-11-14. Консоль временно недоступна; здесь выполнялись только
локальные тесты/сборки. USB Linux7 НЕ объявляется работающим. MTP после watchdog
возврата принадлежит stock4.4 и не подтверждает новый gadget.

## Исправлено в private overlay

`scripts/kernel_lab/usb_overlay.py` удаляет из HC16xx MUSB glue:

- platform enable/disable wrappers, которые только вызывают Linux enable_irq /
  disable_irq, не управляя отдельными SoC регистрами;
- дополнительный disable_irq после platform_device_add дочернего MUSB.

Основание: pinned musb_core.c сам маскирует контроллер; platform callbacks
необязательны в musb_core.h. musb_gadget_stop держит musb->lock, а musb_stop вызывает
platform_disable. Синхронный disable_irq может ждать ISR, который тоже берёт
musb->lock. Менять IRQ-depth при каждом platform callback не требуется.

Это статически установленный опасный lifecycle, **не доказательство**, что именно
он вызывал все прежние enumeration failures. PHY/VBUS/UTMI/reset/EP0 и FIFO ещё
требуют реальной приёмки. Не включались host, DMA или OTG под видом исправления.

Patch строгий к исходнику и повторяемый: при неизвестном callback/anchor отказ,
при повторной интеграции no-op. Исходные upstream/reference repos не публикуются.

## Новый диагностический кандидат

- `scripts/kernel_lab/r36-usb-cdc.dts`: USB0 peripheral, USB1 disabled; общая память
  AVP/старые framebuffer regions сохраняются. Нет display/audio/input takeover.
- `scripts/peripheral_lab/usb_cdc_init.c`: статический RAM PID1; configfs и одна
  функция CDC ACM. Проверка ошибки каждой операции, ожидание UDC до3с; несколько
  UDC — отказ, а не выбор случайного контроллера.
- Модель устройства Linux Foundation VID1d6b/PID0104, serialR36LAB-CDC-DIAG,
  manufacturerR36Lab. Только локальный диагностический опыт; не production USB-ID
  allocation и не попытка выдать устройство за коммерческий продукт.
-12с окно команд PING32hex -> PONG32hex. Нет shell/reboot/writable LUN/host-mode,
  init не кормит и не выключает аппаратный watchdog. После окна unbind и запись
  fresh SD proof/report/interrupts, sync+unmount; затем ожидание watchdog-return.
- `fetch_usb_build.py`: allowlist archive, hash, static MIPS32LE PID1, embedded
  initramfs, exact kernel load layout, config gadget-only/PIO/PHY/ACM, отключённые
  другие роли/клиенты, проверка фактического glue build source.
- Исходники syscall-model tests проверяют настоящий setup C-фрагмент: все этапы
  отказа, delayed/missing/ambiguous UDC. Эти тесты НЕ моделируют USB-транзакции.

Первая сборка exit0 была отклонена preflight: CONFIG_INPUT=y, несмотря на
задуманную изоляцию. Причина: USB включил TTY, оставшийся VT выбирал INPUT;
HID был дополнительной ненужной подсистемой. kernel_usb_cdc_vm_v1 имеет
VALIDATION_FAILED.json, **не использовать**. Private USB profile теперь явно
EXPERT=y/VT=n/HID=n/INPUT=n, с assertion до компиляции.
Финальный комплект **kernel_usb_cdc_vm_v2/build_receipt.json PASS**: build exit0,
static PID1, ELF/flat/hash/initramfs/config/USB isolation/glue source проверены.
Kernel SHA25694684c56a72ab07d7fc1d5a53937905fce4b1fa14027a732b3da87cea2fc1b43.
Hardware/deployed/enumeration/bidirectional=false. Папка kernel_usb_cdc_vm_v2 —
source build profile, не cold deploy target.

## Cold wrapper: проверено офлайн 2026-11-15

`payload/kernel_cold_usb_cdc_v1/OFFLINE_VERIFIED.json`: early restoration,
watchdog30с, stock fallback; candidate SHA256
a9e836992ad0e8c363a1d9d5d34500f33e874a7b3332bd00832f39843337ebb0,
tag0xc840b04c. Native header/CRC/gzip и normal path до start_kernel PASS,
8 success/fault scenarios и отдельный native-decrypt fallback PASS.193 pytest PASS.
Исходные артефакты проверены по hashes, frozen62 files неизменны.

File APIs в эмуляции заменены моделью; физический watchdog/USB/реальная SD этим
не проверены. Hardware_verified=false, deployed=false. Установка запрещена без
отдельного доступа к консоли и preflight. In-place restore boot-файла не является
атомарной транзакцией на случай пропадания питания.

## Аппаратный результат 2026-11-15

**CDC peripheral HARDWARE PASS:** USB_CDC_HARDWARE_VERIFIED.json.
Candidate kernel_cold_usb_cdc_v4, exact present Windows devnode COM12,
3 random PING/PONG, console114received/114sent/3pings,bind/unbind0.
Watchdog вернул stock/MTP,6 boot hashes исходные, native restore verified,
host_cleanup_wrote_boot_file=false. Это НЕ MTP/host/OTG/background acceptance.

## Офлайн-подготовка композитного гаджета `MTP + ADB` (`FunctionFS`) 2026-11-17

- Проверен аппаратный бюджет FIFO в `drivers/usb/musb/hc16xx.c` (`hc16xx_fifo_cfg`):
  доступно `5 FIFO_TX` (`ep1in..ep5in`, 512 B) и `5 FIFO_RX` (`ep1out..ep5out`, 512 B).
  Композитный гаджет `ffs.mtp` (`2 TX + 1 RX`) + `ffs.adb` (`1 TX + 1 RX`) при
  штатном `VID 0x18d1 / PID 0x4e22` укладывается в `3 TX + 2 RX <= 5 TX + 5 RX`.
- Реализован `scripts/peripheral_lab/usb_ffs_mtp_adb.h`:
  - `FunctionFS` v2 дескрипторы и строки для `ffs.mtp` (FS/HS + Microsoft OS
    Extended Compat ID `"MTP"` для автопривязки Windows `WpdMtpDr`) и `ffs.adb`
    (`Class 0xFF, SubClass 0x42, Protocol 0x01`, `"ADB Interface"`), включая
    инициализаторы `r36_ffs_init_mtp_ep0` и `r36_ffs_init_adb_ep0`.
  - Userspace-отправка файлов `r36_mtp_ffs_send_file_with_header` поверх `ep_in`
    (заменяет ядерный `ioctl(MTP_SEND_FILE_WITH_HEADER)` старого `usb_f_mtp.ko`
    при переносе `tfmtp` на Linux 7.2 `FunctionFS`).
  - Пакетный уровень и конечный автомат сессии `ADB` (`CNXN -> OPEN -> WRTE ->
    OKAY -> CLSE`, проверка `magic` и контрольной суммы).
- Добавлен тест `scripts/peripheral_lab/test_usb_ffs_mtp_adb.py` (нативная C-проверка
  и кросс-компиляция `zig cc -target mipsel-linux.4.4-musleabi -Werror`): PASS.
- Реализован полный композитный сервис `scripts/peripheral_lab/usb_mtp_adb_service.c`
  и включён `--enable USB_CONFIGFS_F_FS` в `scripts/peripheral_lab/vm_build_kernel.sh`:
  - Настройка `configfs` (`/sys/kernel/config/usb_gadget/r36composite`,
    `0x18d1:0x4e22`, OS descriptors `MSFT100`), создание и линковка `functions/ffs.mtp`
    и `functions/ffs.adb`, монтирование `functionfs` в `/dev/ffs-mtp` и `/dev/ffs-adb`.
  - Строгий порядок инициализации (`f_fs.c`): запись `FunctionFS` v2 дескрипторов и
    строк в оба `ep0` и открытие всех 5 дата-endpoint'ов (`/dev/ffs-mtp/ep1..3`,
    `/dev/ffs-adb/ep1..2`) **до** привязки `UDC` (`musb-hdrc.0.auto`), плюс чистый
    `r36_teardown_mtp_adb_gadget`.
  - Мультиплексированный цикл `r36_mtp_adb_poll_once`, одновременно обслуживающий
    контейнеры `MTP`/`tfmtp` (`OpenSession`, `CloseSession`, `GetDeviceInfo`,
    `GetStorageIDs`, `GetStorageInfo`, `GetObjectHandles`, `GetObjectInfo`,
    `GetObject`, `GetPartialObject`, `SendObjectInfo`, `SendObject`,
    `DeleteObject`, `OP_TF_Info`) с авто-выбором транспорта
    (`r36_open_mtp_transport`: `FunctionFS` `/dev/ffs-mtp` на Linux 7.2 либо
    legacy `/dev/mtp_usb` на stock 4.4) и сессии `ADB` (`CNXN`, `OPEN("shell:...")`,
    `OPEN("sync:")` с файловыми операциями `SEND`/`adb push`, `STAT`,
    `RECV`/`adb pull`, `QUIT` и защитой от обхода путей `..`).
  - Проверены отказ на каждом шаге инициализации, отсутствие/неоднозначность `UDC`,
    полный цикл файловых операций `MTP` + одновременный `ADB` и кросс-сборка MIPS32r2.
    Аппаратная приёмка `MTP + ADB` на консоли впереди.

## Офлайн-подготовка USB OTG Host + Wi-Fi + Bluetooth 2026-11-17

- Проанализирован upstream-glue `drivers/usb/musb/hc16xx.c` (`payload/kernel_usb_cdc_vm_v2/build_usb_glue.c`)
  и найдены 4 дефекта, блокировавшие Host/OTG:
  1. `hc16xx_set_phy_power()` читал/писал `USB_O_UTMI` (`0x380`) через 32-бит `readl`/`writel`
     (задевая `USB_O_VBUS` `0x381`) и ориентировался на `glue->musb->is_host` до её установки,
     возвращая `UTMI_PERIPHERAL_MODE` (`0x9c`).
  2. `hc16xx_musb_set_mode()` не поддерживал `case MUSB_OTG:` (`-EOPNOTSUPP`) и не переключал
     бит `MUSB_DEVCTL_SESSION` для старта Host-сессии.
  3. `hc16xx_glue_probe()` жёстко назначал `platform_data = &hc16xx_musb_data` с `.mode = MUSB_PERIPHERAL`.
- В `scripts/kernel_lab/usb_overlay.py` добавлен `patch_musb_host_otg_support` (вызывается из
  `scripts/kernel_lab/integrate_ports.py`), устраняющий все 4 причины; добавлены
  `scripts/kernel_lab/r36-usb-otg.dts` (`usb0` `dr_mode = "otg"`, `usb1` `dr_mode = "host"`),
  флаг `R36_OTG_WIFI_BT=1` в `scripts/peripheral_lab/vm_build_kernel.sh` (Dual-Role MUSB,
  `CFG80211`/`MAC80211`/`RTL8XXXU`/`RTW88`/`MT7601U`/`RT2800USB`/`ATH9K_HTC`,
  `BT`/`BT_HCIBTUSB*` и упаковка `modules.tar.gz`) и userspace-зонд
  `scripts/peripheral_lab/usb_otg_wifi_bt_probe.h` (`r36_otg_set_role`, классификация,
  HCI `READ_BD_ADDR`, `wlan0` sysfs + `IFF_UP`). Проверено C-моделями и MIPS `zig cc`;
  физический тест с OTG-кабелем и реальными адаптерами будет возможен при включении консоли.

Первый hardware кандидат отказал ENOENT в configfs link: kern_path разрешает
relative target от syscall cwd, исправлен absolute target. Затем Windows watcher
сначала терял serial с дефисами, потом падал на PowerShell query timeout.
Прямой cfgmgr32 NORMAL lookup + DN_STARTED + exact instance + PortName решил
host detection без ослабления identity check. Все fail raw reports сохранены.

Ниже первоначальный план; пункты enumeration/roundtrip выполнены только в одном
изолированном CDC цикле, sustained/reconnect/file transfer остаются задачами.

## Отложенный аппаратный опыт

1. Подтвердить stock identity,6 hashes, fallback и watchdog. Отдельный новый cold
   wrapper, свежий run_id, не более одного запуска. Никакой записи в NOR.
2. Подтвердить UDC registration, IRQ, PHY и Windows enumeration. При провале
   дождаться watchdog и получить RAM log/SD report. Не выдавать USB disconnect
   старого gadget за успешный startup нового.
3. В диагностическом окне запустить `usb_cdc_host.py --port COMn --out NEW.json`.
   COM указывается явно; открывается только порт с точными VID/PID/serial, три
   независимых random PING/PONG. Ни Windows COM, ни камеры/микрофона офлайн не открывали.
4. Device report `r36-usb-cdc-probe.txt` не заменяет host report. Parser
   `usb_cdc_result` по одному bind даже с pings оставляет enumeration/bidirectional
   verified=false. Для полного PASS нужны согласованные host+device evidence,
   fresh run и подтверждённый stock-return/hashes.
5. После CDC: FunctionFS/MTP адаптация, большие каталоги/файлы/Unicode/checksum,
   disconnect/reconnect, UI/game coexistence. Старые4.4 .ko/tfmtp kernel ABI не подходят.
6. Host/OTG/VBUS/USB peripherals — отдельный перенос и тесты. Writable mass-storage
   нельзя включать на одновременно RW-mounted Linux FAT.

## Известные непроверенные участки

PHY код использует байтовые vendor regs, UTMI glue местами32-bit RMW; без точных
измерений не менять ширину/битовые значения наугад. Error return PHY power/mode,
clock/reset ownership, runtime suspend/resume, DMA/PIO throughput ещё не приняты.
USB diagnostic привязан к30с watchdog, не предназначен для fsck writer.
