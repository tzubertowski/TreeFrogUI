// SPDX-License-Identifier: GPL-2.0
#include <linux/init.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/slab.h>
#include <linux/uaccess.h>

struct old_page { u32 address, usable; };
static unsigned int total, valid, managed, reserved, buddy_heads, allocated;

static ssize_t receive_plan(struct file *file, const char __user *input,
                            size_t count, loff_t *position)
{
    struct old_page *plan;
    size_t i;
    (void)file;
    if (*position || !count || count % sizeof(*plan) || count > 12288 * sizeof(*plan))
        return -EINVAL;
    plan = memdup_user(input, count);
    if (IS_ERR(plan)) return PTR_ERR(plan);
    total = valid = managed = reserved = buddy_heads = allocated = 0;
    for (i = 0; i < count / sizeof(*plan); i++) {
        unsigned long pfn;
        struct page *page;
        if (!plan[i].usable) continue;
        total++;
        if (plan[i].address < 0x80000000 || plan[i].address >= 0x82f91000 ||
            plan[i].address & (PAGE_SIZE - 1)) continue;
        pfn = (plan[i].address & 0x1fffffff) >> PAGE_SHIFT;
        if (!pfn_valid(pfn)) continue;
        valid++;
        page = pfn_to_page(pfn);
        if (PageReserved(page)) reserved++;
        else managed++;
        if (PageBuddy(page)) buddy_heads++;
        if (page_ref_count(page)) allocated++;
    }
    kfree(plan);
    *position += count;
    return count;
}

static int report(struct seq_file *out, void *unused)
{
    unsigned long pfn, old_tail_managed = 0, old_tail_reserved = 0;
    (void)unused;
    /* Part of stock kernel/BSS lying beyond this diagnostic kernel's end. */
    for (pfn = 0x00a00000 >> PAGE_SHIFT; pfn < 0x00b54000 >> PAGE_SHIFT; pfn++) {
        if (!pfn_valid(pfn)) continue;
        if (PageReserved(pfn_to_page(pfn))) old_tail_reserved++;
        else old_tail_managed++;
    }
    seq_printf(out, "stage_total=%u\nstage_valid=%u\nstage_managed=%u\nstage_reserved=%u\n"
               "stage_buddy_heads=%u\nstage_currently_allocated=%u\n"
               "old_tail_managed=%lu\nold_tail_reserved=%lu\n",
               total, valid, managed, reserved, buddy_heads, allocated,
               old_tail_managed, old_tail_reserved);
    return 0;
}

static int open_report(struct inode *inode, struct file *file)
{
    (void)inode;
    return single_open(file, report, NULL);
}

static const struct proc_ops operations = {
    .proc_open = open_report,
    .proc_read = seq_read,
    .proc_write = receive_plan,
    .proc_lseek = seq_lseek,
    .proc_release = single_release,
};

static int __init check_init(void)
{
    return proc_create("r36memcheck", 0600, NULL, &operations) ? 0 : -ENOMEM;
}

static void __exit check_exit(void)
{
    remove_proc_entry("r36memcheck", NULL);
}

module_init(check_init);
module_exit(check_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Inspect ownership of pages formerly used by the stock RAM loader");
