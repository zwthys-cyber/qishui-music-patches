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

// s9 holds ceil(video duration * 1000) in these exact callbacks.
// Only the progress value changes; duration and payload delivery stay intact.
.globl _qs_full_progress
_qs_full_progress:
    fcvt d0, s9

// Limited to the two advertising-player wrapper getters, not TTVideoEngine.
.globl _qs_completed_watch_time
_qs_completed_watch_time:
    movz x8, #0x40ac, lsl #48
    movk x8, #0x2000, lsl #32
    fmov d0, x8
    ret

// Existing SplashServiceManager callers take their normal non-display branch.
.globl _qs_no_splash
_qs_no_splash:
    mov w0, #0
    ret
