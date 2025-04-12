#!/usr/bin/env python3
# vi: ts=4
""" Select a code to return to shell

    May be used for a simple menu control by numbers
    
    The code is entered by the four switches on the tap boards.
    If the push button is pressed, this programmed terminates
    with the code selected. 
    
    The code can also be set with the lightgun selecting one of 16 points.
    In normal mode, the programme immediately returns with the code selected.
    In debug mode, the corresponding LEDs are activated and the push button terminates.
    
    Debug mode is switched with the push button in mode 0.
                                                    
                
    Result is the bitwise or of the code selected by the lightgun and/or the keys.

    original code by Rainer Glaschick
"""

# 
import sys
import time
import vecIFbase as base

def drawNumber(x, y, num):
    base.drawCharacter(x, y, base.digits[num // 8], enlarge=8.0)   # changed to Octal by guy to line up with MIR activation
    base.drawCharacter(x+0.1, y, base.digits[num % 8], enlarge=8.0)
    
# show the menu, set LEDs and show the value on top
def do_show() :
    was_gun = False
    # draw pattern for light gun and set LEDs
    for i in range(0,16):
        x = i % 4
        y = int(i / 4)
        x = -0.6 + x * 0.4
        y = -0.7 + y * 0.4
        drawNumber(x+0.05, y, i)
        base.drawPoint(x, y)
        if 0 < base.getLightGuns():
            was_gun = True
            for b in [1, 2, 3, 4]:
                m = 2**(b-1)
                base.setKey(b, i&m)
    # get LEDs
    res = base.getKeys()
    # show value on top
    drawNumber(0, 0.9, int(res/2))
    return res, was_gun
        
# main loop
def loop():
    res = 0
    mode = 0
    was_gun = False
    # update the LEDs
    while True:
        # update the LEDs
        res, was_gun  = do_show()
        # in normal mode, stop if light gun
        if mode == 0 and was_gun:
            break
        # in debug mode, use activation point
        if mode != 0:
            # activation point
            base.drawPoint(-0.05, 0.9)
            # check lightgun (last dot drawn)
            if 0 < base.getLightGuns():
                   break
        # check for push button
#        print(res)
        if 1 == base.getKeys() % 2:
            if res < 2:
                mode = (mode + 1 ) % 2
                print("Debug Mode")
                # wait for PB off
                while 1 == base.getKeys() % 2:
                    time.sleep(0.1)
            else:
                break;
    # loop end, clear LEDs
    for b in [1, 2, 3, 4]:
        base.setKey(b, 0)
    # wait until PB is released		
    while 1 == base.getKeys() % 2:
        time.sleep(0.1)
    return int(res/2)

# run the main loop
try:
    base.vecIFopen()
    
     # wait for key release
    while True:
      for i in [1, 2, 3, 4]:
        base.setKey(i, 1)
        time.sleep(0.1)
      for i in [4, 3, 2, 1]:
        base.setKey(i, 0)
        time.sleep(0.1)
      if 0 == base.getKeys()%2:
        break;
        
    # do the menu and exit code returned
    res = loop()
    print("res=", res)
    sys.exit(res)
    
except KeyboardInterrupt:
    print("Cancelled")
    sys.exit(127)
finally:
    base.vecIFclose()
    print("Stopped.")
