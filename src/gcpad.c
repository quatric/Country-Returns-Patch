/*
 * GameCube controller -> Classic Controller bridge for Donkey Kong Country
 * Returns.
 *
 * The game links the SI library but not PAD, so nothing polls the pads: the
 * SI poller (poller.s) drives the Serial Interface's own auto-polling. Each
 * frame, from the game's controller update, gc_update() turns a pad into a
 * Classic Controller sample in the KPAD library's sample ring, and
 * gc_probe() makes WPADProbe report a controller on that channel. Everything
 * downstream is the game's own Classic Controller path, i.e. Vague Rant's and
 * crediar's Classic Controller hack, which presents it as a Wii Remote and
 * Nunchuk.
 *
 * Without a Wii Remote the game never hears that a controller exists, so
 * gc_update() also plays the part of the WPAD library: it calls the game's
 * connect callback and its extension callback, exactly as they are called
 * for a real Classic Controller, and the connect callback again with -1 when
 * the pad goes away.
 *
 * Build rules (see tools/build_blobs.py): freestanding, integer only, and no
 * relocations, so no static data. Region constants arrive as -D macros; the
 * scratch area is passed in, so the code works wherever it is placed.
 */
typedef unsigned int u32;
typedef int s32;
typedef unsigned short u16;
typedef short s16;
typedef unsigned char u8;

#if !defined(SI_TYPE) || !defined(WPAD_TBL) || !defined(KPAD_BASE) || !defined(EXT_CB)
#error "SI_TYPE, WPAD_TBL, KPAD_BASE and EXT_CB must be defined"
#endif

#define SI_REG(n)   (((volatile u32 *)0xCD006400)[n])
#define W(p, o)     (*(volatile u32 *)((u8 *)(p) + (o)))

#define CHANNELS    2                   /* the game has two players */
#define TB_MS       60750u              /* time base ticks per millisecond */

/* scratch layout, mirrored in src/wrappers.s */
#define DEBUG_OFF   0x28                /* update calls, connects, disconnects, probes */
#define FEED_OFF    0x40                /* DEBUG_FEED: pad response per channel */
#define STATE_OFF   0x60
#define STATE_SIZE  0x20

/* KPAD library channel state */
#define KPAD_STRIDE 0x688
#define K_IDX       0x17A               /* next sample slot to write */
#define K_CNT       0x17B               /* samples queued */
#define K_RING      0x180               /* 16 samples of 0x42 bytes */
#define K_EXTRING   0x5A0               /* pointer to extra samples, and their count at +4 */
#define K_CONNECTCB 0x63C               /* the game's connect callback (chan, result) */
#define SAMPLE_SIZE 0x42

/* GameCube pad buttons, SICnINBUFH >> 16 */
#define PAD_START   0x1000
#define PAD_Y       0x0800
#define PAD_X       0x0400
#define PAD_B       0x0200
#define PAD_A       0x0100
#define PAD_L       0x0040
#define PAD_R       0x0020
#define PAD_Z       0x0010
#define PAD_UP      0x0008
#define PAD_DOWN    0x0004
#define PAD_RIGHT   0x0002
#define PAD_LEFT    0x0001

/* Classic Controller buttons as WPAD reports them */
#define CL_UP       0x0001
#define CL_LEFT     0x0002
#define CL_ZR       0x0004
#define CL_X        0x0008
#define CL_A        0x0010
#define CL_Y        0x0020
#define CL_B        0x0040
#define CL_ZL       0x0080
#define CL_R        0x0200
#define CL_PLUS     0x0400
#define CL_HOME     0x0800
#define CL_MINUS    0x1000
#define CL_L        0x2000
#define CL_DOWN     0x4000
#define CL_RIGHT    0x8000

struct state {
    u32 faked;                          /* we told the game a controller is connected */
    u32 absent;                         /* since when the pad has been missing (time | 1) */
    u32 pad[6];
};

static inline u32 timebase(void)
{
    u32 t;
    __asm__ volatile("mftb %0" : "=r"(t));
    return t;
}

/* Call fn(a, b) with r12 = fn, the way the game's own callers do: the Classic
 * Controller hack's extension-callback hook finds its data through r12. */
static void call2(u32 fn, u32 a, u32 b)
{
    register u32 r3 __asm__("r3") = a;
    register u32 r4 __asm__("r4") = b;
    register u32 r12 __asm__("r12") = fn;
    __asm__ volatile("mtctr 12\n\tbctrl"
                     : "+r"(r3), "+r"(r4), "+r"(r12)
                     :
                     : "r0", "r5", "r6", "r7", "r8", "r9", "r10", "r11", "lr", "ctr",
                       "cr0", "cr1", "cr5", "cr6", "cr7", "xer", "memory");
}

/* A valid, error-free GameCube pad response on `chan`. */
static int pad_in(u8 *S, u32 chan, u32 *h, u32 *l)
{
#ifdef DEBUG_FEED
    /* test builds: a debugger writes the pad's response to scratch +0x40 + 8 * chan */
    if (!W(S, FEED_OFF + chan * 8))
        return 0;
    *h = W(S, FEED_OFF + chan * 8);
    *l = W(S, FEED_OFF + chan * 8 + 4);
    return 1;
#else
    u32 type = ((volatile u32 *)SI_TYPE)[chan], v;

    (void)S;
    if ((type & 0x80) || (type & 0x18000000) != 0x08000000)
        return 0;
    v = SI_REG(1 + 3 * chan);
    if (v & 0x80000000u)                /* ERRSTAT: nothing answered */
        return 0;
    *h = v;
    *l = SI_REG(2 + 3 * chan);
    return 1;
#endif
}

/* What WPADProbe(chan) returns: 0 for a connected remote, -1 for none, -2 if
 * the channel isn't set up yet. Same reads the library makes. */
static s32 remote_probe(u32 chan)
{
    u8 *blk = *(u8 **)(WPAD_TBL + chan * 4);
    s32 ret = (s32)W(blk, 0x900);

    if (ret != -1) {
        if (blk[0x905] == 0xFD)
            ret = -1;
        else if (W(blk, 0x920) == 0)
            ret = -2;
    }
    return ret;
}

/* one stick axis, raw byte (0..255, centre 128) -> the library's +-308 range */
static s16 stick(u32 raw)
{
    s32 v = ((s32)(raw & 0xFF) - 128) * 3;
    if (v > 308)
        v = 308;
    if (v < -308)
        v = -308;
    return (s16)v;
}

/* GameCube pad -> Classic Controller buttons. The Classic Controller hack
 * turns A/B into the Wii Remote's A (jump), R/ZR into B (grab), L/ZL into the
 * Nunchuk's Z (grab, zoom out) and X/Y into a shake (roll, ground pound). */
static u32 cc_buttons(u32 h)
{
    u32 btn = (h >> 16) & 0x1FFF, b = 0;

    if (btn & (PAD_A | PAD_X))          b |= CL_A;      /* jump, confirm */
    if (btn & PAD_B)                    b |= CL_Y;      /* roll, ground pound */
    if (btn & PAD_Y)                    b |= CL_X;
    if (btn & PAD_R)                    b |= CL_R;      /* grab, cancel */
    if (btn & PAD_Z)                    b |= CL_ZR;
    if (btn & PAD_L)                    b |= CL_L;
    if (btn & PAD_UP)                   b |= CL_UP;
    if (btn & PAD_DOWN)                 b |= CL_DOWN;
    if (btn & PAD_LEFT)                 b |= CL_LEFT;
    if (btn & PAD_RIGHT)                b |= CL_RIGHT;
    if (btn & PAD_START) {
        if ((btn & (PAD_L | PAD_R)) == (PAD_L | PAD_R))
            b |= CL_HOME;
        else if (btn & PAD_Z)
            b = (b & ~CL_ZR) | CL_PLUS | CL_MINUS;      /* the controller-mode toggle */
        else
            b |= CL_PLUS;                               /* pause */
    }
    return b;
}

static u8 *ring_slot(u8 *k, u32 i)
{
    return i < 0x10 ? k + K_RING + i * SAMPLE_SIZE
                    : *(u8 **)(k + K_EXTRING) + (i - 0x10) * SAMPLE_SIZE;
}

/* Queue one Classic Controller sample for the KPAD library. */
static void put_sample(u8 *k, u32 h, u32 l)
{
    u32 total = *(u8 **)(k + K_EXTRING) ? W(k, K_EXTRING + 4) + 0x10 : 0x10;
    u32 idx = k[K_IDX], cnt = k[K_CNT], i;
    u8 *s;

    if (total > 0x400 || idx >= total || cnt)
        return;
    s = ring_slot(k, idx);
    for (i = 0; i < SAMPLE_SIZE; i++)
        s[i] = 0;
    *(u16 *)(s + 0x2A) = (u16)cc_buttons(h);
    *(s16 *)(s + 0x2C) = stick(h >> 8);                 /* control stick */
    *(s16 *)(s + 0x2E) = stick(h);
    *(s16 *)(s + 0x30) = stick(l >> 24);                /* C-stick */
    *(s16 *)(s + 0x32) = stick(l >> 16);
    s[0x34] = (h & (PAD_L << 16)) ? 180 : 0;            /* the game reads L/R only as buttons */
    s[0x35] = (h & (PAD_R << 16)) ? 180 : 0;
    s[0x28] = 2;                                        /* extension: Classic Controller */
    s[0x29] = 0;                                        /* no extension error */
    s[0x40] = 8;                                        /* data format: classic + accel + pointer */
    k[K_IDX] = idx + 1 >= total ? 0 : idx + 1;
    k[K_CNT] = 1;
}

/* Runs at the top of the game's per-frame controller update, `mgr` being the
 * controller manager. */
void gc_update(u8 *mgr, u8 *S)
{
    u32 chan;

    (void)mgr;
    W(S, DEBUG_OFF)++;
    for (chan = 0; chan < CHANNELS; chan++) {
        struct state *st = (struct state *)(S + STATE_OFF + chan * STATE_SIZE);
        u8 *k = (u8 *)KPAD_BASE + chan * KPAD_STRIDE;
        u32 h, l;

        if (remote_probe(chan) >= 0) {                  /* a real Wii Remote has the channel */
            st->faked = 0;
            st->absent = 0;
            continue;
        }
        if (!pad_in(S, chan, &h, &l)) {
            /* The pad can drop out for a moment while the poller re-probes the
             * port, so only call it gone after a full second. */
            if (st->faked) {
                u32 now = timebase();
                if (!st->absent)
                    st->absent = now | 1;
                else if (now - st->absent > 1000u * TB_MS) {
                    st->faked = 0;
                    st->absent = 0;
                    W(S, DEBUG_OFF + 8)++;
                    if (W(k, K_CONNECTCB))
                        call2(W(k, K_CONNECTCB), chan, (u32)-1);
                }
            }
            continue;
        }
        st->absent = 0;
        if (!st->faked) {
            /* What WPAD does for a Classic Controller being connected: the
             * game's connect callback, then its extension callback. */
            st->faked = 1;
            W(S, DEBUG_OFF + 4)++;
            if (W(k, K_CONNECTCB))
                call2(W(k, K_CONNECTCB), chan, 0);
            call2(EXT_CB, chan, 2);
        }
        put_sample(k, h, l);
    }
}

/* WPADProbe(chan, &type): with no remote but a pad, say a Classic Controller
 * is there, so the KPAD library reads it instead of reporting the channel
 * as disconnected. Returns 1 if it answered (the result is 0). */
int gc_probe(u32 chan, s32 *type, u8 *S)
{
    u32 h, l;

    if (chan >= CHANNELS || remote_probe(chan) >= 0 || !pad_in(S, chan, &h, &l))
        return 0;
    W(S, DEBUG_OFF + 12)++;
    if (type)
        *type = 2;
    return 1;
}
