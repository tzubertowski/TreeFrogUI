# r36_amprpc_poll

Opt-in kernel transport diagnostic для HC16E310/stock AVP. Собран под
`7.2.0-rc5-r36port`, MIPS32r2/O32/LE; на железе пока не проверен.

Driver probe не посылает запросов. DT compatible `r36lab,amprpc-poll`, точные
ресурсы TX18800800/100 и RX18866800/100. Default node disabled. Для теста используется
отдельный module-mode DTB и строго соответствующий kernel/module manifest.

Когда консоль снова доступна, PID1-пробник с аргументом `--kernel-probe`:
1. Загружает r36_amprpc_poll.ko через finit_module без force flags.
2. Записывает1 в sysfs test_roundtrip.
3. Считывает last_result в SD log и выдаёт kernel_transport=PASS только при
   завершённом отрицательном open ответе AVP.
4. Закрывает log, синхронизирует и размонтирует SD, сохраняет PID1 до watchdog reset.

Это один запрос отсутствующего пути, а не реализация framebuffer/audio ioctl.
IRQ/callback API, очереди нескольких клиентов, nested buffers и отмена не перенесены.
Не подключать модуль к существующим avp-proxy узлам и не подавать его на stock4.4
или frozen7.2-r36lab: vermagic должен совпадать с r36port kernel.

Модуль не вызывает присланные function pointers, не подтверждает чужие RX packets,
имеет bounded poll/ack. После публикации packet page сохраняется до reset, включая
timeout/unload, чтобы peer не обращался к переработанной Linux странице.
Последующие запросы той же инстанции дают EALREADY. Ничего не записывается в
GPIO/DSI/audio/flash/standby как часть этого диагностического теста.

Исходные wire/register наблюдения: analysis/driver_port/AMPRPC_NOTES.ru.md.
Packet builder и IRQ planner сравниваются с настоящими stock MIPS инструкциями.
