#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/proc_fs.h>
#include <linux/uaccess.h>
#include <linux/string.h>

#define BUFSZ (1024 * 1024)

static unsigned char kbuf[BUFSZ];
static unsigned int dlen = 16;

static unsigned long addr = 0x80000000UL;
static unsigned int len = 64;
module_param(addr, ulong, 0);
module_param(len, uint, 0);

static void do_dump(unsigned long a, unsigned int l)
{
	unsigned int i;
	volatile unsigned char *src;

	if (a < 0x80000000UL) {
		dlen = 0;
		return;
	}
	if (l > BUFSZ)
		l = BUFSZ;
	src = (volatile unsigned char *)a;
	for (i = 0; i < l; i++)
		kbuf[i] = src[i];
	dlen = l;
}

static ssize_t r36k_read(struct file *f, char __user *ub, size_t n, loff_t *off)
{
	return simple_read_from_buffer(ub, n, off, kbuf, dlen);
}

static ssize_t r36k_write(struct file *f, const char __user *ub, size_t n, loff_t *off)
{
	char tmp[48];
	char *p;
	unsigned int i;
	unsigned long a;
	unsigned int l;

	if (n > sizeof(tmp) - 1)
		n = sizeof(tmp) - 1;
	for (i = 0; i < n; i++) {
		if (__get_user(tmp[i], ub + i))
			return -EFAULT;
	}
	tmp[n] = 0;
	p = tmp;
	while (*p == ' ' || *p == '\t' || *p == '\n')
		p++;
	a = simple_strtoul(p, &p, 16);
	l = 16;
	if (*p && *p != '\n') {
		l = simple_strtoul(p, NULL, 16);
	}
	do_dump(a, l);
	return n;
}

static const struct file_operations fops = {
	.owner = THIS_MODULE,
	.read = r36k_read,
	.write = r36k_write,
};

static int __init r36k_init(void)
{
	do_dump(addr, len);
	if (!proc_create_data("r36k", 0666, NULL, &fops, NULL))
		return -ENOMEM;
	pr_info("r36k: ready, initial dump %lx+%x\n", addr, len);
	return 0;
}

static void __exit r36k_exit(void)
{
	remove_proc_entry("r36k", NULL);
}

module_init(r36k_init);
module_exit(r36k_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("kernel mem reader");
