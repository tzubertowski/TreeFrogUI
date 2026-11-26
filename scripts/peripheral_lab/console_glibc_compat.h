/* SPDX-License-Identifier: MIT */
#ifndef R36_CONSOLE_GLIBC_COMPAT_H
#define R36_CONSOLE_GLIBC_COMPAT_H
/* Measured from saved console MIPS ELF version tables, not host defaults.
 * GNU libc still supplies these compatibility symbols. Link libdl explicitly
 * from the measured old runtime; never deploy a replacement libc to the SD.
 */
#if defined(__mips__) && defined(__GLIBC__)
__asm__(".symver __libc_start_main,__libc_start_main@GLIBC_2.0");
__asm__(".symver dlopen,dlopen@GLIBC_2.2");
__asm__(".symver dlclose,dlclose@GLIBC_2.0");
__asm__(".symver dlsym,dlsym@GLIBC_2.0");
__asm__(".symver dlerror,dlerror@GLIBC_2.0");
#endif
#endif
