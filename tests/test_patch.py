"""Tests that need no game files: they build a skeleton DOL that holds only the
retail instructions the patcher checks, and patch that."""
import json
import os
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))

import build_blobs                      # noqa: E402
import crpatch                          # noqa: E402
import make_riivolution                 # noqa: E402
from dol import Dol                     # noqa: E402
from regions import REGIONS, TEXT_ADDRESS as BASE, TEXT_LIMIT  # noqa: E402

TEXT_START, TEXT_END = 0x80004000, 0x80540000


def skeleton(region):
    """A DOL with one big text section and the retail words at every hook site."""
    size = TEXT_END - TEXT_START
    text = bytearray(size)
    for addr, word in crpatch.retail_words(region).items():
        struct.pack_into('>I', text, addr - TEXT_START, word)
    header = bytearray(0x100)
    struct.pack_into('>I', header, 0x00, 0x100)
    struct.pack_into('>I', header, 0x04, 0)
    struct.pack_into('>I', header, 0x48, TEXT_START)
    struct.pack_into('>I', header, 0x90, size)
    struct.pack_into('>I', header, 0xE0, TEXT_START)
    return bytes(header) + bytes(text)


class PatchTests(unittest.TestCase):
    def patch(self, region, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, 'in.dol'), os.path.join(tmp, 'out.dol')
            open(src, 'wb').write(skeleton(region))
            result = crpatch.inject(src, dst, key=region.key, **kw)
            return result, Dol(dst)

    def test_blobs_match_sources(self):
        data = json.load(open(crpatch.BLOBS))
        self.assertEqual(data['sha256'], build_blobs.digest(),
                         'tools/prebuilt/blobs.json is stale: run tools/build_blobs.py')
        self.assertFalse(data['debug'])

    def test_every_build_and_option_set(self):
        for region in REGIONS.values():
            for gamecube, hooks in ((True, 9), (False, 7)):
                with self.subTest(region=region.key, gamecube=gamecube):
                    (section, sites, size, found), out = self.patch(region, gamecube=gamecube)
                    self.assertIs(found, region)
                    self.assertEqual(len(sites), hooks)
                    self.assertLessEqual(BASE + size, TEXT_LIMIT)
                    self.assertEqual(out.addr[section], BASE)
                    for site, target in sites.items():
                        word = struct.unpack('>I', out.read(site, 4))[0]
                        self.assertEqual(word >> 26, 18)            # b
                        off = word & 0x03FFFFFC
                        off -= 0x4000000 if off & 0x2000000 else 0
                        self.assertEqual(site + off, target)
                        self.assertTrue(BASE <= target < BASE + size)

    def test_gecko_bodies_return_to_the_game(self):
        region = REGIONS['SF8E01_rev1']
        (_, sites, size, _), out = self.patch(region, gamecube=False)
        _, hooks = crpatch.load_gecko(region)
        for name, (site, body) in hooks.items():
            at = sites[site]
            last = struct.unpack('>I', out.read(at + 4 * (len(body) - 1), 4))[0]
            off = last & 0x03FFFFFC
            off -= 0x4000000 if off & 0x2000000 else 0
            self.assertEqual(at + 4 * (len(body) - 1) + off, site + 4, name)

    def test_gc_wrappers_return_to_the_game(self):
        for region in REGIONS.values():
            _, sym = crpatch.load_blob(region)
            (_, sites, size, _), out = self.patch(region)
            for hook, site in (('update', region.update), ('probe', region.wpad_probe)):
                at = sites[site]
                self.assertEqual(at, BASE + sym[hook + '_entry'])
                orig = struct.unpack('>I', out.read(BASE + sym[hook + '_orig'], 4))[0]
                self.assertEqual(orig, {'update': crpatch.UPDATE_PREIMAGE,
                                        'probe': crpatch.WPAD_PROBE_PREIMAGE}[hook])
                hi = struct.unpack('>I', out.read(BASE + sym[hook + '_hi'], 4))[0]
                lo = struct.unpack('>I', out.read(BASE + sym[hook + '_lo'], 4))[0]
                self.assertEqual((hi & 0xFFFF) << 16 | lo & 0xFFFF, site + 4)

    def test_mode_word_is_initialised(self):
        region = REGIONS['SF8E01_rev1']
        _, out = self.patch(region)
        writes, _ = crpatch.load_gecko(region)
        self.assertIn(0x02010201, [v for _, v in writes])
        for addr, value in writes:
            self.assertEqual(struct.unpack('>I', out.read(addr, 4))[0], value)

    def test_refuses_to_patch_twice(self):
        region = REGIONS['SF8P01']
        with tempfile.TemporaryDirectory() as tmp:
            src, once, twice = (os.path.join(tmp, n) for n in ('in.dol', 'once.dol', 'twice.dol'))
            open(src, 'wb').write(skeleton(region))
            crpatch.inject(src, once)
            with self.assertRaises(AssertionError):
                crpatch.inject(once, twice)

    def test_other_build_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, 'in.dol'), os.path.join(tmp, 'out.dol')
            open(src, 'wb').write(skeleton(REGIONS['SF8P01']))
            with self.assertRaises(AssertionError):
                crpatch.inject(src, dst, key='SF8E01_rev0')

    def test_riivolution_matches_retail(self):
        with tempfile.TemporaryDirectory() as tmp:
            for region in REGIONS.values():
                path = make_riivolution.write_region(region, tmp)
                xml = open(path).read()
                self.assertIn(region.game_id, xml)
                for addr, word in crpatch.retail_words(region).items():
                    self.assertIn(f'offset="0x{addr:08X}"', xml)
                    self.assertIn(f'original="{word:08X}"', xml)


if __name__ == '__main__':
    unittest.main()
