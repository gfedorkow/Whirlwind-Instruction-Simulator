# Copyright 2022 Guy C. Fedorkow
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#   The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Museum Demo Mode Controller
# This module controls the simulator, causing it to repeatedly step through several modes
# with different parameters.
# The initial goal is to run "bounce" for a while at normal speed, then run a few cycles in slow
# motion, then revert to normal speed.
# an Alternate Application may be switching to another program.

from screeninfo import get_monitors


class RunModeClass:
    def __init__(self, name, cycle_delay:int=0, cycle_limit:int=0, crt_fade_delay:int=0,
                 pop_up_tag:str=None, core_file:str = None):
        self.name = name
        self.instruction_cycle_delay = cycle_delay
        self.cycle_limit = cycle_limit
        self.pop_up_tag = pop_up_tag
        self.core_file = core_file
        self.crt_fade_delay = crt_fade_delay


class MuseumModeClass:
    def __init__(self):
        self.state = 0
        self.pop_up_win = None

        self.states = [
            RunModeClass(name="Fast", cycle_delay=0, cycle_limit=15000, crt_fade_delay=0,
                         pop_up_tag="Full Speed", core_file=None),
            RunModeClass(name="Slow", cycle_delay=300, cycle_limit=30, crt_fade_delay=200,
                         pop_up_tag="Slow Motion", core_file=None)
        ]
        # size of the primary display
        #self.screen_x = None
        #self.screen_y = None

        self.gfx = None
        self.win = None
        self.xpos = 300
        self.ypos = 50
        self.txt_obj = None  # the graphical object representing the string we last drew

    def next_state(self, cb, cpu, start=False):
        if start:
            self.state = 0
        else:
            self.state = (self.state + 1) % len(self.states)

        #        if self.txt_obj:
#            self.txt_obj.undraw()
#            cb.log.info("Close Pop Up")
        ns = self.states[self.state]
        cb.log.info("switch to sim state %s" % self.states[self.state].name)
        if ns.pop_up_tag:
            cb.log.info("Title '%s'" % ns.pop_up_tag)
            cb.dbwgt.screen_title = ns.pop_up_tag
        return ns


#    # read the size of the display itself from Windows
#   moved to wwinfra, Aug 25, 2022

    # cause Windows to size and place the CRT graphics window in the top right quarter of the
    # display.
    def museum_gfx_window_size(self, cb, win):
        geo_arg = "%dx%d+%d+%d" % (cb.screen_x/2, cb.screen_y/2, cb.screen_x/2, 0)
        win.master.geometry(geo_arg)


# finding the DPI rating for a screen
# This sample returns "pixels per one inch" (i.e., '1i')
# https://stackoverflow.com/questions/42961810/detect-dpi-scaling-factor-in-python-tkinter-application
"""
import tkinter
root = tkinter.Tk()
dpi = root.winfo_fpixels('1i')
"""