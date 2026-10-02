#!/usr/bin/env python3
"""Patch a clean Donkey Kong Country Returns main.dol (USA Rev 0 or Rev 1,
Europe, or Japan) with GameCube controller support on top of Vague Rant and
crediar's Classic Controller hack.

Everything is injected as one extra DOL text section at 0x80001820 and
reached through direct branches, so no Gecko code handler is needed:

  Classic Controller  Vague Rant's / crediar's seven C2 hooks and five 04 writes
                      (codes/<build>.ini), applied as branches to the same bodies.
                      The Classic Controller shows up to the game as a Wii Remote
                      with a Nunchuk.
  GameCube controller an SI poller and a feeder hooked into the game's per-frame
                      controller update, plus a WPADProbe hook (src/). A pad is
                      turned into a Classic Controller sample, so it needs the
                      Classic Controller code above and is always installed
                      together with it.
"""
import json
import os
import struct
import sys

from dol import Dol
from gecko import parse
from regions import REGIONS, TEXT_ADDRESS, TEXT_LIMIT, UPDATE_PREIMAGE, WPAD_PROBE_PREIMAGE

if getattr(sys, 'frozen', False):
    HERE = os.path.join(sys._MEIPASS, 'tools')
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
CODES = os.path.join(HERE, '..', 'codes')
BLOBS = os.path.join(HERE, 'prebuilt', 'blobs.json')

# Instruction each Gecko hook replaces, in the order they appear in the .ini.
GECKO_HOOKS = ('ext_state', 'stick_a', 'stick_b', 'stick_c', 'ext_callback', 'dpd', 'buttons')
GECKO_PREIMAGES = (0x90190020, 0x7C9A0214, 0x7C9A0214, 0x28080001, 0x9421FFF0, 0x9421FFC0,
                   0x90030068)
# The 04 writes, in .ini order, and the retail word under each: the extension
# type check, the "mode" the callback reads instead of a constant (its home is
# zeroed padding), and the two constants it replaces.
GECKO_WRITE_PREIMAGES = (0x28000005, 0x28000001, 0x00000000, 0x38A00004, 0x38A00005)
NOP = 0x60000000


def word(dol, address):
    raw = dol.read(address, 4)
    return None if raw is None else struct.unpack('>I', raw)[0]


def branch(src, dst, link=False):
    off = dst - src
    if off & 3 or not -0x2000000 <= off < 0x2000000:
        raise ValueError(f'branch 0x{src:08X} -> 0x{dst:08X} is out of range/alignment')
    return 0x48000000 | (off & 0x03FFFFFC) | (1 if link else 0)


def load_gecko(region):
    writes, hooks = parse(os.path.join(CODES, region.gecko))
    if len(writes) != len(GECKO_WRITE_PREIMAGES) or len(hooks) != len(GECKO_HOOKS):
        raise AssertionError(f'{region.gecko}: expected {len(GECKO_WRITE_PREIMAGES)} writes '
                             f'and {len(GECKO_HOOKS)} C2 codes')
    return writes, dict(zip(GECKO_HOOKS, hooks.items()))


def load_blob(region, path=BLOBS):
    entry = json.load(open(path))['regions'][region.key]
    return [int(w, 16) for w in entry['words']], entry['symbols']


def lis_ori(value):
    """`lis r0,hi` / `ori r0,r0,lo` words that load `value` into r0."""
    return 0x3C000000 | value >> 16, 0x60000000 | value & 0xFFFF


def retail_words(region):
    """Retail word at every address the patch overwrites, gamecube or not."""
    writes, hooks = load_gecko(region)
    checks = [(a, p) for (a, _), p in zip(writes, GECKO_WRITE_PREIMAGES)]
    checks += [(hooks[n][0], p) for n, p in zip(GECKO_HOOKS, GECKO_PREIMAGES)]
    checks += [(region.update, UPDATE_PREIMAGE), (region.wpad_probe, WPAD_PROBE_PREIMAGE)]
    return dict(checks)


def detect_region(dol, key=None):
    """The region whose hook sites in `dol` all hold the retail instructions."""
    candidates = [REGIONS[key]] if key else list(REGIONS.values())
    problems = []
    for region in candidates:
        bad = [(a, word(dol, a), want) for a, want in retail_words(region).items()
               if word(dol, a) != want]
        if not bad:
            return region
        a, got, want = bad[0]
        problems.append(f'{region}: 0x{a:08X} holds '
                        + ('nothing' if got is None else f'0x{got:08X}')
                        + f', expected 0x{want:08X}')
    raise AssertionError('not a clean retail Donkey Kong Country Returns main.dol (other '
                         'version, or already patched): ' + '; '.join(problems))


class Patch:
    """Everything the patch puts in memory: a block of code and data at `base`,
    the instructions that now branch into it, and plain word writes."""

    def __init__(self, base, blob, sites, writes):
        self.base, self.blob, self.sites, self.writes = base, bytes(blob), sites, writes

    def site_words(self):
        return {site: branch(site, target) for site, target in self.sites.items()}


def make_patch(region, gamecube=True, base=TEXT_ADDRESS, blobs=BLOBS):
    """Build the patch for `region` to be placed at `base`."""
    gecko_writes, gecko = load_gecko(region)
    blob = bytearray()
    sites, writes = {}, list(gecko_writes)

    gc_words, sym = load_blob(region, blobs) if gamecube else ([], {})
    gc_words = list(gc_words)
    if gamecube:
        def idx(name):
            return sym[name] // 4
        for hook, site, pre in (('update', region.update, UPDATE_PREIMAGE),
                                ('probe', region.wpad_probe, WPAD_PROBE_PREIMAGE)):
            gc_words[idx(hook + '_orig')] = pre
            gc_words[idx(hook + '_hi')], gc_words[idx(hook + '_lo')] = lis_ori(site + 4)
            sites[site] = base + sym[hook + '_entry']
        blob.extend(struct.pack('>%dI' % len(gc_words), *gc_words))

    # Classic Controller bodies follow the GameCube half
    at = base + len(blob)
    for name in GECKO_HOOKS:
        site, body = gecko[name]
        body = list(body)
        if body[-1] != 0:
            raise AssertionError(f'{name}: C2 body does not end with its branch slot')
        body[-1] = branch(at + 4 * (len(body) - 1), site + 4)
        blob.extend(struct.pack('>%dI' % len(body), *body))
        sites[site] = at
        at += 4 * len(body)
    return Patch(base, blob, sites, writes)


def inject(src, dst, key=None, gamecube=True):
    """Patch `src` into `dst`. Returns (text section index, {site: target}, size, region)."""
    dol = Dol(src)
    region = detect_region(dol, key)
    patch = make_patch(region, gamecube)
    if patch.base + len(patch.blob) > TEXT_LIMIT:
        raise AssertionError(f'injected section ends at 0x{patch.base + len(patch.blob):08X}, past '
                             f'0x{TEXT_LIMIT:08X} (OS low-memory globals)')
    section = dol.add_text_section(patch.base, patch.blob)
    for addr, value in patch.writes:
        dol.write(addr, struct.pack('>I', value))
    for site, value in patch.site_words().items():
        dol.write(site, struct.pack('>I', value))
    dol.save(dst)
    return section, patch.sites, len(patch.blob), region


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--no-gamecube', action='store_true',
                    help='Classic Controller only, no GameCube controller support')
    ap.add_argument('--region', choices=sorted(REGIONS),
                    help='refuse a DOL from any other build (default: detect)')
    args = ap.parse_args()
    section, sites, size, region = inject(args.src, args.dst, args.region,
                                          not args.no_gamecube)
    print(f'{region}: injected {len(sites)} hooks into text section {section} at '
          f'0x{TEXT_ADDRESS:08X} ({size} bytes)')
    for site, target in sorted(sites.items()):
        print(f'  0x{site:08X} -> 0x{target:08X}')
