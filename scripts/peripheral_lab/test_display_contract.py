"""Exercise generated board guards and its actual no-retiming function."""
import os
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = Path(os.environ.get("R36_DISPLAY_SOURCE", ROOT / "payload/display_driver_source_v2"))


def run_c(tmp_path, source):
    path = tmp_path / "check.c"
    binary = tmp_path / "check.exe"
    path.write_text(source)
    subprocess.run(["gcc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(DRIVER), str(path), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_descriptor_addresses_and_aliases(tmp_path):
    run_c(tmp_path, r'''
#include <assert.h>
#include "r36_display_contract.h"
int main(void) {
    uint32_t p;
    assert(!r36_display_descriptor(0x02f92a80, &p) && p == 0x02f92a80);
    assert(!r36_display_descriptor(0x0af92a80, &p) && p == 0x02f92a80);
    assert(r36_display_descriptor(0x02f92a81, &p));
    assert(r36_display_descriptor(0x02f92e40, &p));
    assert(r36_display_descriptor(0x1883a000, &p));
    assert(r36_display_descriptor(0xa2f92a80, &p));
    assert(r36_display_descriptor(0xffffffe0, &p));
    return 0;
}
''')


def test_boot_header_geometry_and_dma_bounds(tmp_path):
    run_c(tmp_path, r'''
#include <assert.h>
#include "r36_display_contract.h"
int main(void) {
    uint32_t w[8] = { 0x11, 0, 639u << 16, 479u << 16,
                      640u | 480u << 16, 255u | 2560u << 16, 0, 0x02f93000 };
    assert(!r36_display_header(w));
    w[7] |= 0x08000000; assert(!r36_display_header(w));
    w[7] = 0xffffff00; assert(r36_display_header(w));
    w[7] = 0x02f92000; assert(r36_display_header(w));
    w[7] = 0x03da2000; assert(r36_display_header(w));
    w[7] = 0x02f93000;
    w[4] = 720u | 1280u << 16; assert(r36_display_header(w));
    w[4] = 640u | 480u << 16;
    w[5] = 255u | 10u << 16; assert(r36_display_header(w));
    w[5] = 255u | 65535u << 16; assert(r36_display_header(w));
    w[5] = 255u | 1280u << 16; w[0] = 0x61; assert(!r36_display_header(w));
    w[0] = 0x71; assert(r36_display_header(w));
    w[0] = 0x60; assert(r36_display_header(w));
    return 0;
}
''')


def test_only_our_board_totals_match(tmp_path):
    run_c(tmp_path, r'''
#include <assert.h>
#include "r36_display_contract.h"
int main(void) {
    assert(r36_display_timing(518u << 16 | 868u * 2));
    assert(!r36_display_timing(594u << 16 | 917u * 2));
    assert(!r36_display_timing(0xffffffffu));
    return 0;
}
''')


def test_actual_ported_timing_method_never_writes(tmp_path):
    text = (DRIVER / "r36_hc16xx_drm.c").read_text()
    match = re.search(r"static void hc16xx_set_timing\([^;{}]*\)\s*\{", text)
    assert match
    start, depth, end = match.start(), 1, match.end()
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    function = text[start:end]
    run_c(tmp_path, r'''
#include <assert.h>
#include <stdint.h>
#include "r36_display_contract.h"
typedef uint32_t u32;
static int writes;
struct hc16xx_drm { void *regs; struct { int htotal, vtotal; } native; struct { void *dev; } drm; };
#define DE_CTL 0
#define DE_TOTAL 12
#define DE_HSYNC 16
#define DE_VSYNC 24
#define DE_VTOTAL2 44
#define DE_CTL_UPDATE 4
#define readl(p) (*(u32 *)(p))
#define writel(v,p) do { writes++; *(u32 *)(p) = (v); } while(0)
#define dev_err_ratelimited(...) ((void)0)
''' + function + r'''
int main(void) {
    u32 regs[32] = {0};
    struct hc16xx_drm h = { .regs=regs, .native={868,518} };
    regs[3] = 518u << 16 | 868u * 2;
    hc16xx_set_timing(&h, 868, 518);
    hc16xx_set_timing(&h, 917, 594);
    regs[3] = 0; hc16xx_set_timing(&h, 868, 518);
    assert(writes == 0 && regs[3] == 0);
    return 0;
}
''')
