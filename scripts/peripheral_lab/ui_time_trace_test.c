/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <assert.h>
#include <stdio.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

int main(void)
{
    struct timespec first,last,request={0,2000000};
    struct timeval wall;
    assert(!clock_gettime(CLOCK_MONOTONIC,&first));
    assert(!nanosleep(&request,NULL));
    assert(!usleep(2000));
    assert(!gettimeofday(&wall,NULL));
    assert(!clock_gettime(CLOCK_MONOTONIC,&last));
    assert(last.tv_sec>first.tv_sec || (last.tv_sec==first.tv_sec && last.tv_nsec-first.tv_nsec>=2000000));
    puts("TIME_TRACE_FORWARDING=PASS");
    return 0;
}
