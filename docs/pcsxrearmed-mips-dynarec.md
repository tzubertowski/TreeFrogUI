# pcsx_rearmed: a lighter MIPS dynarec

← [back to README](../README.md)

**Problem:** on our ALi MIPS SoCs (SF3000/SF3500/R36SX/GB350), the `ps1r`
(pcsx_rearmed) core is slow because it is stuck on **lightrec**, whose portable
IR pipeline is too heavy for a weak in-order MIPS. This doc records why, and what
it would take to give it a lighter dynarec. **No code has been written yet** - this is the scoping analysis.

## Why it's slow here

pcsx_rearmed's fast dynarec is **ari64 / new_dynarec**. Its host backend is
selected in `libpcsxcore/new_dynarec/new_dynarec.c`:

```c
#include "assem_x86.h" / "assem_x64.h"
#ifdef __arm__     -> assem_arm.h
#ifdef __aarch64__ -> assem_arm64.h
```

There is **no `__mips__` branch and no `assem_mips.c`** in the tree, and none in
git history. So on MIPS, ari64 is unavailable and the build falls back to
**lightrec** (`Makefile.libretro`: `DYNAREC ?= lightrec`, ari64 is set only for
ARM/ARM64 targets).

lightrec's weight is not line count (~12k, about the same as pcsx4all's rec).
It's the **pipeline**: guest MIPS → IR → optimization passes → generic host
emitter, with register allocation over a portable IR, **per block**. On this CPU
that per-block compile cost dominates. pcsx4all's recompiler is
**guest-MIPS → host-MIPS directly**, one stage, hand-written for exactly this
ISA (mips32r2), and it already runs on the hardware.

## The interface is pluggable

Both emulators are PCSX-lineage. A dynarec is just an `R3000Acpu` vtable
(`libpcsxcore/r3000a.h`):

```c
Init / Reset / Execute / ExecuteBlock / Clear / Shutdown / SetPGXPMode
```

pcsx4all's rec exposes the same `recInit / recReset / recExecute / recClear /
recShutdown` shape. So an alternative dynarec slots in as another `psxRec` - no
surgery needed to *select* it.

## Path A - write `assem_mips.c` for new_dynarec (best engine)

Implement ari64's backend for MIPS: host register map (`HOST_REGS`), the
`emit_*` primitives (mov/add/load/store/branch/call), literal pools, i-cache
flush, and a `linkage_mips.S`.

- **Pros:** ari64 is genuinely better than pcsx4all's rec (regalloc, block
  linking, constant propagation - it's *why* pcsx_rearmed flies on ARM). Native
  integration with pcsx_rearmed's memory + timing. Clean, intended backend seam.
- **Cons:** `assem_arm.c` is thousands of lines of arch codegen, and MIPS is
  **not** a mechanical translation of it:
  - **No condition-flags register.** ARM leans on flags heavily; MIPS needs
    compare-into-register + branch, so all conditional codegen is reworked.
  - **Branch delay slots.**
  - Limited addressing modes.
  No existing MIPS backend to crib from. Weeks of work, needs real dynarec
  expertise. Highest payoff, highest cost.

## Path B - graft pcsx4all's MIPS rec into pcsx_rearmed (pragmatic)

Drop pcsx4all's `src/recompiler/mips/` in as an alternative `R3000Acpu`.

**Reuse mostly as-is** (bulk of the 11.5k lines): `mips_codegen`,
`rec_alu/bcu/lsu/mdu/gte/cp0.cpp.h`, `host_asm.S` - the emitters that already
produce working mips32r2 on our exact CPU.

**Rewire (the real work, ~1–2k lines of glue):**
1. **Register struct** - pcsx4all `psxRegs` layout ≠ pcsx_rearmed's; every
   emitter that touches a guest reg by offset must be retargeted.
2. **Memory access** - pcsx4all `mem_mapping.c` vs pcsx_rearmed `pcsxmem.c`
   (different mmap layout + load/store LUTs). Load/store emitters must call
   pcsx_rearmed's memory path.
3. **Timing / events** - pcsx_rearmed has a real event scheduler; pcsx4all's is
   simpler. Cycle counting, IRQ checks, `psxException` hooks must match
   pcsx_rearmed or games desync/hang.
4. **GTE** - pcsx_rearmed uses its own `gte.c`; bridge pcsx4all's `rec_gte` or
   call rearmed's.
5. **Block-cache invalidation** (`Clear`) semantics.

- **Pros:** codegen proven on this device; smaller than a from-scratch backend;
  zero IR overhead.
- **Cons:** the glue points (memory + timing + GTE) are exactly where PSX
  dynarecs are subtle - bugs = crashes/desyncs, hard to debug. Risk of importing
  pcsx4all's lower compatibility in those edge cases. Still a multi-week port.

## Recommendation

**Cheaper shots before any port:**
- **Profile lightrec on-device** - is the cost compile (IR/opt passes) or
  dispatch? Try `lightrec_set_unsafe_opt_flags`, a bigger code cache, and confirm
  **`NDRC_THREAD`** (threaded recompile) is on so compilation overlaps emulation.
  This alone may reclaim enough and costs almost nothing.
- **Question the premise.** We already ship **pcsx4all** with the fast MIPS rec.
  Speed-critical games run there; `ps1r`/pcsx_rearmed is the compatibility
  fallback. The port only pays off for titles needing *both* rearmed-compat *and*
  speed - enumerate those first.

**If a port is warranted:** **Path B** (graft pcsx4all's rec) is the shorter,
lower-risk route to a result on this hardware - the codegen already runs here;
the work is core-glue, not new codegen. **Path A** is the better engine but a
much larger, expert-only effort.

License: all GPL, no conflict either way.

## Status

Parked at analysis. Next concrete step if pursued: profile lightrec on-device to
confirm a port is even warranted, then (Path B) map pcsx4all `psxRegs` +
memory + timing onto pcsx_rearmed's and stand up a minimal
recInit/recExecute/recClear against rearmed's core.
