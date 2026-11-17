/* SPDX-License-Identifier: MIT: synchronous, no hardware checkpoint test. */
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
static int clock_second, calls, opens, resolves, closes;
static int fake_clock(clockid_t id,struct timespec *v) { assert(id==CLOCK_MONOTONIC);v->tv_sec=clock_second;v->tv_nsec=0;return 0; }
static const char *fake_getenv(const char *key) { assert(!strcmp(key,"PICOARCH_DRIVER"));return "/test/backend.so"; }
static void observe(void) { calls++; }
static void *fake_open(const char *path,int flags) { assert(!strcmp(path,"/test/backend.so") && (flags&RTLD_NOLOAD));opens++;return (void *)42; }
static void *fake_resolve(void *library,const char *name) { assert(library==(void *)42 && !strcmp(name,"r36_scanout_live_checkpoint"));resolves++;return (void *)observe; }
static int fake_close(void *library) { assert(library==(void *)42);closes++;return 0; }
static void *(*next_dlsym)(void *,const char *)=fake_resolve;
#include <stdlib.h>
#define clock_gettime fake_clock
#define getenv fake_getenv
#define dlopen fake_open
#define dlclose fake_close
#include "ui_live_checkpoint.h"
#undef clock_gettime
#undef getenv
#undef dlopen
#undef dlclose
int main(void) {
    checkpoint_poll(60);assert(!calls);
    clock_second=100;checkpoint_begin();
    clock_second=105;checkpoint_begin();assert(checkpoint_start.tv_sec==100);
    clock_second=109;checkpoint_poll(60);assert(!calls);
    clock_second=110;checkpoint_poll(61);assert(!calls);
    checkpoint_poll(120);assert(calls==1 && opens==1 && resolves==1 && closes==1);
    clock_second=120;checkpoint_poll(180);assert(calls==1);
    puts("LIVE_CHECKPOINT_SCHEDULING=PASS");return 0;
}
