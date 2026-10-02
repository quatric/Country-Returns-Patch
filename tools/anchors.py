"""Find the addresses the GameCube-pad patch needs in every Donkey Kong Country
Returns build.

Everything is written once against USA Rev 1 (SF8E01 rev 1); the other builds
share the same compiled code at other addresses. A function is located by
matching a window of USA instructions against the target DOL with the
relocatable bits (branch displacements, address halves, load/store offsets)
masked out, and it must match exactly once. Data addresses are read back from
the matched code (the lis/addi pair that references them), never guessed.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dol import Dol  # noqa: E402


def mask(w):
    op = w >> 26
    if op == 18:                                    # b / bl: keep opcode, AA, LK
        return w & 0xFC000003
    if op == 16:                                    # bc: keep everything but displacement
        return w & 0xFFFF0003
    if op in (14, 15, 24, 25, 26, 27, 28, 29):      # addi/lis/ori/oris/xori/andi
        return w & 0xFFFF0000
    if 32 <= op <= 55:                              # loads/stores: drop displacement
        return w & 0xFFFF0000
    return w


def words(d, va, n):
    b = d.read(va, n * 4)
    return list(struct.unpack('>%dI' % n, b)) if b and len(b) == n * 4 else None


def imm(w):
    v = w & 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class Finder:
    def __init__(self, ref, tgt):
        self.ref, self.tgt = ref, tgt
        o, a, s, _ = [x for x in tgt.secs if x[3] == 1][0]
        self.tw = struct.unpack('>%dI' % (s // 4), tgt.data[o:o + s])
        self.tbase = a
        self.tm = [mask(w) for w in self.tw]

    def locate(self, ref_va, n=24):
        """Address in the target of the code at ref_va; must match exactly once."""
        rm = [mask(w) for w in words(self.ref, ref_va, n)]
        first = rm[0]
        hits = [self.tbase + i * 4 for i in range(len(self.tm) - n)
                if self.tm[i] == first and self.tm[i:i + n] == rm]
        if len(hits) != 1:
            raise SystemExit('anchor %08X: %d matches' % (ref_va, len(hits)))
        return hits[0]

    def pair(self, ref_va, ref_target, n=80):
        """The target build's value for the address that the lis + addi pair
        near ref_va loads (ref_target in the reference build)."""
        t_va = self.locate(ref_va, 40)
        rw, tw = words(self.ref, ref_va, n), words(self.tgt, t_va, n)
        for i in range(n):
            w = rw[i]
            if w >> 26 != 15:
                continue
            reg = (w >> 21) & 31
            for j in range(i + 1, min(n, i + 16)):
                w2 = rw[j]
                if w2 >> 26 == 14 and (w2 >> 16) & 31 == reg:
                    if (((w & 0xFFFF) << 16) + imm(w2)) & 0xFFFFFFFF == ref_target:
                        t, t2 = tw[i], tw[j]
                        assert t >> 26 == 15 and t2 >> 26 == 14
                        return (((t & 0xFFFF) << 16) + imm(t2)) & 0xFFFFFFFF
        raise SystemExit('no pair for %08X near %08X' % (ref_target, ref_va))


# (name, USA Rev 1 address, instructions to match)
FUNCS = (
    ('update', 0x80386F60, 40),         # the game's per-frame controller update
    ('wpad_probe', 0x804CAE80, 24),     # WPADProbe(chan, &type)
    ('si_gettype', 0x804BEC90, 40),     # SIGetType(chan)
    ('os_disable', 0x804B6F30, 6),
    ('os_restore', 0x804B6F70, 6),
    ('ext_cb', 0x80389AC0, 40),         # the game's WPAD extension callback
    ('kpad_read', 0x804A8560, 40),      # KPADiRead (after KPADRead's two-instruction prologue)
)


def resolve(ref, tgt):
    f = Finder(ref, tgt)
    r = {name: f.locate(va, n) for name, va, n in FUNCS}
    si_types = f.pair(0x804BEC90, 0x80592190)
    r['si_state'] = si_types - 0x18     # busy flag; SIPOLL shadow at +4, types at +0x18
    r['kpad_base'] = f.pair(0x804A8560, 0x805CBCE8)
    r['wpad_tbl'] = f.pair(0x804CAE80, 0x805CEED0)
    return r


if __name__ == '__main__':
    ref = Dol(sys.argv[1])
    for p in sys.argv[2:]:
        r = resolve(ref, Dol(p))
        print(os.path.basename(os.path.dirname(os.path.dirname(p))),
              {k: '%08X' % v for k, v in r.items()})
