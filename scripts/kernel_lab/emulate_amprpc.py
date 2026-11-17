"""Execute the measured stock AMPRPC ISR against synthetic mailbox registers.

This validates the recovered register algorithm, NOT real hardware, cache,
concurrency, AVP compatibility or ownership. No target device is contacted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2
from unicorn.mips_const import UC_MIPS_REG_PC, UC_MIPS_REG_RA, UC_MIPS_REG_SP, UC_MIPS_REG_V0
from unicorn.mips_const import UC_CPU_MIPS32_74KF

from amprpc_inspect import MAILBOX_PHYS

ROOT = Path(__file__).resolve().parents[2]
ISR = 0x802BA840
ISR_END = 0x802BA9C8
FIND_WORK = 0x802BA7F4
WORK_QUEUE = 0x802BC600
RELEASE = 0x802BA5FC
DO_MSG = 0x802BABF8
DATA = 0x80B509B0
STOP = 0x81200000


def run_case(image, statuses, *, stuck_ack=False):
    if len(statuses) != 8:
        raise ValueError("exactly eight interrupt status words are required")
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_MIPS32_74KF)
    uc.mem_map(0, 0x400000)
    uc.mem_write(0, image[:0x400000])
    uc.mem_map(0xB50000, 0x10000)
    uc.mem_map(0x1000000, 0x10000)
    uc.mem_map(STOP & 0x1FFFFFFF, 0x1000)
    # Unicorn resolves MIPS KSEG1 accesses to these physical addresses.
    uc.mem_map(0x18800000, 0x1000)
    uc.mem_map(0x18866000, 0x1000)
    resources = [0xA0000000 | p for p in MAILBOX_PHYS]
    uc.mem_write(DATA & 0x1FFFFFFF, struct.pack("<17I", 66, *resources))
    messages = [0xA2200000 + i * 0x1000 for i in range(4)]
    for i, status in enumerate(statuses):
        uc.mem_write(MAILBOX_PHYS[i] + 8, struct.pack("<I", status))
        if i >= 4:
            uc.mem_write(MAILBOX_PHYS[i + 8] + 12, struct.pack("<I", messages[i - 4]))
    events, queued, acknowledgements = [], [], []
    pending_clear = {}
    returned = False

    def address_phys(address):
        return address & 0x1FFFFFFF

    def read_register(machine, access, address, size, value, user):
        physical = address_phys(address)
        if physical in pending_clear and not stuck_ack:
            machine.mem_write(physical, struct.pack("<I", pending_clear.pop(physical)))

    def write_register(machine, access, address, size, value, user):
        physical = address_phys(address)
        events.append({"address": hex(physical), "value": value})
        if physical in [p + 8 for p in MAILBOX_PHYS[:8]]:
            # Model only the observed W1C pending bits, retaining configuration.
            pending_clear[physical] = value & ~0x10100
            acknowledgements.append({"mailbox": MAILBOX_PHYS.index(physical - 8),
                                     "write": value})

    def code(machine, address, size, user):
        nonlocal returned
        if address == STOP:
            returned = True
            machine.emu_stop()
        elif address == FIND_WORK:
            machine.reg_write(UC_MIPS_REG_V0, 0x80B509F4)
            machine.reg_write(UC_MIPS_REG_PC, machine.reg_read(UC_MIPS_REG_RA))
        elif address == WORK_QUEUE:
            queued.append({"function": hex(machine.reg_read(UC_MIPS_REG_A1)),
                           "argument": hex(machine.reg_read(UC_MIPS_REG_A2))})
            machine.reg_write(UC_MIPS_REG_PC, machine.reg_read(UC_MIPS_REG_RA))

    uc.hook_add(UC_HOOK_CODE, code)
    for begin, end in [(0x18800000, 0x18800FFF), (0x18866000, 0x18866FFF)]:
        uc.hook_add(UC_HOOK_MEM_READ, read_register, begin=begin, end=end)
        uc.hook_add(UC_HOOK_MEM_WRITE, write_register, begin=begin, end=end)
    uc.reg_write(UC_MIPS_REG_SP, 0x8100F000)
    uc.reg_write(UC_MIPS_REG_RA, STOP)
    uc.emu_start(ISR, 0, count=10000)
    return {"returned": returned, "irq_return": uc.reg_read(UC_MIPS_REG_V0),
            "pc": hex(uc.reg_read(UC_MIPS_REG_PC)), "queued": queued,
            "writes": events, "acknowledgements": acknowledgements}


def suite(image):
    cases = []
    for index in range(8):
        status = [0] * 8
        status[index] = 0x10000 if index < 4 else 0x100
        result = run_case(image, status)
        expected_function = RELEASE if index < 4 else DO_MSG
        expected_argument = index if index < 4 else 0xA2200000 + (index - 4) * 0x1000
        passed = (result["returned"] and result["irq_return"] == 1 and
                  result["queued"] == [{"function": hex(expected_function),
                                        "argument": hex(expected_argument)}] and
                  result["acknowledgements"] == [{"mailbox": index, "write": status[index]}])
        cases.append({"name": f"mailbox_{index}", "passed": passed, **result})
    result = run_case(image, [0x10000] * 4 + [0x100] * 4)
    cases.append({"name": "all_pending", "passed": result["returned"] and
                  len(result["queued"]) == 8 and len(result["acknowledgements"]) == 8, **result})
    result = run_case(image, [0] * 8)
    cases.append({"name": "no_pending", "passed": result["returned"] and
                  not result["queued"] and not result["writes"], **result})
    for name, status, stuck in [
        ("unexpected_rx_in_tx_group", [0x100] + [0] * 7, False),
        ("unexpected_tx_in_rx_group", [0] * 4 + [0x10000] + [0] * 3, False),
        ("stuck_ack", [0x10000] + [0] * 7, True),
    ]:
        result = run_case(image, status, stuck_ack=stuck)
        cases.append({"name": name, "passed": not result["returned"], **result})
    return {"passed": all(c["passed"] for c in cases), "cases": cases,
            "isr_sha256": hashlib.sha256(image[ISR - 0x80000000:ISR_END - 0x80000000]).hexdigest(),
            "scope": "actual stock ISR, synthetic W1C MMIO, stubbed work queue; no hardware acceptance"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=ROOT / "analysis/kmem/kernel_80000000.bin")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = suite(args.kernel.read_bytes())
    with args.output.open("x", encoding="ascii") as handle:
        handle.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"]),
                      "output": str(args.output), "isr_sha256": report["isr_sha256"]}))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
