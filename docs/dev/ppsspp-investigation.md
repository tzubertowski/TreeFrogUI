# PPSSPP / PSP investigation

Status: parked after initial integration and hardware testing. PPSSPP is not
currently considered a supported emulator on TreeFrogUI.

## What we added

- Added a `psp` ROM folder entry to TreeFrogUI.
- Added PSP documentation and an optional standalone launch path.
- Added the `PPSSPP-DATAFROGSF3000` source repository to `clone_cores.sh`:
  <https://github.com/DevBobby-REP/PPSSPP-DATAFROGSF3000>.
- Updated release staging so an executable at `cubegm/ppsspp` is copied into
  a package.
- PSP launch prefers `cubegm/ppsspp` when present and otherwise falls back to
  `ppsspp_libretro.so`.
- Added PSP artwork to the default and bundled theme packs.

The standalone binary remains optional; it is not fabricated or silently
shipped when no device-ready executable exists.

## Build work tried

The local PPSSPP checkout was configured for the SF3000 MIPS32 little-endian
toolchain (`mips32r2`, `74kc`, hard-float). The port contains SF3000-specific
changes for GL stubs, an IR-JIT path, and a software renderer. The libretro
target was built far enough to produce a core; a standalone device build was
also investigated from the same source family.

Because the native MIPS JIT was suspected of crashing on this target, the
libretro defaults were changed temporarily to the portable interpreter and a
stale per-core JIT setting was overridden on MIPS. This was a diagnostic
change, not proof that the interpreter is a viable long-term configuration.

## Hardware tests and observations

- Tested with a very small 32 KiB PSP homebrew payload to remove game-size and
  loading-time variables.
- Tested the libretro route through Picoarch.
- Tested the optional standalone route through the launcher.
- Both routes reached a black screen and then exited/crashed on the console.
- Changing the default CPU mode to interpreter did not establish a working
  PSP frame, so the failure is not demonstrated to be only the native JIT.
- No claim has been made that the console's display path, GPU/GL interface, or
  PPSSPP renderer contract is complete. The current port's GL stubs/software
  renderer are still suspected areas, along with early startup and MIPS ABI
  integration.

## What this does *not* establish

- It does not prove that PSP is impossible on the hardware.
- It does not prove that the 32 KiB test payload is valid for this PPSSPP
  build; validity still needs to be checked independently.
- It does not prove that a standalone executable and a libretro core share the
  same failure path.
- It does not justify enabling PSP by default for users.

## Next useful debug pass

1. Capture the complete launcher/Picoarch log from process start through the
   crash, including the selected CPU core, GPU core, framebuffer dimensions,
   and the first failed return/error.
2. Run the standalone executable directly with its own config redirected to a
   writable SD location, separating PPSSPP startup from FrogUI dispatch.
3. Force the simplest renderer and interpreter in a clean config, then compare
   against IR-JIT in separate boots.
4. Confirm whether the crash is a signal/ABI fault, renderer initialization
   failure, or invalid PSP content before doing more porting work.

