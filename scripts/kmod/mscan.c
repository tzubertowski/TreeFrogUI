#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>

#define WIN (1u << 20)

struct pat {
	const char *name;
	const unsigned char *b;
	int n;
};

static const unsigned char p_uimg[] = {0x27, 0x05, 0x19, 0x56};
static const unsigned char p_elf[] = {0x7f, 'E', 'L', 'F'};
static const unsigned char p_lin[] = "Linux version";
static const unsigned char p_nonce_avp[] = {0x41, 0xe9, 0x74, 0x26, 0xc9, 0x0d, 0x7a, 0x5e, 0x65, 0xb6, 0xaf, 0xd9};
static const unsigned char p_nonce_vml[] = {0x47, 0x6d, 0xe6, 0x9e, 0x35, 0xa6, 0x52, 0x80, 0x5d, 0x1c, 0x4c, 0xc9};
static const unsigned char p_nonce_drv[] = {0x71, 0xfb, 0xf0, 0x7e, 0x1c, 0xd1, 0x61, 0x53, 0x06, 0xdb, 0x94, 0x46};
static const unsigned char p_chip[] = "HC16E310";
static const unsigned char p_aes[] = {0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5};

static const struct pat pats[] = {
	{"uImage", p_uimg, sizeof p_uimg},
	{"ELF", p_elf, sizeof p_elf},
	{"LinuxVersion", p_lin, sizeof p_lin - 1},
	{"nonce_avp", p_nonce_avp, sizeof p_nonce_avp},
	{"nonce_vmlinux", p_nonce_vml, sizeof p_nonce_vml},
	{"nonce_driver", p_nonce_drv, sizeof p_nonce_drv},
	{"chip", p_chip, sizeof p_chip - 1},
	{"aes_sbox", p_aes, sizeof p_aes},
};
#define NPATS (int)(sizeof pats / sizeof pats[0])

static void scan(const unsigned char *d, size_t len, unsigned long long base)
{
	size_t i;
	int k;
	for (i = 0; i < len; i++) {
		for (k = 0; k < NPATS; k++) {
			int n = pats[k].n;
			if (i + n > len)
				continue;
			if (d[i] == pats[k].b[0] && !memcmp(d + i, pats[k].b, n))
				printf("%s 0x%08llx\n", pats[k].name, base + i);
		}
	}
}

int main(int argc, char **argv)
{
	unsigned long long addr, end;
	int fd;
	unsigned long long a;

	if (argc < 3) {
		fprintf(stderr, "usage: mscan <hexstart> <hexend>\n");
		return 2;
	}
	addr = strtoull(argv[1], NULL, 16);
	end = strtoull(argv[2], NULL, 16);

	fd = open("/dev/mem", O_RDONLY);
	if (fd < 0) {
		perror("open /dev/mem");
		return 1;
	}
	for (a = addr & ~0xfffULL; a < end; a += WIN) {
		size_t len = WIN;
		unsigned char *p;
		if (a + len > end)
			len = end - a;
		p = mmap(NULL, WIN, PROT_READ, MAP_SHARED, fd, (off_t)a);
		if (p == MAP_FAILED) {
			perror("mmap");
			munmap(p, WIN);
			continue;
		}
		scan(p, len, a);
		munmap(p, WIN);
	}
	return 0;
}
