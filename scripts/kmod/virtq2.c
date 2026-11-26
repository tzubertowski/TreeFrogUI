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

static unsigned char buf[262144];

int main(int argc, char **argv)
{
	int fd, ms = 800;
	double t0, last;
	size_t got = 0, n = 0, k = 0;
	char out[4096];
	double next_write, deadline;

	if (argc < 2) {
		fprintf(stderr, "usage: virtq2 <text-with-\\n-escapes> [ms]\n");
		return 2;
	}
	if (argc > 2)
		ms = atoi(argv[2]);
	if (ms <= 0)
		return 2;

	fd = open("/dev/virtuart", O_RDWR | O_NONBLOCK);
	if (fd < 0) {
		perror("open /dev/virtuart");
		return 1;
	}

	{
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
	}

	t0 = last = now();
	next_write = t0;
	deadline = t0 + n * 0.02 + ms / 1000.0;
	/* Drain while typing, including immediately after the final CR. */
	while (now() < deadline && got < sizeof buf) {
		ssize_t r = read(fd, buf + got, sizeof buf - got);
		if (r > 0) {
			got += r;
			last = now();
			continue;
		}
		if (r < 0 && errno != EAGAIN && errno != EINTR) {
			perror("read");
			close(fd);
			return 1;
		}
		if (k < n && now() >= next_write) {
			r = write(fd, out + k, 1);
			if (r == 1) {
				k++;
				next_write = now() + 0.02;
				last = now();
			} else if (r < 0 && errno != EAGAIN && errno != EINTR) {
				perror("write");
				close(fd);
				return 1;
			}
		}
		/* This driver can return zero when its ring is temporarily empty. */
		if (k == n && got && now() - last > 0.5)
			break;
		usleep(500);
	}

	fwrite(buf, 1, got, stdout);
	fflush(stdout);
	close(fd);
	return 0;
}
