# Автоматический возврат диагностической загрузки

## Реализация

Аппаратный watchdog запускается **до** перехода в новое ядро, чтобы сработать
также при остановке до PID1. Таймер не зависит от планировщика Linux.

- Измеренная частота при control0x26: samples187495,188358,187467 Гц;
  median187495 Гц. Для диагностических загрузок используется187500 Гц.
- Counter: phys0x18818500; control:0x18818504.
- Counter растёт до переполнения; reload равен `0 - rate_hz * seconds`.
- Clock gate watchdog: bit22 регистра0x18800060, enable очищает бит.
- Штатная последовательность restart использует reload=-6, control0x26.

`r36bootctl boot-detached` сначала запускает внешний armer, затем отключает
старый USB gadget. Внутри BOOT ioctl загрузчик повторно заводит watchdog прямо
перед cache flush/relocation. Поэтому предусмотрен возврат и при срыве userspace
части после UDC disconnect. Если внешний armer завершился ошибкой, UDC не отключается.

В новом ядре watchdog clock помечен CLK_IS_CRITICAL. Сам диагностический init
его не кормит и не отменяет, поэтому штатный timeout остаётся30 секунд.
Другие аппаратные блоки и причина последнего неполученного USB пока исследуются.

## Что проверено на консоли

1. Три20-мс измерения со штатным ядром, после каждого восстановлены control/counter/gate.
2. Stock-only test: arm187495 Гц на10 секунд. Без физического вмешательства снова
   появился штатный MTP; uptime до552.81с, после28.25с.
3. Метка tag0xbc4c48f3 в хвосте RAM пережила этот сброс. Результат:
   `wdt_reset_trial_result.json`, capture `wdt_reset_trial_tail.bin`.
4. Запуск собственного ядра с30-секундным watchdog: после ожидания вернулся stock,
   uptime41.36с; метка tag0x3e67b554 показала stage4 (`kernel_entry reached`).
   Подтверждены автоматический возврат и вход в новый kernel_entry.
5. Следующий запуск с более подробными метками **не вернул USB к ожидаемому сроку**.
   Поэтому надёжность полного цикла ещё не считается доказанной. Причина неизвестна:
   отсутствие USB не позволяет отличить отсутствие reset от проблемы последующей загрузки.
6. Позднее замороженный комплект `payload/kernel_ready` успешно выполнил оба
   минимальных профиля boot/driver и дважды автоматически вернулся в stock.
   Для именно этого комплекта полный цикл подтверждён; это не распространяется
   автоматически на прежние расширенные ports-образы.
   Отчёт: `analysis/acceptance/1794498370587679900/suite.json`.

## Настройка и запуск

По умолчанию30 секунд; допустимо5..300 при сборке loader:

```powershell
$env:R36_BOOT_TIMEOUT = '30'
python D:\r36s-\scripts\kernel_lab\build_loader.py
Remove-Item Env:R36_BOOT_TIMEOUT
```

Timeout и частота записываются в `payload/kernel_lab/manifest.json` и в trace.
После изменения loader на текущем стоке его нельзя заменить через rmmod:
CONFIG_MODULE_UNLOAD у штатного ядра выключен; нужен перезапуск перед новой версией.

Один автоматизированный диагностический цикл:

```powershell
python D:\r36s-\scripts\kernel_lab\run_cycle.py
```

Runner проверяет manifest, доставляет комплект, проверяет prepare/probe,
выполняет handoff, кратко проверяет CDC, ждёт watchdog + время stock boot,
включает keepawake и читает trace. Это один ограниченный прогон, не бесконечный
цикл повторных загрузок. Промежуточные результаты сохраняются в
`analysis/driver_port/attempts/`; итог — в `last_cycle.json`.

## Устойчивый участок трассировки

Phys0x02f91000, размер0xe00 (3584 байта). Linux отдаёт allocator только полные
страницы до0x02f90fff, а System RAM заканчивается0x02f91e4f. Наш участок лежит
в последней неполной странице и не пересекает следующий регион.

Схема private ABI v2: 64-байтный header +3520-байтное кольцо. Header содержит magic,
версию, stage, entry/control/trampoline, watchdog_hz/seconds, session tag и page count.
Поздние слова используются для fw_arg0/fw_arg1/FDT.

Основные стадии:1 loader;2 relocation;3 copy complete;4 kernel_entry;
5 RAM console;6 userspace. Дополнительные33..59 локализуют BSS, stack, start_kernel,
setup_arch, CPU/FDT, MMU/cache, IRQ/time и console init.

```powershell
python D:\r36s-\scripts\kernel_lab\collect_ramconsole.py
```

Trace каждого полученного tag сохраняется в `analysis/driver_port/runs/<tag>/`.
Сохранность после watchdog-reset проверена; полный power-off может стереть trace.
