# Состояние исследования независимой загрузки

## Главное

**Последнее аппаратное обновление:** прямой NOR-start Linux7 после watchdog-reset
прошёл до PID1/SD proof. Stage6/tag0xc5d28f11, fresh run_id
aa8961f5e8fd47cdabb0a2dc3081efa7; release7.2.0-rc5-r36lab build#12, pid1.
Watchdog автоматически вернул stock, все6 boot hashes исходные, ПК не переписывал
boot-файл. `kernel_cold_early_restore_v1_trial_VERIFIED.json`, подробности
`COLD_BOOT.ru.md`. Это NOR-start без RAM-handoff; полный power-off/on не испытан.

Предшествующий аппаратный этап: восстановление `advapi32.dll` до входа в
Linux реально прошло. Stage202/tag0xbd6eb903,3954299B, source/readback CRCc3693b14,
штатный MD53510ffdfd039f850345ace1489572659; ПК файл не переписывал.
`kernel_loader_early_restore_probe_v1_trial.json`, `host_cleanup_wrote_boot_file=false`.
Перед этим отдельно подтверждены watchdog pending-skip, sandbox read/write и
полная sandbox copy. Подробности и ограничения интеграции: `EARLY_RESTORE.ru.md`.
В этих подготовительных испытаниях запускался stock4.4; последующий Linux7 тест
описан в начале этой сводки.

Алгоритм и ключ контейнеров SD **восстановлены и проверены**. Прямой старт Linux7
из NOR после аппаратного reset подтверждён. Frozen `kernel_ready` сам по себе —
RAM-handoff bundle; новый NOR candidate находится отдельно в
`payload/kernel_cold_early_restore_v1`. Полное выключение питания — отдельная проверка.

2026-11-13 аппаратно подтверждён промежуточный путь: NOR загружает заново
зашифрованный образ, выполняет добавленный нами зонд и затем запускает исходный
Linux 4.4. Уникальная RAM-метка stage193/tag0xa1227d68 считана через MTP.
После теста оригинальный `advapi32.dll` восстановлен и проверен через MTP.
Отчёт: `stock_bridge_trial.json`; это не доказательство холодного старта Linux 7.

Кандидат Linux 7 `payload/kernel_direct_advapi_oneshot` ранее не вернул MTP и
не восстановил загрузочный файл. Пользователь видел логотип TreeFrogUI.
Оригинал восстановлен через проверенный кардридер, CHKDSK вернул0, затем stock
4.4 и MD5 проверены на консоли. RAM-журнал после выключения невалиден:
`post_restore_20261113T020302Z/report.json`; точная последняя стадия неизвестна.

Найдена условная ошибка старого размещения shim: helper0x89dba100 перед прыжком
при magic0x1995 читает u16 по физическому0x2 как порог таймера. Первая инструкция
shim давала16736 вместо штатного0. Это доказано оригинальным кодом в эмуляторе,
но значение magic при неудачном старте неизвестно. Исправление переносит вход
на0x80010000 и сохраняет низ RAM нулевым. Отдельный кандидат
`payload/kernel_direct_advapi_lowram_v3` не установлен; kernel_entry/start_kernel
в эмуляторе достигнуты. `loader_wait_emulation.json` и `cold_emulation.json`.
Исправленный v3 также принят оригинальным bootm/gzip с негативными CRC-кейсами:
`loader_image_emulation_v3.json`.

Pre-kernel восстановление и stock fallback теперь интегрированы и проверены:
native fallbackstage208/tag0xb7b7c950, normal Linux7stage6/tag0xc5d28f11.
Далее: power-off/on acceptance, чистое завершение loader FAT-сессии и перенос
периферии/TreeFrogUI. Холодная проверка внешнего модуля в boot-профиле не проводилась.
Старый SD-root/PID1 one-shot восстанавливал advapi слишком поздно; предыдущий сбой
показал, что этот механизм не гарантирует возврат. Не повторять прежний образ.
В старый шаблон добавлен progress log; новый loader restorer от PID1 не зависит.

## Проверенные данные

- Контейнер: nonce12 || u32LE(длина plaintext) || ChaCha20 ciphertext.
  Фиксированный ключ256бит, IETF nonce96бит, counter0. OTP/DSC не нужны.
- Ключ извлекает `scripts/boot_crypto/codec.py` из распакованного TPL;
  SHA256 ключа9854a91538f96b8a67c1ff0db7d9df5e6ad6c8e6e355c1c0c37730fc9d81b659.
- Два ELF совпали полностью; четыре исходных контейнера воспроизведены
  побайтно с исходными nonce. Оригинальный MIPS decryptor принял нашу шифровку.
  `cipher_verified.json`, `loader_cipher_emulation.json`, `native_oracle.json`.
- `AcXtrnal`: текст XOR0x5a, checksum=zlib.crc32(полный файл)^0xffffffff.
  Все18 строк проверены: `integrity_verified.json`. Это не подпись.
- Для этой платы resolver выбирает Windows-алиасы: vmlinux.uImage→advapi32.dll,
  dtb.bin→Bubbles.scr, avp.uImage→ApplicationFrame.dll.
  `boot_names_verified.json`, `actual_bootfiles.json`.
- Оригинальный код bootm принял заголовки/CRC stock и нашего образа, отверг
  испорченные варианты. Оригинальный gzip распаковал оба образа побайтно точно.
  `loader_image_emulation.json`. Аллокатор и вывод заменены emulator stubs;
  это не полная эмуляция SoC/SD/кэшей.
-14 crypto pytest PASS после изменений; синтаксис PID1 shell проверен.

## Отброшенный ложный bootloader dump

NOR header указывает load/entry0xa9e70000 и size0x4a620. Через NSH снят
`bootloader_ram.bin` (304672B), но затем проверено: AVP `xd 9e70000` и
`xd 1e70000` дают одинаковый256-байтный prefix. Это aliased live RAM, содержит
libz/BusyBox/HarfBuzz и dentry slab, а не доказанно сохранившийся загрузчик.
Название файла историческое; **не анализировать его как подтверждённый TPL**.

В отличие от ложного live-dump, `card2_files/kdump/tpl_decrypted.bin` теперь
разобран: LZMA-alone по0x2e48, распакованный размер812464B, корректный EOF.
Результат `tpl_lzma_unpacked.bin`, SHA256
c95aa3062c308818e4572f65e8c29632ec04cd390cceac0a63d4b053fb4d0ebc.
Именно его код даёт проверенные cipher, resolver и bootm.

Исторически строка `ha_decrypt` обнаружена в старом RAM-dentry рядом с `tls`. DWARF layout
подтвердил: действительное имя этого dentry `tls`, inode0, а `ha_decrypt` —
остаток inline-name. Это совместимо с прежним именем `chacha_decrypt`, но не
доказывает ни наличие такого файла, ни функцию, ни алгоритм. Позднее настоящий
`/usr/bin/chacha_decrypt` извлечён из расшифрованного штатного initramfs отдельно.

## Одноразовый захват initramfs: испытан, неуспешен, откатан

Подготовлен capture_dtb.py: меняет только `/chosen/bootargs`, пытается запустить
BusyBox shell до `/init`, сохранить ранние scripts/`*crypt*` в RAM `/r36-capture`,
затем `exec /init`. Оригинальное дерево и прочие свойства побайтово/семантически
сверены;4 pytest PASS, candidate33643B вместо33251B.

Диагностический DTB был установлен с резервными копиями на ПК и SD.
После перезапуска MTP не появился; пользователь увидел сообщение о повреждённой
карте. Причина не локализована: это может быть bootargs/boot verification,
а не повреждение FAT. Успешного перехвата initramfs нет.

**Исходный DTB затем восстановлен в картридере**, MD5
`9492f590fc2db86694d3fdc52a25c3e4`. Диагностическая правка больше не активна.
Авторитетный статус: `capture_deployment.json`, `original_restored=true`.
Не повторять тот же capture вслепую: проверить реальные ограничения bootloader,
короткий bootargs/командную строку и контроль целостности.

## Ремонт карты после испытания

Карта поддельная: reported~64GB, фактический разрешённый раздел~16GB.
В Windows идентифицированы F:,serial5446089B,disk2 Realtek PCIe CardReader,
offset16384,size15728508928. Фальшивый хвост не затрагивался.

Полный backup именно раздела сохранён до изменений:
`analysis/fat_repair/reader-20261112-231822/partition-before.img`.
SHA256 `d776da6e1e4a704dc019fc01f9e529f19cb2a5c32a034839d4ff8e1f7f00ea7b`.

Windows CHKDSK F: /F /X (без /R) исправил FAT, сохранил одну потерянную цепочку
16KiB в FOUND.001/FILE0000.CHK. Prefix совпадает с нашим keepawake shell script;
это не найденный decryptor. Повторный CHKDSK F: вернул0 и сообщил об отсутствии проблем.
Stock Linux/AVP/DTB hashes совпали с оригинальными.
Отчёт: `analysis/fat_repair/reader-20261112-231822/verified_repair.json`.

## Внешний источник для следующего исследования

https://github.com/csnewman/gb350-linux — проект для GB350v1.22/HC1600A.
README и scripts/build-kernel.sh описывают обычный gzip legacy uImage и stock NOR
bootloader без encryption step. Это интересный возможный путь plaintext fallback,
**но совместимость именно с нашей encrypted-версией загрузчика не проверена**.

https://raw.githubusercontent.com/csnewman/gb350-linux/master/scripts/build-kernel.sh
https://raw.githubusercontent.com/csnewman/gb350-linux/master/README.md

Нельзя просто копировать его полный образ/DTB/AVP: пользователь хочет сохранить
нынешний TreeFrogUI, а проект использует другой userspace и своё AVP firmware.
Можно исследовать boot protocol и драйверы с учётом лицензии и отличий платы.
