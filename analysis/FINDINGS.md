# Журнал находок (append-only)

Консоль-клон «SF3000» на HiChip HC16E310 (MIPS 74Kc), Linux 4.4.186 + AVP/HCRTOS.
Всё ниже — проверено на живом устройстве (MTP-root-shell `tfmtp`), дампы лежат в `analysis/kmem/`.
Формат записи: **находка → доказательство → следствие**.

---

## 2026-11-11

### 1. Объём и карта RAM
- `/proc/iomem`: `System RAM 00000000-02f91e4f` (47.7 МБ), `Kernel code 0-0033a4cf`, `Kernel data 0033a4d0-0047dfff`.
- dmesg: `memory: 02f91e50 @ 00000000 (usable)`, `Memory: 36368K/48708K available ... 12340K reserved`.
- `MemTotal: 43160 kB`, swap 128 МБ на карте (`/mnt/sdcard/cubegm/pagefile.sys`).
- Снят полный дамп: `mdump 80000000 0x00b54000` → `analysis/kmem/kernel_80000000.bin` (11 878 400 б, md5 `d5540aa9c01f08669b34d5235e583a74`), offset = vaddr − 0x80000000.
  Остальная RAM: `ram_00b54000.bin`, `ram_01354000.bin`, `ram_01b54000.bin`, `ram_02354000.bin` (по 8 МБ), `ram_02b54000.bin`.
- Скан всей RAM: `\x7fELF` — 63 совпадения, `uImage` magic — 0, 12-байтные nonce блобов — по одному разу (это page-cache от наших же `dd`-чтений: avp @0x17a2000, vmlinux @0x1d00000, driver @0x27d2000).

### 2. Адресация DRAM: старшие биты игнорируются (важно!)
- `md5(mdump 0833c000 0x200) == md5(mdump 0033c000 0x200) == md5(local 0x33c000)` → физический `0x08000000` **алиасится** на `0x00000000`.
- Следствие: чтение «памяти AVP» по адресам `0x09da0000`, `0x0a504a30` и т.п. через `/dev/mem` даёт **зеркало первых 64–128 МБ** (там же лежат наши собственные процессы, `mscan` в куче, page-cache).
  Память AVP/HCRTOS через `/dev/mem` с CPU-стороны **недоступна**. Путь «сдампить AVP и вытащить ключ» закрыт.
- Проверено: `08833c000`-подобные «находки» (`aes_sbox`, `nonce_*`, `chip` подряд) — это строки самого `mscan` в RAM, ложные срабатывания.

### 3. DSC (крипто-движок): адрес и как безопасно трогать
- DT (`dtb.bin`, plaintext): узел `dsc@0x18870000 { compatible="hichip,dsc"; reg=<0x18834000 0x1000>; interrupts=<0x2c>; }` — **реальная база 0x18834000** (имя узла — опечатка вендора).
- Чтение `0x18834000` через `/dev/mem` **без драйвера вешает шину** (D-state, MTP-remote умирает, лечится только power-cycle). Причина: блок не тактирован.
- Решение: `insmod /lib/modules/4.4.186-release/extra/dsc.ko` (штатный модуль 339 648 б, живёт в `rootfs/lib/modules/.../extra/dsc.ko`) — драйвер делает `hc_clk_enable` + `of_iomap`, после этого регистры читаются без зависаний. `/dev/dsc` = misc 10:57.
- Дамп регистров после загрузки (`analysis/kmem/dsc_18834000.bin`):
  `+0x000=0x00000001, +0x010=0x00030000, +0x050=0x00000010, +0x090=0x00000047, +0x094=0x01010000, +0x0a8=0x00000080, +0x0e4=0x03010000, +0x0f0=0x0000003c, +0x0f4=0x00000dff, +0x200=0x00000004`.
  `AES_ODD_KEY0..7` (`+0x240..+0x25c`) и `KEY_RAM_RD_DATA` (`+0x24..0x30`) — **нули**.
- `dsc.ko` импортирует только `hc_clk_enable/disable`, `of_iomap`, `misc_register`, `remap_pfn_range`, ... — **доступа к efuse/OTP нет**. Ключ ставит userspace через ioctl (SET_KEY) либо он приходит извне (загрузчик/AVP).
- Следствие: DSC можно *использовать* (запрограммировать свой ключ и прогнать данные через ioctl — хороший оракул), но ключ блобов он не отдаёт.

### 4. efuse/OTP в Linux недоступен
- DT: `linux-efuse { compatible="hichip,efuse"; }` — **без `reg`**.
- В системе: `/sys/devices/platform/soc/soc:linux-efuse` есть, но драйвер не привязан; нет `/sys/bus/nvmem`, `/sys/class/nvmem`, нет `/dev/efuse`, нет `/dev/nvmem`.
- В `kallsyms` нет символов `efuse/otp`. В HCRTOS-DT есть `efuse { devpath="/dev/efuse"; }` → efuse читает **AVP-сторона**, не Linux.
- Следствие: OTP-ключ с Linux не прочитать штатно; только через сам AVP (см. п.6) или через регистры контроллера (`0x18818000+`, сейчас читаются нулями).

### 5. Регистры «security»-блока
- `0x18800000` (0x40 б): chip id word `0x1600ac01` (сравнение в `hcdaemon` с `0x1600`/`0x1512`).
- `0x18818000` (0xe50 б, блок efuse/key-adc/watchdog): сейчас **все нули**.
- `hcdaemon` (`/usr/bin/hcdaemon`, 6532 б, `(deleted)`): читает 32 б из `0x18818000+0x10` как TEA-ключ (delta `0x9e3779b9`), TEA-расшифровывает константу `38 65 93 67 35 59 47 69 10 09 27 75 b9 e9 c7 ef` и пишет 16 б в `/dev/ZZd2C`. Т.к. ключ = нули, токен детерминированный → «проверка» тривиальна.
- `/proc/devices`: 229/230 `hc_checkadc_class`, 231 `ge`, 232 `mmz`, 235 `ZZd2C`, 241 `dis`, 251 `kshmdev`, 252 `virtuart`.

### 6. Консоль AVP/HCRTOS через `/dev/virtuart`
- `/usr/bin/avpconsole` (4948 б) просто гоняет stdin/stdout ↔ `/dev/virtuart`.
- Собран `virtq <text> [ms]` (static MIPS, `scripts/kmod/virtq.c`, на карте `/cubegm/virtq`): пишет по байту (30 мс) в `/dev/virtuart` и читает N мс.
- В порту виден **живой лог RTOS** и приглашение шелла:
  `VER:VIDDRIVER(Dec 26 2024 15:11:15)`, `open /dev/persistentmem failed`, `get tvtype in sysdata fail,from dts:15`,
  `get_dts_panel_info 72 109 19 1 640 480`, `Unplug_card_display_display_init 320`, `CFG 48K`,
  `backlight_probe:308 Failed to probe node: /hcrtos/backlight1`, `HDMI WAIT PHY RDY TIME OUT`,
  промпт: `hc1600a@dbE3100v20#`.
- Ввод: RTOS эхом отдаёт `help` + `r`/`n` (управляющие байты рендерятся как буквы), команды **не исполняются** — интерактивный шелл через virtuart пока не подтверждён (похоже, порт только для лога/эха).
- Побочный факт: строка `KdwaYewCiBETqFZPvtZFqORuSKMqoSzp 0` в логе (sysdata/tvtype, 32 симв.).

### 7. SPI NOR (mtd0..mtd4) — карта и структура
Разметка (DT + `/proc/mtd`): mtd0 `nor` 0x80000 (весь чип), mtd1 `boot` 0x61000, mtd2 `dtb` 0x9000 @0x61000, mtd3 `eromfs` 0x6000 @0x6a000, mtd4 `persistentmem` 0x10000 @0x70000.
Свежие дампы: `mtd0_fresh.bin` (524 288 б), `mtd1_fresh.bin` (397 312 б) — старые `mtd0..4.bin` битые (не пользоваться).

| Смещение | Что | Энтропия |
|---|---|---|
| 0x00000–0x004000 | заголовок загрузчика (plaintext) | 4.89 |
| 0x004000–0x04c000 | тело загрузчика | **7.99** (шифр/сжатие) |
| 0x04c000–0x050000 | хвост | 5.71, ff 41 % |
| 0x050000–0x061000 | стёрто | ff |
| 0x061000–0x06a000 | DTB (plaintext FDT, `d00dfeed`) | — |
| 0x06a000–0x070000 | eromfs | 5.98/7.21 |
| 0x070000–0x080000 | persistentmem | ASCII + записи |

- Заголовок (LE, `0x10` = magic `0x5a5aa5a5`): `+0x20 = 0x0004a620` (размер 304 672), `+0x24 = 0xa9e70000` (адрес загрузки, kseg1), `+0x28 = 0xafc04000`, `+0x2c = 0xa9e70000`, `+0x40 = 0x2` (кол-во CPU?), `+0x44 = 0x02faf080` (SPI 50 МГц — совпадает с DT `sclk`), `+0x48 = 0x03200007` (scpu PLL 0x320, clk idx 7 — совпадает с DT), `+0x4c = 0x04b00005` (mcpu 0x4b0 idx 5 — совпадает с DT).
  → заголовок BootROM/загрузчика **не зашифрован**; тело — да.
- persistentmem: `00 a4 00 00 01 00 a0 00 "HC16E3100V20"` + записи sysdata (CRC32-подобные, `be515eab`, `121796b5` и т.п.), 65 536 б.
- eromfs — **настоящий romfs** (big-endian): magic `-rom1fs-`, size `0x5e10`, volume name `rom 697876dd`; внутри файлы (`I`, `..`) — подлежит распаковке (24 КБ).

### 8. Штатные тулзы и их бесполезность для ключа
- `hcfota` (6504 б) + `libhcfota.so` (26 084 б): формат **HCFOTA** — заголовок `crc / compress type / ignore version / version / uncompressed length / length / board`, payload-таблица (device index/type, offset in payload/device/mtdblock, length, erase length), пишет в `/dev/mtdN`, `/dev/mmcblk0`, `/dev/persistentmem`.
  Это **не** формат `cubegm`-блобов: `hcfota info /mnt/sdcard/cubegm/avp.uImage` → `crc check failed! crc calc 0xbd7267b2, crc in fota 0x2674e941` (в поле crc попадает первый u32 nonce `41 e9 74 26`).
- `hcprojector` (14 741 136 б): нет AES S-box, нет `EVP_/AES_/libcrypto`, нет `9e3779b9`, нет `/dev/dsc` → не расшифровывает.
- `icube` (12 760 б): только `shmget/shmat/execl` → лаунчер `rkgame`.
- `libcrypto.so.1.0.0` на карте есть, но к этим файлам отношения не имеет.
- `dsc.ko` — единственный штатный компонент, работающий с DSC (см. п.3).

### 9. Процессы/окружение текущей (нашей) загрузки
`init`, `hcdaemon`, `sh`, `/tmp/cubegm/icube`, `[rkgame]` (зомби), `zhijack.sh`, `cubevol`, `nosleep` (патчит код: `0x406bd4:0xac62b758` и др.), `tfusbd.bin -d`, `picoarch …/frogui_libretro.so`, `f_mtp`, `tfmtp /mnt/sdcard`.
`/proc/modules`: `dsc`, `usb_f_mtp`, `usb_f_mass_storage`, `libcomposite`.

### 10. Сбои и восстановление
- Чтение несвязанного DSC-регистра подвешивает CPU-сторону; `pnputil /restart-device` USB не помогает, **помогает только power-cycle** (Power ~8 с), после чего MTP-remote (`tfmtp … remote=1`) поднимается сам.
- Перезагрузка «тёплая» — DRAM частично сохраняет содержимое, поэтому в дампах встречаются остатки прошлых загрузок (`open backlight failed` из `ram_01b54000.bin`).

### 11. Инструменты, оставленные на карте (`/mnt/sdcard/cubegm/`)
- `mdump <hexaddr> <len>` — дамп phys-памяти в stdout (static MIPS).
- `mscan <hexstart> <hexend>` — поиск сигнатур (uImage/ELF/«Linux version»/nonce блобов/`HC16E310`/AES S-box), печатает `NAME 0xADDR`.
- `virtq <text> [ms]` — запись/чтение `/dev/virtuart`.
- Host-обёртки: `scripts/_kmdump.py` (dump в файл через MTP), `_kfetch.py` (бинарный `cat` файла), `_avpfetch.py` (чанками).

### 12. Открытые направления
- Распаковать `eromfs` (romfs, 24 КБ) — что внутри (возможно, код загрузки AVP).
- Прогнать известные/подобранные ключи через **живой DSC** (`/dev/dsc` ioctl) как оракул (проверка: плейнтекст `driver.so` = ELF).
- `hcfota info` на настоящем `.fota`, если найдётся; поискать формат в `libhcfota.so` (compress type: чем жмут образы).
- Проверить, есть ли в AVP-логе команды/режим, включающие отладочный shell (сейчас ввод не исполняется).

### 13. Уточнения к прежним выводам
- Пункт 6 устарел: интерактивный AVP shell работает. Нужен CR, затем команда `nsh` из корневого CLI; приглашение меняется на `(nsh)#`.
- Пункт 2 относится к Linux `/dev/mem`: память AVP удалось читать со стороны самого AVP командой `xd`.
- Отсутствие открытого `/dev/dsc` в текущем списке `/proc/*/fd` НЕ доказывает отсутствие его использования при загрузке: процесс мог уже закрыть дескриптор или завершиться.
- Отсутствие AES-таблиц/названий API в `hcprojector` (п.8) само по себе не доказывает отсутствие расшифровки. Путь создания `/tmp/cubegm` пока не установлен.
- Строки `AES` и `Decrypting graphics` в `rkgame.elf` относятся к Neo Geo/FBA; это не свидетельство расшифровки контейнеров cubegm.

### 14. Проверенные расшифрованные ELF из `/tmp/cubegm`
- На устройстве `od -An -tx1 -N48 /tmp/cubegm/rkgame` и аналогичная проверка `driver.so` показывают ELF magic; на SD `rkgame` начинается с заголовка контейнера и шифртекста.
- Получены полные файлы: `analysis/card2_files/rkgame.elf`, 6 208 364 байта, MD5 `6901fd5ad29837e39d2e9c36bb37ba53`, ET_EXEC, entry `0x409030`, 38 секций; `analysis/card2_files/driver_plain.so`, 98 216 байт, MD5 `ee629cce4710d501a7feb682e2850def`, ET_DYN, entry `0x24e0`, 37 секций.
- Совпадение MD5 `driver_plain.so` с `driver_sf3500.so` означает совпадение ПЛЕЙНТЕКСТА, а не неудачную расшифровку. Прежний вывод об обратном ошибочен.
- Обе точки `/media/mmc` и `/mnt/sdcard` — vfat одного `/dev/mmcblk0p1`, не FUSE. Чтение `rkgame` по обеим точкам возвращает контейнер; обычный `cp` в `/tmp` также сохраняет контейнер. Прозрачная расшифровка при обычном чтении не обнаружена.
- `zhijack.sh` — наш TreeFrogUI-скрипт, запускаемый уже работающим stock rkgame через autorun. Он останавливает icube и убивает rkgame; не является найденным штатным расшифровщиком.
- `ApplicationFrame.dll` в расшифрованном виде пока не получен. Его назначение и формат плейнтекста не установлены; расширение `.dll` не доказывает Windows PE.

### 15. Исправлена диагностика AVP `xd`; быстрый дамп RAM работает
- Верифицировано: `xd` принимает адрес как hex, но РАЗМЕР КАК ДЕСЯТИЧНОЕ ЧИСЛО. `xd 3de0000 800` возвращает ровно 800 байт (50 строк, последняя `a3de0310`), а не 0x800. Это ошибочно принимали за потерю данных в кольце.
- С исправленным инструментом `xd 3de0000 2048` возвращает 128 последовательных строк; `xd 3de0000 16384` — 1024 строки, от `a3de0000` до `a3de3ff0`. Гипотеза о пределе 1.6/3.2 КБ на команду опровергнута этими проверками.
- `scripts/kmod/virtq2.c`: читает одновременно с побайтовой отправкой команды, повторяет чтение при нулевом результате, обрабатывает EAGAIN/EINTR. Собран static MIPS с `-Wall -Wextra -Werror`; на карте отдельное имя `/cubegm/virtq2_fixed`.
- `scripts/_avpdump.py`: чанки по 16 384 байта; точное число строк и каждый адрес проверяются; слова пакуются LE; сырые ответы сохраняются в `.chunks` для возобновления; JSON содержит адрес, размер и SHA256.
- `analysis/avp_ram.bin`: phys `0x03de0000`, 1 381 713 байт за 107.2 с, SHA256 `79aa5aca8c75a12841c8dbe80bfcf583a895a98884848d606f7ef49cacc3573b`.
- Это УЧАСТОК RAM, не доказанная побайтовая копия `avp.uImage`. Начало участка — середина MIPS-кода. Размер зашифрованного файла не определяет размер развернутой прошивки в памяти.
- Дополнительные проверенные дампы: `analysis/avp_03f30000.bin`, phys `0x03f30000`, 851 968 байт, SHA256 `f2f7b6f9f53375df90fca40ea28b363c29955ec039ff772dba6ad92503b89f5f`; `analysis/avp_04000000.bin`, phys `0x04000000`, 393 216 байт, SHA256 `390c3f31ae3a4883a308c75777a32a44e13158e09c24b017a7fe1578d53813ab`.
- В новом соседнем дампе найдена rodata AVP: `0x83f5ff38` путь к `apps-avp/source/main.c`, `0x83f82c3c` строка `HCRTOS`, `0x83ffcb14` `/dev/efuse_protect`, `0x83ffcb28` `/dev/efuse`, `0x83fff314` `libefuse`.
- В первом участке нет стандартного начала AES S-box и строки `expand 32-byte k`. Это ограниченный отрицательный поиск, не доказательство отсутствия алгоритма в прошивке.

### 16. Скрытый initramfs и сохраненный BusyBox
- В текущей загрузке `/bin`, `/sbin`, `/usr`, `/lib`, `/etc` перекрыты отдельными vfat-монтированиями SD. Поэтому текущие init/mdev-скрипты могут не отражать самую раннюю фазу старта.
- Временное нерекурсивное bind-монтирование `/` позволило увидеть исходный rootfs: каталоги `bin/etc/usr/sbin/hcdemo_files` уже пусты; `/init` остался обычным скриптом `exec /sbin/init`.
- `/proc/1/exe` ведет на `/bin/busybox (deleted)`, но доступен для чтения. Сохранен `analysis/kmem/busybox_init.bin`, 361 892 байта, полноценный MIPS ELF с symtab/DWARF. Поиск строк `cubegm`, ChaCha-констант и характерных crypto-путей не дал зацепки.
- Оба локальных `hcprojector` (`kmem/hcprojector.bin` и `rootfs_card2/usr/bin/hcprojector`) идентичны: 14 741 136 байт, SHA256 `6040b6ed97d28828e35d0047d20f3c9176724cc5bc73331d0a438bb2224d05db`. Неудачный MTP get `/usr/bin/hcprojector` не означает отсутствия файла в Linux.
- Следующие направления: установить реальные границы загруженного AVP; исследовать ссылки на строки/драйвер efuse и ранний загрузочный код; установить создателя `/tmp/cubegm` по исходным загрузочным материалам. Ключ и алгоритм контейнеров пока НЕ установлены.

### 17. Главная цель: собственное ядро Linux; первый RAM-handoff
- Пользователь уточнил приоритет: запуск своего ядра и драйверов, затем документация. Исследование ключа контейнеров больше не является самостоятельной основной целью.
- Найден открытый порт https://github.com/SiarheiVolkau/linux-hichip, ревизия `da5f1a22ef2ff5c46aa3f750fa10825813970b09`, Linux `7.2.0-rc5`. Автор заявляет bring-up SF3000; это внешнее утверждение, не наша проверка.
- На нашем компьютере успешно собраны upstream sf3000_defconfig и собственный профиль `7.2.0-rc5-r36lab` с отдельным initramfs. Исходники находятся в `/root/linux-hichip-da5f1a22ef2ff5c46aa3f750fa10825813970b09` дистрибутива WSL ubmips.
- Наш DTS: память `<0 0x02f91e50>`, UART/IRQ/timer/SD, без повторной настройки pinmux GPIO/PWM/дисплея AVP. Стандартный DTS автора с mem=192M не соответствует текущему разделению памяти на этой консоли.
- Наш raw-образ: `payload/kernel_lab/vmlinux.bin`, 5 940 192 байта; load `0x80100000`, entry `0x804e4e38`, memsz 7 209 776. SHA256 `2204bbca46b7a3901a036233be966124dea3047087a9e7f1f879f49c0c149d19`.
- `payload/kernel_lab/r36-lab.dtb`, 4225 байт, передаётся по `0x82e00000`, SHA256 `1821d999e93ab1d14a3c5d0158f433f9ea50071ea0f0d1b9d150da896e51d8cf`.
- Собственный RAM-загрузчик `r36boot.ko` не требует CONFIG_KEXEC: минимальный ABI измерен по DWARF stock dsc.ko (`module=320`, init offset208; fops=108, ioctl offset32). Компилируется отдельно, не зависит от общей сборки 4.4.186 в другой сессии.
- Впервые ПРОВЕРЕНО НА КОНСОЛИ: insmod r36boot.ko rc=0; /proc/r36boot показывает idle; prepare rc=0, 1763 страницы, 310 исключённых из source-областей; uncached trampoline probe rc=0. Все source/list/control/trampoline-страницы находятся вне будущих областей назначения.
- До handoff контрольные суммы файлов на SD совпали с локальными: raw MD5 `efe1965817f2b8108427f1de916928ed`, DTB MD5 `23cba008a4098f6b267e7d31560a147e`. Свидетельства сохранены в `analysis/kernel_lab_preboot.txt`.
- Выполнен `sync; (sleep 2; /mnt/sdcard/cubegm/r36bootctl boot) ... &`. Штатный MTP после этого не отвечает; Windows ещё видит старое USB-устройство. Достижение нового Linux/PID1 пока НЕ ПОДТВЕРЖДЕНО.
- Диагностический init должен записать `cubegm/r36-own-kernel-proof.txt` с release и pid=1, после чего остаётся работать без UI/MTP. Для чтения результата требуется полный power-cycle и возвращение штатного MTP. Одно отсутствие ответа MTP успехом не считается.
- Штатные boot-файлы и NOR не менялись. До опыта MD5 stock Linux `f994b5e32dc90c5eec7e4bd965bff8fe`, AVP `36cf812151712a8a1ec01911ac03ab74`, DTB `9492f590fc2db86694d3fdc52a25c3e4`.
- Документация: `analysis/KERNEL_AND_DRIVERS.ru.md`; исходники и сборочные команды: `scripts/kernel_lab/`.

### 18. Временная блокировка автоматического сна
- В этой версии cubevol адреса от профиля GB350 не совпадают с ожидаемыми инструкциями: `0x406bd4=0x8c42be20`, `0x406ecc=0x0c101d6a`, `0x406a00=0x00e0b025` в локальном штатном ELF. Защищённый nosleep пропускает их, one-shot rc=1.
- На время исследования создан `scripts/r36_keepawake.sh`, загружен в cubegm и запущен: он удерживает cubevol в STOP и следит за новыми PID. На консоли подтверждены PID watcher4214 и cubevol594 State=T; uptime достигал более 2700 секунд без прежнего автоотключения.
- Приостановлены также кнопки/громкость, обслуживаемые cubevol. Возврат: `sh /mnt/sdcard/cubegm/r36_keepawake.sh stop`. После power-cycle watcher нужно запускать вновь. Это не защита от разряда батареи.

### 19. УСПЕХ: собственный Linux 7.2 дошёл до PID 1 на нашей консоли
- После физического перезапуска прочитан `cubegm/r36-own-kernel-proof.txt`: `sysname=Linux`, `release=7.2.0-rc5-r36lab`, `version=#2 Wed Nov 11 18:50:36 UTC 2026`, `machine=mips`, `pid=1`.
- Это подтверждает не только переход на новую точку входа: новый Linux выполнил собственный initramfs/init, смонтировал SD/vfat и записал файл. Работа экрана/звука/USB под новым Linux этим опытом не подтверждена.
- `scripts/kernel_lab/collect_proof.py` проверил release/build по локальному бинарнику, совпадение raw-образа/DTB на SD и сохранность штатных boot-файлов. Результат: `analysis/kernel_lab_boot_result.json`, `hardware_boot_verified=true`.
- SHA256 proof `3c9a33d1d4ae076775b8e75a3c69e5729e2ea65e167f48a7ded24869806c8e81`; исходный текст сохранён в `analysis/kernel_lab_boot_proof.txt`. Постзагрузочная проверка: `analysis/kernel_lab_postboot.txt`.
- После опыта снова работает штатный `4.4.186-release #23`. MD5 stock Linux/AVP/DTB совпали с п.17. Защита keepawake вновь запущена, PID881.
- Основной первый рубеж достигнут: запуск собственного ядра и собственного PID1 без расшифровки SD-контейнера и без изменения NOR/штатного boot-образа. Следующие рубежи — интерактивный доступ под новым ядром и последовательный перенос аппаратных драйверов.

### 20. Запущен отдельный тест освобождения памяти и модулей
- Рабочий первый комплект сохранён в `payload/kernel_lab_verified_boot1`, свидетельства — в `analysis/kernel_lab_boot1`. Изменения для нового теста его не заменяют.
- Новая сборка: raw 5 974 848 байт, load `0x80100000`, entry `0x804e4e38`, memsz 7 275 312, SHA256 `13de9a51a17aa4adea8f8905d9234a44fa7bee94e3ebc71d539c95a0e762e5f4`.
- Новый init выполняет загрузку/выгрузку r36hello и r36memcheck, проверяет владение прежними страницами, выполняет 3 прохода записи/чтения до 24 МиБ RAM и считает повторно использованные страницы загрузчика через pagemap. Исходники в scripts/kernel_lab.
- На стоке проверены новый insmod/prepare/probe (все rc=0), 1779 страниц копирования, 376 исключённых кандидатов; control `0x81962000`, trampoline `0x81f06000`.
- План `analysis/kernel_lab_reclaim_plan.bin`: 2161 LE-пар, 1785 живых уникальных выровненных страниц вне областей назначения. SHA256 `7e877bb2d29203b55363b23730f7516abb4ebd60fc0bc72876182b07d6fc1e65`. Файл также записан на SD для нового init.
- Файлы на SD сверены с локальными MD5, старые диагностические отчёты удалены перед запуском. Предварительные данные: `analysis/kernel_lab_memory_preboot.txt`.
- Выполнен новый RAM-handoff. Включена попытка автоматического возврата через последовательность штатного board_restart (дизасм 0x80000e4c: iowrite32(-6,0xb8818500), iowrite32(0x26,0xb8818504)). Факт выполнения этой попытки и результаты тестов пока неизвестны.
- MTP не вернулся в пределах проведённых ожиданий. Нужен ручной power-cycle, затем `scripts/kernel_lab/collect_memory_test.py`. До чтения отчёта нельзя утверждать ни PASS RAM/модулей, ни причину отсутствия автоматического возврата.

### 21. Результат теста RAM и начало общего переноса драйверов
- После следующего физического старта collector и прямой Linux `ls/cat` подтвердили: proof, memory report и kmsg от теста RAM отсутствуют. Результат теста не получен; причина не локализована. Нельзя говорить, что память/драйверы этот тест прошли.
- Пользователь запросил перенос всех драйверов. Проведена инвентаризация: `analysis/driver_port/stock_*.txt` и `stock_dtb_nodes.json`, 96 compatible nodes /70 enabled /38 unique enabled compatible, 68 platform devices, 18 avp-proxy nodes.
- Большинство мультимедийных char devices — один общий AVP transport. AMPRPC/avp-proxy/kshm/mmz в ядре7.2 пока отсутствуют; статические опорные точки зафиксированы в `analysis/driver_port/AMPRPC_NOTES.ru.md`.
- Добавлены собственные встроенные restart handler, read-only SAR ADC/IIO и RAM console. ADC result mapping подтверждён дизасмом и живым чтением на стоке: channels0..5 =231,169,0,0,0,0; channel>=4 использует регистровый offset+2. Калибровка/вольтаж и полноценная инициализация ADC пока не перенесены.
- Добавлены компактный USB CDC init и host-клиент; MUSB Kconfig исправлен на gadget-only/PIO, соответствующий заявленным возможностям текущего glue.
- Handoff улучшен: `boot-detached` отделяет child от MTP job, отключает старый UDC; после cache flush ассемблер не обращается к cached stack. Это устранение возможного DMA/cache риска, а не доказанная причина прошлого сбоя.
- Профиль ports собран и доставлен: raw6 360 224 байта, entry0x80534658, SHA256 `67ef2a7b72df69236a688b8d393703b140c21ddca07d598002410c68a7a5538c`; новый loader prepare/probe rc0, 1875 copy pages. Выполнен boot-detached; старое USB исчезло, новая CDC за50 секунд не появилась. Успех нового профиля не подтверждён; нужно физическое включение и чтение RAM console/SD.
- Отдельный input-профиль собран в `payload/kernel_lab_input`, не загружался: GPIO/pinctrl/evdev, serializer и прямые кнопки по нашему panel DT. Порядок12 сериализованных битов ещё требует аппаратной проверки. Его SHA256 raw `03f08a7d93ce3e54f36f06f417f7f3598b5b0f7c6661138fa9393461e2ba9d9e`.
- Матрица реального статуса всех подсистем: `analysis/driver_port/PORT_MATRIX.ru.md`. Неперенесённые драйверы не заменены заглушками и не отмечены работающими.

### 22. Повторный сбор логов и исправление таймера
- После очередного физического старта old stock доступен, uptime31.46; keepawake снова запущен PID882. Файлы proof/driver-test отсутствуют. `collect_ramconsole.py` снял64 КиБ, но magic/version/capacity не прошли проверку: журнал не сохранился или был переиспользован. Это не ранний kernel log.
- Статически обнаружен конфликт в upstream `timer-hc16xx.c`: один counter одновременно обслуживает clocksource/sched_clock и clockevent, но shutdown/next_event останавливают его. Это может нарушать время, однако причиной конкретного зависания пока не доказано.
- Private arch Kconfig исправлен: MACH_HICHIP теперь выбирает CEVT_R4K/CSRC_R4K вместо MIPS_EXTERNAL_TIMER; node timer@4 и HC16XX_TIMER отключены. Сборка действительно содержит cevt-r4k.o и csrc-r4k.o; сток также использует MIPS Count/Compare/IRQ7.
- Новый raw image6 386 080 байт, entry0x80534f18, SHA256 `6e66adbcbe85b1f06517ede5ca1f4caa3497af7f5419c3d67d314c18448331b5`. На консоли insmod/prepare/probe rc0, 1875 страниц, 381 исключённых, control0x828f3000, trampoline0x824ba000.
- Новый boot-detached выполнен; CDC за50 секунд опять не перечислилась. Не считать таймерное исправление подтверждённым решением handoff/boot failure. Требуется ранняя трассировка/следующий физический возврат в сток.
- Подготовлен и с -Wall -Wextra -Werror собран `payload/kernel_lab/r36-wdt-diag` из wdt_diag.c. Read-only inspection / короткое измерение счётчика / arm с измеренной частотой разделены. Аппаратная калибровка и применение watchdog для диагностического warm-reset ещё не выполнялись.

### 23. Watchdog измерен и проверен; автоматический возврат реализован
- На стоке control0x18818504=0, counter0xffffd7d8, gate0=0x0e000f8c. Три коротких запуска0x26 дали187495/188358/187467 Гц, median187495; регистры после каждого восстановлены. Свидетельство `driver_port/wdt_calibration.json`.
- Stock-only arm10с действительно автоматически вернул штатный MTP. Uptime552.81с ->28.25с. Сохранился trace tag0xbc4c48f3. Результат `driver_port/wdt_reset_trial_result.json`.
- Найден проверенный сохраняющийся участок: phys0x02f91000,0xe00 байт в последней неполной странице Linux RAM. Полные страницы allocator заканчиваются0x02f90fff, SystemRAM заканчивается0x02f91e4f. Старые64 КиБ по2d00000 могли переиспользоваться стоком.
- В loader BOOT добавлен watchdog187500Гц/30с и маркеры1/2/3; в kernel_entry маркер4, в RAM-console5, userspace6. Новая сборка помечает watchdog clock как CLK_IS_CRITICAL.
- Один прогон с новым ядром автоматически вернулся в stock (uptime41.36), trace tag0x3e67b554,stage4,entry0x80534f18,copy_pages1875. Это подтверждает вход в kernel_entry и автоreset, но не загрузку PID1 расширенного профиля.
- Для локализации добавлены более мелкие маркеры33..59 (BSS/stack/start_kernel/setup_arch/CPU/FDT/cache/IRQ/time/console).
- Добавлен внешний armer в boot-detached до UDC disconnect и `run_cycle.py` для ограниченного автоматического цикла с checkpoints. Timeout настраиваетсяR36_BOOT_TIMEOUT, default30с.
- Последний прогон подробной трассировки (rawSHA256e7c8171b03a0fc34f3d60ac8b2abd8b5e81a2212ca2870c76252352253e02a33) не вернул USB к ожидаемому сроку. Причина неизвестна; отсутствие USB не доказывает отсутствие самого watchdog-reset. Полная надёжность цикла пока НЕ подтверждена.
- Документация: `analysis/driver_port/AUTOREBOOT.ru.md`. Нужен однократный физический возврат/Reset для чтения последнего trace; новых слепых запусков до получения этих данных не выполнять.

### 24. Подготовлен и проверен до подключения замороженный комплект
- Пользователь запросил подготовить всё до подключения консоли. В этом этапе USB/консоль не открывались; выполнены сборки, анализ и имитация на ПК. WPD selfcheck импортирует клиент, но не создаёт R36 device.
- Готовый каталог `payload/kernel_ready`, запуск `START.py`. Два последовательных минимальных профиля boot/driver; без непроверенных USB gadget/ADC/GPIO/UART-доступов. Не начинать аппаратный порт с прежнего расширенного ports-профиля.
- Оба кандидата собраны с отдельными manifest/init/initramfs, UHI DTB и Count/Compare. Boot SHA256 `fb6552de75904ae38aef46c1df119a22bbf865d9e20bf208f58f65d46c2e35be`; driver SHA256 `1379d2f14371096b7be96485bb0a0659b0c5aa19012cb81567679c41208aee9d`.
- Добавлены CRC32 назначения в фактический relocation stub и `.r36.binding` в stock .ko. Повреждённый payload не исполняется, stage225 до watchdog-reset. Probe вынесен в последние16 байт trampoline page, чтобы не перезаписывать растущий stub (344 байта).
- Unicorn MIPS74KF выполнил фактический stub и kernel head до start_kernel: проверены байты ядра/BSS/DTB, UHI a0/a1, fw_arg0/fw_arg1, SP/GP, отсутствие записей вне разрешённых областей. Для каждого кандидата3 кейса: contiguous, scattered, scattered+bitflip. Все6 PASS; bitflip приводит CRC mismatch и запрету входа в kernel_entry.
-18 pytest-кейсов PASS: сценарий успешного возврата, задержки/обрыв handoff, неверный firmware, повреждение доставки/stock-файла, сбой prepare, отсутствие возврата, stale proof, CRC mismatch, failure unload, duplicate keys, trace wrap, worker timeout, реальные изменённые ELF/DTB и старый emulator report.
- Offline frozen audit:62 хэшируемых файла,4 ссылки (stock dump/kallsyms/dsc/client), оба preflight PASS, launcher ROOT D:\r36s-, WPD import-only PASS. Bundle manifest SHA256 `4d6f77f1cf20637d56940df53fc3975d09780a47c58ea4d5c0eef8623122515a`.
- Воспроизведён WSL1/GCC hang при vfork->cc1; прозрачный compiler `-wrapper /usr/bin/env` устранил его. Сборка не меняет системный compiler, wrapper передаётся нашим командам. Для наблюдения установлен strace/libunwind8; dpkg --audit после подготовки чист.
- Hardware acceptance именно этих кандидатов НЕ выполнялась. Эмулятор не моделирует SoC MMIO, DMA и аппаратную cache coherency; полный перенос периферийных драйверов всё ещё не завершён. После подключения запускать замороженный acceptance-сценарий и оценивать его свежие результаты.

### 25. УСПЕХ: весь замороженный acceptance прошёл на консоли
- `payload/kernel_ready/START.py` выполнил boot и driver, оба `passed=true`, без ручных перезапусков. Полный отчёт `analysis/acceptance/1794498370587679900/suite.json`, внешняя аттестация `analysis/kernel_ready_HARDWARE_VERIFIED.json`.
- Boot: свежий run_id4e1ed63d71b940e38c1a499a70f9cfe8, собственный7.2.0-rc5-r36lab build#12, pid1, trace stage6/tag0xb9ca87fb, destinationCRC0c2f2606. Автовозврат: stock uptime97.66с ->16.98с.
- Driver: run_id1c8eb81fe0d3453299121817ef9fc926, собственный7.2.0-rc5-r36lab build#13, pid1, trace stage6/tag0x2166766e, CRCce5a479a. r36hello load_rc0/parameter_ok1/unload_rc0/sysfs_removed1/resultPASS. Автовозврат: stock uptime23.55с ->18.03с.
- Оба trace:1523 copy pages, UHI a0=0xfffffffe,a1=fdt=0x82e00000, watchdog187500Гц/30с. Ядро/DTB/модуль на SD сверены с замороженными локальными файлами.
- После обоих циклов MD5 stock Linux/AVP/DTB осталисьf994b5e32dc90c5eec7e4bd965bff8fe/36cf812151712a8a1ec01911ac03ab74/9492f590fc2db86694d3fdc52a25c3e4.
- Финальная живая проверка: снова4.4.186-release, watchdog control0, keepawake769, cubevol595 в STOP. Данные сохранены в stock_final.txt внутри отчёта.
- Kernel logs подтверждают clocksource MIPS, sched_clock594MHz, SDXC58.6GiB, SD I/O и lifecycle модуля. IRQ snapshot: timer154, ERR0, dw-mci0. Последнее требует отдельного исследования учёта/режима IRQ.
- Meminfo driver-профиля до загрузки модуля: MemTotal42648KiB, Free37180KiB, Available36108KiB. Это не RAM stress и не доказательство освобождения каждой старой страницы.
- В обоих логах есть FAT dirty-volume warning: переход от живого RW stock mount пока выполняетsync, но не полноценную чистую передачу SD. Повреждение файлов не установлено; fsck/ремонт автоматически не выполнялись. До массовых испытаний улучшить RO/unmount quiesce.
- Frozen bundle не менялся; его READY.json остаётся build-time документом, аппаратный PASS хранится внешним receipt по bundleSHA2564d6f77f1cf20637d56940df53fc3975d09780a47c58ea4d5c0eef8623122515a.
- Этот результат подтверждает минимальное своё ядро/PID1/SD и собственные .ko. USB/ADC/GPIO, AVP/экран/звук, RAM-нагрузка и длительная стабильность остаются отдельными задачами. Причина старых зависаний расширенных ports-профилей не установлена одним лишь успешным минимальным тестом.

### 26. Подготовка ремонта FAT и передача другому агенту
- Пользователь уточнил цель: вся консоль на новом ядре с прежним интерфейсом/звуками/кнопками, и явно разрешил запуск ремонта файловой системы. Затем попросил документировать результаты и передать работу. Действия по ремонту остановлены до реализации безопасного offline flow.
- Ремонт fsck НЕ запускался. На этом этапе только чтение MBR/VBR/состояния и загрузка исходного архива на ПК; swapoff/remount/правки FAT не выполнялись.
- В `analysis/fat_repair/` сохранены512B MBR,512B VBR, geometry.json, handoff_preparation.json, handoff_stock_status.txt. Это не полный backup FAT/каталогов.
- Раздел FAT32: startLBA32,type0x0c,sectors30719744,bytes15728508928;512B sector,32 sectors/cluster,959480 clusters,reserved1392,2FAT по7496 sectors,serial0x5446089b. Data offset16384 sectors =8MiB относительно раздела.
- SD по-прежнему RW-mounted в7 местах, swapfile активен. На устройстве fsck.fat/dosfsck/fsck.vfat в PATH не найдены. Ремонтировать активный том нельзя; нужен RAM-only repair-init с несмонтированной SD и без опасного30-секундного cutoff во время записи.
- Скачан `modbuild/dosfstools-4.2.tar.gz`,320917B,SHA25664926eebf90092dca21b14259a5301b7b98e7b1943e8a201c7d726084809b527. Не распакован/не собран; MIPS fsck ещё нет.
- WSL заблокирован: `LxssManager=StopPending`, `wsl -- true` и UNC root не отвечают. Службу/дистрибутив не перезапускали, чтобы не затронуть параллельную сессию пользователя.
- Последняя console-проверка:stock4.4.186#23,uptime1799.13,keepawake769,cubevol595 STOP,swap12KiB used. MD5 трёх boot-файлов прежние.
- Самостоятельная точка входа для следующего агента: `D:\r36s-\AGENT_HANDOFF.ru.md`. В ней достижения/границы/команды/backup scope/план ремонта и оставшегося переноса.

### 27. Исследование шифрования и неуспешный захват раннего initramfs
- Цель пользователя снова уточнена: независимая загрузка своего ядра без предварительного stock Linux. Алгоритм/ключ SD контейнеров пока не восстановлены.
- Снят304672B RAM по0x09e70000, но проверки NSH0x09e70000/0x01e70000 дали идентичный prefix: это alias с текущими Linux library/slab pages, не доказанный bootloader. Файл bootloader_ram.bin таковым больше не считать.
- Найденha_decrypt suffix в старом dentry; фактическое имяtls,inode0. Реконструкция предыдущего имениchacha_decrypt — только гипотеза, не найденная функция/утилита.
-980 ограниченных ключевых/IV-гипотез ChaCha8/12/20,Salsa20,RC4 не дали совпадения64B с кандидатами plaintext. ChaCha reference прошёл RFC8439/PyCryptodome. Не считать это исключением семейства cipher.
- AcXtrnal раскрыт XOR0x5a в path/hash список. Формула hash не установлена.
- Найден внешний проектcsnewman/gb350-linux с обычным gzip legacy uImage/stock NOR. Для нашей encrypted-ревизии plaintext fallback не подтверждён.
- Capture-DTB менял толькоchosen/bootargs; source/candidate33251/33643B,4 tests PASS. После одного старта MTP не вернулся, пользователь сообщил «карта повреждена». Успешного capture нет. Позднее исходный DTB восстановлен в картридере; capture_deployment.json inactive/restored.
- Детальная актуальная сводка: analysis/boot_crypto/STATUS.ru.md. Рабочий frozen kernel_ready не изменялся.

### 28. FAT реально исправлена в Windows, исходный DTB возвращён
- Пользователь указал карту в картридере и уточнил fake capacity: разрешён только реальный16-ГБ раздел. Идентификация F:,serial5446089B,disk2 Realtek PCIE CardReader,offset16384,size15728508928; reported-disk62914560000 не использовался как диапазон ремонта.
- До изменений при exclusive volume lock снят полный partition backup15728508928B в analysis/fat_repair/reader-20261112-231822/partition-before.img. SHA256d776da6e1e4a704dc019fc01f9e529f19cb2a5c32a034839d4ff8e1f7f00ea7b. Ничего за концом раздела не читалось/не исправлялось.
- DTB до восстановления имелMD5 51f7338a3dcf3597819a272473900a55 (capture). Возвращён trusted original9492f590fc2db86694d3fdc52a25c3e4.
- Elevated CHKDSK F: /F /X завершился1, сообщил об исправлениях и сохранении1 lost chain16KiB. Файл FOUND.001/FILE0000.CHK сохранён также в отчёт наD:, prefix — наш keepawake shell script.
- Независимый CHKDSK F: завершился0, текст «Windows проверила файловую систему и не обнаружила проблем».
- После ремонта hashes Linuxf994b5e32dc90c5eec7e4bd965bff8fe /AVP36cf812151712a8a1ec01911ac03ab74 /DTB9492f590fc2db86694d3fdc52a25c3e4 совпали со stock.
- Авторитетный проверенный отчёт verified_repair.json. В исходном done.json backup_bytes отражает последний progress checkpoint, а не EOF; фактическая длина img проверена и исправлена в verified receipt. Скрипт для будущего исправлен.
- /R, тест fake capacity, форматирование, запись вне раздела и изменение NOR не выполнялись. Причина сообщения консоли пока не разделена между capture-DTB и FAT; восстановлены обе стороны, следующий обычный старт нужно проверить отдельно.

### 29. Шифрование восстановлено; реальные boot-алиасы подтверждены
- Проверенный контейнер: nonce12/u32LE length/ChaCha20 counter0, фиксированный256-битный ключ из распакованного TPL. Два полных ELF совпали;4 исходных контейнера воспроизведены побайтно. Оригинальный MIPS decryptor принимает нашу шифровку. `analysis/boot_crypto/cipher_verified.json`.
- LZMA-alone TPL по0x2e48 даёт812464B; cipher-wrapper0x89dab188. Resolver0x89da9130 выбирает advapi32.dll/Bubbles.scr/ApplicationFrame.dll при сброшенном startup RAM-alias флаге. Нативная эмуляция resolver PASS; runtime FDT совпал с Bubbles.scr.
- AcXtrnal XOR0x5a; значения равны complement CRC32 полных файлов. Все18 строк проверены. Это не криптографическая подпись.
- Оригинальный код bootm принимает stock и custom uImage, отвергает изменённый header/data CRC; оригинальный gzip побайтно распаковывает оба. В эмуляции заменены выделение памяти и вывод; периферия/SD/кэши не эмулированы. `loader_image_emulation.json`.

### 30. Неуспешный cold Linux7 и восстановление через кардридер
- Кандидат advapi SHA2569dbc41403ac25700612741e8bf227237628da81d238e5ea6e1e2fc2b3d800082 не вернул MTP; пользователь видел TreeFrogUI logo. PID1 proof отсутствует, actual advapi остался тестовым. Автооткат не подтверждён.
- Карта F:/5446089B/disk2/offset16384/size15728508928 проверена. Возвращён original_advapi32.dll, MD53510ffdfd039f850345ace1489572659; все6 boot hashes совпали. Read-only CHKDSK exit0. Карта безопасно извлечена, затем stock4.4/MTP/hash подтверждены на устройстве.
- После power-cycle trace-header невалиден; отсутствие RAM-следа не доказывает, что shim не исполнялся. `post_restore_20261113T020302Z/report.json`. Точная точка остановки утрачена.

### 31. NOR→добавленный код→stock аппаратно проверено; найдена low-RAM зависимость
- Отдельный stock bridge сохраняет все11650400B исходного распакованного Linux4.4 и добавляет232B зонд. Entry0x80b1c560 записывает trace и прыгает на исходный0x803337c0, сохраняя UHI/CP0 и не трогая MMIO.
- Реальный watchdog-reset с RO SD/swapoff дал stage193/tag0xa1227d68, UHI a0=-2/a1=0x89f56000; stock/MTP вернулся. Затем original advapi восстановлен и hash проверен. `stock_bridge_trial.json`, `stock_bridge_trace.bin`. Это аппаратный успех custom entry из NOR, не собственного Linux7.
- Статически helper0x89dba100 вызывается из0x89dadbac перед jalr0x89dadbc0. При MMIO magic0x1995 он сравнивает таймер с u16 по physical0x2. Stock prefix даёт0, старый shim даёт16736. Три native-code сценария с synthetic timer подтвердили эту зависимость; фактический magic неудачного старта неизвестен. Нельзя объявлять это единственной причиной сбоя.
- Builder теперь сохраняет низ RAM нулевым, entry shim0x80010000. Новый отдельный `payload/kernel_direct_advapi_lowram_v3` SHA25618d6f470b0de4573cda78d59ad16b18868233876ba615df9257de83ff43fb08f не установлен; cold-shim/kernel-head emulation до start_kernel PASS.14 crypto tests PASS.
- PID1-template дополнен отдельным progress log до проверки uname/backup и после этапов восстановления, чтобы отсутствие финального proof больше не скрывало всю userspace-стадию. Текущая консоль работает со штатным advapi; новый template на SD не устанавливался.

### 32. Файловые операции и восстановление advapi до Linux аппаратно работают
- Watchdog pending-gate испытан намеренным30-секундным ожиданием: после reset stage197/tag0x365938bb, stock/MTP вернулся без ручного запуска. Повторная попытка по тому же pending tag не выполняется.
- Read-probe сначала возвращал196. Реальная причина resolve-ошибки: при alias flag0 resolver отвергает неизвестные имена, не дошедшие до Windows-map. После временного flag1 с восстановлением и корректного выхода из critical section read64B прошёл: stage195/tag0x549fd903.
- На реальном pre-jump Status11000900 ->11000901 ->11000900, critical depth1. Loader mount name был/media/mmcblk0p2, в Linux/dev/mmcblk0p1; это разные пространства имён одной проверенной карты. API prefixes совпали с TPL; read/open/close исправны.
- Native write64B, FAT sync, close и повторное чтение отдельного R36WRITE.BIN далиstage200/tag0xa6586e83; MD5 проверен после Linux. Никакой записи в kernel-файл на этом этапе не было кроме установки/последующего host rollback самого stock probe.
- Full sandbox copy3954299B далаstage203/tag0x8736e1bf: оба CRCc3693b14, MD53510ffdfd039f850345ace1489572659. Ошибка смещения в host decoder исправлена по сохранённому raw trace без повторного аппаратного старта; decoder_correction отражена в receipt.
- Затем actual early restore stage202/tag0xbd6eb903 восстановилadvapi32.dll до Linux,3954299B/CRCc3693b14/исходныйMD5. stock_already_restored_before_host_cleanup=true, host_cleanup_wrote_boot_file=false. ПК не выполнял восстановительную запись. Receipt kernel_loader_early_restore_probe_v1_trial.json.
- Restore-code проверяет backup size/EOF/CRC до открытия target на запись, пишет существующий файлO_RDWR порциями<=64KiB, делаетFAT sync/close, повторно читает весь target и проверяетEOF/CRC. Boot-кандидат padded внутри plaintext до исходной длины, поэтому усечение/переименование не нужны.
-23 fault/control сценария с65537B и отдельное полное MIPS CRC/copy испытание3954299B PASS. Родные critical/mask helpers исполнялись, filesystem APIs в emulator заменены stubs; hardware receipts подтверждают реальные SD операции отдельно.
- Linux7 в этой серии не запускался. Следующий шаг — интеграция native restorer с корректным stock fallback для собственного ядра. Текущий stock-probe fallback entry нельзя использовать после замещения stock kernel memory. EARLY_RESTORE.ru.md содержит ABI/команды/контракт и дальнейший шаг. NOR и frozen kernel_ready не менялись.

### 33. Native stock fallback и прямой NOR-start Linux7 аппаратно подтверждены
- Fallback загружает `R36STOCK.ENC` в scratch81000000, проверяет length/EOF/CRC, вызывает оригинальные decrypt89dab188 и bootm89daa840 с исходным FDT. Он не прыгает по старому entry в память Linux7. Hardware stage208/tag0xb7b7c950, decrypt_rc0/plaintext3954283, stock/MTP вернулся. Receipt: kernel_loader_stock_fallback_probe_v1_trial.json.
- Candidate `kernel_cold_early_restore_v1`: encrypted SHA2562da0c4016a9aa356bc6ddc2d195dd5866707c6378bc85f0b23e2ae99c839948b. Frozen boot kernel/DTB/initramfs сохранены; kernel SHAfb6552de75904ae38aef46c1df119a22bbf865d9e20bf208f58f65d46c2e35be. Shim80010000, low RAM нулевой, inline FDT806f1000.
- Один hardware watchdog-reset, без r36boot RAM-handoff: NOR расшифровал кандидат, native helper восстановил stock SD-файл, Linux7 дошёл до PID1 и SD proof. Stage6/tag0xc5d28f11, entry804e5898, UHI a0=-2/a1=806f1000; run_idaa8961f5e8fd47cdabb0a2dc3081efa7. Proof: release7.2.0-rc5-r36lab/build#12/pid1/mips.
- Restore stamp64B по physical02f91e00 вне ring сохранил tag/source/readback CRCc3693b14/phase6/entry. Builder проверяет4KiB page и partial RAM end02f91e50; stamp end02f91e40. Лог обернулся4001B при capacity3520, receipt не затёрт.
- Watchdog автоматически вернул stock4.4, MTP uptime19.55с. Все6 boot hashes уже совпали до host cleanup; host_cleanup_wrote_boot_file=false. Аудит kernel_cold_early_restore_v1_trial_VERIFIED.json перепроверил сохранённые kernel/DTB bytes, trace, stamp, proof.
- Kernel log: clocksource MIPS/sched_clock594MHz, MMC270a/internal DMA/mmcblk0p1, init запущен; MemTotal42648KiB, MemAvailable36104KiB, timerIRQ155/ERR0. Boot profile не имеет driver-test proof: module/экран/звук/кнопки/TreeFrogUI на Linux7 этой проверкой не приняты.
- Это старт через NOR после аппаратного reset, не проверка полного отключения питания. power_cycle_verified=false. В kernel log остался dirty-volume warning; повреждение ФС не установлено, fsck на активном томе не выполнялся. Не объявлять старый SD-root сбой полностью объяснённым low-RAM fix: рабочий candidate использует frozen initramfs.
- Подробности COLD_BOOT.ru.md;14 crypto pytest PASS. Frozen kernel_ready/NOR не изменены; аппаратный статус хранится во внешних receipts.

### 34. Начат перенос UI/peripherals: реальный код и source build, hardware отложен
- Native static MIPS read-only inventory выполнен на stock#23: fb0RGB565/640x480/pitch1280/phys02f92000/14749264B, fb1ARGB8888/pitch2560/phys01a00000/1228800B. UI=picoarch+frogui_libretro, backenddriver_gb350.so, активенtfshim. /proc/asound отсутствует, evdev inventory пуст. runtime_20261113T041911Z/inventory.txt.
- UI keyboard ABI найден в рабочем tfkey/zhijack: cubevol/GPIO -> ftok(/tmp/joy_key,'a')/4B, B4000. Frozen kernel имеетSYSVIPC=n, поэтому минимальный boot сам по себе UI не поддерживает. В новом source build SYSVIPC включён. Driver ABI dependencies/exports сохранены вUI_ABI.json; для выбранных high-level exports DWARF types не нашлись, неизвестные сигнатуры не придуманы.
- Созданы userspace AVP polling probe и kernel r36_amprpc_poll.c: coherent/pinned page, request open отсутствующего пути, проверка state/opcode/pointer, bounded poll/ack, без callback function-pointer execution. Driver probe не отправляет RPC; source-build DT node по умолчанию disabled. Это diagnostic transport, не full proxy/ioctl stack.
- Open packet builder побайтно совпал с настоящими инструкциями stock avp_open802bad04 в7 случаях, включая максимальный path и отказ oversized. amprpc_open_wire_verified.json. Crypto/planner48 checks + ELF/header4 + result parser4 PASS; hardware AVP response не проверен.
- WSL ubmips всё ещёStopPending, не трогалась. Поднята отдельная portable QEMU/WHPX Alpine VM, /work на собственном8GBqcow2, SSH127.0.0.1:22222. Native clang20/GNU MIPS as2.44 собрали новыйkernel иmodules. GNUas нужен дляgenex forward-immediates; modules_prepare — дляmodule.lds. LLD PT_LOAD normalized только поverified initialized prefix/NOBITS, p_memsz и kernel code сохранены;4 regressions PASS.
- Полный source kernel7.2.0-rc5-r36port SHA990e005eb3035748e6440849ca2dbe178f2c40358da6538017f6cd5ed0f51c2d, moduleSHAb28ee39a05f9f9a8852227973d605332963c85300045df2787c7bbc2dbcfeeda, matchingvermagic. kernel_port_avp_vm_v1/build_receipt.json: build_passed=true, hardware_verified=false, init_matches_latest_probe=true. Kernel archive sourceSHA228d84d8384924dad741c90f1625a04e2dfe1379d4b844f750989bf09de5106b, pinnedcommitda5f1a22.
- Cold artifacts kernel_cold_avp_probe_v3, kernel_cold_port_avp_vm_v1 иkernel_cold_port_avp_module_vm_v1 прошли original bootm/CRC/gzip, pre-kernel restore + real head доstart_kernel и native-decrypt fallback. Framebuffer1 и conservativeGE mmap range зарезервированы. В module-mode PID1 использует толькоkernel sysfs, не параллельный userspace MMIO client. Fresh complete logs отдельно отличают userspace/kernel PASS.
- Пользователь ответил «Пока без консоли» после потериMTP; после этого ни одного нового device boot/deploy. AVP transport/hcfb/audio/input/USB/UI hardware acceptance остаётся следующей задачей. Источник native reference DRM/I2S/input: csnewman/gb350-linux commitbff93e84, read-only checkout; его256MiBDTB/firmware не ставились на128MiBплату.
- ПодробностиUI_PORT_PLAN.ru.md. Не объявлять перенос всегоUI завершённым и не подменять ioctl/callback методы возвращением0. Frozen kernel_ready и существующие TreeFrogUI binaries/assets/source не менялись.
