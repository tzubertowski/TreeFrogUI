"""Validate exact kernel/userspace ALSA UAPI before any hardware audio test."""
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile


def read_audio_abi(path):
    with Path(path).open("rb") as handle:
        elf = ELFFile(handle)
        if elf.elfclass != 32 or not elf.little_endian or elf["e_machine"] != "EM_MIPS":
            raise ValueError("audio ABI requires little-endian MIPS32")
        section = elf.get_section_by_name(".r36audio")
        if section is None or section["sh_size"] != 48:
            raise ValueError("audio ABI section missing or wrong size")
        words = struct.unpack("<12I", section.data())
        if words[:2] != (0x52334142, 1):
            raise ValueError("audio ABI protocol differs")
        return words


def validate_audio_abi(probe, module):
    user, kernel = read_audio_abi(probe), read_audio_abi(module)
    if user != kernel:
        raise ValueError(f"ALSA userspace/kernel UAPI differs: {user} != {kernel}")
    return list(user)
