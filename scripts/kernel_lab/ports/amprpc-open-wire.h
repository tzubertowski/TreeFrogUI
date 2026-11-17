/* SPDX-License-Identifier: GPL-2.0 */
#ifndef R36_AMPRPC_OPEN_WIRE_H
#define R36_AMPRPC_OPEN_WIRE_H
#include "amprpc-mailbox-plan.h"

static inline int r36_amp_open_packet(volatile r36_amp_word *packet,
                                      r36_amp_word token, const char *path,
                                      r36_amp_word flags, r36_amp_word mode)
{
    unsigned int length = 0, i;
    volatile unsigned char *bytes = (volatile unsigned char *)packet;
    while (length < 4096u - 28u && path[length]) length++;
    if (length == 4096u - 28u) return -1;
    packet[0] = 1;
    packet[1] = 0x1000;
    packet[2] = 1;
    packet[3] = token;
    packet[5] = flags;
    packet[6] = mode;
    for (i = 0; i <= length; i++) bytes[28 + i] = (unsigned char)path[i];
    return 0;
}
#endif
