/* SPDX-License-Identifier: MIT */
#ifndef R36_UI_NAVIGATION_BRIDGE_H
#define R36_UI_NAVIGATION_BRIDGE_H
static pid_t navigation_pid = -1;
static int navigation_ready;

static int navigation_start(key_t key)
{
    int log = open("/tmp/ui-keys.txt", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    int status;
    if (log < 0) return -1;
    navigation_pid = fork();
    if (!navigation_pid) {
        if (setpgid(0,0) || dup2(log,1)<0 || dup2(log,2)<0) _exit(126);
        close(log);
        execl("/sd/cubegm/r36-navigation-keys", "r36-navigation-keys",
              "/sd/cubegm/r36-navigation.map", "/dev/input/event0", "/dev/input/event1", (char *)NULL);
        _exit(127);
    }
    close(log);
    if (navigation_pid < 0) return -1;
    if (setpgid(navigation_pid,navigation_pid) && errno!=EACCES && errno!=ESRCH) return -1;
    for (unsigned t=0;t<30;t++) {
        int id;
        if (waitpid(navigation_pid,&status,WNOHANG)==navigation_pid) { navigation_pid=-1; return -1; }
        id=shmget(key,4,0600);
        if (id>=0) {
            /* The service alone owns/initializes this segment. Its ready marker
             * follows initial held-key restoration and signal setup. */
            FILE *file=fopen("/tmp/ui-keys.txt","r");
            char line[160];
            if (file) {
                while (fgets(line,sizeof(line),file))
                    if (!strcmp(line,"keys_diagnostic_ready=1\n")) navigation_ready=1;
                fclose(file);
            }
            if (navigation_ready) { puts("ui_navigation_bridge_ready=1 directions_only=1"); return 0; }
        }
        usleep(100000);
    }
    return -1;
}
static int navigation_alive(void)
{
    int status;
    pid_t result;
    if (navigation_pid<0) return 0;
    result=waitpid(navigation_pid,&status,WNOHANG);
    if (result==0) return 1;
    if (result==navigation_pid) navigation_pid=-1;
    return 0;
}
static int navigation_stop(void)
{
    int status;pid_t got;
    if (navigation_pid<0) return 0;
    kill(-navigation_pid,SIGTERM);
    for (unsigned t=0;t<20;t++) {
        got=waitpid(navigation_pid,&status,WNOHANG);
        if (got==navigation_pid) { navigation_pid=-1; return 0; }
        if (got<0 && errno!=EINTR) return -1;
        usleep(100000);
    }
    kill(-navigation_pid,SIGKILL);
    do { got=waitpid(navigation_pid,&status,0); } while(got<0 && errno==EINTR);
    if (got!=navigation_pid) return -1;
    navigation_pid=-1;return 0;
}
#endif
