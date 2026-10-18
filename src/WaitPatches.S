// These instructions are assembled by Apple's iPhoneOS assembler in Actions.
// Every replacement is applied only to the exact input hash in patches.json.
.section __TEXT,__text,regular,pure_instructions
.p2align 2
.globl _qs_skip_wait
_qs_skip_wait:
    nop
.globl _qs_finish_native
_qs_finish_native:
    b . + 0x98
.globl _qs_one_second
_qs_one_second:
    fmov d0, #1.0
    ret
    nop
