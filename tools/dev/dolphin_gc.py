#!/usr/bin/env python3
"""Run Donkey Kong Country Returns in Dolphin with the debug build of the patch (a
scripted GameCube pad on port 1, no Wii Remote) and read the game's KPAD state
back over the GDB stub.

The pad's response is written by a debugger to the patch's scratch area
(+0x40 + 8 * channel, see src/gcpad.c DEBUG_FEED): Dolphin's emulated SI never
delivered input through its Pipe device, and this tests the KPAD/WPAD side
deterministically. The real SI path in Dolphin only proves detection.
"""
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gdbmem import Gdb  # noqa: E402

DOLPHIN = '/Applications/Dolphin.app/Contents/MacOS/Dolphin'
PORT = 2260

# pad responses: SICnINBUFH / SICnINBUFL
BTN = dict(A=0x01000000, B=0x02000000, X=0x04000000, Y=0x08000000, S=0x10000000, Z=0x00100000,
           L=0x00400000, R=0x00200000, U=0x00080000, D=0x00040000, LT=0x00010000, RT=0x00020000)
NEUTRAL = (0x00808080, 0x80800000)


def prepare(user, wiimote=False):
    shutil.rmtree(user, ignore_errors=True)
    for d in ('Config', 'GameSettings'):
        os.makedirs(os.path.join(user, d))
    open(os.path.join(user, 'Config', 'Dolphin.ini'), 'w').write(
        "[General]\nGDBPort = %d\n[Interface]\nConfirmStop = False\nUsePanicHandlers = False\n"
        "[Core]\nMMU = True\nCPUThread = False\nCPUCore = 4\nEnableDebugging = True\nEnableCheats = False\n"
        "WiimoteContinuousScanning = False\nWiimoteControllerInterface = False\nSIDevice0 = 6\nSIDevice1 = 0\n"
        "[Analytics]\nPermissionAsked = True\nEnabled = False\n" % PORT +
        ("[Movie]\nDumpFrames = True\nDumpFramesSilent = True\nDumpFramesAsImages = True\n"
         if os.environ.get('FRAMEDUMP') else ""))
    open(os.path.join(user, 'Config', 'Logger.ini'), 'w').write(
        "[Options]\nVerbosity = 5\nWriteToFile = True\nWriteToConsole = False\n"
        "[Logs]\nOSREPORT = True\nOSREPORT_HLE = True\nPOWERPC = True\n")
    open(os.path.join(user, 'Config', 'WiimoteNew.ini'), 'w').write(
        "[Wiimote1]\nSource = %d\n" % (1 if wiimote else 0))


def launch(user, image, video):
    cmd = ['-b', '-u', user, '-e', image, '-v', video]
    subprocess.check_call(['open', '-n', '-a', '/Applications/Dolphin.app', '--args'] + cmd)
    time.sleep(2)


def pid(user):
    out = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True).stdout
    for ln in out.splitlines():
        if user in ln and 'Dolphin' in ln and 'dolphin_gc' not in ln:
            return int(ln.split()[0])


def stop(user):
    p = pid(user)
    if p:
        os.kill(p, 15)
        time.sleep(2)
        if pid(user):
            os.kill(pid(user), 9)


def connect(tries=120):
    for _ in range(tries):
        try:
            return Gdb(timeout=30)
        except OSError:
            time.sleep(1)
    raise RuntimeError('no GDB stub')
