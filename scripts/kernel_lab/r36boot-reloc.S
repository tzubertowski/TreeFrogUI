/* Position-independent MIPS32r2 copy loop; all pointers are uncached KSEG1. */
#include "ports/r36-trace.h"
    .set noreorder
    .set noat
    .text
    .align 4
    .globl r36_reloc_start
    .globl r36_reloc_end
r36_reloc_start:
    li $t8, R36_TRACE_KSEG1
    li $t7, R36_STAGE_RELOC
    sw $t7, 16($t8)
    sync
    lw $s0, 0($a0)
    move $s4, $s0
    addiu $s5, $a0, 16
    lw $s6, 12($a0)
    lw $t9, 4($a0)
    lw $s1, 8($a0)
1:
    beqz $s0, 5f
    nop
    lw $s2, 0($s0)
    lw $s3, 4($s0)
    addiu $s0, $s0, 8
2:
    beqz $s3, 4f
    nop
    lw $t0, 0($s0)
    lw $t1, 4($s0)
    li $t2, 1024
3:
    lw $t3, 0($t0)
    sw $t3, 0($t1)
    addiu $t0, $t0, 4
    addiu $t1, $t1, 4
    addiu $t2, $t2, -1
    bnez $t2, 3b
    nop
    addiu $s0, $s0, 8
    addiu $s3, $s3, -1
    b 2b
    nop
4:
    move $s0, $s2
    b 1b
    nop
5:
    sync
    li $t7, 17
    sw $t7, 16($t8)
    move $s0, $s4
    li $s7, -1
6:
    beqz $s0, 10f
    nop
    lw $s2, 0($s0)
    lw $s3, 4($s0)
    addiu $s0, $s0, 8
7:
    beqz $s3, 9f
    nop
    lw $t1, 4($s0)
    li $t2, 4096
8:
    lbu $t3, 0($t1)
    xor $t4, $s7, $t3
    andi $t4, $t4, 255
    sll $t4, $t4, 2
    addu $t4, $t4, $s5
    lw $t5, 0($t4)
    srl $s7, $s7, 8
    xor $s7, $s7, $t5
    addiu $t1, $t1, 1
    addiu $t2, $t2, -1
    bnez $t2, 8b
    nop
    addiu $s0, $s0, 8
    addiu $s3, $s3, -1
    b 7b
    nop
9:
    move $s0, $s2
    b 6b
    nop
10:
    nor $s7, $s7, $zero
    sw $s7, 60($t8)
    bne $s7, $s6, 12f
    nop
    li $t7, R36_STAGE_COPIED
    sw $t7, 16($t8)
    sync
    li $a0, -2
    move $a1, $s1
    move $a2, $zero
    move $a3, $zero
    jr.hb $t9
    nop
    .globl r36_crc_failed
12:
r36_crc_failed:
    li $t7, 225
    sw $t7, 16($t8)
    sync
11:
    b 11b
    nop
r36_reloc_end:

    /* No cached stack accesses between cache flush and uncached relocation. */
    .globl r36_handoff
r36_handoff:
    move $s0, $a1
    move $s1, $a2
    move $t9, $a0
    di
    ehb
    jalr $t9
    nop
    move $a0, $s0
    jr $s1
    nop
