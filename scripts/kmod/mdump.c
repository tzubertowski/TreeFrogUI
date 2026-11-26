#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>

int main(int argc, char **argv)
{
	unsigned long addr, len, page, off, done = 0;
	int fd;
	unsigned char *p;

	if (argc < 3) {
		fprintf(stderr, "usage: mdump <hexaddr> <len>\n");
		return 2;
	}
	addr = strtoul(argv[1], NULL, 16);
	len = strtoul(argv[2], NULL, 0);
	page = addr & ~0xfffUL;
	off = addr - page;

	fd = open("/dev/mem", O_RDONLY);
	if (fd < 0) {
		perror("open /dev/mem");
		return 1;
	}
	p = mmap(NULL, off + len, PROT_READ, MAP_SHARED, fd, page);
	if (p == MAP_FAILED) {
		perror("mmap");
		return 1;
	}
	while (done < len) {
		ssize_t n = write(1, p + off + done, len - done);
		if (n <= 0)
			break;
		done += n;
	}
	return done == len ? 0 : 1;
}
