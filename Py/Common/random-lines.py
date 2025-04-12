

# Draw a grid of boxes using short vectors.
# But draw the vectors in random order

# G Fedorkow, May 26, 2024; Jun 13, 2024

import sys
import time
import random
import os
import analog_scope
try:
    import RPi.GPIO as gpio
    import spidev
except ImportError:
    pass

pin_pwr_ctl = 19
class PwrCtlClass:
    def __init__(self):
        self.pwr_state: int = 0

    def pwr_on(self) -> None:
        global pin_pwr_ctl

        self.pwr_state = 1

        gpio.setmode(gpio.BCM)
        gpio.setup(pin_pwr_ctl, gpio.OUT)

        gpio.output(pin_pwr_ctl, self.pwr_state)


def nsec_delay(duration):
    stop = time.perf_counter_ns() + int(duration)
    while time.perf_counter_ns() < stop:
        pass

# Take one entry out of a list
# I'm sure there's a builtin function for this, but there's no wifi on this airplane to look it up!
def delete_entry(list, offset):
    n = len(list)
    newlist = []
    for i in range(0, n):
        if i != offset:
            newlist.append(list[i])
    return(newlist)

class DisplayPoints():
    def __init__(self, dimension):
        self.dimension = dimension
        self.scrambled_list = []
        
        self.ordered_list = []
        for x in range(0, self.dimension):
            for y in range(0, self.dimension):
                if x != self.dimension - 1:
                    self.ordered_list.append([x, y, 'h'])
                if y != self.dimension - 1:
                    self.ordered_list.append([x, y, 'v'])

    def scramble_display_list(self):
        still_to_go = []

        n = len(self.ordered_list)
        # I just need a separate copy of the ordered list, but I can't recall how to do
        # that so it makes a copy, not an alias
        for i in range(0,n):
            still_to_go.append(self.ordered_list[i])
        for i in range(0,n):
            n_left = len(still_to_go)
            next_rand_entry = random.randrange(n_left)
            # print("place n=%d, still_to_go len %d, rand_entry %d" % (i, n_left, next_rand_entry))
            self.scrambled_list.append(still_to_go[next_rand_entry])
            still_to_go = delete_entry(still_to_go, next_rand_entry)
        
        return self.scrambled_list


    def render_scrambled_list(self, ana_scope, delay = 0):
        center = self.dimension / 2
        scale = 200
        short_vec = 31

        dp = self.scrambled_list
        for p in dp:
            x = scale * (p[0] - center)
            y = scale * (p[1] - center)
            if p[2] == 'v':
                dx = 0
                dy = short_vec
            else:
                dx = short_vec
                dy = 0
            ana_scope.drawVector(x, y, dx, dy)
            if delay:
                nsec_delay(delay)
        return


def main():
    host_os = os.getenv("OS")
    dimension = 8

    cb = ConstantsClass()
    ana_scope = analog_scope.AnaScope(host_os, cb)
    PwrCtlClass()

    dpc = DisplayPoints(dimension)
    dpc.scramble_display_list()
    dp = dpc.scrambled_list

    #for p in dp:
        # print("pt: %d %d %s" % (p[0], p[1], p[2]))
    while True:
        for i in range(0,100):
            dpc.render_scrambled_list(ana_scope, delay = 0)

        incr = 1
        d = 1
        i = 1
        while True:
            if i < 55:
                m = 1.15
            else:
                m = 1.5
            if incr < 0:
                m = 1/m
            dpc.render_scrambled_list(ana_scope, delay = d * 1000 )
            d = d * m
            if i > 30 and (i % 5 == 0):
               print("Delay = %d usec, i = %d, incr = %d" % (d, i, incr))
            i += incr
            if incr > 0 and i == 60:
                incr = -incr
            if incr < 0 and i == 0:
                break
        if gpio.input(ana_scope.pin_isKey) == 0:   # detect the Interrupt button
            return

if __name__ == "__main__":
    class LogClass:
        def __init__(self):
            pass

    class ConstantsClass:
        def __init__(self):
            self.SCOPE_MAIN = 1
            self.SCOPE_AUX = 2


main()
