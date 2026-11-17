#!/bin/sh
# Image-test only: qemu-user does not automatically emulate execve of MIPS ELF.
# The parent guard runs as native VM code; the real fsck still runs as MIPS.
exec qemu-mipsel -cpu 74Kf /work/r36-fsck-cp437-v2 "$@"
