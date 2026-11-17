/* SPDX-License-Identifier: MIT
 * Userspace policy for measured r36-direct-keys evdev inputs and GPIO19 speaker
 * PA / GPIO15 headphone-detect routing (see INPUT_PHYSICAL_v3_RESULT.json).
 */
#ifndef R36_DIRECT_KEYS_POLICY_H
#define R36_DIRECT_KEYS_POLICY_H

#include <stdint.h>

/* Verified physical scan/evdev codes from r36-direct-keys (kernel_input_physical_v3) */
#define R36_DIRECT_CODE_FN       59u
#define R36_DIRECT_CODE_R2       104u
#define R36_DIRECT_CODE_L2       109u
#define R36_DIRECT_CODE_VOL_DOWN 114u
#define R36_DIRECT_CODE_VOL_UP   115u
#define R36_DIRECT_CODE_POWER    116u

#define R36_POWER_LONG_HOLD_MS   1500ULL
#define R36_BRIGHTNESS_MIN_PCT   5
#define R36_BRIGHTNESS_MAX_PCT   100
#define R36_VOLUME_MIN_PCT       0
#define R36_VOLUME_MAX_PCT       100

enum r36_direct_action {
    R36_DIRECT_ACTION_NONE = 0,
    R36_DIRECT_ACTION_VOLUME_CHANGED = 1,
    R36_DIRECT_ACTION_BRIGHTNESS_CHANGED = 2,
    R36_DIRECT_ACTION_SLEEP_TOGGLE = 3,
    R36_DIRECT_ACTION_POWEROFF = 4
};

struct r36_direct_keys_policy {
    int fn_held;
    int l2_held;
    int r2_held;
    int power_held;
    int poweroff_emitted;
    uint64_t power_press_ms;
    uint64_t power_long_ms;
    int volume_pct;
    int volume_step;
    int brightness_pct;
    int brightness_step;
};

static inline int r36_clamp_int(int val, int lo, int hi)
{
    if (val < lo) return lo;
    if (val > hi) return hi;
    return val;
}

static inline void r36_direct_keys_policy_init(struct r36_direct_keys_policy *p,
                                               int initial_volume_pct,
                                               int initial_brightness_pct)
{
    if (!p) return;
    p->fn_held = 0;
    p->l2_held = 0;
    p->r2_held = 0;
    p->power_held = 0;
    p->poweroff_emitted = 0;
    p->power_press_ms = 0;
    p->power_long_ms = R36_POWER_LONG_HOLD_MS;
    p->volume_pct = r36_clamp_int(initial_volume_pct, R36_VOLUME_MIN_PCT, R36_VOLUME_MAX_PCT);
    p->volume_step = 5;
    p->brightness_pct = r36_clamp_int(initial_brightness_pct, R36_BRIGHTNESS_MIN_PCT, R36_BRIGHTNESS_MAX_PCT);
    p->brightness_step = 10;
}

static inline enum r36_direct_action r36_direct_keys_tick(
    struct r36_direct_keys_policy *p, uint64_t now_ms)
{
    if (!p || !p->power_held || p->poweroff_emitted)
        return R36_DIRECT_ACTION_NONE;
    if (now_ms >= p->power_press_ms && (now_ms - p->power_press_ms) >= p->power_long_ms) {
        p->poweroff_emitted = 1;
        return R36_DIRECT_ACTION_POWEROFF;
    }
    return R36_DIRECT_ACTION_NONE;
}

static inline enum r36_direct_action r36_direct_keys_handle_event(
    struct r36_direct_keys_policy *p, uint16_t code, int value, uint64_t now_ms)
{
    int pressed;
    if (!p) return R36_DIRECT_ACTION_NONE;

    pressed = (value != 0) ? 1 : 0;

    switch (code) {
    case R36_DIRECT_CODE_FN:
        if (value == 0 || value == 1)
            p->fn_held = pressed;
        return R36_DIRECT_ACTION_NONE;

    case R36_DIRECT_CODE_L2:
        if (value == 0 || value == 1)
            p->l2_held = pressed;
        return R36_DIRECT_ACTION_NONE;

    case R36_DIRECT_CODE_R2:
        if (value == 0 || value == 1)
            p->r2_held = pressed;
        return R36_DIRECT_ACTION_NONE;

    case R36_DIRECT_CODE_VOL_UP:
    case R36_DIRECT_CODE_VOL_DOWN: {
        int dir = (code == R36_DIRECT_CODE_VOL_UP) ? 1 : -1;
        if (value != 1 && value != 2)
            return R36_DIRECT_ACTION_NONE;
        if (p->fn_held) {
            p->brightness_pct = r36_clamp_int(
                p->brightness_pct + dir * p->brightness_step,
                R36_BRIGHTNESS_MIN_PCT, R36_BRIGHTNESS_MAX_PCT);
            return R36_DIRECT_ACTION_BRIGHTNESS_CHANGED;
        }
        p->volume_pct = r36_clamp_int(
            p->volume_pct + dir * p->volume_step,
            R36_VOLUME_MIN_PCT, R36_VOLUME_MAX_PCT);
        return R36_DIRECT_ACTION_VOLUME_CHANGED;
    }

    case R36_DIRECT_CODE_POWER:
        if (value == 1) {
            if (!p->power_held) {
                p->power_held = 1;
                p->poweroff_emitted = 0;
                p->power_press_ms = now_ms;
            }
            return R36_DIRECT_ACTION_NONE;
        }
        if (value == 0 && p->power_held) {
            int already = p->poweroff_emitted;
            int long_hold = (now_ms >= p->power_press_ms &&
                             (now_ms - p->power_press_ms) >= p->power_long_ms);
            p->power_held = 0;
            p->poweroff_emitted = 0;
            if (already)
                return R36_DIRECT_ACTION_NONE;
            return long_hold ? R36_DIRECT_ACTION_POWEROFF
                             : R36_DIRECT_ACTION_SLEEP_TOGGLE;
        }
        return R36_DIRECT_ACTION_NONE;

    default:
        return R36_DIRECT_ACTION_NONE;
    }
}

/* GPIO19 speaker PA enable rule conditioned on GPIO15 headphone detect, mute, volume, sleep */
static inline int r36_speaker_amp_should_enable(int hp_det_gpio15_level,
                                                int hp_active_low,
                                                int muted,
                                                int volume_pct,
                                                int sleeping)
{
    int hp_inserted = hp_active_low ? (hp_det_gpio15_level == 0)
                                    : (hp_det_gpio15_level != 0);
    if (sleeping || muted || volume_pct <= 0 || hp_inserted)
        return 0;
    return 1;
}

#endif
