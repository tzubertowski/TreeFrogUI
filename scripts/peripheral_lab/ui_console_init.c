/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <dirent.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/mount.h>
#include <sys/resource.h>
#include <sys/shm.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>
#include "../kernel_lab/user_trace.h"
#ifdef R36_UI_NAVIGATION
#include "ui_navigation_bridge.h"
#endif
#ifndef R36_UI_WINDOW_TICKS
#define R36_UI_WINDOW_TICKS 160
#endif
#if R36_UI_WINDOW_TICKS < 10 || R36_UI_WINDOW_TICKS > 600
#error "UI lifetime outside diagnostic bounds"
#endif

/* First unchanged UI appearance test: no write access to SD, neutral input,
 * genuine launcher audio-off setting in RAM, no stock init or fake audio API.
 * This must never be reported as navigation/game/audio acceptance.
 */
static void copy_log(const char *source,const char *destination)
{
    char buffer[2048]; int in=open(source,O_RDONLY|O_CLOEXEC),out;
    ssize_t n;
    if(in<0)return;
    out=open(destination,O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0644);
    if(out>=0){while((n=read(in,buffer,sizeof(buffer)))>0){ssize_t done=0;while(done<n){ssize_t w=write(out,buffer+done,n-done);if(w<=0)break;done+=w;}if(done!=n)break;}fsync(out);close(out);}close(in);
}
/* /tmp reports die with the watchdog reset; the retained kernel ring does not. */
static void kmsg_line(int fd,const char *text)
{
    size_t length=strlen(text);
    if(fd>=0&&write(fd,text,length)!=(ssize_t)length){}
}
static void kmsg_mark(int fd,const char *text)
{
    char line[192];int length=snprintf(line,sizeof(line),"<3>R36PID1 %s\n",text);
    if(length>0&&length<(int)sizeof(line))kmsg_line(fd,line);
}
static void kmsg_sample(int fd,pid_t pid)
{
    char path[160],line[512],out[400];FILE *file;DIR *tasks;struct dirent *entry;
    if(fd<0)return;
    snprintf(path,sizeof(path),"/proc/%ld/status",(long)pid);file=fopen(path,"r");
    if(file){
        while(fgets(line,sizeof(line),file))if(!strncmp(line,"State:",6)||!strncmp(line,"Threads:",8)){
            int length=snprintf(out,sizeof(out),"<3>R36PID1 ui_state %s",line);
            if(length>0&&length<(int)sizeof(out))kmsg_line(fd,out);
        }
        fclose(file);
    }
    snprintf(path,sizeof(path),"/proc/%ld/task",(long)pid);tasks=opendir(path);if(!tasks)return;
    while((entry=readdir(tasks))){
        int at,length;
        if(entry->d_name[0]=='.')continue;
        length=snprintf(out,sizeof(out),"<3>R36PID1 ui_thread %.32s",entry->d_name);
        at=(length>0&&length<(int)sizeof(out))?length:0;
        snprintf(path,sizeof(path),"/proc/%ld/task/%.32s/wchan",(long)pid,entry->d_name);
        file=fopen(path,"r");
        if(file){
            if(fgets(line,sizeof(line),file)){
                line[strcspn(line,"\r\n")]=0;
                length=snprintf(out+at,sizeof(out)-at," wchan=%s",line);
                if(length>0&&length<(int)sizeof(out)-at)at+=length;
            }
            fclose(file);
        }
        snprintf(path,sizeof(path),"/proc/%ld/task/%.32s/syscall",(long)pid,entry->d_name);
        file=fopen(path,"r");
        if(file){
            if(fgets(line,sizeof(line),file)){
                line[strcspn(line,"\r\n")]=0;
                length=snprintf(out+at,sizeof(out)-at," sys=%s",line);
                if(length>0&&length<(int)sizeof(out)-at)at+=length;
            }
            fclose(file);
        }
        if(at>0&&at<(int)sizeof(out)-1){out[at++]='\n';out[at]=0;kmsg_line(fd,out);}
    }
    closedir(tasks);
}
static void sample_process(pid_t pid)
{
    char path[160],line[512];FILE *file;DIR *tasks;struct dirent *entry;
    snprintf(path,sizeof(path),"/proc/%ld/status",(long)pid);file=fopen(path,"r");
    if(file){while(fgets(line,sizeof(line),file))if(!strncmp(line,"Vm",2)||!strncmp(line,"Threads:",8)||!strncmp(line,"State:",6))printf("ui_sample=%s",line);fclose(file);}
    snprintf(path,sizeof(path),"/proc/%ld/task",(long)pid);tasks=opendir(path);if(!tasks)return;
    while((entry=readdir(tasks))){
        if(entry->d_name[0]=='.')continue;
        snprintf(path,sizeof(path),"/proc/%ld/task/%.32s/wchan",(long)pid,entry->d_name);file=fopen(path,"r");
        if(file){if(fgets(line,sizeof(line),file))printf("ui_thread=%s wchan=%s\n",entry->d_name,line);fclose(file);}
        snprintf(path,sizeof(path),"/proc/%ld/task/%.32s/syscall",(long)pid,entry->d_name);file=fopen(path,"r");
        if(file){
            long number;unsigned long address;char *end;
            if(fgets(line,sizeof(line),file)){
                printf("ui_thread=%s syscall=%s",entry->d_name,line);
                number=strtol(line,&end,10);address=strtoul(end,NULL,16);
                /* Read-only inspect the actual time32 nanosleep request in
                 * this same short-lived child, never write process memory. */
                if(number==4166&&address){
                    int memory;int32_t request[2];
                    snprintf(path,sizeof(path),"/proc/%ld/mem",(long)pid);memory=open(path,O_RDONLY|O_CLOEXEC);
                    if(memory>=0){if(pread(memory,request,sizeof(request),(off_t)address)==sizeof(request))printf("ui_sleep_request tid=%s sec=%ld nsec=%ld\n",entry->d_name,(long)request[0],(long)request[1]);close(memory);}
                }
            }fclose(file);
        }
    }
    closedir(tasks);
}
static int ram_settings(void)
{
    FILE *in=fopen("/sd/frogui/settings.txt","r"),*out=fopen("/tmp/r36-ui-settings.txt","w");
    char line[4096];int result=0;
    if(!in||!out){if(in)fclose(in);if(out)fclose(out);return -1;}
    while(fgets(line,sizeof(line),in)){
        if(!strchr(line,'\n')&&!feof(in)){result=-1;break;}
        if(!strncmp(line,"menu_sounds=",12))continue;
        if(fputs(line,out)==EOF){result=-1;break;}
    }
    if(ferror(in))result=-1;
    if(fputs("\nmenu_sounds=off\n",out)==EOF||fflush(out))result=-1;
    if(fclose(out))result=-1;
    fclose(in);
    if(result)return result;
    return mount("/tmp/r36-ui-settings.txt","/sd/frogui/settings.txt",NULL,MS_BIND,NULL);
}
int main(void)
{
    struct utsname u;char id[80]="missing";char mark[200];int fd,attempt,status=0,done=0,module=-1,childlog=-1,kfd=-1;
    pid_t child=-1,got;int ipc=-1;key_t key;volatile unsigned int *keys=(void *)-1;
    mkdir("/dev",0755);mkdir("/proc",0755);mkdir("/sys",0755);mkdir("/sd",0755);mkdir("/tmp",01777);mkdir("/mnt",0755);
    if(mount("devtmpfs","/dev","devtmpfs",0,NULL)||mount("proc","/proc","proc",0,NULL)||mount("sysfs","/sys","sysfs",0,NULL)||uname(&u))goto wait_reset;
    /* Initramfs starts PID1 without /dev/console (fds 0..2 closed); reserve
     * 0..2 on /dev/null and keep kfd>=3 so open+dup2(fd,1)+close(fd) never
     * closes stdout/stderr in PID1 or in navigation_start's child. */
    while((fd=open("/dev/null",O_RDWR))>=0&&fd<3){}if(fd>=3)close(fd);
    kfd=open("/dev/kmsg",O_WRONLY|O_CLOEXEC);
    if(kfd>=0&&kfd<3){fd=fcntl(kfd,F_DUPFD_CLOEXEC,3);if(fd>=3){close(kfd);kfd=fd;}else{close(kfd);kfd=-1;}}
    mark_userspace();
    for(attempt=0;attempt<10;attempt++){if(!mount("/dev/mmcblk0p1","/sd","vfat",MS_RDONLY|MS_NOATIME,"iocharset=iso8859-1"))break;sleep(1);}
    if(attempt==10){kmsg_mark(kfd,"stage=sd_mount_failed");goto wait_reset;}
    fd=open("/sd/cubegm/r36-run-id.txt",O_RDONLY|O_CLOEXEC);if(fd>=0){ssize_t n=read(fd,id,sizeof(id)-1);if(n>0){id[n]=0;id[strcspn(id,"\r\n")]=0;}close(fd);}
    fd=open("/tmp/ui-report.txt",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);if(fd<0)goto finish_sd;
    if(dup2(fd,1)<0||dup2(fd,2)<0){if(fd>2)close(fd);goto finish_sd;}if(fd>2)close(fd);setvbuf(stdout,NULL,_IOLBF,0);
    printf("R36 UNCHANGED UI PROBE V1\nrun_id=%s\nrelease=%s\nversion=%s\n",id,u.release,u.version);
    snprintf(mark,sizeof(mark),"stage=report_open rel=%.40s",u.release);kmsg_mark(kfd,mark);
    if(strncmp(u.release,"7.2.0-rc5-r36",sizeof("7.2.0-rc5-r36")-1))goto finish_log;
    if(symlink("/sd","/mnt/sdcard")||symlink("/sd/rootfs/lib","/lib")||symlink("/sd/rootfs/usr","/usr")||
       symlink("/sd/rootfs/bin","/bin")||symlink("/sd/rootfs/sbin","/sbin")||symlink("/sd/rootfs/etc","/etc")){
        perror("ui_paths");goto finish_log;
    }
    fd=open("/tmp/tfdevice.env",O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0)goto finish_log;
    dprintf(fd,"TF_DEVICE=GB350\nTF_PANEL_W=640\nTF_PANEL_H=480\nTF_UI_SCALE=150\nTF_ASPECT_NUM=4\nTF_ASPECT_DEN=3\nTF_ROTATE=0\nTF_PRESENT=dispframe\nTF_DRIVER=/sd/cubegm/driver_r36_drm_ui_test.so\n");close(fd);
    if(ram_settings()){perror("ui_ram_settings");goto finish_log;}
    fd=open("/tmp/joy_key",O_CREAT|O_EXCL|O_WRONLY,0600);if(fd<0)goto finish_log;close(fd);
    key=ftok("/tmp/joy_key",'a');if(key==(key_t)-1)goto finish_log;
#ifdef R36_UI_NAVIGATION
    snprintf(mark,sizeof(mark),"stage=nav_starting key=%ld",(long)key);kmsg_mark(kfd,mark);
    if(navigation_start(key))goto finish_log;
#else
    ipc=shmget(key,4,IPC_CREAT|IPC_EXCL|0600);if(ipc<0)goto finish_log;
    keys=shmat(ipc,NULL,0);if(keys==(void *)-1)goto finish_log;*keys=0;
#endif
    kmsg_mark(kfd,"stage=setup_done");
    fd=open("/sd/cubegm/r36_hc16xx_drm.ko",O_RDONLY|O_CLOEXEC);if(fd<0)goto finish_log;
    module=syscall(SYS_finit_module,fd,"",0);close(fd);printf("ui_module_load_rc=%d\n",module);if(module)goto finish_log;
    kmsg_mark(kfd,"stage=module_loaded");
    childlog=open("/tmp/ui-child.txt",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);if(childlog<0)goto finish_log;
    /* FrogUI reserves ~79MiB sparse BSS but stock UI RSS is ~6MiB. Without
     * stock swap, heuristic commit accounting rejects mmap before first touch.
     * Diagnostic-only RAM policy; not a claim that physical RAM is unlimited. */
    fd=open("/proc/sys/vm/overcommit_memory",O_WRONLY|O_CLOEXEC);
    if(fd<0)goto finish_log;
    if(write(fd,"1\n",2)!=2){close(fd);goto finish_log;}close(fd);
    puts("diagnostic_overcommit=1 child_address_limit_MiB=192 SD_swap=OFF");
    child=fork();if(child<0)goto finish_log;
    if(!child){
        struct rlimit address_limit={192u*1024u*1024u,192u*1024u*1024u};
        if(setrlimit(RLIMIT_AS,&address_limit))_exit(126);
        if(setpgid(0,0)||chdir("/mnt/sdcard/cubegm")||dup2(childlog,1)<0||dup2(childlog,2)<0)_exit(126);
        close(childlog);
        if(setenv("LD_LIBRARY_PATH","/sd/cubegm/lib:/sd/rootfs/lib:/sd/rootfs/usr/lib",1)||setenv("PICOARCH_DRIVER","/sd/cubegm/driver_r36_drm_ui_test.so",1)||setenv("TF_DEVICE","GB350",1)||setenv("HOME","/tmp",1))_exit(126);
#if defined(R36_UI_CORE_TRACE) && defined(R36_UI_TIME_TRACE)
#error "Use one diagnostic preload at a time"
#elif defined(R36_UI_CORE_TRACE)
        if(setenv("LD_PRELOAD","/sd/cubegm/r36-ui-core-trace.so",1))_exit(126);
#elif defined(R36_UI_TIME_TRACE)
        if(setenv("LD_PRELOAD","/sd/cubegm/r36-ui-time-trace.so",1))_exit(126);
#endif
#ifdef R36_UI_DIRECT_EXEC
        /* Use the binary's original PT_INTERP via /lib alias, preserving
         * /proc/self/exe and argv[0] as they are in the stock launcher. */
        execl("/mnt/sdcard/cubegm/picoarch","/mnt/sdcard/cubegm/picoarch",
              "/mnt/sdcard/cubegm/cores/frogui_libretro.so","/mnt/sdcard/cubegm/cores/frogui_libretro.so",(char *)NULL);
#else
        execl("/sd/rootfs/lib/ld.so.1","ld.so.1","--library-path","/sd/cubegm/lib:/sd/rootfs/lib:/sd/rootfs/usr/lib","/sd/cubegm/picoarch","/sd/cubegm/cores/frogui_libretro.so","/sd/cubegm/cores/frogui_libretro.so",(char *)NULL);
#endif
        _exit(127);
    }
    close(childlog);childlog=-1;
    snprintf(mark,sizeof(mark),"stage=child_forked pid=%ld",(long)child);kmsg_mark(kfd,mark);
    /* Establish the group from both sides before the child can create helpers. */
    if(setpgid(child,child)&&errno!=EACCES&&errno!=ESRCH){kmsg_mark(kfd,"stage=setpgid_failed");kill(child,SIGKILL);do{got=waitpid(child,&status,0);}while(got<0&&errno==EINTR);if(got!=child)goto wait_reset;goto finish_log;}
    for(unsigned int tick=0;tick<R36_UI_WINDOW_TICKS;tick++){
#ifdef R36_UI_NAVIGATION
        if(!navigation_alive()){puts("ui_navigation_bridge_lost=1");break;}
#endif
        got=waitpid(child,&status,WNOHANG);if(got==child){done=1;break;}if(got<0&&errno!=EINTR)break;
        if(tick==40||tick==80||tick==120){printf("ui_sample_tick=%u\n",tick);sample_process(child);}
        if(tick==40||tick==120)kmsg_sample(kfd,child);
        usleep(100000);
    }
    if(!done){
        char path[64],line[256];FILE *sample;
        snprintf(path,sizeof(path),"/proc/%ld/status",(long)child);sample=fopen(path,"r");
        if(sample){while(fgets(line,sizeof(line),sample))if(!strncmp(line,"Vm",2)||!strncmp(line,"Threads:",8))printf("ui_memory=%s",line);fclose(sample);}
    }
    printf("ui_alive_at_deadline=%d\n",!done);
    snprintf(mark,sizeof(mark),"stage=window_done alive=%d",!done);kmsg_mark(kfd,mark);
    if(!done){kmsg_mark(kfd,"stage=killing_child");kill(-child,SIGTERM);for(unsigned int t=0;t<10;t++){got=waitpid(child,&status,WNOHANG);if(got==child){done=1;break;}usleep(100000);}if(!done){kill(-child,SIGKILL);do{got=waitpid(child,&status,0);}while(got<0&&errno==EINTR);}}
    /* Remove/reap any helper in the same process group before allowing report
     * writes. Refuse RW remount if the original child could not be reaped. */
    if(!done&&got!=child)kmsg_mark(kfd,"stage=reap_child_failed");
    if(!done&&got!=child)goto wait_reset;
    kill(-child,SIGKILL);
    kmsg_mark(kfd,"stage=reaping_helpers");
    for(;;){int helper_status;pid_t helper=waitpid(-child,&helper_status,0);if(helper>0)continue;if(helper<0&&errno==EINTR)continue;if(helper<0&&errno==ECHILD)break;goto wait_reset;}
    snprintf(mark,sizeof(mark),"stage=reaped exit=%d signalled=%d",WIFEXITED(status)?WEXITSTATUS(status):-1,!WIFEXITED(status));
    kmsg_mark(kfd,mark);
    printf("ui_child_exit=%d signalled=%d\n",WIFEXITED(status)?WEXITSTATUS(status):-1,!WIFEXITED(status));
finish_log:
#ifdef R36_UI_NAVIGATION
    if(!navigation_ready){
        struct stat key_file;char sample[48];long key_bytes=-1;int has_ready=0,has_zero=0;ssize_t sample_bytes;
        fd=open("/tmp/ui-keys.txt",O_RDONLY|O_CLOEXEC);
        if(fd>=0){sample_bytes=read(fd,sample,sizeof(sample)-1);close(fd);if(sample_bytes>0){sample[sample_bytes]=0;has_ready=strstr(sample,"keys_diagnostic_ready=1")!=NULL;has_zero=strstr(sample,"keys_diagnostic_ready=0")!=NULL;}}
        if(stat("/tmp/ui-keys.txt",&key_file)==0)key_bytes=(long)key_file.st_size;
        snprintf(mark,sizeof(mark),"stage=nav_incomplete pid=%ld keys=%ld ready1=%d ready0=%d",
                 (long)navigation_pid,key_bytes,has_ready,has_zero);kmsg_mark(kfd,mark);
    }
    if(navigation_stop())goto wait_reset;
    kmsg_mark(kfd,"stage=nav_stopped");
#endif
    if(childlog>=0)close(childlog);
    if(keys!=(void *)-1)shmdt((const void *)keys);
    if(ipc>=0)shmctl(ipc,IPC_RMID,NULL);
    puts("navigation_verified=0\naudio_verified=0\nUI_visual_confirmation=REQUIRED\nR36 UNCHANGED UI PROBE END");
    fflush(stdout);close(1);close(2);
    umount("/sd/frogui/settings.txt");
    /* No child is allowed to write SD during the test. Re-enable writes only
     * after all children have exited, solely to commit our bounded reports. */
    {
        struct stat report_file;long report_bytes=-1,key_bytes=-1,child_bytes=-1;
        if(stat("/tmp/ui-report.txt",&report_file)==0)report_bytes=(long)report_file.st_size;
        if(stat("/tmp/ui-keys.txt",&report_file)==0)key_bytes=(long)report_file.st_size;
        if(stat("/tmp/ui-child.txt",&report_file)==0)child_bytes=(long)report_file.st_size;
        snprintf(mark,sizeof(mark),"stage=report_sizes ui=%ld keys=%ld child=%ld",
                 report_bytes,key_bytes,child_bytes);
        kmsg_mark(kfd,mark);
    }
    if(!mount(NULL,"/sd","vfat",MS_REMOUNT,"iocharset=iso8859-1")){
        kmsg_mark(kfd,"stage=sd_rw");
        fd=open("/sd/cubegm/r36-own-kernel-proof.txt",O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0644);
        if(fd>=0){dprintf(fd,"R36 OWN KERNEL USERSPACE REACHED\nrun_id=%s\nsysname=Linux\nrelease=%s\nversion=%s\nmachine=%s\npid=1\n",id,u.release,u.version,u.machine);fsync(fd);close(fd);}
        copy_log("/tmp/ui-report.txt","/sd/cubegm/r36-ui-probe.txt");copy_log("/tmp/ui-child.txt","/sd/cubegm/r36-ui-child.txt");
#ifdef R36_UI_NAVIGATION
        copy_log("/tmp/ui-keys.txt","/sd/cubegm/r36-ui-keys.txt");
#endif
        kmsg_mark(kfd,"stage=reports_written");
    }else kmsg_mark(kfd,"stage=sd_remount_failed");
finish_sd:
    sync();if(umount("/sd")){mount(NULL,"/sd","vfat",MS_REMOUNT|MS_RDONLY,NULL);sync();}
wait_reset:
    kmsg_mark(kfd,"stage=waiting_reset");
    for(;;)pause();
}
