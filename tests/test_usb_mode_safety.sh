#!/bin/sh
# Host-only guardrails for the privileged USB mass-storage helper.
set -eu

cd "$(dirname "$0")/.."
SCRIPT=apps/usb_mode/usb_mode.sh
MODULE=apps/usb_mode/modules/4.4.186-release/usb_f_mass_storage.ko
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM

fail() { echo "usb-mode safety test failed: $*" >&2; exit 1; }

[ -f "$SCRIPT" ] || fail "missing $SCRIPT"
sh -n "$SCRIPT" || fail "shell syntax"
[ -f "$MODULE" ] || fail "missing mass-storage module"
file "$MODULE" | grep -q 'ELF 32-bit LSB relocatable, MIPS, MIPS32 rel2' ||
    fail "mass-storage module has wrong architecture"
strings "$MODULE" | grep -q '4.4.186-release preempt MIPS32_R2 32BIT' ||
    fail "mass-storage module has wrong vermagic"
grep -q 'apps/usb_mode/usb_mode.sh' build_release.sh ||
    fail "release does not package runtime"
grep -q 'apps/usb_mode/modules/4.4.186-release/usb_f_mass_storage.ko' build_release.sh ||
    fail "release does not package module"

# Public test/diagnostic interface.  Keep these names stable: they are also
# useful for recovering a device whose vendor kernel uses a different path.
for name in TF_USB_SYS_ROOT TF_USB_PROC_MOUNTS TF_USB_MOUNTPOINT \
            TF_USB_BLOCK_DEVICE TF_USB_CONFIG_ROOT TF_USB_MODULE_DIR TF_USB_LOG; do
    grep -q "$name" "$SCRIPT" || fail "missing override $name"
done

# A forced or lazy unmount makes a clean host hand-off unknowable.
if grep -Eq '(^|[[:space:]])umount[[:space:]]+(-[^[:space:]]*[fl]|--force|--lazy)' "$SCRIPT"; then
    fail "forced/lazy unmount is forbidden"
fi

# Reject an invalid backing device before any command with storage side effects.
mkdir -p "$TMP/bin" "$TMP/sys/class/udc/musb-hdrc.0.auto" "$TMP/config/usb_gadget" "$TMP/sd"
: > "$TMP/sys/class/udc/musb-hdrc.0.auto/state"
: > "$TMP/mode"
printf '/dev/not-an-sd-device %s vfat rw 0 0\n' "$TMP/sd" > "$TMP/mounts"
for cmd in sync umount mount modprobe insmod; do
    printf '#!/bin/sh\necho %s >> "$TF_USB_TEST_COMMANDS"\nexit 99\n' "$cmd" > "$TMP/bin/$cmd"
    chmod +x "$TMP/bin/$cmd"
done
: > "$TMP/commands"
if PATH="$TMP/bin:$PATH" TF_USB_TEST_COMMANDS="$TMP/commands" \
    TF_USB_SYS_ROOT="$TMP/sys" TF_USB_CONFIG_ROOT="$TMP/config" \
    TF_USB_PROC_MOUNTS="$TMP/mounts" TF_USB_MOUNTPOINT="$TMP/sd" \
    TF_USB_BLOCK_DEVICE=/dev/not-an-sd-device TF_USB_ROLE_PATH="$TMP/mode" \
    TF_USB_LOG="$TMP/log" "$SCRIPT" run >/dev/null 2>&1; then
    fail "accepted invalid backing device"
fi
[ ! -s "$TMP/commands" ] || fail "mutated system before backing-device validation"

# status must be usable by the UI without root and must have no side effects.
printf 'not attached\n' > "$TMP/sys/class/udc/musb-hdrc.0.auto/state"
out=$(PATH="$TMP/bin:$PATH" TF_USB_SYS_ROOT="$TMP/sys" \
    TF_USB_CONFIG_ROOT="$TMP/config" TF_USB_PROC_MOUNTS="$TMP/mounts" \
    TF_USB_MOUNTPOINT="$TMP/sd" TF_USB_LOG="$TMP/log" "$SCRIPT" status)
case "$out" in inactive*) ;; *) fail "unexpected inactive status: $out";; esac
[ ! -s "$TMP/commands" ] || fail "status executed a mutating command"

# An external stop must never tear a disk from a host that may be writing.
if PATH="$TMP/bin:$PATH" TF_USB_SYS_ROOT="$TMP/sys" TF_USB_CONFIG_ROOT="$TMP/config" \
    TF_USB_LOG="$TMP/log" "$SCRIPT" stop >/dev/null 2>&1; then
    fail "unsafe external stop was accepted"
fi
[ ! -s "$TMP/commands" ] || fail "stop executed a mutating command"

echo "usb-mode safety tests passed"
