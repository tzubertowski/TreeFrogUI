# Перенос драйверов HC16E310: фактическая матрица

## Обновление 2026-11-13

Прямой NOR-start минимального Linux7/PID1/SD прошёл после аппаратного reset;
подробности analysis/boot_crypto/COLD_BOOT.ru.md. Это не принятие UI/peripherals.
Затем снят новый read-only stock ABI inventory, подготовлены AVP polling client
и kernel diagnostic module. Полный source build `7.2.0-rc5-r36port`
и `r36_amprpc_poll.ko` собраны в изолированной QEMU/WHPX VM; SYSVIPC включён.
Module vermagic/ELF и image/header/gzip/entry проверены офлайн. **Аппаратного
AVP response/UI/display/audio/input PASS нет**: пользователь отложил консоль.

Актуальный план и artifact map: UI_PORT_PLAN.ru.md. Frozen kernel_ready и
существующий TreeFrogUI source/assets не изменялись. На SD новые port/probe images
не устанавливались после ответа «Пока без консоли».

## Основание

Сняты живые sysfs bindings, `/proc/devices`, IRQ, модули, dmesg и исходный DTB.
Снимки: `stock_*.txt`, `stock_dtb_nodes.json`; сбор —
`scripts/kernel_lab/inventory_drivers.py`.

В DTB 96 compatible-узлов, 70 включённых, 38 уникальных включённых compatible.
В живом platform bus 68 устройств. Присутствие compatible или файла драйвера
не означает, что устройство физически установлено или драйвер проверен.

Критерии статусов: **исходник** — код найден; **собран** — компиляция прошла;
**железо** — наблюдалась требуемая операция именно под нашим Linux 7.2.

## Матрица

| Подсистема / стоковый драйвер | Новый Linux / путь | Статус и недостающие проверки |
|---|---|---|
| CPU/MMU/cache/FPU | arch/mips/generic, MACH_HICHIP | Два замороженных минимальных профиля прошли до PID1 и вернулись автоматически; расширенные профили и нагрузка ещё не подтверждены |
| CPU IRQ + sys_irq | irq-mips-cpu.c, irq-hc16xx-intc.c | Исправлен SoC flow handle_percpu_irq->handle_simple_irq. KMS v5: display IRQ2->18, MMC213, ERR0; длительная IRQ-нагрузка ещё не испытана |
| CPU/SoC clocks | clk-hc16xx.c | Частичная реализация upstream-порта; в исходнике есть явно предположительные parent clocks |
| Reset controller | reset-hc16xx.c | Есть и собран; проверка отдельных периферийных resets впереди |
| Clocksource/clockevent | MIPS Count/Compare, csrc-r4k/cevt-r4k | Подтверждены clocksource MIPS, sched_clock594MHz, timer IRQ и ERR0 в минимальных профилях; длительный прогон впереди |
| UART/early console | 8250/of + ранний 8250 | Собран; физический UART на ПК не подключён |
| SD/MMC + block + vfat | dw_mmc + dw_mmc-pltfm | Подтверждены SDXC/mount/write/fsync и свежие proof в boot/driver; dirty-flag при warm handoff, IRQ accounting и нагрузка требуют доработки |
| USB0 peripheral | musb/hc16xx.c + phy-hichip-usb.c | HARDWARE CDC PASS:Windows exact present devnode COM12,3random PING/PONG,114B each direction,bind/unbind0; USB_CDC_HARDWARE_VERIFIED.json. MTP/host/OTG/background pending |
| USB1, USB host/OTG/DMA | тот же MUSB IP + `usb_overlay.py` + `r36-usb-otg.dts` + `usb_otg_wifi_bt_probe.h` | В private overlay (`patch_musb_host_otg_support`) исправлены 8-бит доступ к `USB_O_UTMI` (`0x380`), сохранение `role_mode`, импульс `MUSB_DEVCTL_SESSION` и проброс `pdata.mode` из `dr_mode`; добавлены `r36-usb-otg.dts` (`usb0=otg`, `usb1=host`), опции сборки `R36_OTG_WIFI_BT=1` (USB Wi-Fi/BT модули в `modules.tar.gz`) и зонд `usb_otg_wifi_bt_probe.h`; C-модели glue и BT/Wi-Fi PASS, аппаратная проверка с адаптером на консоли впереди |
| libcomposite, ACM/serial | стандартные Linux 7.2 gadget drivers | Один isolated CDC Windows roundtrip HARDWARE PASS,3 challenges; sustained/reconnect/UI coexistence ещё не приняты |
| MTP/PTP | stock usb_f_mtp/ptp + `usb_mtp_adb_service.c` (`FunctionFS`) | Старые `.ko` непригодны для 7.2; реализованы userspace `FunctionFS` v2 дескрипторы и полный цикл `tfmtp` (`GetStorageInfo`/`GetObjectHandles`/`GetObjectInfo`/`GetObject`/`GetPartialObject`/`SendObjectInfo`/`SendObject`/`DeleteObject`/`OP_TF_Info`) + авто-выбор `FunctionFS`/legacy `/dev/mtp_usb` и одновременный `ADB` (`usb_mtp_adb_service.c`), офлайн-тест PASS; аппаратная приёмка на консоли впереди |
| iAP/IUM | stock f_iap, f_ium, ium | Нет исходников в текущем дереве; необходимость для нашей ОС отдельно оценить |
| GPIO: четыре банка | gpio-hc16xx.c | Собран в отдельном input-профиле; на железе не проверен |
| Pinmux | pinctrl-hc16xx.c | Собран в input-профиле; pin names/значения проверить на железе |
| Кнопки/стики | gpio_serializer_keys.c + poll-only keys + legacy_keys SysV publisher | Console input inventory2devices PASS,events0/IRQERR2,physical pins/order/navigation not verified. Native VM evdev->SysV8 cases PASS; real SysV->MIPS Gambatte->synthetic ROM press/release PASS. MIPS publisher QEMU evdev ioctl ENOTTY, not accepted. Human-label calibration tool ready; physical calibration pending |
| PWM/backlight | pwm-hc16xx.c + pwm-backlight | Есть; владение PWM сейчас у AVP, необходима согласованная передача |
| ADC check_adc1/check_adc5 | наш hc16xx-adc-ro.c (IIO + `/dev/check_adc1`, `/dev/check_adc5`) + `adc_battery_osd.h` | Сохраняет passive IIO, добавлены calibrated char-узлы `miscdevice` без EOF при удержанном открытом fd и userspace-кривая `{64,153,180}->{0,50,100}%` + зарядка `>=64`; офлайн C-модель и тесты PASS, на железе ещё не проверялось |
| Перезапуск через watchdog | наш hc16xx-restart.c | Собран restart handler с включением watchdog clock; аппаратно пока не проверен |
| Полный watchdog /dev/watchdog | отсутствует | Неизвестны точные timing/prescaler semantics; одного restart callback недостаточно |
| AMPRPC mailbox, IRQ66 | r36_amprpc_poll + userspace bring-up client | Polling diagnostic собран под7.2-r36port; packet/ISR algorithms проверены оригинальным кодом. Hardware response, IRQ/callback/nested ioctl transport ещё не приняты |
| avp-proxy: 18 узлов | stock avp-proxy | Общая зависимость от AMPRPC; не 18 независимых законченных портов |
| virtuart | stock virtuart | Требуется AMPRPC и восстановление callback/poll ABI |
| kshmdev | stock kshmdev | Требуются формат кольца, coherency и shared-memory mapping |
| mmz | stock mmz | Требуются allocator ABI, регионы и mmap/cache rules; не отдавать AVP RAM обычному allocator Linux |
| fb0/fb1 | stock hcfb; r36_hc16xx_drm fixed-timing port | KMS v5 IRQ-fix HARDWARE PASS: SETCRTC/vblank/DMA pixel hashes8d21d5c5 совпали, IRQ2->18/ERR0, камера подтвердила полосы640x480RGB565. DISPLAY_HARDWARE_VERIFIED.json. Watchdog вернул stock/MTP,6 boot hashes целы. Не full UI/audio/input acceptance |
| GE/2D | stock hcge, reg18806000, IRQ4 | Нет исходника в новом дереве; нужно восстановить command queue + interrupt/mmap ABI |
| MIPI/панель | AVP mipi proxy, DSI1884a000 | DTB содержит panel/reset/init параметры, но DSI host ещё не реализован |
| Звук I2SO/CS4344 | native ALSA r36_hc16xx_i2s + `driver_r36_combined_backend.c` + `direct_keys_policy.h` | Silent DMA HARDWARE PASS: 24576 frames 48kStereoS16LE, gain0/mute1, IRQ0->41, DROP0/RUN0; `AUDIO_SILENT_HARDWARE_VERIFIED.json`. Офлайн реализованы объединённый видео+аудио `PICOARCH_DRIVER` и правило `GPIO19` amp / `GPIO15` HP-detect; аппаратная проверка слышимого звука и GPIO впереди |
| Аудио-/видеодекодеры, sinks, avsync | auddec/audsink/viddec/vidsink/avsync0 | Зависят от AVP transport, kshm/mmz и userspace ioctl ABI |
| HDMI, HDMI-RX, TV/PQ, VIN | AVP proxies | В Linux узлы есть, часть блоков выключена на AVP; перенос зависит от фактической надобности/железа |
| Standby/ZZd2C | AVP proxies | Нужны AMPRPC и точный ABI; GPIO power latch отдельно не трогается |
| SPI-NOR/SFSPI/MTD | stock hc_spi_sf, 25HD40 | Новый controller driver отсутствует; начальный перенос должен быть read-only |
| persistentmem | stock persistentmem | Требует SFSPI/MTD, формата записей и совместимости с AVP; запись пока не переносилась |
| DSC | stock dsc.ko | Реализация и DWARF доступны для анализа; API crypto-engine 7.2 и clock/reset/IRQ ещё не перенесены |
| efuse | stock node без bound driver, AVP /dev/efuse | Linux native support не подтверждён; нельзя подменять неизвестный reg угадыванием |
| hwspinlock | DT18867000, без bound driver | Нужны owner/lock semantics; завязан на безопасность shared transport |
| I2C0..3, SPI master, NAND, IR, Ethernet, LVDS | выключены в Linux DTB | Не считать используемыми драйверами нашей платы; часть I2C обслуживает AVP |

## Реальная разводка платы из DTB

- Сериализатор кнопок: data GPIO9, clock GPIO8; плечевые GPIO11/GPIO7.
- Volume-/Volume+: GPIO12/GPIO13; FN GPIO2; power button GPIO14.
- Headphone detect GPIO15; speaker output GPIO19; LCD reset GPIO6; power pin GPIO1.
- SD detect GPIO109. Батарея: check_adc1; charging: check_adc5; calibration channel0.
- AVP audio: I2S clocks GPIO3/GPIO4, data GPIO5, format left-justified, codec CS4344.
- Подсветка: PWM GPIO0, частота100000 в DTB. Не смешивать с конфигурацией другой ревизии SF3000.

## Что реально изменено в этом этапе

1. Добавлены встроенные `hc16xx-restart`, `hc16xx-adc-ro`, RAM-console.
2. Добавлен USB CDC diagnostic init, который поднимает связь до mount SD.
3. Исправлен Kconfig HC16xx MUSB: gadget-only/PIO вместо принудительного dual-role,
   поскольку сам glue объявляет host/OTG неподдерживаемыми.
4. В RAM выделено 64 КиБ no-map для кольца kernel log, phys0x02d00000.
5. Все изменения находятся в нашем overlay, устанавливаются `integrate_ports.py`.

Сборка проходит. **Аппаратный успех этого профиля пока не подтверждён.**
Не реализованные строки матрицы — реальные оставшиеся задачи, а не фиктивные
драйверы-заглушки. Самый большой общий блок — AMPRPC/AVP/shared memory.

## Первый аппаратный опыт этого этапа

Исторические неудачные ports-прогоны ниже не относятся к последующей успешной
базовой приёмке `kernel_ready`: оба её профиля boot/driver прошли до PID1,
модуль r36hello загружен/проверен/выгружен, watchdog дважды вернул stock.
Свидетельство `analysis/kernel_ready_HARDWARE_VERIFIED.json`.
USB/ADC/GPIO/AVP при этой успешной приёмке не включались.

На SD доставлен профиль `ports` (raw SHA256
`67ef2a7b72df69236a688b8d393703b140c21ddca07d598002410c68a7a5538c`).
Новый loader подготовил1875 страниц и прошёл probe. Выполнен `boot-detached`:
старый USB gadget исчез из Windows, но новая CDC-консоль за50 секунд не появилась.
Это не подтверждает работоспособность перенесённых драйверов и ещё не локализует
остановку. Нужен физический перезапуск и чтение RAM-ring/SD отчётов.

В отличие от прежнего handoff, `boot-detached` отсоединяет старый UDC до передачи
управления. После cache flush переход идёт через ассемблер без cached stack access.
Это устранение возможных причин, а не установленная причина предыдущего сбоя.

Отдельно собран `payload/kernel_lab_input/`: GPIO, pinctrl, gpio-keys и
двухпроводный serializer. Он пока не загружался на консоли. Разводка отдельных
GPIO взята из нашего DTB; порядок12 сериализованных битов пока наследуется из
upstream и требует проверки каждой кнопки.

Статические опорные точки AMPRPC записаны в `AMPRPC_NOTES.ru.md`.

## Исправление clocksource и повторный опыт

В `timer-hc16xx.c` один counter используется sched_clock/clocksource и clockevent.
`set_state_shutdown` и установка следующего события вызывают stop этого counter.
Это статически установленный конфликт непрерывного времени и выключаемого
таймера событий. Причина конкретной остановки консоли этим ещё не доказана.

В private Kconfig MACH_HICHIP заменён `MIPS_EXTERNAL_TIMER` на
`CEVT_R4K` + `CSRC_R4K`, как в штатной схеме Count/Compare/IRQ7;
`HC16XX_TIMER` выключен, node timer@4 disabled.

Новый ports-образ: raw SHA256
`6e66adbcbe85b1f06517ede5ca1f4caa3497af7f5419c3d67d314c18448331b5`,
entry0x80534f18. После доставки, insmod, prepare и probe (все rc0) выполнен
boot-detached; CDC вновь не появилась за50 секунд. Значит таймерное исправление
само по себе не дало наблюдаемого успешного запуска этого профиля.

Следующий шаг — восстановить связь и получить ранний лог, а не добавлять ещё
периферии в неподтверждённую загрузку. Подготовлен `wdt_diag.c`: режим без аргументов
только читает clock/control/counter; `--sample` временно запускает счётчик для
измерения частоты; `--arm measured_hz seconds` позволяет задать диагностический
warm-reset timeout. Ни sample, ни arm на устройстве ещё не выполнялись.
