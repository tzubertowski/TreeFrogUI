/* SPDX-License-Identifier: GPL-2.0 */
#ifndef R36_FAT_BOOT_POLICY_H
#define R36_FAT_BOOT_POLICY_H

/* Only run_fsck's marker-validated status from the patched binary is accepted.
 * Upstream dosfstools status 1 is ambiguous and must not reach this policy. */
enum r36_fat_action { R36_FAT_BOOT, R36_FAT_REPAIR, R36_FAT_STOP };
static inline enum r36_fat_action r36_fat_after_check(int status, int signalled)
{
    if (signalled) return R36_FAT_STOP;
    if (status == 0) return R36_FAT_BOOT;
    if (status == 1) return R36_FAT_REPAIR;
    return R36_FAT_STOP;
}
static inline int r36_fat_repair_may_verify(int status, int signalled)
{
    return !signalled && (status == 0 || status == 1);
}
static inline int r36_fat_verified(int status, int signalled)
{
    return !signalled && status == 0;
}
#endif
