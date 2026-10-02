import sys,os,time,struct
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import dolphin_gc as dg

KPAD=0x805CBCE8
SCR=0x8000193C
def state(g, ch=0):
    b=g.read_mem(KPAD+ch*0x688,0x180)
    hold,trig,rel=struct.unpack('>III',b[0:12])
    return dict(hold=hold,dev=b[0x5C],err=b[0x5D],idx=b[0x17A],cnt=b[0x17B])
def feed(g,h,l,ch=0):
    g.interrupt(); g.cmd('M%x,8:%s'%(SCR+0x40+ch*8,struct.pack('>II',h,l).hex())); g.cont()
if __name__=='__main__':
    user=os.path.abspath('dumps/dolphin_user')
    dg.prepare(user)
    import subprocess
    p=subprocess.Popen([dg.DOLPHIN,'-b','-u',user,'-e',os.path.abspath('dumps/test_rev1.iso'),'-v','Null'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    g=dg.connect(60)
    g.cont()
    try:
        time.sleep(float(os.environ.get('BOOT',20)))
        feed(g,*dg.NEUTRAL)
        time.sleep(8)
        g.interrupt()
        print('scratch dbg',g.read_mem(SCR+0x28,0x10).hex())
        print('state0',state(g,0))
        g.cont()
    finally:
        p.terminate()
