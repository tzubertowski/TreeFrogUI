"""Native pre-kernel file probes, restoration, and retained-RAM watchdog gating."""
import struct

from build_direct_candidate import li, store

TRACE = 0xA2F91000
RESTORE_RECEIPT = 0xA2F91E00
RESTORE_MAGIC = 0x52535431
RESOLVE = 0x89DA9130
OPEN = 0x89DDCE88
READ = 0x89DDD374
CLOSE = 0x89DDE110
WRITE = 0x89DDDB60
GET_FILE_POINTER = 0x89DDE004
FAT_SYNC = 0x89DE0A80
CRITICAL_ENTER = 0x89DBD4F8
CRITICAL_LEAVE = 0x89DBD598
MASK_INTERRUPTS = 0x89DC04A4


def decode_copy_trace(raw):
    values = struct.unpack_from("<9I", raw, 396)
    return {key: value for key, value in zip(
        ["read_bytes", "written_bytes", "reserved0", "reserved1", "reserved2",
         "source_crc32", "readback_crc32", "phase", "source_fd"], values)
        if not key.startswith("reserved")}


class Assembly:
    def __init__(self, base):
        self.base = base
        self.words = []
        self.labels = {}
        self.fixups = []

    def emit(self, *words):
        self.words.extend(words)

    def constant(self, register, value):
        self.words.extend(li(register, value))

    def label(self, name):
        self.labels[name] = len(self.words)

    def branch(self, opcode, rs, rt, label):
        self.fixups.append((len(self.words), label))
        self.emit(opcode << 26 | rs << 21 | rt << 16, 0)

    def jump(self, label):
        self.branch(4, 0, 0, label)

    def call(self, address):
        self.constant(25, address)
        self.emit(0x0320F809, 0)  # jalr t9; nop

    def pointer(self, register, label):
        self.fixups.append((len(self.words), label, register))
        self.emit(0, 0)

    def data(self, label, data):
        self.label(label)
        data += bytes((-len(data)) % 4)
        self.words.extend(struct.unpack("<" + "I" * (len(data) // 4), data))

    def finish(self):
        words = self.words.copy()
        for fixup in self.fixups:
            index, label = fixup[:2]
            if len(fixup) == 3:
                words[index:index + 2] = li(fixup[2], self.base + 4 * self.labels[label])
            else:
                offset = self.labels[label] - index - 1
                assert -32768 <= offset <= 32767
                words[index] |= offset & 65535
        return struct.pack("<" + "I" * len(words), *words)


def lw(register, offset, base):
    return 0x8C000000 | base << 21 | register << 16 | offset & 65535


def move(dst, src):
    return src << 21 | dst << 11 | 0x21


def addiu(dst, src, value):
    return 0x24000000 | src << 21 | dst << 16 | value & 65535


def restore_interrupt_masks(a):
    # Exact saved-state slots populated by the original pre-jump mask helper.
    for source, target in [(0x89E7B864, 0xB8800038), (0x89E7B868, 0xB880003C),
                           (0x89E7B868, 0x89E7BBB4), (0x89E7B854, 0xB8800044),
                           (0x89E7B858, 0xB88000C4), (0x89E7B85C, 0xB88000E4),
                           (0x89E7B860, 0xB8800344)]:
        a.constant(8, source)
        a.emit(lw(9, 0, 8))
        a.constant(8, target)
        a.emit(store(9, 0, 8))
    a.constant(8, 0x89E7B86C)
    a.emit(lw(9, 0, 8))
    a.constant(8, 0xB8800040)
    a.emit(lw(10, 0, 8), 0x01495025, store(10, 0, 8), 0x0000000F)


def arm_watchdog(a, seconds):
    a.constant(8, 0xB8800060)
    a.emit(lw(9, 0, 8))
    a.constant(10, 0xFFBFFFFF)
    a.emit(0x012A4824, store(9, 0, 8), 0x0000000F)
    a.constant(8, 0xB8818500)
    a.constant(9, -187500 * seconds)
    a.emit(store(9, 0, 8))
    a.constant(9, 0x26)
    a.emit(store(9, 4, 8), 0x0000000F)


def refresh_watchdog(a, seconds=30):
    a.constant(8, 0xB8818500)
    a.constant(9, -187500 * seconds)
    a.emit(store(9, 0, 8), 0x0000000F)


def resolve_path(a, filename_label, error="failed"):
    a.constant(8, 0x89E5F168)
    a.emit(lw(18, 0, 8))
    a.constant(9, 1)
    a.emit(store(9, 0, 8), 0x0000000F, addiu(4, 29, 0x20))
    a.pointer(5, "directory")
    a.pointer(6, filename_label)
    a.emit(move(7, 0))
    a.call(RESOLVE)
    a.constant(8, 0x89E5F168)
    a.emit(store(18, 0, 8), 0x0000000F)
    a.branch(5, 2, 0, error)


def call_local(a, label):
    a.pointer(25, label)
    a.emit(0x0320F809, 0)


def emit_copy(a, spec):
    a.constant(8, 1)
    a.emit(store(8, 424, 16))
    resolve_path(a, "copy_source")
    a.emit(addiu(4, 29, 0x20), move(5, 0), move(6, 0), move(7, 0))
    a.call(OPEN)
    a.emit(store(2, 428, 16))
    a.branch(1, 2, 0, "failed")
    a.emit(move(17, 2))
    call_local(a, "read_exact_crc")
    a.emit(store(12, 416, 16), move(4, 17))
    a.call(CLOSE)
    a.branch(5, 2, 0, "failed")
    a.branch(4, 19, 0, "failed")
    a.constant(8, 2)
    a.emit(store(8, 424, 16))
    resolve_path(a, "copy_target")
    a.emit(addiu(4, 29, 0x20))
    a.constant(5, 2)
    a.emit(move(6, 0), move(7, 0))
    a.call(OPEN)
    a.emit(store(2, 112, 16))
    a.branch(1, 2, 0, "failed")
    a.emit(move(17, 2))
    a.constant(22, 0x81000000)
    a.constant(23, spec["bytes"])
    a.constant(8, 3)
    a.emit(store(8, 424, 16))
    a.label("copy_write_loop")
    refresh_watchdog(a)
    a.emit(move(4, 17), move(5, 22), move(6, 23))
    a.constant(8, 65536)
    a.emit(0x02E8482B)  # sltu t1,s7,t0
    a.branch(5, 9, 0, "copy_write_count")
    a.emit(move(6, 8))
    a.label("copy_write_count")
    a.emit(store(6, 0xC4, 29))
    a.call(WRITE)
    a.emit(store(2, 116, 16))
    a.branch(6, 2, 0, "copy_write_failed")  # blez v0
    a.emit(lw(8, 0xC4, 29), 0x0102482B)  # sltu t1,t0,v0
    a.branch(5, 9, 0, "copy_write_failed")
    a.emit(0x02C2B021, 0x02E2B823)  # addu s6,s6,v0; subu s7,s7,v0
    a.constant(8, spec["bytes"])
    a.emit(0x01174823, store(9, 400, 16))  # subu t1,t0,s7
    a.branch(5, 23, 0, "copy_write_loop")
    a.jump("copy_sync")
    a.label("copy_write_failed")
    a.emit(move(19, 0))
    a.label("copy_sync")
    a.constant(8, 4)
    a.emit(store(8, 424, 16), move(4, 17), addiu(5, 29, 0xC0))
    a.call(GET_FILE_POINTER)
    a.branch(1, 2, 0, "copy_sync_failed")
    a.emit(lw(4, 0xC0, 29))
    a.call(FAT_SYNC)
    a.emit(store(2, 120, 16))
    a.branch(4, 2, 0, "copy_close_output")
    a.label("copy_sync_failed")
    a.emit(move(19, 0))
    a.label("copy_close_output")
    a.emit(move(4, 17))
    a.call(CLOSE)
    a.emit(store(2, 124, 16))
    a.branch(5, 2, 0, "failed")
    a.branch(4, 19, 0, "failed")
    a.constant(8, 5)
    a.emit(store(8, 424, 16), addiu(4, 29, 0x20), move(5, 0), move(6, 0), move(7, 0))
    a.call(OPEN)
    a.emit(store(2, 384, 16))
    a.branch(1, 2, 0, "failed")
    a.emit(move(17, 2))
    call_local(a, "read_exact_crc")
    a.emit(store(12, 420, 16), move(4, 17))
    a.call(CLOSE)
    a.emit(store(2, 392, 16))
    a.branch(5, 2, 0, "failed")
    a.branch(4, 19, 0, "failed")
    a.constant(8, 6)
    a.emit(store(8, 424, 16))


def emit_read_exact_crc(a, spec):
    a.label("read_exact_crc")
    a.emit(store(31, 0xCC, 29))
    a.constant(22, 0x81000000)
    a.constant(23, spec["bytes"])
    a.constant(19, 1)
    a.label("copy_read_loop")
    refresh_watchdog(a)
    a.emit(move(4, 17), move(5, 22), move(6, 23))
    a.constant(8, 65536)
    a.emit(0x02E8482B)
    a.branch(5, 9, 0, "copy_read_count")
    a.emit(move(6, 8))
    a.label("copy_read_count")
    a.emit(store(6, 0xC4, 29))
    a.call(READ)
    a.emit(store(2, 388, 16))
    a.branch(6, 2, 0, "copy_read_failed")
    a.emit(lw(8, 0xC4, 29), 0x0102482B)
    a.branch(5, 9, 0, "copy_read_failed")
    a.emit(0x02C2B021, 0x02E2B823)
    a.constant(8, spec["bytes"])
    a.emit(0x01174823, store(9, 396, 16))
    a.branch(5, 23, 0, "copy_read_loop")
    a.emit(move(4, 17), addiu(5, 29, 0xC8))
    a.constant(6, 1)
    a.call(READ)
    a.branch(5, 2, 0, "copy_read_failed")
    refresh_watchdog(a)
    a.constant(10, 0x81000000)
    a.constant(11, spec["bytes"])
    a.constant(12, 0xFFFFFFFF)
    a.constant(9, 0xEDB88320)
    a.label("crc_byte")
    a.emit(0x91480000, 0x01886026)  # lbu t0,0(t2); xor t4,t4,t0
    a.constant(13, 8)
    a.label("crc_bit")
    a.emit(0x31880001, 0x00084023, 0x000C6042, 0x01094024, 0x01886026,
           addiu(13, 13, -1))
    a.branch(5, 13, 0, "crc_bit")
    a.emit(addiu(10, 10, 1), addiu(11, 11, -1))
    a.branch(5, 11, 0, "crc_byte")
    a.emit(0x000C6027, store(12, 60, 16))  # nor t4,zero,t4
    a.constant(8, spec["crc32"])
    a.branch(4, 12, 8, "copy_read_return")
    a.label("copy_read_failed")
    a.emit(move(19, 0))
    a.label("copy_read_return")
    a.emit(lw(31, 0xCC, 29), 0x03E00008, 0)


def make_probe(base, original_entry, tag, content, loader, *, force_watchdog=False, write_probe=False,
               copy_spec=None, fallback_spec=None, force_fallback=False, kernel_handoff=None,
               symbols_out=None, watchdog_seconds=30):
    if type(watchdog_seconds) is not int or not 30 <= watchdog_seconds <= 120:
        raise ValueError('diagnostic watchdog must be30..120seconds')
    assert len(content) == 64
    if kernel_handoff:
        assert copy_spec and copy_spec["restore_stock"] and fallback_spec
    if copy_spec and fallback_spec:
        assert (copy_spec["bytes"], copy_spec["crc32"]) == (fallback_spec["bytes"], fallback_spec["crc32"])
    a = Assembly(base)
    a.emit(addiu(29, 29, -0x200))
    saved = [4, 5, 6, 7, 31, 16, 17, 18, 19, 20, 21, 22, 23]
    for index, reg in enumerate(saved):
        a.emit(store(reg, 0x100 + 4 * index, 29))
    a.constant(16, TRACE)
    for offset, expected in [(0, 0x5233364C), (8, 3520), (12, 2), (40, tag), (16, 194)]:
        a.emit(lw(8, offset, 16))
        a.constant(9, expected)
        a.branch(5, 8, 9, "fresh")
    a.constant(8, 197)
    a.emit(store(8, 16, 16), 0x0000000F)
    a.jump("return_to_stock")

    a.label("fresh")
    metadata = [0x5233364C, 0, 3520, 2, 194, original_entry, 0, base,
                187500, watchdog_seconds, tag, 0, 0, 0, 0, 0]
    for index, value in enumerate(metadata):
        a.constant(8, value)
        a.emit(store(8, index * 4, 16))
    for index in range(64, 128, 4):
        a.constant(8, 0xFFFFFFFF)
        a.emit(store(8, index, 16))
    a.emit(store(4, 48, 16), store(5, 52, 16), store(5, 56, 16))
    a.emit(0x40086000, store(8, 64, 16))  # mfc0 t0,Status
    a.constant(8, 0x89E665D4)
    a.emit(lw(8, 0, 8), store(8, 100, 16), 0x0000000F)
    arm_watchdog(a, 30)
    if force_watchdog:
        a.label("forced_wait")
        a.jump("forced_wait")
    globals_to_capture = [0x89E5F0E0 + 4 * index for index in range(9)] + [
        0x89E66644, 0x89E6665C, 0x89E7FD74]
    if not copy_spec:
        for index, address in enumerate(globals_to_capture):
            a.constant(8, address)
            a.emit(lw(9, 0, 8), store(9, 192 + 4 * index, 16))
    apis = [RESOLVE, OPEN, READ, CLOSE, CRITICAL_ENTER, CRITICAL_LEAVE, MASK_INTERRUPTS]
    if write_probe or copy_spec:
        apis += [WRITE, GET_FILE_POINTER, FAT_SYNC]
    for index, address in enumerate(apis):
        for word_index in range(4):
            a.constant(8, address + 4 * word_index)
            a.emit(lw(9, 0, 8), store(9, 512 + 16 * index + 4 * word_index, 16))
            a.constant(10, struct.unpack_from("<I", loader, address - 0x89DA0000 + 4 * word_index)[0])
            a.branch(5, 9, 10, "code_mismatch")
    a.constant(8, 0x89E6665C)
    a.emit(lw(8, 0, 8))
    a.branch(4, 8, 0, "context_mismatch")
    a.emit(lw(20, 0x48, 8), store(20, 108, 16))
    a.constant(9, 33)
    a.emit(0x0289482B)  # sltu t1,s4,t1
    a.branch(4, 9, 0, "context_mismatch")
    a.branch(4, 20, 0, "context_mismatch")
    restore_interrupt_masks(a)
    a.emit(move(21, 20))
    a.label("leave_critical")
    a.call(CRITICAL_LEAVE)
    a.emit(addiu(21, 21, -1))
    a.branch(5, 21, 0, "leave_critical")
    a.emit(0x40086000, store(8, 68, 16))
    # The resolver accepts arbitrary filenames only with alias remapping disabled.
    a.constant(8, 0x89E5F168)
    a.emit(lw(18, 0, 8))
    a.constant(9, 1)
    a.emit(store(9, 0, 8), 0x0000000F)
    a.emit(addiu(4, 29, 0x20))
    a.pointer(5, "directory")
    a.pointer(6, "filename")
    a.emit(move(7, 0))
    a.call(RESOLVE)
    a.emit(store(2, 72, 16))
    a.constant(8, 0x89E5F168)
    a.emit(store(18, 0, 8), 0x0000000F)
    if not copy_spec:
        for index in range(32):
            a.emit(lw(8, -0x100 + 4 * index, 29), store(8, 256 + 4 * index, 16))
    a.branch(5, 2, 0, "failed")
    a.emit(addiu(4, 29, 0x20), move(5, 0), move(6, 0), move(7, 0))
    a.call(OPEN)
    a.emit(store(2, 76, 16))
    a.branch(1, 2, 0, "failed")  # bltz v0
    a.emit(move(17, 2), move(4, 2), addiu(5, 29, 0x80))
    a.constant(6, 64)
    a.call(READ)
    a.emit(store(2, 80, 16))
    a.constant(19, 1)
    a.constant(8, 64)
    a.branch(5, 2, 8, "read_mismatch")
    for index, word in enumerate(struct.unpack("<16I", content)):
        a.emit(lw(8, 0x80 + 4 * index, 29), store(8, 128 + 4 * index, 16))
        a.constant(9, word)
        a.branch(5, 8, 9, "read_mismatch")
    a.jump("close")
    a.label("read_mismatch")
    a.emit(move(19, 0))
    a.label("close")
    a.emit(move(4, 17))
    a.call(CLOSE)
    a.emit(store(2, 84, 16))
    a.branch(5, 2, 0, "failed")
    a.branch(4, 19, 0, "failed")
    if copy_spec:
        emit_copy(a, copy_spec)
    elif write_probe:
        a.constant(8, 0x89E5F168)
        a.emit(lw(18, 0, 8))
        a.constant(9, 1)
        a.emit(store(9, 0, 8), 0x0000000F)
        a.emit(addiu(4, 29, 0x20))
        a.pointer(5, "directory")
        a.pointer(6, "write_filename")
        a.emit(move(7, 0))
        a.call(RESOLVE)
        a.constant(8, 0x89E5F168)
        a.emit(store(18, 0, 8), 0x0000000F)
        a.branch(5, 2, 0, "failed")
        a.emit(addiu(4, 29, 0x20))
        a.constant(5, 2)  # O_RDWR, no creation or truncation
        a.emit(move(6, 0), move(7, 0))
        a.call(OPEN)
        a.emit(store(2, 112, 16))
        a.branch(1, 2, 0, "failed")
        a.emit(move(17, 2), move(4, 2), addiu(5, 29, 0x80))
        a.constant(6, 64)
        a.call(WRITE)
        a.emit(store(2, 116, 16))
        a.constant(8, 64)
        a.branch(4, 2, 8, "write_length_ok")
        a.emit(move(19, 0))
        a.label("write_length_ok")
        a.emit(move(4, 17), addiu(5, 29, 0xC0))
        a.call(GET_FILE_POINTER)
        a.branch(1, 2, 0, "sync_error")
        a.emit(lw(4, 0xC0, 29))
        a.call(FAT_SYNC)
        a.emit(store(2, 120, 16))
        a.branch(4, 2, 0, "write_close")
        a.label("sync_error")
        a.emit(move(19, 0))
        a.label("write_close")
        a.emit(move(4, 17))
        a.call(CLOSE)
        a.emit(store(2, 124, 16))
        a.branch(5, 2, 0, "failed")
        a.branch(4, 19, 0, "failed")
        a.emit(addiu(4, 29, 0x20), move(5, 0), move(6, 0), move(7, 0))
        a.call(OPEN)
        a.emit(store(2, 384, 16))
        a.branch(1, 2, 0, "failed")
        a.emit(move(17, 2), move(4, 2), addiu(5, 29, 0x80))
        a.constant(6, 64)
        a.call(READ)
        a.emit(store(2, 388, 16))
        a.constant(8, 64)
        a.branch(5, 2, 8, "verify_mismatch")
        for index, word in enumerate(struct.unpack("<16I", content)):
            a.emit(lw(8, 0x80 + 4 * index, 29), store(8, 704 + 4 * index, 16))
            a.constant(9, word)
            a.branch(5, 8, 9, "verify_mismatch")
        a.jump("verify_close")
        a.label("verify_mismatch")
        a.emit(move(19, 0))
        a.label("verify_close")
        a.emit(move(4, 17))
        a.call(CLOSE)
        a.emit(store(2, 392, 16))
        a.branch(5, 2, 0, "failed")
        a.branch(4, 19, 0, "failed")
    a.constant(8, (202 if copy_spec["restore_stock"] else 203) if copy_spec else 200 if write_probe else 195)
    a.jump("finish_io")
    a.label("failed")
    a.constant(8, 196)
    a.label("finish_io")
    a.emit(store(8, 16, 16), 0x0000000F)
    a.emit(move(21, 20))
    a.label("enter_critical")
    a.call(CRITICAL_ENTER)
    a.emit(addiu(21, 21, -1))
    a.branch(5, 21, 0, "enter_critical")
    a.call(MASK_INTERRUPTS)
    a.emit(0x40086000, store(8, 88, 16), 0x0000000F)
    a.jump("return_to_stock")
    a.label("code_mismatch")
    a.constant(8, 198)
    a.emit(store(8, 16, 16), 0x0000000F)
    a.jump("return_to_stock")
    a.label("context_mismatch")
    a.constant(8, 199)
    a.emit(store(8, 16, 16), 0x0000000F)

    a.label("return_to_stock")
    if fallback_spec:
        if kernel_handoff:
            a.emit(lw(8, 16, 16))
            a.constant(9, 202)
            a.branch(5, 8, 9, "fallback_start")
            # This 64-byte receipt is outside the RAM-console ring, in the
            # same non-allocatable partial RAM page, below the AVP boundary.
            a.constant(8, RESTORE_RECEIPT)
            values = [0, 1, tag, 1, copy_spec["bytes"], 0, 0, 6,
                      original_entry, kernel_handoff["dtb"], watchdog_seconds, 0, 0, 0, 0, 0]
            for index, value in enumerate(values):
                a.constant(9, value)
                a.emit(store(9, 4 * index, 8))
            a.emit(lw(9, 416, 16), store(9, 20, 8), lw(9, 420, 16), store(9, 24, 8))
            a.constant(9, RESTORE_MAGIC)
            a.emit(store(9, 0, 8), 0x0000000F)
            refresh_watchdog(a, watchdog_seconds)
        elif force_fallback:
            a.jump("fallback_start")
    for index, reg in enumerate(saved):
        a.emit(lw(reg, 0x100 + 4 * index, 29))
    a.emit(addiu(29, 29, 0x200))
    if kernel_handoff:
        a.constant(4, 0xFFFFFFFE)
        a.constant(5, kernel_handoff["dtb"])
        a.emit(move(6, 0), move(7, 0))
    a.constant(25, original_entry)
    a.emit(0x03200408, 0)
    if fallback_spec:
        from loader_fallback import emit_fallback
        emit_fallback(a, fallback_spec, loader)
    if copy_spec or fallback_spec:
        emit_read_exact_crc(a, copy_spec or fallback_spec)
    a.data("directory", b"cubegm\0")
    a.data("filename", b"R36PROBE.BIN\0")
    a.data("write_filename", b"R36WRITE.BIN\0")
    if copy_spec:
        a.data("copy_source", b"R36STOCK.ENC\0")
        a.data("copy_target", b"advapi32.dll\0" if copy_spec["restore_stock"] else b"R36COPY.BIN\0")
    if symbols_out is not None:
        symbols_out.update({name: a.base + 4 * index for name, index in a.labels.items()})
    return a.finish()
