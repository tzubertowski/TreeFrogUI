/* Test only: compile together with staged upstream charconv.c, no iconv. */
#include <assert.h>
#include <locale.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "charconv.h"

int main(void)
{
    unsigned int c;
    assert(set_dos_codepage(437));
    for (c = 1; c < 256; c++) {
        char input[2] = {(char)c, 0}, output[4] = {0};
        struct { wchar_t value[2]; unsigned int canary; } wide = {{0, 0}, 0x12345678};
        assert(dos_string_to_wchar_string(wide.value, input, sizeof(wide.value)));
        assert(wide.canary == 0x12345678 && wide.value[1] == 0);
        assert(wchar_string_to_dos_string(output, wide.value, sizeof(output)));
        assert((unsigned char)output[0] == c && output[1] == 0);
    }
    {
        char input[] = "ABCDEFGHIJK", output[12];
        struct { wchar_t value[12]; unsigned int canary; } wide = {{0}, 0x12345678};
        assert(dos_string_to_wchar_string(wide.value, input, sizeof(wide.value)));
        assert(wide.canary == 0x12345678);
        assert(wchar_string_to_dos_string(output, wide.value, sizeof(output)));
        assert(!strcmp(input, output));
        assert(!dos_string_to_wchar_string(wide.value, input, sizeof(wchar_t)));
        assert(!wchar_string_to_dos_string(output, wide.value, 0));
    }
    puts("CP437_ROUNDTRIP_255_AND_BOUNDS=PASS");
    return 0;
}
