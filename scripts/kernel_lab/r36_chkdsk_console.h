/* SPDX-License-Identifier: GPL-2.0 */
#ifndef R36_CHKDSK_CONSOLE_H
#define R36_CHKDSK_CONSOLE_H

#include <stddef.h>
#include <string.h>
#include "fat_boot_policy.h"

enum r36_chkdsk_result {
    R36_CHKDSK_CLEAN = 0,
    R36_CHKDSK_REPAIRED_VERIFIED = 1,
    R36_CHKDSK_REFUSED_MOUNTED = 2,
    R36_CHKDSK_CHECK_FAILED = 3,
    R36_CHKDSK_REPAIR_FAILED = 4,
    R36_CHKDSK_VERIFY_FAILED = 5,
    R36_CHKDSK_REMOUNT_FAILED = 6,
    R36_CHKDSK_NO_ERROR_DETECTED = 7
};

/* Returns 1 when a /dev/kmsg or dmesg line reports dirty unmount, FS corruption,
 * or SD I/O failure requiring offline check/repair; 0 for normal boot messages. */
static inline int r36_kmsg_line_indicates_fs_error(const char *line)
{
    if (!line || !line[0])
        return 0;

    if (strstr(line, "Volume was not properly unmounted") != NULL ||
        strstr(line, "Filesystem has been set read-only") != NULL ||
        strstr(line, "Buffer I/O error") != NULL ||
        strstr(line, "I/O error, dev mmcblk0") != NULL ||
        strstr(line, "EXT4-fs error") != NULL ||
        strstr(line, "panic") != NULL) {
        return 1;
    }

    if ((strstr(line, "FAT-fs (") != NULL || strstr(line, "exFAT-fs (") != NULL) &&
        (strstr(line, "error") != NULL || strstr(line, "corrupt") != NULL ||
         strstr(line, "failed") != NULL || strstr(line, "Directory bread") != NULL)) {
        return 1;
    }

    if (strstr(line, "mmcblk0:") != NULL &&
        (strstr(line, "error") != NULL || strstr(line, "timed out") != NULL)) {
        return 1;
    }

    return 0;
}

#endif
