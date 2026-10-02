#!/usr/bin/env python3
"""Drive the game in Dolphin with a scripted pad (the debug build) and save frames.

  play.py <image> <steps> <out prefix>
steps: comma list of  <seconds>:<name>  where name is a button (A B X Y Z S L R U D LT RT), 'N' (neutral),
or stk=<x>/<y> / cst=<x>/<y> with -1..1; each step is held until the next one. The newest frame is saved 3 s after every step (frames are dumped to disk by Dolphin and
pruned as we go: unpruned they fill the disk in a minute).
"""
import glob, os, shutil, struct, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ['FRAMEDUMP'] = '1'
import threading
import dolphin_gc as dg
import probe_state as ps

def state(name):
    h, l = dg.NEUTRAL
    if all(n in dg.BTN for n in name.split('+')):
        for n in name.split('+'):
            h |= dg.BTN[n]
    elif name.startswith('stk='):
        x, y = [float(v) for v in name[4:].split('/')]
        h = (h & ~0xFFFF) | (int(128 + 127 * x) << 8) | int(128 + 127 * y)
    elif name.startswith('cst='):
        x, y = [float(v) for v in name[4:].split('/')]
        l = (int(128 + 127 * x) << 24) | (int(128 + 127 * y) << 16)
    return h, l

def frames(user):
    return sorted(glob.glob(os.path.join(user, 'Dump', 'Frames', '**', '*.png'), recursive=True), key=os.path.getmtime)

def prune(user, stop):
    while not stop.is_set():
        fr = frames(user)
        for f in fr[:-20]:
            try: os.remove(f)
            except OSError: pass
        time.sleep(0.5)

def main():
    image, steps, out = sys.argv[1:4]
    user = os.path.abspath(os.environ.get('USERDIR', 'dumps/dolphin_user'))
    dg.prepare(user)
    p = subprocess.Popen([dg.DOLPHIN, '-b', '-u', user, '-e', os.path.abspath(image), '-v', os.environ.get('VIDEO', 'Metal')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    g = dg.connect(60)
    g.cont()
    # wait for the game's controller update to have run (the boot can take a minute the first time)
    for _ in range(120):
        time.sleep(3)
        g.interrupt()
        ready = struct.unpack('>I', g.read_mem(ps.SCR + 0x28, 4))[0]
        g.cont()
        if ready > 60:
            break
    time.sleep(3)
    t0 = time.time()
    stop = threading.Event()
    threading.Thread(target=prune, args=(user, stop), daemon=True).start()
    plan = [(float(a), b) for a, b in (s.split(':', 1) for s in steps.split(','))]
    try:
        for i, (t, name) in enumerate(plan):
            while time.time() - t0 < t:
                time.sleep(0.2)
            h, l = state(name)
            ps.feed(g, h, l)
            time.sleep(float(os.environ.get('SHOT_DELAY', 3)))
            fr = frames(user)
            if len(fr) > 3:
                shutil.copy(fr[-3], '%s_%02d_%s.png' % (out, i, name.replace('=', '').replace(',', '_')))
    finally:
        stop.set(); p.terminate(); time.sleep(2)
        shutil.rmtree(os.path.join(user, 'Dump'), ignore_errors=True)

main()
