"""Per-build addresses for Donkey Kong Country Returns.

Everything here was found by reading the USA Rev 1 main.dol in Ghidra and then
matching the surrounding code (branch targets and immediates masked out)
against the other DOLs with tools/anchors.py; each match was unique. The
Classic Controller hook sites come straight from Vague Rant's per-build Gecko
codes (codes/). The two Japanese revisions ship the same main.dol.
"""

TEXT_ADDRESS = 0x80001820   # start of the patch's DOL text section
TEXT_LIMIT = 0x80003000     # the OS's low-memory globals start here


class Region:
    def __init__(self, key, name, game_id, revision, gecko, **addrs):
        self.key = key
        self.name = name
        self.game_id = game_id          # disc ID6, as read from the image
        self.revision = revision        # disc revisions that carry this main.dol
        self.gecko = gecko              # codes/<gecko>.ini
        self.__dict__.update(addrs)

    def __repr__(self):
        return f'{self.name} ({self.game_id})'


REGIONS = {
    'SF8E01_rev0': Region(
        'SF8E01_rev0', 'USA (Rev 0)', 'SF8E01', (0,), 'SF8E01_rev0.ini',
        update=0x803850C0,              # the game's per-frame controller update
        wpad_probe=0x804C8ED0,          # WPADProbe(chan, &type)
        si_gettype=0x804BCCE0,
        os_disable=0x804B4F80,
        os_restore=0x804B4FC0,
        ext_cb=0x80387C20,              # the game's WPAD extension callback
        si_state=0x80590158,            # si:: busy flag, SIPOLL shadow at +4, types at +0x18
        kpad_base=0x805C9CA8,           # KPAD library state, 0x688 per channel
        wpad_tbl=0x805CCE90,            # per-channel WPAD control block pointers
    ),
    'SF8E01_rev1': Region(
        'SF8E01_rev1', 'USA (Rev 1)', 'SF8E01', (1,), 'SF8E01_rev1.ini',
        update=0x80386F60,
        wpad_probe=0x804CAE80,
        si_gettype=0x804BEC90,
        os_disable=0x804B6F30,
        os_restore=0x804B6F70,
        ext_cb=0x80389AC0,
        si_state=0x80592178,
        kpad_base=0x805CBCE8,
        wpad_tbl=0x805CEED0,
    ),
    'SF8P01': Region(
        'SF8P01', 'Europe', 'SF8P01', (0,), 'SF8P01.ini',
        update=0x803864C0,
        wpad_probe=0x804CA320,
        si_gettype=0x804BE130,
        os_disable=0x804B63D0,
        os_restore=0x804B6410,
        ext_cb=0x80389020,
        si_state=0x805915F8,
        kpad_base=0x805CB168,
        wpad_tbl=0x805CE350,
    ),
    'SF8J01': Region(
        'SF8J01', 'Japan (Rev 0 and Rev 1)', 'SF8J01', (0, 1), 'SF8J01.ini',
        update=0x8038AFD0,
        wpad_probe=0x804CEF50,
        si_gettype=0x804C2D60,
        os_disable=0x804BB000,
        os_restore=0x804BB040,
        ext_cb=0x8038DB30,
        si_state=0x80596598,
        kpad_base=0x805D0128,
        wpad_tbl=0x805D3310,
    ),
}

UPDATE_PREIMAGE = 0x9421EC60            # stwu r1,-0x13a0(r1)
WPAD_PROBE_PREIMAGE = 0x9421FFF0        # stwu r1,-0x10(r1)
