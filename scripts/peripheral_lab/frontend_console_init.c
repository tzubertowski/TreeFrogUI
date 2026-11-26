/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>
#include "../kernel_lab/user_trace.h"

/* Real glibc video ABI harness, not picoarch/UI acceptance. Static RAM PID1;
 * module/loader/library artifacts are independently hashed by the host runner.
 * No power GPIO, audio, old init or module4.4 is executed. */
int main(void)
{
    struct utsname u;
    char id[80] = "missing";
    int fd, attempt, result = -1, status = 0, completed = 0;
    pid_t child, waited;
    mkdir("/dev",0755);mkdir("/proc",0755);mkdir("/sys",0755);mkdir("/sd",0755);mkdir("/tmp",01777);
    if (mount("devtmpfs","/dev","devtmpfs",0,NULL) || mount("proc","/proc","proc",0,NULL) ||
        mount("sysfs","/sys","sysfs",0,NULL) || uname(&u)) goto wait_reset;
    mark_userspace();
    for (attempt=0;attempt<10;attempt++) {
        if (!mount("/dev/mmcblk0p1","/sd","vfat",MS_NOATIME,"iocharset=iso8859-1")) break;
        sleep(1);
    }
    if (attempt==10) goto wait_reset;
    fd=open("/sd/cubegm/r36-run-id.txt",O_RDONLY|O_CLOEXEC);
    if(fd>=0) {ssize_t n=read(fd,id,sizeof(id)-1);if(n>0){id[n]=0;id[strcspn(id,"\r\n")]=0;}close(fd);}
    fd=open("/sd/cubegm/r36-own-kernel-proof.txt",O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0644);
    if(fd>=0) {
        dprintf(fd,"R36 OWN KERNEL USERSPACE REACHED\nrun_id=%s\nsysname=Linux\nrelease=%s\nversion=%s\nmachine=%s\npid=1\n",id,u.release,u.version,u.machine);
        fsync(fd);close(fd);
    }
    fd=open("/sd/cubegm/r36-frontend-probe.txt",O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0644);
    if(fd<0) goto finish_sd;
    if(dup2(fd,1)<0||dup2(fd,2)<0){close(fd);goto finish_sd;}close(fd);
    setvbuf(stdout,NULL,_IOLBF,0);
    printf("R36 FRONTEND BACKEND PROBE V1\nrun_id=%s\nrelease=%s\nversion=%s\n",id,u.release,u.version);
    if(strncmp(u.release,"7.2.0-rc5-r36",sizeof("7.2.0-rc5-r36")-1))goto finish_log;
    fd=open("/sd/cubegm/r36_hc16xx_drm.ko",O_RDONLY|O_CLOEXEC);
    if(fd<0)goto finish_log;
    result=syscall(SYS_finit_module,fd,"",0);close(fd);
    printf("frontend_module_load_rc=%d\n",result);
    if(result)goto finish_log;
    result=-1;
    child=fork();
    if(child<0)goto finish_log;
    if(!child) {
        if(chdir("/tmp"))_exit(126);
        execl("/sd/rootfs/lib/ld.so.1","ld.so.1","--library-path",
              "/sd/cubegm/lib:/sd/rootfs/lib:/sd/rootfs/usr/lib",
              "/sd/cubegm/r36-frontend-backend-harness",
              "/sd/cubegm/driver_r36_drm_console_test.so",(char *)NULL);
        _exit(127);
    }
    for(unsigned int tick=0;tick<80;tick++) {
        waited=waitpid(child,&status,WNOHANG);
        if(waited==child){completed=1;break;}
        if(waited<0&&errno!=EINTR)break;
        usleep(100000);
    }
    if(!completed) {
        /* This child only generates RAM pixels and diagnostics, never fsck or
         * user saves. The independent watchdog remains armed if teardown hangs. */
        kill(child,SIGKILL);
        do{waited=waitpid(child,&status,0);}while(waited<0&&errno==EINTR);
        puts("frontend_child_timeout=1");
    }
    printf("frontend_child_exit=%d signalled=%d\n",WIFEXITED(status)?WEXITSTATUS(status):-1,!WIFEXITED(status));
    result=completed&&WIFEXITED(status)&&!WEXITSTATUS(status)?0:-1;
finish_log:
    printf("frontend_probe_rc=%d\nfull_UI_verified=0\nR36 FRONTEND BACKEND PROBE END\n",result);
    fflush(stdout);fsync(1);close(1);close(2);
finish_sd:
    sync();if(umount("/sd")){mount(NULL,"/sd","vfat",MS_REMOUNT|MS_RDONLY,NULL);sync();}
wait_reset:
    for(;;)pause();
}
