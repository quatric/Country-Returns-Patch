"""Boot the debug build in Dolphin with no Wii Remote, feed pad presses over GDB and print what the
KPAD library and the game's controller manager make of them."""
import sys, os, time, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin_gc as dg
import probe_state as ps

def status(g, ch=0):
    b = g.read_mem(ps.KPAD + ch * 0x688, 0x90)
    hold, trig, rel = struct.unpack('>III', b[0:12])
    cl, = struct.unpack('>I', b[0x60:0x64])
    ls = struct.unpack('>ff', b[0x6C:0x74])
    return dict(hold=hold, trig=trig, rel=rel, cl=cl, dev=b[0x5C], ls=ls)

def main():
    image = os.environ.get('IMAGE', 'dumps/test_rev1.iso')
    user = os.path.abspath('dumps/dolphin_user')
    dg.prepare(user)
    p = subprocess.Popen([dg.DOLPHIN, '-b', '-u', user, '-e', os.path.abspath(image), '-v', 'Null'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    g = dg.connect(60)
    g.cont()
    try:
        time.sleep(float(os.environ.get('BOOT', 22)))
        ps.feed(g, *dg.NEUTRAL)
        time.sleep(4)
        tests = [(n, dg.BTN[n]) for n in ('A', 'B', 'X', 'Y', 'S', 'Z', 'L', 'R', 'U', 'D', 'LT', 'RT')]
        tests += [('stick right', 0x0000E080 | 0x00800000 & 0), ('stick up', 0x00808000 | 0xE0)]
        for name, hb in tests:
            h = dg.NEUTRAL[0] | hb if not name.startswith('stick') else (0x00800000 | (0xE0 << 8 if name == 'stick right' else 0xE0) | (0x80 if name == 'stick right' else 0x8000))
            ps.feed(g, h, dg.NEUTRAL[1])
            time.sleep(1.0)
            g.interrupt(); s = status(g); g.cont()
            print('%-12s hold=%08X trig=%08X cl=%04X dev=%d ls=(%.2f,%.2f)' % (name, s['hold'], s['trig'], s['cl'], s['dev'], *s['ls']), flush=True)
            ps.feed(g, *dg.NEUTRAL); time.sleep(0.5)
        # combos
        for name, hb in (('Start+Z', dg.BTN['S'] | dg.BTN['Z']), ('L+R+Start', dg.BTN['L'] | dg.BTN['R'] | dg.BTN['S'])):
            ps.feed(g, dg.NEUTRAL[0] | hb, dg.NEUTRAL[1]); time.sleep(1.0)
            g.interrupt(); s = status(g); g.cont()
            print('%-12s hold=%08X cl=%04X' % (name, s['hold'], s['cl']), flush=True)
            ps.feed(g, *dg.NEUTRAL); time.sleep(0.5)
    finally:
        p.terminate()

main()
