#!/bin/bash
cd /root/linux-4.4.186 || exit 1
echo "=== memcpy ==="
grep -n "EXPORT_SYMBOL" arch/mips/lib/memcpy.S lib/string.c
echo "=== slab ==="
grep -n "EXPORT_SYMBOL" mm/slab_common.c | grep -E "kmalloc_caches|kmem_cache_alloc|kmalloc_order"
echo "=== proc ==="
grep -n "EXPORT_SYMBOL" fs/proc/generic.c fs/libfs.c
echo "=== vsprintf/printk ==="
grep -n "EXPORT_SYMBOL" lib/vsprintf.c kernel/printk/printk.c
echo "=== get_free_pages ==="
grep -n "EXPORT_SYMBOL" mm/page_alloc.c | grep -E "get_free_pages"
