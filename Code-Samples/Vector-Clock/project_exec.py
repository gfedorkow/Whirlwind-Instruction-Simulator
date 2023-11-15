# project-specific python
# These project-specific files would usually contain functions called by .exec statements
# embedded in ww source code.


import wwinfra
import time
import re
from tzlocal import get_localzone
from datetime import datetime


def breakp():
    print("breakpoint")

TZ = -5
cm = None
rl = None

def set_timezone_offset(cml, rll, tz=None):
    global TZ, cm, rl

    if tz is None:
        local = get_localzone()
        print("Timezone: %s" % str(local))
        now = str(datetime.now(local))
        m = re.search("([+-][0-9]*):([0-9]*)", now)
        tz = int(m.group(1))
    TZ = tz
    print("set timezone offset to %d hours" % TZ)
    cm = cml
    rl = rll

def get_posix_time(secp, minp, hourp, cml=None, rll=None):
    global TZ, cm
    if cml:
        cm = cml
    if rll:
        rl = rll
        
    posix_time = time.time()
    
    
    sec = int(posix_time % 60)
    min = int((posix_time/60) % 60)
    hour = int(((posix_time/(60 * 12)) + (TZ * 5)) % 60)

    cm.wr(rl(secp), sec)
    cm.wr(rl(minp), min)
    cm.wr(rl(hourp), hour)
    
    #yvelo_i = py_int(cm.rd(rl("y_velo1"))) 



def main():
    
    class core_mem_class:
        def __init__(self):
            pass
        def wr(addr, val):
            print("cm.wr addr %d, val %d" % (addr, val))
    def rll(name):
        symtab = {"sec": 1, "min": 2, "hour":3}
        return symtab[name]
    cml = core_mem_class
    set_timezone_offset(cml, rll) #, tz=0)
    get_posix_time("sec", "min", "hour", cml=cml, rll=rll)
    print("There is no Main!")


if __name__ == "__main__":
    
    main()

