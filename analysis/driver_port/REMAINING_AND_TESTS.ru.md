# Остаток переноса и очередь испытаний

Исходный чек-лист:2026-11-14; обновление результатов:2026-11-15.
Цель — прежний TreeFrogUI/picoarch, эмуляторы, звук,
кнопки и USB на собственном Linux7, без замены интерфейса новым макетом.
Консоль сейчас недоступна по решению пользователя: не опрашивать MTP,
не запускать загрузочные опыты, камеру и микрофон до её подключения.
Чекбоксы ниже — НЕ выполненные задачи, если явно не сказано обратное.

## Актуальное уточнение: UI appearance принят

- UI_LIVE_SCANOUT_v11_REPEAT1_RESULT.json: неизменённый picoarch/FrogUI на Linux7,
  пользователь увидел интерфейс с недавней игрой и явно подтвердил, что это было
  ДО автоматического перезапуска. Это human eyewitness appearance PASS, без камеры.
- First+late scanout hashes совпали через10040ms; stock/native restore/6boot и3UI
  hashes PASS. Bootstrap/runtime/backend launch приняты предыдущими trial slices.
- Следующая отдельная задача: physical input calibration/navigation; потом
  audio/frontend и actual game integration. Темы/языки/анимации/настройки/навигация,
  игровой процесс, audible audio и full power-cycle всё ещё не приняты.
- Этот раздел новее исторического чек-листа ниже; прежние unavailable-console,
  UI-not-started и другие pending-утверждения сверять с текущими UI_PORT_PLAN и
  FRONTEND_PORT_STATUS. Камеры остаются запрещены.

## Что уже подтверждено на консоли

- Linux7 достигает PID1, работает с SD, загружает собственные модули.
- Прямой запуск через штатный NOR-загрузчик после watchdog-reset проверен;
  это не приёмка полного выключения/включения питания.
- Fixed-mode DRM640x480RGB565: modeset, vblank, DMA readback, растущий IRQ,
  совпадение CPU/DMA pixel hash и реальные цветные полосы на панели — PASS.
  Авторитетный результат: DISPLAY_HARDWARE_VERIFIED.json.
- Во всех завершённых экранных опытах watchdog30с автоматически вернул stock/MTP;
  исходные6 boot hashes восстановлены до host cleanup. NOR не перепрошивалась.
- Это ещё не подтверждение полного интерфейса, игр, звука, кнопок или USB в Linux7.

## 1. Интерфейс и запуск userspace

Готово офлайн: video_drm_backend.c, glibc/MIPS hard-float library
analysis/driver_port/driver_r36_drm_video_v2.so; реальный scaler/DRM, mocked DRM
и MIPS dlopen/error-path PASS. Не экспортирует фиктивные GE/audio методы.

- [ ] Проверить actual console libc/loader/SDL/libstdc++/FreeType/прочие зависимости
  picoarch и frogui_libretro.so. Сохранённая локальная rootfs неполна; Debian
  библиотеки тестового стенда не считать библиотеками консоли.
- [ ] Подготовить RAM/userspace bootstrap, монтирование библиотек/ресурсов,
  необходимые /tmp, SysV IPC, окружение устройства и рабочие каталоги.
  Не запускать stock init целиком: оно может загрузить старые4.4 .ko/службы.
- [ ] Запустить frontend_backend_harness с настоящим новым DRM-драйвером,
  проверить загрузку .so, кадры320x240/640x480, pitch/scaling, ошибки/cleanup.
- [ ] Запустить неизменённый picoarch+frogui_libretro.so через PICOARCH_DRIVER
  без подмены штатной библиотеки на SD. Его отдельный audio-loader ещё требует
  настоящей адаптации; video override не решает звук.
- [ ] Проверить прежние темы, шрифты/кириллицу, список игр, настройки, анимацию,
  вход/выход из меню. Не считать живой процесс или один кадр UI-приёмкой.
- [ ] Проверить tearing/frame pacing/CPU/RAM. Backend пока single-buffer CPU-copy,
  не готовое ускорение GE. При недостаточной производительности доработать
  буферизацию/масштабирование; GE переносить отдельно, если реально понадобится.

## 2. Кнопки

Готово офлайн: отдельный GPIO/serializer kernel candidate, poll-only safe pins,
legacy_keys publisher, явная карта evdev->прежние4B SysV. Native Linux
uinput->evdev->SysV8 cases PASS; сквозная связка native publisher->SysV->MIPS
Gambatte->synthetic ROM press/release PASS. MIPS publisher под QEMU-user получает
EVIOCGID ENOTTY: не выдавать native VM тест за MIPS/physical acceptance.

- [ ] Пересобрать diagnostic init с последними SYN_DROPPED checks: frozen input
  v1 binary был собран до этих source changes. Существующий v1 не перезаписывать.
- [ ] В isolated watchdog-cycle принять GPIO/pinctrl/оба evdev устройства,
  отсутствие влияния на дисплей/SD и корректный автоматический возврат.
- [ ] По очереди записать физические UP/DOWN/LEFT/RIGHT/A/B/X/Y/START/SELECT/L1/R1;
  подписать event ordinals. Порядок12 serial bits не угадывать по чужой плате.
- [ ] Создать карту calibrate_legacy_keys.py, сверить каждую кнопку/отпускание,
  диагонали, несколько одновременных кнопок, debounce/удержание/repeat.
- [ ] Проверить настоящий MIPS evdev->SysV publisher на консоли: held-at-start,
  перезапуск, конфликт с другим publisher, сброс состояния при ошибке.
- [ ] Проверить навигацию прежнего UI и управление внутри эмулятора.
- [ ] Отдельно перенести FN, volume, power-short/long и sleep-policy. Текущий
  diagnostic не выполняет sleep/power/volume действия и не трогает GPIO1/6/19.
- [ ] Учесть пользовательский frogui/keymap.txt, а не навязывать default bits.

## 3. Звук — аппаратная задача отложена

Подробный сценарий: AUDIO_TEST_TODO.ru.md. Native ALSA kernel/module и silent
PCM-пробник собраны, exact userspace/kernel UAPI совпал, software rollback PASS.
Ни DMA на реальном аудиоблоке, ни слышимый звук пока НЕ приняты.

- [ ] Passive stock snapshot и проверка владения аудиоблоком; не отнимать
  работающий DMA у AVP. Quiet snapshot не доказывает будущую эксклюзивность.
- [ ] kernel_cold_audio_silent_v1:48k/S16LE/stereo/нулевые сэмплы/gain0/mute,
  движение DMA, рост IRQ, DROP0/RUN0, stock/MTP/hash-return.
- [ ] Собственное управление amplifierGPIO19/headphoneGPIO15 с проверкой полярности,
  mux/ownership/mute. Чужую syscore firmware не устанавливать.
- [ ] Короткий ограниченный по времени и уровню слышимый тон; разрешена локальная
  микрофонная запись по просьбе пользователя. Не записывать окружение заранее.
- [ ] Настоящий sound_driver backend/интеграция audio-loader picoarch:48k и44.1k,
  буферизация/resampling при необходимости, underrun/stop/перезапуск без зависаний.
- [ ] Системные звуки меню + игровые PCM одновременно с видео и вводом,
  громкость, динамик/наушники, подключение/отключение, отсутствие треска.

## 4. Эмуляторы

Офлайн подтверждено:4 unchanged MIPS cores Gambatte/Gearboy/FCEUmm/QuickNES,
8 runs120 frames с press-release/neutral control, непустые video/PCM callbacks,
original synthetic ROM RAM flags, savestate RAM roundtrip.
Отчёт emulator_smoke_v3/suite.json. Это не реальная игровая/скоростная приёмка,
не запуск через stock picoarch и не покрытие всей коллекции cores.

- [ ] Соединить прежний frontend, новый video/audio backend и физический ввод.
- [ ] Выполнить GB/NES synthetic программы на самой консоли; проверить видео,
  слышимый звук, кнопки и возврат в интерфейс в одном цикле.
- [ ] Проверить собственные законно используемые игры GB/GBC/NES/SNES/MD/GBA,
  затем PS1/PSP/arcade и остальные фактически нужные системы.
- [ ] Отдельно проверить dynarec/JIT/FPU/mmap/cacheflush у gpsp/PCSX/PicoDrive/PPSSPP:
  успех простых interpreter cores ничего не доказывает для этих путей.
- [ ] Проверить BIOS, архивы/кириллические пути, core options, controller mapping.
- [ ] Проверить SRAM saves и savestates на SD, восстановление после restart,
  наличие резервных копий; не повреждать пользовательские saves.
- [ ] Измерить реальный FPS/frame pacing/latency/RAM/swap/температуру и длительную
  стабильность; QEMU wall-time не выдавать за скорость устройства.

## 5. USB — обязательная часть порта

Связь MTP, наблюдавшаяся после watchdog-return, принадлежит STOCK4.4, а не Linux7.
В новом ядре есть подготовленный MUSB peripheral/PIO + CDC профиль, но прежние
hardware опыты не дали enumeration. Это нерешённая задача, не готовый USB.
Офлайн-продолжение: USB_PORT_STATUS.ru.md, private IRQ-lifecycle fix, isolated
CDC PID1 и host PING/PONG diagnostic. Новый build пока проверяется; старый
kernel_usb_cdc_vm_v1 отклонён isolation preflight, не устанавливать.

- [ ] Изолировать USB0 peripheral bring-up на проверенной CPU/IRQ/clock основе;
  проверить PHY/reset/clock/DT, interrupts, endpoint FIFO/control transactions.
  Не добавлять одновременно непроверенные audio/input subsystem changes.
- [ ] Принять Windows enumeration: стандартные descriptors, EP0, configfs/ACM,
  появление порта, двусторонняя передача, bounded timeout и disconnect/reconnect.
- [ ] Получить диагностический командный канал под Linux7, не только после отката.
  При провале watchdog возвращает stock; не зависеть от непроверенного USB для reset.
- [ ] Перенести файловую передачу: userspace FunctionFS/MTP либо собственный
  совместимый интерфейс. Нынешний tfmtp ожидает старый kernel MTP ABI; старые4.4
  gadget .ko бинарно не работают в7. Нужна реальная адаптация.
- [ ] Проверить большие каталоги без предварительной индексации всей SD, файлы
  более4ГиБ, Unicode, create/read/write/delete, отмену и переподключение, checksum.
- [ ] Сохранить background USB рядом с UI/игрой без потери кадров/звука/ввода.
  Определение подключения ПК и запуск служб переносить, а не считать унаследованными.
- [ ] USB host/OTG/VBUS/power-role — отдельная реализация: upstream glue пока
  peripheral/PIO only. Проверить HID-клавиатуру/gamepad, накопитель и нужные BT/WiFi
  dongles отдельно после host bring-up. Не выдавать gadget PASS за host PASS.
- [ ] При mass-storage режиме исключить одновременную запись Windows и Linux
  в тот же FAT. Не отдавать живой RW-mounted раздел как writable LUN.

## 6. Файловая система, питание и общая интеграция

- [ ] Встроить staged FAT guard в отдельный initramfs до первого mount;
  аппаратно read-only принять, затем разрешить writer после проверки RAM/geometry,
  backup/logging и безопасного управления watchdog.
- [ ] Автопроверка после нештатного выключения: fsck на mounted SD запрещён;
  принудительный reset во время writer/flush запрещён. Пока self-repair НЕ установлен.
- [ ] Корректные shutdown/reboot/sleep/wake, sync/unmount/swapoff, battery ADC,
  headphone/backlight/brightness и отсутствие записи в неверные persistent/NOR области.
- [ ] Совместный длительный UI+игра+звук+ввод+USB+SD прогон, ошибка периферии,
  нехватка памяти, чистый запуск и полное выключение/включение питания.
- [ ] Временные boot-файлы, backup/fallback,6 hashes, fresh proof и watchdog проверять
  перед каждым кандидатом. Проверенный DISPLAY_HARDWARE_VERIFIED baseline не менять.

## Порядок продолжения

Пока консоль недоступна: офлайн bridge/emulator/runtime work, строгие проверки
кандидатов, никакого фиктивного hardware PASS.
После подключения: input calibration и video-backend harness; отдельно silent audio;
ранний USB командный канал; затем прежний UI/игра со всеми backend. ФС-ремонт —
отдельный maintenance опыт, не смешивать с коротким30-секундным watchdog-тестом.
Полный AVP ioctl/kshm/mmz/GE стек переносить только по подтверждённой необходимости:
native DRM/ALSA может обходить часть старого стека, но не подменять требуемые функции
заглушками. Необязательные HDMI/TV/codecs — не блокер базового handheld UI без запроса.

## Опорные документы

- FRONTEND_PORT_STATUS.json — машинные статусы compatibility components.
- DISPLAY_HARDWARE_VERIFIED.json — фактическая приёмка дисплея.
- AUDIO_TEST_TODO.ru.md — отложенная звуковая приёмка.
- fat_boot_guard_STATUS.json — staged repair, production writer disabled.
- PORT_MATRIX.ru.md — подробная матрица платформенных драйверов.
- AGENT_HANDOFF.ru.md в корне — передача работы и история, старые записи исторические.
