"""Boot the debug build with Null video and walk a pad through its life: connect, buttons, the
controller-mode toggle, a second pad, and unplugging. Prints the KPAD status and the patch's debug
counters (update calls, connects, disconnects, probe answers)."""
import sys, os, time, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dolphin_gc as dg
import probe_state as ps

MODE = int(os.environ.get('MODE_ADDR', '0x80389ABC'), 16)

def dbg(g):
    return struct.unpack('>4I', g.read_mem(ps.SCR + 0x28, 16))

def show(g, what):
    g.interrupt()
    s0 = ps.state(g, 0); s1 = ps.state(g, 1)
    b0 = g.read_mem(ps.KPAD, 0x70); b1 = g.read_mem(ps.KPAD + 0x688, 0x70)
    h0 = struct.unpack('>I', b0[:4])[0]; h1 = struct.unpack('>I', b1[:4])[0]
    mode = g.read_mem(MODE, 4).hex()
    print('%-22s ch0 dev=%d hold=%08X | ch1 dev=%d hold=%08X | mode=%s | dbg update=%d connect=%d disconnect=%d probe=%d' % (
        what, s0['dev'], h0, s1['dev'], h1, mode, *dbg(g)), flush=True)
    g.cont()

def main():
    image = os.environ.get('IMAGE', 'dumps/test_rev1.iso')
    user = os.path.abspath('dumps/dolphin_user')
    dg.prepare(user)
    p = subprocess.Popen([dg.DOLPHIN, '-b', '-u', user, '-e', os.path.abspath(image), '-v', 'Null'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    g = dg.connect(60)
    g.cont()
    try:
        for _ in range(120):
            time.sleep(3)
            g.interrupt(); n = dbg(g)[0]; g.cont()
            if n > 60: break
        time.sleep(3)
        show(g, 'no pad')
        ps.feed(g, *dg.NEUTRAL); time.sleep(2); show(g, 'pad 1 neutral')
        ps.feed(g, dg.NEUTRAL[0] | dg.BTN['S'] | dg.BTN['Z'], dg.NEUTRAL[1]); time.sleep(1); show(g, 'Start+Z (toggle)')
        ps.feed(g, *dg.NEUTRAL); time.sleep(1); show(g, 'released')
        ps.feed(g, dg.NEUTRAL[0] | dg.BTN['S'] | dg.BTN['Z'], dg.NEUTRAL[1]); time.sleep(1); show(g, 'Start+Z again')
        ps.feed(g, *dg.NEUTRAL); time.sleep(1); show(g, 'released')
        ps.feed(g, dg.NEUTRAL[0] | dg.BTN['A'], dg.NEUTRAL[1], 1); time.sleep(2); show(g, 'pad 2 neutral+A on 1')
        ps.feed(g, dg.NEUTRAL[0] | dg.BTN['A'], dg.NEUTRAL[1], 1); time.sleep(1); show(g, 'pad 2 A')
        ps.feed(g, 0, 0, 0); time.sleep(3); show(g, 'pad 1 unplugged 3s')
        ps.feed(g, *dg.NEUTRAL); time.sleep(2); show(g, 'pad 1 back')
    finally:
        p.terminate()

main()
