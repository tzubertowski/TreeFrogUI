#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
#include "../kernel_lab/ports/amprpc-open-wire.h"

int main(int argc, char **argv)
{
    uint32_t packet[1024] = {0};
    int32_t rc;
    if (argc != 5) return 2;
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    rc = r36_amp_open_packet(packet, (uint32_t)strtoul(argv[2], NULL, 0), argv[1],
                             (uint32_t)strtoul(argv[3], NULL, 0), (uint32_t)strtoul(argv[4], NULL, 0));
    if (fwrite(&rc, sizeof(rc), 1, stdout) != 1) return 3;
    return fwrite(packet, sizeof(packet), 1, stdout) == 1 ? 0 : 3;
}
