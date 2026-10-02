#!/usr/bin/env python3
"""Generate the Riivolution patches (riivolution/sd/) from the same code the
DOL patcher injects.

Copy the contents of riivolution/sd/ to the root of the SD card. There is one
XML per build, each with a choice of controller set; the patch's code is
written to 0x80001820 from a file in /CountryReturnsPatch, and the game's hook
sites are overwritten with branches into it, each checked against the retail
word first.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crpatch                                      # noqa: E402
from regions import REGIONS, TEXT_ADDRESS           # noqa: E402

ROOT = os.path.join(HERE, '..')
FOLDER = 'CountryReturnsPatch'
CHOICES = (
    ('GameCube controller + Classic Controller', 'gc', True),
    ('Classic Controller only', 'cc', False),
)
# the disc's version byte, where one build of main.dol is not shared by every revision
VERSION = {'SF8E01_rev0': 0, 'SF8E01_rev1': 1}


def write_region(region, sd):
    folder = os.path.join(sd, FOLDER)
    os.makedirs(folder, exist_ok=True)
    retail = crpatch.retail_words(region)
    patches = []
    for title, key, gamecube in CHOICES:
        patch = crpatch.make_patch(region, gamecube)
        assert patch.base == TEXT_ADDRESS
        name = f'{region.key}_{key}.bin'
        open(os.path.join(folder, name), 'wb').write(patch.blob)
        mem = [f'    <memory offset="0x{patch.base:08X}" valuefile="/{FOLDER}/{name}" />']
        words = dict(patch.site_words())
        words.update(patch.writes)
        for addr, value in sorted(words.items()):
            mem.append(f'    <memory offset="0x{addr:08X}" value="{value:08X}" '
                       f'original="{retail[addr]:08X}" />')
        patches.append((title, key, mem))
    version = f' version="{VERSION[region.key]}"' if region.key in VERSION else ''
    xml = ['<wiidisc version="1">',
           f'  <id game="{region.game_id}"{version} />',
           '  <options>',
           '    <section name="Donkey Kong Country Returns">',
           '      <option name="Controllers" default="1">']
    for title, key, _ in patches:
        xml.append(f'        <choice name="{title}"><patch id="cr_{key}" /></choice>')
    xml += ['      </option>', '    </section>', '  </options>']
    for _, key, mem in patches:
        xml.append(f'  <patch id="cr_{key}">')
        xml += mem
        xml.append('  </patch>')
    xml.append('</wiidisc>')
    path = os.path.join(sd, 'riivolution', f'CountryReturnsPatch_{region.key}.xml')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w').write('\n'.join(xml) + '\n')
    return path


def main():
    sd = os.path.join(ROOT, 'riivolution', 'sd')
    shutil.rmtree(os.path.join(ROOT, 'riivolution'), ignore_errors=True)
    for region in REGIONS.values():
        print(os.path.relpath(write_region(region, sd), ROOT))


if __name__ == '__main__':
    main()
