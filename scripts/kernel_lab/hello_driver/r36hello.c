// SPDX-License-Identifier: GPL-2.0
#include <linux/init.h>
#include <linux/module.h>
#include <linux/moduleparam.h>

static unsigned int marker = 0x523336;
module_param(marker, uint, 0444);
MODULE_PARM_DESC(marker, "Read-only marker for checking module parameter/sysfs support");

static int __init r36hello_init(void)
{
    pr_info("r36hello: custom driver loaded, marker=%x\n", marker);
    return 0;
}

static void __exit r36hello_exit(void)
{
    pr_info("r36hello: custom driver unloaded\n");
}

module_init(r36hello_init);
module_exit(r36hello_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Minimal external driver example for the R36 laboratory kernel");
