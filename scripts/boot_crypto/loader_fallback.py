"""Emit a native hcboot fallback that reloads and boots the validated SD backup."""
from loader_fs_probe import (Assembly, TRACE, RESOLVE, OPEN, READ, CLOSE,
                             CRITICAL_ENTER, CRITICAL_LEAVE, MASK_INTERRUPTS,
                             lw, move, addiu, restore_interrupt_masks,
                             arm_watchdog, refresh_watchdog, resolve_path, call_local)
from build_direct_candidate import store
import struct

DECRYPT = 0x89DAB188
BOOTM = 0x89DAA840
FAIL_ENTRY = 0x80F00000


def terminal_stub(base=FAIL_ENTRY):
    a = Assembly(base)
    a.constant(16, TRACE)
    a.constant(8, 209)
    a.emit(store(8, 16, 16), 0x0000000F)
    arm_watchdog(a, 5)
    a.label("terminal")
    a.jump("terminal")
    return a.finish()


def emit_fallback(a, spec, loader):
    a.label("fallback_start")
    a.constant(8, 206)
    a.emit(store(8, 16, 16), 0x0000000F)
    arm_watchdog(a, 30)
    for address in (RESOLVE, OPEN, READ, CLOSE, CRITICAL_ENTER, CRITICAL_LEAVE,
                    MASK_INTERRUPTS, DECRYPT, BOOTM):
        for index in range(4):
            a.constant(8, address + 4 * index)
            a.emit(lw(9, 0, 8))
            a.constant(10, struct.unpack_from("<I", loader, address - 0x89DA0000 + 4 * index)[0])
            a.branch(5, 9, 10, "fallback_failed")
    a.constant(8, 0x89E6665C)
    a.emit(lw(8, 0, 8))
    a.branch(4, 8, 0, "fallback_failed")
    a.emit(lw(20, 0x48, 8))
    a.constant(9, 33)
    a.emit(0x0289482B)
    a.branch(4, 9, 0, "fallback_failed")
    a.branch(4, 20, 0, "fallback_failed")
    restore_interrupt_masks(a)
    a.emit(move(21, 20))
    a.label("fallback_leave")
    a.call(CRITICAL_LEAVE)
    a.emit(addiu(21, 21, -1))
    a.branch(5, 21, 0, "fallback_leave")
    a.constant(8, 2)
    a.emit(store(8, 432, 16))
    resolve_path(a, "fallback_source", error="fallback_failed")
    a.emit(addiu(4, 29, 0x20), move(5, 0), move(6, 0), move(7, 0))
    a.call(OPEN)
    a.branch(1, 2, 0, "fallback_failed")
    a.emit(move(17, 2))
    call_local(a, "read_exact_crc")
    a.emit(store(12, 436, 16), move(4, 17))
    a.call(CLOSE)
    a.branch(5, 2, 0, "fallback_failed")
    a.branch(4, 19, 0, "fallback_failed")
    refresh_watchdog(a)
    a.constant(4, 0x81000000)
    a.constant(5, spec["bytes"])
    a.constant(6, 0x81000010)
    a.emit(addiu(7, 29, 0xDC))
    a.call(DECRYPT)
    a.emit(store(2, 440, 16))
    a.branch(5, 2, 0, "fallback_failed")
    a.emit(lw(8, 0xDC, 29), store(8, 444, 16))
    a.constant(9, spec["bytes"] - 16)
    a.branch(5, 8, 9, "fallback_failed")
    a.constant(8, 0x81000010)
    a.emit(lw(8, 0, 8))
    a.constant(9, 0x56190527)
    a.branch(5, 8, 9, "fallback_failed")

    # Four normal bootm argv entries; keep the original loader-provided DTB.
    a.emit(lw(8, 0x104, 29))
    a.pointer(10, "fallback_hex")
    for index in range(8):
        shift = 28 - 4 * index
        a.emit(8 << 16 | 9 << 11 | shift << 6 | 2)  # srl t1,t0,shift
        a.emit(0x3129000F, 0x01494821, 0x91290000,
               0xA3A90000 | (0xE0 + index))  # nibble lookup and sb
    a.emit(0xA3A000E8)
    for index, label in enumerate(("fallback_bootm", "fallback_address", "fallback_dash")):
        a.pointer(8, label)
        a.emit(store(8, 0x160 + 4 * index, 29))
    a.emit(addiu(8, 29, 0xE0), store(8, 0x16C, 29))
    a.constant(8, 208)
    a.emit(store(8, 16, 16))
    a.constant(8, 6)
    a.emit(store(8, 432, 16), 0x0000000F)
    refresh_watchdog(a)
    a.emit(move(4, 0), move(5, 0))
    a.constant(6, 4)
    a.emit(addiu(7, 29, 0x160))
    a.constant(31, spec.get("fail_entry", FAIL_ENTRY))
    a.constant(25, BOOTM)
    a.emit(0x03200408, 0)

    a.label("fallback_failed")
    a.constant(8, 207)
    a.emit(store(8, 16, 16), 0x0000000F)
    arm_watchdog(a, 5)
    a.label("fallback_wait")
    a.jump("fallback_wait")
    a.data("fallback_source", b"R36STOCK.ENC\0")
    a.data("fallback_bootm", b"bootm\0")
    a.data("fallback_address", b"81000010\0")
    a.data("fallback_dash", b"-\0")
    a.data("fallback_hex", b"0123456789abcdef")
