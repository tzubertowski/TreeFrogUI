"""Exercise the actual diagnostic gadget setup with syscall models, not USB HW."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_actual_setup_order_failures_and_udc_selection(tmp_path):
    text = (ROOT / 'scripts/peripheral_lab/usb_cdc_init.c').read_text()
    first = text.index('static int value(')
    last = text.index('static int transmit(', first)
    setup = text[first:last]
    code = tmp_path / 'usb.c'
    code.write_text(r'''
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#define O_WRONLY 1
#define O_CLOEXEC 0
static const char base[]="/sys/kernel/config/usb_gadget/r36diag";
static char last_phase[64],bound_udc[128],current[128];
static int step, writes, bound, fail_at, udcs, index_in_dir, scans, late;
typedef int DIR;
struct dirent { char d_name[128]; };
static int open(const char *p,int flags) { (void)flags; snprintf(current,sizeof(current),"%s",p); return ++step==fail_at ? -1 : 3; }
static int close(int fd) { assert(fd==3); return 0; }
static ssize_t write(int fd,const void *p,size_t n) {
    assert(fd==3);writes++;
    if (!strcmp(current,"UDC")) { assert(!strcmp(p,"musb-hdrc.0.auto")); bound++; }
    return (ssize_t)n;
}
static int mkdir(const char *p,int mode) { (void)p;(void)mode;return ++step==fail_at ? -1 : 0; }
static int mount(const char *a,const char *b,const char *c,unsigned long d,const void *e) {
    (void)a;(void)b;(void)c;(void)d;(void)e;return ++step==fail_at ? -1 : 0;
}
static int chdir(const char *p) { (void)p;return ++step==fail_at ? -1 : 0; }
static int symlink(const char *a,const char *b) {
    assert(!strcmp(a,"/sys/kernel/config/usb_gadget/r36diag/functions/acm.GS0"));
    assert(!strcmp(b,"configs/c.1/acm.GS0"));
    return ++step==fail_at ? -1 : 0;
}
static DIR *opendir(const char *p) { static DIR d;assert(!strcmp(p,"/sys/class/udc"));index_in_dir=0;scans++;return &d; }
static struct dirent *readdir(DIR *d) {
    static struct dirent e;(void)d;
    if (late && scans<3) return NULL;
    if (index_in_dir++>=udcs) return NULL;
    snprintf(e.d_name,sizeof(e.d_name),"%s", index_in_dir==1 ? "musb-hdrc.0.auto" : "other-udc");return &e;
}
static int closedir(DIR *d) { (void)d;return 0; }
static int usleep(unsigned int n) { (void)n;return 0; }
''' + setup + r'''
static void reset(void) { step=writes=bound=fail_at=index_in_dir=scans=late=0;udcs=1;errno=EIO;bound_udc[0]=0; }
int main(void) {
    int total;
    reset();assert(setup_gadget()==0 && bound==1 && !strcmp(last_phase,"bound"));total=step;
    for (int i=1;i<=total;i++) { reset();fail_at=i;assert(setup_gadget()==-1 && bound==0); }
    reset();udcs=0;assert(setup_gadget()==-1 && bound==0 && scans==30);
    reset();udcs=2;assert(setup_gadget()==-1 && bound==0);
    reset();late=1;assert(setup_gadget()==0 && bound==1 && scans==3);
    return 0;
}
''')
    output = tmp_path / 'usb.exe'
    subprocess.run(['gcc','-std=gnu11','-Wall','-Wextra','-Werror',str(code),'-o',str(output)],check=True,capture_output=True,timeout=20)
    subprocess.run([str(output)],check=True,timeout=5)
