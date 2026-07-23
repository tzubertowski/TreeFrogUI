# PCSX ReARMed (lightrec JIT) on SF3000

PlayStation 1 via the libretro **pcsx_rearmed** core with the **lightrec** dynamic
recompiler, running on the SF3000's MIPS32r2 CPU. ROM folder: **`roms/ps1r`**.
(The standalone **pcsx4all** still serves `ps1`/`psx`/`PS` - see the main README.)

Built by `build_all.sh` from a clean `libretro/pcsx_rearmed` clone in
`cores/pcsx_rearmed`, with `patches/pcsx_rearmed-sf3000-lightrec.patch` applied.

## Why a patch was needed

lightrec normally runs on ARM/x86 hosts. Running it **on a MIPS host** (PS1-MIPS
recompiled to SF3000-MIPS) on a 2.6.32 kernel exposed several issues, all fixed
in the patch:

1. **`memfd_create` ENOSYS** - kernel predates it (added Linux 3.17). Fallback to
   `mkstemp("/tmp/...")` + `unlink` for the shared RAM-mirror fd.
2. **`MAP_FIXED_NOREPLACE` ignored** - added Linux 4.17; old kernel silently maps
   elsewhere. Emulated with a `mincore` free-range check + plain `MAP_FIXED`.
3. **`_flush_cache(ICACHE)` is a no-op** here - JIT code ran against a stale
   I-cache. Replaced lightning's `jit_flush` with `__builtin___clear_cache`.
4. **GNU lightning MIPS-backend bug (the real blocker).** When lightning
   **restarts** a function's emission (frame-size change), it resets the output
   PC to the function start but does **not** clear its 1-deep delay-slot *pending*
   buffer. The leftover instruction is then flushed at offset 0 - *duplicated at
   the function entry, before the prologue*. For lightrec's C-wrapper trampoline
   this put a stray `lw v1,612(v1)` at the entry; blocks jumping in with `v1` =
   wrapper index dereferenced `~0x268` → `SIGSEGV`. Fix: clear the pending buffer
   (`_jitc->inst.pend = 0`) before the function restart in `jit_mips.c`.

This last one is a genuine upstream GNU lightning bug, reproduced in isolation
under `qemu-mipsel-static` (a 30-line harness emitting `prolog;tramp;add_state;
ldxi;epilog`), not specific to lightrec or the SF3000.

## Status / performance

- **Works** - boots + runs (verified on device, e.g. THPS3).
- **Slower than pcsx4all.** Two reasons:
  - "Sub-par memory map": the process occupies low memory, so PSX RAM can't be
    identity-mapped at host `0x0` (offset 0). lightrec maps at `0x40000000` and
    emits offset-addressed (slower) code rather than its "perfect map" path.
  - HLE BIOS by default. Drop a real `scph1001.bin` in `cubegm/bios/` for
    better compatibility (pcsx_rearmed `system_dir`).

## Build flags

`make -f Makefile.libretro platform=unix ARCH=mips DYNAREC=lightrec
BUILTIN_GPU=unai HAVE_NEON=0` with the SF3000 cross wrappers (`CC`/`CXX`/`CC_AS`/
`CC_LINK`). Needs the `frontend/libpicofe` submodule. `deps/lightning` and
`deps/libchdr` are vendored in the pcsx_rearmed tree (no extra submodules).
