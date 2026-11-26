# Проверка звука: результаты и оставшиеся задачи

## Обновление 2026-11-15

Пользователь подключил консоль и разрешил аппаратные тесты. Silent v3 **PASS**:
analysis/boot_crypto/kernel_cold_audio_silent_v3_trial.json. Ровно24576frames,
DMA movement, IRQ0->41, gain0/mute1, DROP0/RUN0, fresh report. Watchdog вернул
stock/MTP,6 hashes исходные до host cleanup, host_cleanup_wrote_boot_file=false.
Первые v1/v2 strict FAIL из-за бюджета retries/последней partial write сохранены,
результаты не подменялись. Source active profile kernel_audio_silent_active_v3.
Следующие открытые пункты —4..7: amplifier/headphone policy, короткий слышимый
сигнал/локальный микрофон и настоящий backend picoarch. Silent DMA не audible PASS.

## Офлайн-подготовка ALSA-бэкенда `picoarch` (`sound_driver_*`) 2026-11-17

- Статическим дизассемблированием `picoarch` (`0x42c2a0..0x42cf88`) и `driver_gb350.so`
  (`0x8b60..0x8de8`) подтверждён точный контракт вызовов аудио-загрузчика:
  - `picoarch` читает `getenv("PICOARCH_DRIVER")` (`0x42c4e4`) также для аудио и
    резолвит `sound_driver_init(void *dev, int rate, int channels)`,
    `sound_driver_playframe(const void *buf, int frames)`, `sound_driver_deinit(void)`
    (и опциональный `sound_driver_flush(void)`).
  - При старте потока (`0x42ce80..0x42cfb8`) `picoarch` обязательно выполняет
    прогревочный цикл `sound_driver_init(NULL, 48000, 2) -> sound_driver_deinit() ->
    usleep(100000) -> sound_driver_init(NULL, 48000, 2)` и только после второго
    успешного `init` входит в рабочий цикл `sound_driver_playframe(buf, 480)`
    (блоки по 480 стерео-фреймов `S16_LE` = 10 мс при 48 кГц).
- Реализован `scripts/peripheral_lab/audio_alsa_backend.c` поверх проверенного
  12-словного UAPI `r36_hc16xx_i2s` (`/dev/snd/pcmC0D0p`, проверка `info.id == "I2S"`,
  `48000 Hz`, `S16_LE`, стерео, `period=512`, `buffer=4096`), с идемпотентным
  повторным `init -> deinit -> init`, восстановлением после `EPIPE`/`ESTRPIPE`
  через `SNDRV_PCM_IOCTL_PREPARE`, обработкой `EAGAIN` и конвертацией частоты/моно
  при вызове не-48kHz источником.
- Добавлен `scripts/peripheral_lab/test_audio_alsa_backend.py` (C-модель ioctl +
  кросс-компиляция `zig cc -target mipsel-linux.4.4-musleabi -Werror`): PASS.
  Аппаратная приёмка слышимого звука и `GPIO19`/`GPIO15` остаётся отдельной задачей
  после включения консоли.

Ниже — первоначальный план, его статусы на2026-11-14 исторические.

Статус 2026-11-14: пользователь временно не может подключить консоль и просит
продолжать кнопки/эмуляторы офлайн. Звук НЕ проверен на железе; слышимый сигнал,
микрофон, amplifier/headphone acceptance НЕ выполнены. Постоянное опрашивание
MTP и запись окружения не нужны.

## Подготовленный комплект

- Source: payload/audio_driver_source_v3.
- Проверенный build: payload/kernel_audio_silent_vm_v1/build_receipt.json.
- Silent profile: payload/kernel_audio_silent_active_v1.
- Cold wrapper: payload/kernel_cold_audio_silent_v1, оба cold_restore отчёта PASS.
- Userspace/kernel ALSA ABI12 words совпали;29 imports модуля экспортированы.
- Начальные gain0/mute=true; old DMA RUN вызывает отказ до reset аудиоблока.
- Параметр allow_takeover обязателен; чужая syscore firmware не используется.

## После подключения консоли

1. Проверить точную stock identity,6 boot hashes, watchdog off и backup.
2. Выполнить пассивный snapshot analysis/driver_port/r36-audio-passive-v1.
   Неподвижные регистры не доказывают исключительное владение AVP; при активном
   RUN или движении DMA сначала разобраться с владельцем, не сбрасывать вслепую.
3. Один isolated kernel7 silent PCM опыт с watchdog30с и early stock restoration.
   Проверить24576 frames48kHz/S16LE/stereo, DMA movement, IRQ growth, gain0/mute1,
   DROP0 и RUN0. Вернуть stock/MTP и подтвердить hashes. Не засчитывать cold/PID1
   proof как audio PASS; использовать audio_result и полный свежий report.
4. При silent PASS проверить собственные GPIO19 amp/GPIO15 headphone policy и
   владение ими. Затем короткий умеренный тон, ограниченный по времени и уровню.
   Пользователь разрешал слышимый/громкий сигнал, но неизвестный тракт сначала
   проверяется без максимального gain. Не переключать powerGPIO1/LCD reset6.
5. По разрешению пользователя записать короткий локальный микрофонный фрагмент
   только на время тона, без публикации. Проверить наличие ожидаемой частоты и
   отличие от фонового шума; не заявлять прослушивание, если доступен только анализ.
6. Обязательно STOP/mute, watchdog-return,6 stock hashes, UI/MTP после опыта.
7. После аппаратного PASS адаптировать настоящий audio backend picoarch. Video
   PICOARCH_DRIVER override не заменяет независимый audio loader. Не экспортировать
   dummy-success sound_driver_*.

## Известные ограничения

Авторемонт FAT не установлен. Эти audio-кандидаты не запускают fsck на mounted SD.
Driver probe меняет audio reset/PLL/pad clocks после opt-in, поэтому не загружать
его в штатный Linux. GPIO19/15 пока не реализованы. Ни гарнитура, ни динамик не
объявляются рабочими по одному движению DMA.
