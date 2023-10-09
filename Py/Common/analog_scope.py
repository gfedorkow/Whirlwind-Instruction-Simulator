
# Copyright 2023 Guy C. Fedorkow
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

# This module interfaces the simulator to an analog scope driver built by Rainer Glaschick at
# Heinz Nixdorf Forum in Paderborn, Germany.
# The converter comprises two D/A converters and integrators to draw points and vectors on an X/Y/Z
# oscilloscope, and is packaged on a small PCB.
# The converters are accessed via SPI bus
# The PCB also includes an interface to a "light gun" that can report clicks via GPIO
# The interface is designed to work with Raspberry Pi
#
# Note that we haven't found a digital oscilloscope that works for general X/Y/Z inputs
#
# Part of this code was drawn from Rainer's python-based test program for the interface card.
# g fedorkow, July 7, 2023

DebugAnaScope = False
DebugGun = True

import time
import math
import os
try:
    import RPi.GPIO as gpio
    import spidev
except ImportError:
    pass


# Analog Scope Interface Class
class AnaScope:
    def __init__(self, host_os, cb):
        #
        version = "g1.1gf"
        if DebugAnaScope: print("Analog Scope Interface Version %s" % version)
        if host_os == "Windows_NT":
            self.PCDebug = True
        else:
            self.PCDebug = False  # RasPi seems to return "none" for this environment variable
        self.cb = cb  # this class is full of all kinds of helpful infra
        self.screen_max = 1024
        # pin definitions in BCM numbering
        self.pin_doMove = 17
        self.pin_doDraw = 22
        self.pin_enZ1 = 23  # not yet used
        self.pin_enZ2 = 18  # not yet used
        self.pin_isKey = 27 # used as the Stop signal
        self.pin_isGun1 = 24
        self.pin_isGun2 = 25
        self.pin_isGun1on = 7
        self.pin_isGun2on = 4
        self.pin_isIntercept = 21  # used to indicate Target or Intercept to air-defense sim

        # SPI pins are defined by SPI interface

        self.move_delay = 35.0E-6
        self.draw_delay = 55.0E-6

        # for light gun
        self.wasPoint = False
        self.wasGunPulse1 = True  # if a pulse was delivered
        self.gunTime1 = 0.0
        self.wasGunPulse2 = True  # if a pulse was delivered
        self.gunTime2 = 0.0
        self.debounceGunTime = 0.05

        # initialize RasPi hardware
        if not self.PCDebug:
            gpio.setmode(gpio.BCM)
            gpio.setup(self.pin_doMove, gpio.OUT)
            gpio.setup(self.pin_doDraw, gpio.OUT)
            gpio.setup(self.pin_enZ1,   gpio.OUT)
            gpio.setup(self.pin_enZ2,   gpio.OUT)
            gpio.setup(self.pin_isKey, gpio.IN, pull_up_down=gpio.PUD_UP)
            gpio.setup(self.pin_isIntercept, gpio.IN, pull_up_down=gpio.PUD_UP)
            gpio.setup(self.pin_isGun1, gpio.IN, pull_up_down=gpio.PUD_UP)
            gpio.setup(self.pin_isGun2, gpio.IN, pull_up_down=gpio.PUD_UP)
            gpio.setup(self.pin_isGun1on, gpio.IN, pull_up_down=gpio.PUD_UP)
            gpio.setup(self.pin_isGun2on, gpio.IN, pull_up_down=gpio.PUD_UP)
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)
            # spi.max_speed_hz = 4000000

    def __del__(self):
        if not self.PCDebug:
            gpio.cleanup()
            self.spi.close()

    # time.sleep has 70us overhead on Raspi B+ with python 3.7, use quicker method
    def _delay(self, duration):
        stop = time.perf_counter_ns() + int(duration * 1e9)
        while time.perf_counter_ns() < stop:
            pass

    # private routine to send numbers to the D/A converter
    def _setDA(self, n, val):
        """ sets one D/A converter
            n: SPI address 0 or 1 for converter number
            val: python int -1023 to +1023
        """
        # It's a 12-bit D/A converter, so we wire in the range of 0-4095
        if val >= 1024:
            val = 1023
        if val <= -1023:
            val = -1023

        x = int(val * 2)
        ival = 2048 - int(x)  # convert range to 0-4095

        hival = ival // 256
        loval = ival % 256
        mask = 0x30
        if n == 0:
            mask = mask | 0x80
        outv = [mask | hival, loval]
        if not self.PCDebug:
            self.spi.writebytes(outv)
        else:
            pass  # print("SPI write=[0x%02x, 0x%02x]" % (outv[0], outv[1]))

    def _movePoint(self, posx, posy):
        # move to destination
        self._setDA(0, posx)
        self._setDA(1, posy)
        if not self.PCDebug:
            gpio.output(self.pin_doMove, 1)
            # time.sleep(self.move_delay)  # don't use the built-in sleep...
            self._delay(self.move_delay)   #  ... use the local one instead
            gpio.output(self.pin_doMove, 0)

    def _drawSegment(self, speedx, speedy, scope):
        # set speed and intensity
        self._setDA(0, speedx)
        self._setDA(1, speedy)
        if scope == self.cb.SCOPE_MAIN:
            gpio.output(self.pin_enZ1, 1)
            gpio.output(self.pin_enZ2, 0)
        elif scope == self.cb.SCOPE_AUX:
            gpio.output(self.pin_enZ1, 0)
            gpio.output(self.pin_enZ2, 1)
        else:
            self.cb.log.fatal("DrawSegment: Scope #%d is unrecognized" % scope)
        if not self.PCDebug:
            gpio.output(self.pin_doDraw, 1)
            # time.sleep(self.draw_delay)  # don't use the built-in sleep...
            self._delay(self.draw_delay)   #  ... use the local one instead
            gpio.output(self.pin_doDraw, 0)

    def _drawSmallVector(self, posx, posy, speedx, speedy, scope):
        """ Basic operation: Draw a vector with given speed
            As the endpoint is not directly given,
            but as a speed, the length is limited
            so that the endpoint can be predicted precise enough.
            The draw mechanism draws for 50us
            with maximum speed, it draws 1/8 of the screen width.
            To draw a point, use zero speeds
        """
        if DebugAnaScope: print("    drawSmallVector: posx=%d, posy=%d, speedx=%d, speedy=%d" % \
                                (posx, posy, speedx, speedy))
        self._movePoint(posx, posy)
        self._drawSegment(speedx, speedy, scope)
        self.wasPoint = True


    def drawPoint(self, posx, posy, scope=None):
        """ draw a point as a vector of length 0
        """
        if scope is None:
            scope = self.cb.SCOPE_MAIN
        if DebugAnaScope: print("drawPoint: posx=%d, posy=%d" % (posx, posy))
        self._drawSmallVector(posx, posy, 0, 0, scope)


    def drawVector(self, x0, y0, dx, dy, scope=None):
        """ General vector drawing
            if length exceeds the (short) maximum,
            a chain of vectors is used.
        """
        if scope is None:
            scope = self.cb.SCOPE_MAIN

        if DebugAnaScope: print("drawVector: x0=%d, y0=%d, dx=%d, dy=%d" % (x0, y0, dx, dy))
        # maximum move for a short vector at full speed
        xmaxdist = 0.23 * self.screen_max  # 0.25 nominal; adjust hardware
        ymaxdist = 0.23 * self.screen_max

        # determine distances
        # dx = x1 - x0
        # dy = y1 - y0
        # required speed, may be larger that +/- 1.0 for long vectors
        sx = dx / xmaxdist
        sy = dy / ymaxdist
        # print(x0, y0, dx, dy, sx, sy)

        # Rainer, why was this special case needed?
        # # might be a short vector, then draw now
        # if abs(sx) <= 1.0 and abs(sy) <= 1.0:
        #     self.drawSmallVector(x0, y0, sx, sy)
        #     return

        # determine number of segments, at least 1
        xsegs = 1 + math.floor(abs(sx))
        ysegs = 1 + math.floor(abs(sy))
        segs = max(xsegs, ysegs)

        # reduce distance and speed by number of segments
        dx = dx / segs
        dy = dy / segs
        sx = sx / segs
        sy = sy / segs

        # loop
        # print(segs, x0, y0, sx, sy)
        while segs > 0:
            self._drawSmallVector(x0, y0, int(sx * self.screen_max), int(sy * self.screen_max), scope)
            # advance starting point by speed
            x0 += dx
            y0 += dy
            # next segment
            segs -= 1
        self.wasPoint = False


    """
      Draw a circle with center at (x,y) and radius r. 
      TODO: properly truncate at border
    """
    def drawCircle(self, x0, y0, r, scope=None):
        if scope is None:
            scope = self.cb.SCOPE_MAIN

        if DebugAnaScope: print("drawCircle: x0=%d, y0=%d, r=%d" % (x0, y0, r))
        # number of vectors: 30 for radius 1.0
        points = int(30.0 * r)
        # use a minimum of points
        points = max(8, points)
        print("points: %d" % points)

        x1 = x0
        y1 = y0 + r
        for j in range(1, points + 1):
            t = math.radians(j * 360 / points)
            dx = r * math.sin(t)
            dy = y0 + r * math.cos(t)
            self.drawVector(x1, y1, dx, dy, scope)
            x1 += dx
            y1 += dy


    def drawChar(self, x, y, mask, expand, Xwin_crt, scope=None):
        if scope is None:
            scope = self.cb.SCOPE_MAIN

        last_x = x
        last_y = y
        toMove = True
        for i in range(0, 7):
            if Xwin_crt.WW_CHAR_SEQ[i] == "down":
                y = last_y - Xwin_crt.WW_CHAR_VSTROKE * expand
            elif Xwin_crt.WW_CHAR_SEQ[i] == "up":
                y = last_y + Xwin_crt.WW_CHAR_VSTROKE * expand
            elif Xwin_crt.WW_CHAR_SEQ[i] == "left":
                x = last_x - Xwin_crt.WW_CHAR_HSTROKE * expand
            elif Xwin_crt.WW_CHAR_SEQ[i] == "right":
                x = last_x + Xwin_crt.WW_CHAR_HSTROKE * expand
            else:
                print(("OMG its a bug! WW_CHAR_SEQ[%d]=%s " % (i, Xwin_crt.WW_CHAR_SEQ[i])))

            if mask & 1 << (6 - i):
                if toMove:
                    self._movePoint(last_x, last_y)
                    toMove = False
                # self._drawSmallVector(last_x, last_y, 4*(x - last_x), 4*(y - last_y))
                self._drawSegment(4 * (x - last_x), 4 * (y - last_y), scope)
            else:
                toMove = True
            last_x = x
            last_y = y

    """
        The light gun has a trigger switch for one-shot operation:
        Only the first pulse after display of a point is valid;
        more are to be disabled while the trigger switch is still on.

        As no pulses are transmitted before the switch is on,
        the first such pulse (after display of a point) sets a flag
        to disable more (of this light gun).

        This flag is reset once the switch is off more than 50msec (debouncing)
    """

    def getLightGuns(self):
        """
            returns 0 if no light gun detected, or set the (two) lower bits
        """

        # light gun signals are evaluated only if there was a point drawing
        if not self.wasPoint:
            return 0

        mask = 0
        
        # check if this is the first light gun pulse
        if not self.wasGunPulse1 and gpio.input(self.pin_isGun1) == 0:
            mask = 1
            self.wasGunPulse1 = True
            if DebugGun: print("first pulse, Gun 1: isGun1=%d, PushButton=%d" %
                    (gpio.input(self.pin_isGun1on), gpio.input(self.pin_isIntercept)))
        if not self.wasGunPulse2 and gpio.input(self.pin_isGun2) == 0:
            mask = mask | 2
            self.wasGunPulse2 = True
            if DebugGun: print("first pulse, Gun 2")

        if mask != 0:
            return mask

        # print("lg:", gpio.input(self.pin_isGun1on), gpio.input(self.pin_isGun2on))
        # debounce switch 1
        if gpio.input(self.pin_isGun1on) == 0:
            # while switch is on, restart timer
            self.gunTime1 = time.time()
        else:
            # switch must be off some time (debounce)
            delta = time.time() - self.gunTime1
            if delta > self.debounceGunTime:
                self.wasGunPulse1 = False

        # debounce switch 2
        if gpio.input(self.pin_isGun2on) == 0:
            # while switch is on, restart timer
            self.gunTime2 = time.time()
        else:
            # switch must be off some time (debounce)
            delta = time.time() - self.gunTime2
            if delta > self.debounceGunTime:
                self.wasGunPulse2 = False

        return 0

    def checkGun(self):
        if self.PCDebug:
            return(False)

        ret = False
        if self.getLightGuns():
            ret = True
        return ret

    # Return the state of the push button beside the light gun
    # Used in Air Defense to select Target or Interceptor
    # The pin is active low, return True if it's pushed
    def getGunPushButton(self):
        return (gpio.input(self.pin_isIntercept) == 0)


    # Return the state of the "stop" button on Rainer's board attached to Rasp Pi
    def getSimStopButton(self):
        if gpio is None:
            return False
        return(gpio.input(self.pin_isKey) == 0)


""" 
    OXO / noughts and crosses /  tic-tac-toe
    Random computer play
    Sep 2023 -- I broken this routine when changing to WW coordinates
"""
oxo_state = []
for i in range(1, 10): oxo_state.append(0)
oxo_state[4] = 2

def oxo_show(ana_scope):
    rc = -1
    oxo_rad = 0.15 * ana_scope.screen_max

    for k in range(0, 9):
        x = 0.5 * (-1 + k % 3) * ana_scope.screen_max
        y = 0.5 * (1 - k // 3) * ana_scope.screen_max
        state = oxo_state[k]
        if state == 0:  # free
            # need a point for the light gun
            ana_scope.drawPoint(x, y)
            if ana_scope.getLightGuns() == 1:  # check for Light Gun #1
                print("oxo light gun")
                oxo_state[k] = (oxo_state[k] + 1) % 3 
                return k
        if state == 2:
            print("circle(%d %d %d)" % (x, y, oxo_rad))
            ana_scope.drawCircle(x, y, oxo_rad)
        if state == 1:
            ana_scope.drawVector(x, y, oxo_rad, oxo_rad)
            ana_scope.drawVector(x, y, -oxo_rad, oxo_rad)
            ana_scope.drawVector(x, y, oxo_rad, -oxo_rad)
            ana_scope.drawVector(x, y, -oxo_rad, -oxo_rad)
    return -1


"""
    Bouncing ball 
    The ground line is either shown with points (mode = 1)
    or as a a (long) vector for each point (mode=2).
    Modified by guy for a number range of -1023 to +1023 as in Whirlwind 
"""
def show_bounce(ana_scope, mode):
    screen_max = ana_scope.screen_max
    gravi = 0.003 * screen_max
    ground = -0.5 * screen_max
    repel = -0.85  # reflection on ground with loss
    xstep = 0.007 * screen_max # advance in x direction
    xborder = 0.9 * screen_max # right border

    xpos = -xborder  # restart
    ypos = 0.5 * screen_max
    yspeed = 0.0

    while xpos < xborder:
        # compute speed
        yspeed += gravi

        # compute position
        ypos -= yspeed
        if ypos < ground:
            yspeed = yspeed * repel
            ypos = ground

        # advance x
        xpos += xstep

        # plot the point
        ana_scope.drawPoint(int(xpos), int(ypos))
        # plot the axes
        if (mode == 1):
            ana_scope.drawPoint(int(xpos), int(ground))
        else:
            # drawPoint(-xborder, ground)
            ana_scope.drawVector(int(-xborder), int(ground), int(2 * xborder), 0)
            ana_scope.drawVector(int(-xborder), int(ground), 0, int(0.5*screen_max - ground))

        if not ana_scope.PCDebug and gpio.input(ana_scope.pin_isKey) == 0:
            return



class XwinCrt:
    def __init__(self):
        self.win = None
        self.WW_CHAR_HSTROKE = 8  # should be 20.0 in 'expand'
        self.WW_CHAR_VSTROKE = 9  # should be 15.00
        # The Whirlwind CRT character generator uses a seven-segment format with a bit in a seven-bit
        # word to indicate each segment.  This list defines the sequence in which the bits are
        # converted into line segments
        self.WW_CHAR_SEQ = ("down", "right", "up", "left", "up", "right", "down")

def charset_show(ana_scope, xwin_crt):
    mask = 0x7f   #turn on all the segments
    expand = 4
    x = -100
    y = 0
    # print("m=0x%x" % mask)
    ana_scope.drawChar(x, y, mask, expand, xwin_crt)

    mask = 0x11   #turn on all the segments
    expand = 4
    x = 200
    y = 0
    # print("m=0x%x" % mask)
    ana_scope.drawChar(x, y, mask, expand, xwin_crt)

    pass


def main():
    host_os = os.getenv("OS")

    ana_scope = AnaScope(host_os, None)
    xwin_crt = XwinCrt()

    while True:
        # charset_show(ana_scope, xwin_crt)
        oxo_show(ana_scope)
        # show_bounce(ana_scope, 1)


if __name__ == "__main__":
    class LogClass:
        def __init__(self):
            pass

    class ConstantsClass:
        def __init__(self):
            SCOPE_MAIN = 1
            
    main()

