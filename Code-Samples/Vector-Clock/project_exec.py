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

# guy's initial version counted "hours" as 60-per-day, so that all clock hands 
# were computed as 0-59.  Rainer's clock takes conventional hours, as 0-11
hours_60_mode = False

def set_timezone_offset(cml, rll, tz=None, hours_sixty_mode_arg=False):
    global TZ, cm, rl, hours_sixty_mode

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
    hours_sixty_mode = hours_sixty_mode_arg

def get_posix_time(secp, minp, hourp, cml=None, rll=None):
    global TZ, cm, hours_sixty_mode
    if cml:
        cm = cml
    if rll:
        rl = rll
        
    posix_time = time.time()
    
    
    sec = int(posix_time % 60)
    min = int((posix_time/60) % 60)
    hr_correction = 1
    tz_correction = 1
    if hours_sixty_mode:
        hour = int(((posix_time/(60 * 12)) + (TZ * 5)) % 60)
    else:
        hour = int(((posix_time/3600) + TZ) % 12)

    cm.wr(rl(secp), sec)
    cm.wr(rl(minp), min)
    cm.wr(rl(hourp), hour)
    


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

