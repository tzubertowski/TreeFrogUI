/* SPDX-License-Identifier: GPL-2.0 */
#ifndef R36_AMPRPC_MAILBOX_PLAN_H
#define R36_AMPRPC_MAILBOX_PLAN_H

/* Pure register planning for the measured stock mailbox layout. No MMIO,
 * shared-memory dereference, acknowledgement or callback invocation occurs here.
 * This is not yet wired into the Linux platform driver.
 */
#ifdef __KERNEL__
#include <linux/types.h>
typedef u32 r36_amp_word;
#else
#include <stdint.h>
typedef uint32_t r36_amp_word;
#endif

#define R36_AMP_MAILBOX_COUNT 8u
#define R36_AMP_TX_COUNT 4u
#define R36_AMP_TRIGGER_OFFSET 0x00u
#define R36_AMP_RX_RELEASE_OFFSET 0x04u
#define R36_AMP_STATUS_OFFSET 0x08u
#define R36_AMP_PAYLOAD_OFFSET 0x0cu
#define R36_AMP_TX_RELEASE_PENDING 0x00010000u
#define R36_AMP_RX_MESSAGE_PENDING 0x00000100u
#define R36_AMP_PENDING_MASK (R36_AMP_TX_RELEASE_PENDING | R36_AMP_RX_MESSAGE_PENDING)

enum r36_amp_action {
    R36_AMP_IDLE,
    R36_AMP_RELEASE_TX,
    R36_AMP_RECEIVE_MESSAGE,
    R36_AMP_INVALID_INDEX,
    R36_AMP_UNEXPECTED_PENDING,
};

struct r36_amp_irq_plan {
    enum r36_amp_action action;
    r36_amp_word argument;
    r36_amp_word acknowledge;
    r36_amp_word clear_payload;
    r36_amp_word release_receiver;
};

static inline struct r36_amp_irq_plan
r36_amp_plan_irq(unsigned int index, r36_amp_word status, r36_amp_word rx_payload)
{
    struct r36_amp_irq_plan plan = { R36_AMP_IDLE, 0, 0, 0, 0 };
    r36_amp_word pending = status & R36_AMP_PENDING_MASK;
    r36_amp_word expected;

    if (index >= R36_AMP_MAILBOX_COUNT) {
        plan.action = R36_AMP_INVALID_INDEX;
        return plan;
    }
    if (!pending)
        return plan;
    expected = index < R36_AMP_TX_COUNT ? R36_AMP_TX_RELEASE_PENDING :
                                         R36_AMP_RX_MESSAGE_PENDING;
    /* The old ISR spins forever on a wrong-group pending bit. Fail closed
     * instead: the future MMIO caller must mask/report a fault, not busy-loop.
     */
    if (pending != expected) {
        plan.action = R36_AMP_UNEXPECTED_PENDING;
        return plan;
    }
    plan.acknowledge = (status & ~R36_AMP_PENDING_MASK) | expected;
    if (index < R36_AMP_TX_COUNT) {
        plan.action = R36_AMP_RELEASE_TX;
        plan.argument = index;
    } else {
        plan.action = R36_AMP_RECEIVE_MESSAGE;
        plan.argument = rx_payload;
        plan.clear_payload = 1;
        plan.release_receiver = 1;
    }
    return plan;
}

#endif
