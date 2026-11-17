/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef void (*video_cb)(const void *,unsigned int,unsigned int,size_t);
#ifdef R36_TEST_CORE
static video_cb video;
static uint16_t pixels[640*480];
#ifdef R36_TEST_STATE
uint32_t test_state;
unsigned char test_flag;
#endif
void retro_set_video_refresh(video_cb callback) { video=callback; }
void retro_run(void) {
#ifdef R36_TEST_STATE
    test_state++; test_flag = 1;
#endif
    pixels[0]++;
    if(video)video(pixels,640,480,1280);
}
int untouched_function(int value) { return value+7; }
#else
static unsigned int frames;
static void receive(const void *data,unsigned int w,unsigned int h,size_t pitch) {
    const uint16_t *pixels=data;
    assert(w==640 && h==480 && pitch==1280 && pixels);
    frames++; assert(pixels[0]==frames);
}
int main(int argc,char **argv) {
    void *library;
    void (*run)(void),(*set_video)(video_cb);
    int (*untouched)(int);
    if(argc!=2)return 2;
    library=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!library){fputs(dlerror(),stderr);return 1;}
    *(void **)(&run)=dlsym(library,"retro_run");
    *(void **)(&set_video)=dlsym(library,"retro_set_video_refresh");
    *(void **)(&untouched)=dlsym(library,"untouched_function");
    assert(run&&set_video&&untouched&&untouched(35)==42);
    set_video(receive);run();run();assert(frames==2);
    set_video(NULL);run();assert(frames==2);
    dlclose(library);puts("CORE_TRACE_FORWARDING=PASS");return 0;
}
#endif
