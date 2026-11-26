# AMPRPC / AVP: статические опорные точки для переноса

Статус: ABI исследуется по сохранённому ядру4.4.186. Реализованы userspace
polling client и kernel polling diagnostic, kernel module собран под7.2-r36port.
AVP response на устройстве ещё не проверен. Полные callback/ioctl/buffer lifetime
не восстановлены; это не готовый общий avp-proxy transport.

## Что подтверждено статически

Источник: `analysis/kmem/kernel_80000000.bin`, kallsyms, Capstone MIPS32 LE;
просмотр: `scripts/_kmdis.py ADDRESS SIZE`.

- DT предоставляет 16 mailbox MMIO-ресурсов по 0x20 байт:
  `0x18800800..0x188008e0` и `0x18866800..0x188668e0`, шаг0x20; IRQ66.
- `amprpc_probe=0x802ba9c8` получает один объект из kmem_cache, выполняет
  `_dma_cache_wback(object,0x8000)` и переводит его указатель в KSEG1.
  Затем формирует 8 message-slot указателей с шагом0x1000.
- `msgs=0x80b50e44`, `msgbitmap=0x80b50e00` начинается с0xff,
  `mboxbitmap=0x80b50dfc` начинается с0x0f, `msg_wq=0x80b50e04`.
- `g_amprpc_data=0x80b509b0`; probe сохраняет IRQ и mapped resources.
- Для первых четырёх TX mailbox в offset+8 записывается0x00010002,
  для следующих четырёх0x00000101. Значение битов ещё не расшифровано.
- `msg_other_core=0x802ba658`: выбирает свободный TX mailbox из bitmap,
  записывает прямой 32-битный message pointer в mailbox+0x0c, проверяет readback,
  затем устанавливает bit0 mailbox+0. Это не стандартный RPMsg/VirtIO transport.
- `avp_open=0x802bad04`: request opcode0x1000, размер path ограничен одной
  4-КиБ message slot. Ответ ожидается через waitqueue, timeout0x7530 jiffies.
- `avp_open` возвращает word+0x10 после перехода message state+0 к2,
  затем устанавливает state+8 к4 и освобождает slot bitmap.

Наблюдаемый layout именно запроса open:

| Offset | Наблюдение |
|---|---|
| +0x00 | начальное значение1; значение2 означает готовность ответа |
| +0x04 | opcode0x1000 |
| +0x08 | начальное значение1; завершение/освобождение4 |
| +0x0c | указатель на Linux waitqueue, передаваемый как непрозрачное значение |
| +0x10 | return value в ответе |
| +0x14 | второй аргумент avp_open |
| +0x18 | третий аргумент avp_open |
| +0x1c | NUL-terminated path |

`do_msg=0x802babf8` обрабатывает не только ответы, но и callback-сообщения.
Наблюдались type3/opcode0x1009, function pointer+0x10, argument+0x14,
inline/out-of-line data. Требуется восстановление полноценного callback ABI,
проверка владения буферами и жизненного цикла, а не только синхронный open.

## Почему одного generic char proxy недостаточно

`proxy_ioctl=0x802c0bdc` заметно больше простого `_IOC_SIZE`-копирования.
В ioctl могут быть вложенные указатели. Пользовательский адрес Linux нельзя
передавать AVP как будто у него та же MMU. Для корректного переноса нужны:

1. карта совместно доступной памяти и преобразования адресов CPU;
2. правила cache writeback/invalidate и порядок публикации request/response;
3. mailbox acknowledge/release и ISR (`0x802ba840`);
4. read/write/ioctl/poll/mmap ABI и обработка вложенных буферов;
5. callbacks/work queues, отмена при close/удалении, таймауты;
6. kshm/mmz allocator и независимое управление памятью AVP.

Следующие функции для исследования: `do_mbox_release=0x802ba5fc`,
`amprpc_mbox_isr=0x802ba840`, `avp_read=0x802bb154`,
`avp_write=0x802bb3a8`, `avp_ioctl=0x802bb5ec`,
`proxy_ioctl=0x802c0bdc`, `kshm_request_read=0x802bd3dc`,
`kshm_request_write=0x802bd620`.

Все адреса относятся только к измеренному стоковому 4.4.186 #23.
В новом Linux адреса и внутренние структуры будут другими; переносится протокол,
а не старые kernel pointers и не бинарные .ko.

## Продолжение 2026-11-12: ISR, пассивный снимок и первая C-логика

### Статически восстановленный алгоритм

Дополнительно прочитаны `do_mbox_release`, `msg_other_core`, `amprpc_mbox_isr`,
`do_msg`, основной путь `avp_open`. Символы `down`/`up` подтверждают, что
`do_mbox_release` возвращает бит TX bitmap под семафором и освобождает
семафор отправки. Освобождение TX mailbox не равно освобождению message slot.

В `g_amprpc_data` word+0 — IRQ, следующие 16 words — mapped resources:

- `tx[i] = data+4+4*i`, i0..7: phys `0x18800800+0x20*i`;
- `rx[i] = data+0x24+4*i`, i0..7: phys `0x18866800+0x20*i`.

Названия tx/rx здесь описывают наблюдаемый доступ, не полную спецификацию IP.
ISR проверяет `tx[i]+8` для i0..7:

1. Bit16 (`0x10000`), допустимый только i0..3: очередь
   `work_queue(find_work(), do_mbox_release, i)`, запись
   `(status & ~0x10100) | 0x10000` в `tx[i]+8`, ожидание сброса bit16.
2. Bit8 (`0x100`), допустимый только i4..7: читать pointer из `rx[i]+0x0c`,
   записать туда0, дождаться readback0; поставить `do_msg(pointer)` в очередь;
   записать `(status & ~0x10100) | 0x100` в `tx[i]+8`, дождаться сброса bit8;
   затем записать1 в `tx[i]+4`.
3. Неожиданный pending bit в противоположной группе приводит в старом ISR
   к бесконечному циклу. Ожидания readback/ack тоже не ограничены по времени.

`work_queue=0x802bc600`; это отложенная обработка, а не вызов callback
непосредственно в ISR. `find_work` ищет свободную запись среди64 по16 байт;
исчерпание пула нужно отдельно учитывать в новом драйвере.

В `do_msg` для response state2 проверяется также peer state3, затем будится
waitqueue по word+0x0c. Для callback state3/opcode0x1009/peer state1:
peer state переводится к2, function pointer берётся из+0x10, аргумент из+0x14.
Ненулевые13 бит halfword+0x1a выбирают inline данные+0x20; иначе берётся
указатель из+0x1c. После вызова записываются state4 и peer state3, затем сообщение
отправляется обратно. Это **не разрешение** вызывать произвольный pointer в7.2:
регистрация callback, проверка адресов и владение payload ещё не восстановлены.

### Подтверждение исполнением стокового кода, не на железе

`scripts/kernel_lab/emulate_amprpc.py` исполняет реальные инструкции
`0x802ba840..0x802ba9c8` на MIPS74KF. MMIO моделируется с предположением W1C
для pending bits; work allocator/queue заменены наблюдателями.13 сценариев:
все8 mailbox отдельно, все pending, пустое IRQ,2 wrong-group и stuck ack.
Они прошли. Запись: `analysis/driver_port/amprpc_isr_emulation_20261112.json`.
SHA256 ISR: `246faca5f691e5160502c6893bb1768f51ca78c69c2b852479952024e5e5e6d4`.

Начат перенос register planner в
`scripts/kernel_lab/ports/amprpc-mailbox-plan.h`. Код не подключён к MMIO/IRQ
и ещё не является работающим kernel driver. Он возвращает набор необходимых
действий/ack value; правильный порядок обязан обеспечить будущий MMIO caller.
Wrong-group и смешанные pending bits отвергаются без записей.
24 сравнения C-кода с настоящим ISR проверяют8 mailbox и3 конфигурации status.
Компиляция C — host GCC, **не MIPS kernel build**. До интеграции нужны bounded
polling, порядок memory barriers, teardown, очередь с ограничениями и transport.

### Живой пассивный снимок стока

`scripts/kernel_lab/amprpc_inspect.py` проверяет точную stock identity, IRQ/resource
fingerprint, границы RAM/KSEG1/выравнивание/непрерывность8 слотов, затем читает
только RAM через mdump. Не читает/не подтверждает mailbox MMIO, не открывает
AVP-узлы и не отправляет запросы. Каждый WPD вызов ограничен20с отдельным worker.

Снимок: `analysis/driver_port/amprpc/1794501998987075900/`.
Наблюдались IRQ66, bitmap TX0x0f, message bitmap0xff, pool
KSEG1 `0xa21d8000..0xa21df000` (phys base0x021d8000),8 слотов по4096B.
Таблицы до/после побайтно одинаковы, **снимок не атомарный**. Слоты свободны,
поэтому содержимое — не текущие запросы. В слотах6/7 остались похожие на
завершённые сообщения state2/opcode0x1003/peer state4. Это не полная wire spec.

Последний полный pytest:77 passed, включая4 проверки frozen driver candidate.
Обычный pytest temp-dir был недоступен; использован новый --basetemp в analysis.
Unicorn изолирован в дочернем процессе: внутри pytest его Windows native exception
handler печатал access-violation diagnostics несмотря на успешное завершение;
изолированный последний прогон прошёл без этих сообщений.

### Следующий реальный шаг

Обновление13 ноября: WSL не трогалась; отдельная workspace-owned Linux VM
с clang20/GNU MIPS as2.44 собрала kernel7.2-r36port иr36_amprpc_poll.ko.
Пакет open побайтно совпал с original avp_open в7 сценариях. См.
amprpc_open_wire_verified.json и UI_PORT_PLAN.ru.md. Пользователь отложил доступ
к консоли; очередной hardware test пока не выполняется.

Исторический план до появления отдельной VM: восстановить build WSL, затем
собрать отдельный кандидат, не frozen kernel_ready.
Безопасно изолировать input-профиль от USB и получить input inventory/events через
SD proof. **В этом продолжении input-профиль не изменён и не испытан.**
Для AMPRPC сначала восстановить slot/callback lifecycle и shared-memory/cache
правила, затем интегрировать bounded mailbox transport. Не передавать старые
указатели callbacks новому ядру и не объявлять планировщик готовым AVP-драйвером.
