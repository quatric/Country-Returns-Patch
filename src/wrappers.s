    # Hook wrappers. Each saves every register the hooked code might still
    # need (r3-r31, CR, CTR, LR), points r31 at the patch's scratch area, calls
    # into the patch, restores everything, then runs the instruction the hook
    # replaced and jumps back into the game.
    #
    # Position independent: everything is relative to the wrapper itself, so
    # the same words work in a DOL section (tools/crpatch.py) and as a
    # Riivolution memory patch. The patcher fills the *_orig word (the replaced
    # instruction) and the *_hi / *_lo halves of the return address; the jump
    # goes through r0 and CTR, both dead at a function's first instruction.

    .text
    .globl  update_entry, update_orig, update_hi, update_lo, scratch
    .globl  probe_entry, probe_orig, probe_hi, probe_lo

    # The game's per-frame controller update (r3 = the controller manager).
    # Drive the SI poller for all four ports, then let gc_update() turn pads
    # into Wii Remotes the game can read.
update_entry:
    stwu    1, -0xA0(1)
    stmw    3, 0x10(1)
    mflr    0
    stw     0, 0x88(1)
    mfcr    0
    stw     0, 0x8C(1)
    mfctr   0
    stw     0, 0x90(1)
    bl      1f
1:  mflr    31
    addi    31, 31, scratch - 1b
    li      30, 0
2:  mr      3, 30
    bl      poller_body
    addi    30, 30, 1
    cmpwi   30, 4
    blt     2b
    lwz     3, 0x10(1)
    mr      4, 31
    bl      gc_update
    lwz     0, 0x90(1)
    mtctr   0
    lwz     0, 0x8C(1)
    mtcr    0
    lwz     0, 0x88(1)
    mtlr    0
    lmw     3, 0x10(1)
    addi    1, 1, 0xA0
update_orig:
    nop
update_hi:
    lis     0, 0
update_lo:
    ori     0, 0, 0
    mtctr   0
    bctr

    # WPADProbe(chan, &type)
probe_entry:
    stwu    1, -0xA0(1)
    stmw    3, 0x10(1)
    mflr    0
    stw     0, 0x88(1)
    mfcr    0
    stw     0, 0x8C(1)
    mfctr   0
    stw     0, 0x90(1)
    bl      1f
1:  mflr    31
    addi    5, 31, scratch - 1b
    bl      gc_probe
    cmpwi   3, 0
    beq     2f
    li      0, 0
    stw     0, 0x10(1)              # WPADProbe returns 0
    lwz     0, 0x90(1)
    mtctr   0
    lwz     0, 0x8C(1)
    mtcr    0
    lwz     0, 0x88(1)
    mtlr    0
    lmw     3, 0x10(1)
    addi    1, 1, 0xA0
    blr
2:
    lwz     0, 0x90(1)
    mtctr   0
    lwz     0, 0x8C(1)
    mtcr    0
    lwz     0, 0x88(1)
    mtlr    0
    lmw     3, 0x10(1)
    addi    1, 1, 0xA0
probe_orig:
    nop
probe_hi:
    lis     0, 0
probe_lo:
    ori     0, 0, 0
    mtctr   0
    bctr

    # Scratch area, zeroed. Offsets (mirrored in gcpad.c):
    #   +0x00  per-channel last-probe time base      +0x14  per-channel consecutive-NOREP counts
    #   +0x20  SI watchdog time base                 +0x28  debug counters
    #   +0x40  debug-feed pad responses (test builds only), 8 bytes per channel
    #   +0x60  per-channel pad state, 0x20 bytes each
    .balign 4
scratch:
    .space  0x100
