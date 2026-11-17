#!/bin/bash
cd /root/linux-4.4.186 || exit 1
echo "=== export checks ==="
for s in memcpy memset __copy_user kmalloc_caches kmem_cache_alloc __get_free_pages; do
  hit=$(grep -rn "EXPORT_SYMBOL.*\b$s\b" --include=*.c --include=*.S . 2>/dev/null | head -2 | tr '\n' ' ')
  echo "$s -> ${hit:-NOT FOUND}"
done
echo "=== proc/vsprintf exports ==="
grep -rn "EXPORT_SYMBOL" fs/proc/generic.c fs/libfs.c lib/vsprintf.c kernel/printk/printk.c 2>/dev/null | grep -E "proc_create_data|remove_proc_entry|simple_read_from_buffer|simple_strtoul|printk\b" | head
