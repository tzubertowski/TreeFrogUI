/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

/* Diagnostic observation only: forward original calls/values without clamping,
 * acceleration or fake clocks. Output goes to the UI child's bounded RAM log.
 * Build specifically for measured o32 glibc time32 ABI, not musl time64.
 */
static int (*real_nanosleep)(const struct timespec *, struct timespec *);
static int (*real_usleep)(useconds_t);
static int (*real_clock_gettime)(clockid_t, struct timespec *);
static int (*real_gettimeofday)(struct timeval *, void *);
static unsigned int records;
static __thread unsigned int thread_records;

static void note(const char *fmt, ...)
{
    char text[256];va_list args;int length,saved=errno;
    if(__sync_fetch_and_add(&records,1)>=160)return;
    length=snprintf(text,sizeof(text),"tid=%ld ",(long)syscall(SYS_gettid));
    va_start(args,fmt);length+=vsnprintf(text+length,sizeof(text)-(size_t)length,fmt,args);va_end(args);
    if(length>0){if(length>=(int)sizeof(text))length=sizeof(text)-1;syscall(SYS_write,2,text,(size_t)length);}
    errno=saved;
}
__attribute__((constructor)) static void initialize(void)
{
    *(void **)(&real_nanosleep)=dlsym(RTLD_NEXT,"nanosleep");
    *(void **)(&real_usleep)=dlsym(RTLD_NEXT,"usleep");
    *(void **)(&real_clock_gettime)=dlsym(RTLD_NEXT,"clock_gettime");
    *(void **)(&real_gettimeofday)=dlsym(RTLD_NEXT,"gettimeofday");
    note("ui-time: initialized time_t_bytes=%u timespec_bytes=%u\n",(unsigned int)sizeof(time_t),(unsigned int)sizeof(struct timespec));
}
int nanosleep(const struct timespec *request,struct timespec *remaining)
{
    int rc,saved;
    int log_call=thread_records++<12||request->tv_sec>0||request->tv_nsec>100000000;
    if(!real_nanosleep){errno=ENOSYS;return -1;}
    if(log_call)note("ui-time: nanosleep request=%ld.%09ld\n",(long)request->tv_sec,request->tv_nsec);
    rc=real_nanosleep(request,remaining);saved=errno;
    if(log_call)note("ui-time: nanosleep returned=%d errno=%d\n",rc,rc?saved:0);errno=saved;return rc;
}
int usleep(useconds_t microseconds)
{
    int rc,saved;
    int log_call=thread_records++<12||microseconds>100000;
    if(!real_usleep){errno=ENOSYS;return -1;}
    if(log_call)note("ui-time: usleep request_us=%lu\n",(unsigned long)microseconds);
    rc=real_usleep(microseconds);saved=errno;
    if(log_call)note("ui-time: usleep returned=%d errno=%d\n",rc,rc?saved:0);errno=saved;return rc;
}
int clock_gettime(clockid_t clock,struct timespec *value)
{
    int rc,saved;
    if(!real_clock_gettime){errno=ENOSYS;return -1;}
    rc=real_clock_gettime(clock,value);saved=errno;
    if(!rc&&thread_records++<12)note("ui-time: clock=%d value=%ld.%09ld\n",clock,(long)value->tv_sec,value->tv_nsec);
    else if(rc)note("ui-time: clock=%d returned=%d errno=%d\n",clock,rc,saved);
    errno=saved;return rc;
}
int gettimeofday(struct timeval *value,void *zone)
{
    int rc,saved;
    if(!real_gettimeofday){errno=ENOSYS;return -1;}
    rc=real_gettimeofday(value,zone);saved=errno;
    if(!rc&&thread_records++<12)note("ui-time: gettimeofday value=%ld.%06ld\n",(long)value->tv_sec,(long)value->tv_usec);
    errno=saved;return rc;
}
