/* tfexec — dumbest test: a STANDALONE ELF (not a libretro .so).
 * If rkgame autoboot exec()'s the "driver" as a program, this _start runs and
 * writes /mnt/sdcard/tfexec_ran.txt. If it dlopens it as a .so instead, this
 * never runs (no retro_* symbols, EXEC not DYN). Either way it answers the
 * exec-vs-dlopen question. No libc: raw MIPS o32 syscalls, -nostdlib -static. */

#define SYS_exit   4001
#define SYS_write  4004
#define SYS_open   4005
#define SYS_close  4006
#define SYS_execve 4011
#define SYS_fsync  4118
#define M_O_WRONLY 0x0001
#define M_O_CREAT  0x0100
#define M_O_APPEND 0x0008

static long sc(long n, long a, long b, long c) {
    register long v0 asm("$2") = n;
    register long r4 asm("$4") = a;
    register long r5 asm("$5") = b;
    register long r6 asm("$6") = c;
    register long r7 asm("$7") = 0;
    asm volatile("syscall" : "+r"(v0), "+r"(r7) : "r"(r4),"r"(r5),"r"(r6) : "memory");
    return v0;
}

void _start(void) {
    long fd = sc(SYS_open, (long)"/mnt/sdcard/tfexec_ran.txt",
                 M_O_WRONLY | M_O_CREAT | M_O_APPEND, 0644);
    if (fd >= 0) {
        const char *m = "tfexec ELF ran: autoboot exec()'d the driver as a program\n";
        long n = 0; while (m[n]) n++;
        sc(SYS_write, fd, (long)m, n);
        sc(SYS_fsync, fd, 0, 0);
        sc(SYS_close, fd, 0, 0);
    }
    /* if exec model works, chain to the launcher */
    static char *const argv[] = { (char *)"/bin/sh",
                                  (char *)"/mnt/sdcard/cubegm/zhijack.sh", 0 };
    static char *const envp[] = { 0 };
    sc(SYS_execve, (long)"/bin/sh", (long)argv, (long)envp);
    sc(SYS_exit, 0, 0, 0);
}
