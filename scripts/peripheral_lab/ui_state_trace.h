/* SPDX-License-Identifier: MIT */
#ifndef R36_UI_STATE_TRACE_H
#define R36_UI_STATE_TRACE_H
#include <fcntl.h>
#include <sys/types.h>

struct r36_state_field { const char *label; uint32_t offset, size; };
#include "ui_state_profile.h"
static int state_memory = -1;
static uintptr_t state_base;

static int state_read(uint32_t offset, void *out, size_t length)
{
    if (state_memory < 0 || state_base > UINTPTR_MAX - offset ||
        length > UINTPTR_MAX - (state_base + offset)) return -1;
    return pread(state_memory, out, length, (off_t)(state_base + offset)) == (ssize_t)length ? 0 : -1;
}
static int state_file_matches(const char *path)
{
    unsigned char buffer[4096];
    uint64_t hash = UINT64_C(14695981039346656037);
    size_t total = 0;
    ssize_t count;
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return 0;
    while ((count = read(fd, buffer, sizeof(buffer))) > 0) {
        if ((size_t)count > R36_STATE_FILE_BYTES - total) { close(fd); return 0; }
        total += (size_t)count;
        for (ssize_t i = 0; i < count; i++) hash = (hash ^ buffer[i]) * UINT64_C(1099511628211);
    }
    close(fd);
    return count == 0 && total == R36_STATE_FILE_BYTES && hash == R36_STATE_FILE_FNV64;
}
static void state_bind(void *run, const Dl_info *info)
{
    unsigned char signature[sizeof(r36_state_run_signature)], note[sizeof(r36_state_note)];
    if (!state_file_matches(info->dli_fname)) goto reject;
    state_base = (uintptr_t)info->dli_fbase;
    if ((uintptr_t)run < state_base || (uintptr_t)run - state_base != R36_STATE_RUN_OFFSET)
        goto reject;
    state_memory = open("/proc/self/mem", O_RDONLY | O_CLOEXEC);
    if (state_read(R36_STATE_RUN_OFFSET, signature, sizeof(signature)) ||
        state_read(R36_STATE_NOTE_OFFSET, note, sizeof(note)) ||
        memcmp(signature, r36_state_run_signature, sizeof(signature)) ||
        memcmp(note, r36_state_note, sizeof(note))) goto reject;
    dprintf(2, "ui-state: profile_bound build_id=%s\n", R36_STATE_BUILD_ID);
    return;
reject:
    if (state_memory >= 0) close(state_memory);
    state_memory = -1;
    dprintf(2, "ui-state: profile_rejected observation_disabled=1\n");
}
static void state_sample(unsigned int count, const char *phase)
{
    if (state_memory < 0 || !(count <= 2 || count % 600 == 0)) return;
    dprintf(2, "ui-state: run=%u phase=%s", count, phase);
    for (size_t i = 0; i < sizeof(r36_state_fields) / sizeof(r36_state_fields[0]); i++) {
        uint32_t value = 0;
        if (state_read(r36_state_fields[i].offset, &value, r36_state_fields[i].size))
            dprintf(2, " %s=UNREADABLE", r36_state_fields[i].label);
        else dprintf(2, " %s=%u", r36_state_fields[i].label, value);
    }
    dprintf(2, "\n");
}
#endif
