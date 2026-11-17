#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <errno.h>
#include <ctype.h>

static double now(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec + ts.tv_nsec / 1e9;
}

int main(int argc, char **argv)
{
	int fd, ms = 800, i;
	unsigned char buf[8192];
	double t0;
	size_t got = 0;

	if (argc < 2) {
		fprintf(stderr, "usage: virtq <text-with-\\n-escapes> [ms]\n");
		return 2;
	}
	if (argc > 2)
		ms = atoi(argv[2]);

	fd = open("/dev/virtuart", O_RDWR | O_NONBLOCK);
	if (fd < 0) {
		perror("open /dev/virtuart");
		return 1;
	}

	{
		char out[4096];
		size_t n = 0, k;
		const char *s = argv[1];
		while (*s && n < sizeof out - 1) {
			if (s[0] == '\\' && s[1] == 'n') { out[n++] = '\n'; s += 2; }
			else if (s[0] == '\\' && s[1] == 'r') { out[n++] = '\r'; s += 2; }
			else if (s[0] == '\\' && s[1] == 't') { out[n++] = '\t'; s += 2; }
			else if (s[0] == '\\' && s[1] == 'x' && isxdigit((unsigned char)s[2]) && isxdigit((unsigned char)s[3])) {
				char h[3] = {s[2], s[3], 0};
				out[n++] = (char)strtoul(h, NULL, 16);
				s += 4;
			} else out[n++] = *s++;
		}
		for (k = 0; k < n; k++) {
			ssize_t w = write(fd, out + k, 1);
			if (w < 0)
				perror("write");
			usleep(30000);
		}
	}

	t0 = now();
	while (now() - t0 < ms / 1000.0 && got < sizeof buf) {
		ssize_t r = read(fd, buf + got, sizeof buf - got);
		if (r > 0) { got += r; continue; }
		if (r < 0 && (errno == EAGAIN || errno == EINTR)) { usleep(20000); continue; }
		break;
	}

	printf("got %u bytes\n", (unsigned)got);
	for (i = 0; i < (int)got; i++) {
		if (i % 16 == 0)
			printf("%04x  ", i);
		printf("%02x ", buf[i]);
		if (i % 16 == 15) {
			int j;
			printf(" |");
			for (j = i - 15; j <= i; j++)
				putchar(isprint(buf[j]) ? buf[j] : '.');
			printf("|\n");
		}
	}
	if (got % 16) {
		int j, pad = 16 - (got % 16);
		for (j = 0; j < pad; j++)
			printf("   ");
		printf(" |");
		for (j = got - (got % 16); j < (int)got; j++)
			putchar(isprint(buf[j]) ? buf[j] : '.');
		printf("|\n");
	}
	close(fd);
	return 0;
}
