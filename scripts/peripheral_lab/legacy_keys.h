/* SPDX-License-Identifier: MIT */
#ifndef R36_LEGACY_KEYS_H
#define R36_LEGACY_KEYS_H
#include <stdint.h>
#include <string.h>
#define R36_KEY_LIMIT 768u
#define R36_KEY_SOURCES 16u
struct r36_key_bridge {
    uint32_t mapping[R36_KEY_LIMIT];
    uint32_t source[R36_KEY_SOURCES];
    unsigned char pressed[R36_KEY_SOURCES][R36_KEY_LIMIT];
};
static inline uint32_t r36_key_word(const struct r36_key_bridge *state)
{
    uint32_t word = 0;
    unsigned int i;
    for (i = 0; i < R36_KEY_SOURCES; i++) word |= state->source[i];
    return word;
}
static inline int r36_key_event(struct r36_key_bridge *state, unsigned int source,
                                unsigned int code, int value)
{
    unsigned int i;
    if (source >= R36_KEY_SOURCES || code >= R36_KEY_LIMIT || value < 0 || value > 2) return -1;
    if (value == 2) return 0;
    state->pressed[source][code] = value != 0;
    state->source[source] = 0;
    for (i = 0; i < R36_KEY_LIMIT; i++)
        if (state->pressed[source][i]) state->source[source] |= state->mapping[i];
    return 0;
}
static inline void r36_key_clear(struct r36_key_bridge *state, unsigned int source)
{
    if (source >= R36_KEY_SOURCES) return;
    state->source[source] = 0;
    memset(state->pressed[source], 0, sizeof(state->pressed[source]));
}
#endif
