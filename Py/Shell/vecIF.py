#!/usr/bin/env python3
# vi: ts=4
""" Stand-alone test for the WWI vector interface
    Shows some tests, switches to next by key
    Last one uses light pen
    
    uses floating point numbers for convenience,
    not (yet) fixed point fractions as in WWI
    
"""

# 
import math
import random
import time
import vecIFbase as base

""" Give navigation point bottom left and right
    need to wait until gun is no longer active
"""
def navi():
    base.drawPoint(-0.9, -0.8)
    if base.getLightGuns():
        # time.sleep(0.5)
        return -1
        
    base.drawPoint(0.9, -0.8)
    if base.getLightGuns():
        # time.sleep(0.5)
        return +1
    return 0
    

"""
    Bouncing ball 
    The ground line is either shown with points (mode = 1)
    or as a a (long) vector for each point (mode=2)
    Not yet with hole..
"""
def show_bounce(mode) :
  
    gravi = 0.003
    ground = -0.5
    repel = -0.85       # reflection on ground with loss 
    xstep = 0.007       # advance in x direction
    xborder = 0.9       # right border 

    xpos = -xborder        # restart
    ypos = 0.5
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
        base.drawPoint(xpos, ypos)
        # plot the axes
        if (mode == 2):
            base.drawVector(-xborder, ground, xborder, ground)
            base.drawVector(-xborder, 0.5, -xborder, ground)
        
        rc = navi()
        if (rc != 0): return rc
 
        # check for stop
        if base.getKeys() > 0:
            #time.sleep(0.2)
            return 0;
    if (mode == 1):
        # draw a chain of dots
        for i in range(0,100):
             base.drawPoint(xborder*(-1+i/50), ground)
    return 0
        
""" 
    OXO / noughts and crosses /  tic-tac-toe
    Radom computer play
"""

oxo_state = []
for i in range(1,10): oxo_state.append(0)

oxo_rad = 0.15

def oxo_show():
    rc = -1
    for i in range(0, 9):
        x = 0.5 * (-1 + i % 3)
        y = 0.5 * (1 - i // 3)
        state = oxo_state[i]
        if state == 0:  # free
                # need a point for the light gun
                base.drawPoint(x, y)
                if base.getLightGuns():
                    return i
        if state == 1:
                base.drawCircle(x, y , oxo_rad)
        if state == 2:
                base.drawVector(x, y, x+oxo_rad, y+oxo_rad)
                base.drawVector(x, y, x+oxo_rad, y-oxo_rad)
                base.drawVector(x, y, x-oxo_rad, y+oxo_rad)
                base.drawVector(x, y, x-oxo_rad, y-oxo_rad)
    return -1


"""  
    play oxo
"""
def do_oxo() :
    # start pattern
    for i in range(0, 9):
        oxo_state[i] = random.randrange(3)
        
    while base.getKeys() == 0:
        hit = oxo_show()
        if hit >= 0:
            oxo_state[hit] = random.randrange(1, 3)
        # clear if full
        isfull = True
        for i in range(9) : 
            if oxo_state[i] == 0 :
                isfull = False
                break
        if (isfull) :
            for i in range(9):
                oxo_state[i] = 0
            oxo_show()
            # time.sleep(0.5)
         
        rc = navi()
        if (rc != 0): return rc
    return 0


"""
  Simple ballistic Rocket launch
  without air resistance
"""
def do_rocket(mode) :
    # gravitation 
    grav = 0.0028
    # launch angle in degrees
    launchdir = 87.0
    # fuel left
    fuel = 1.0
    # rocket speed
    xspeed = 0.0
    yspeed = 0.0
    # rocket position
    xpos = -0.9
    ypos = 0.0
    # acceleration per fuel unit
    accel = 0.004
    # 
    burn = 0.04
    
    # upon launch, set inital speeds
    xspeed = 0.01 * math.cos(math.radians(launchdir))
    yspeed = 0.01 * math.sin(math.radians(launchdir))

    
    # main loop: accelerate while fuel, show fuel and speed
    cnt = 99
    while ypos >= -0.1 and ypos < 1.0 and xpos < 1.0 :
        speed = math.sqrt(xspeed*xspeed + yspeed*yspeed)
        cnt += 1
        if cnt > 12:
          cnt = 0
          # accelerate if still fuel
          if fuel > 0.0 :
              # no need to calculate flight angle, just the speed
              xspeed += xspeed / speed * accel
              yspeed += yspeed / speed * accel
              fuel -= burn
        
          # gavitation is always in y direction
          yspeed -= grav
 
          # integrate to positions
          xpos += xspeed
          ypos += yspeed
        
        # always actual point and base line
        base.drawPoint(xpos, ypos)
        base.drawVector(-1.0, 0.0, 1.0, 0.0)
        #base.drawCharacter(0.0, -0.8, base.digits[mode])

        # show fuel as bar at the left side
        if fuel > 0.0:
            base.drawVector(-0.99, 0.0, -0.99, fuel)
        # base.drawPoint(-0.99, fuel)   # show end point
 
        
        # mode 0 and 1: 
        if mode == 0 or mode == 1 :
            # show velocity
            base.drawVector(0.99, 0.0, 0.99, speed*10.0)
            #base.drawPoint(0.99, 0.0 + speed*10.0)

        fueli = int(fuel*100)
        speedi = int(speed*1000)
 
        # mode 1 and 2: show fuel, skip to reduce visible luminance
        if cnt == 1 and (mode == 1 or mode == 2) :
           base.drawCharacter(-0.9, -0.3, base.digits[fueli // 10])
           base.drawCharacter(-0.8, -0.3, base.digits[fueli % 10])
           base.drawCharacter(0.8, -0.3, base.digits[speedi // 10])
           base.drawCharacter(0.9, -0.3, base.digits[speedi % 10])
         

        # mode 2: speed vector 
        if mode == 2 :
            base.drawVector(xpos, ypos, xpos + 4*xspeed, ypos + 4*yspeed)
        
        if base.getKeys() > 0:
            #time.sleep(0.2)
            return 0

        rc = navi()
        if (rc != 0): return rc
    return 0


def show_circles():
    base.drawPoint(0, 0)
    base.drawCircle(0, 0, 0.9)
    base.drawCircle(0.5, 0.5, 0.2)
    #base.drawCircle(0.5, 0.5, 0.6)
    #base.drawVector(1.0, 1.0, 1.0, -1.0)
    #base.drawVector(1.0, 1.0, -1.0, 1.0)
    #base.drawVector(-1.0, -1.0, 1.0, -1.0)
    #base.drawVector(-1.0, -1.0,  -1.0, 1.0)
    rc = navi()
    return rc
    


def fig1():
    #base.drawPoint(1.0, 1.0)
    base.drawVector(1.0, 1.0, -1.0, -1.0)
    base.drawVector(1.0, -1.0, -1.0, 1.0)
    #base.drawPoint(-1.0, -1.0)
    base.drawVector(0.0, -1.0, 0.0, 1.0)
    base.drawVector(-1.0, 0.0, 1.0, 0.0)
    #base.drawPoint(-0.5, 0.0);
    #base.drawPoint(0.0, 0.2);
    base.drawVector(-0.2, 0.0, 0.0, 0.2)
    base.drawVector(0.2, 0.0, 0.0, 0.2)
    base.drawVector(-0.5, 0.0, 0.0, -0.5)
    base.drawVector(0.5, 0.0, 0.0, -0.5)    
    rc = navi()
    return rc
 
def loop():
    mode = 5
    omode = mode
    while True:
        #base.drawCharacter(0, 0, base.digits[8])
        #base.drawCharacter(-0.5, 0, base.digits[1])
        #continue;
        if mode > 9:
             mode = 1
        if mode < 1:
             mode = 9
        if omode != mode:
             print("Mode: " + str(mode));
             omode = mode
 
        if mode == 1:
            mode += 1 # fig1()
        if mode == 2:
            mode += 1 # show_circles()
        if mode == 3:
            mode += 1 # show_bounce(1)
        if mode == 4:
            mode += 1 # show_bounce(2)
        if mode == 5:
            for i in range(0,10):
                base.drawCharacter(-0.5 + i * 0.1, 0.0, base.digits[i])
            time.sleep(0.01)
            rc = navi()
            mode += rc
 
        if mode == 6:
            mode += do_rocket(0)
        if mode == 7:
            mode += do_rocket(1)
        if mode == 8:
            mode += do_rocket(2)
        if mode == 9:
            mode += 1 # do_oxo()
 
        if 1 == base.getKeys() % 2 :
            mode += 1
            print(mode);
            time.sleep(1.0)
            if base.getKeys() > 0:
                return
        

# run the main loop
try:
    base.vecIFopen()
    loop()
except KeyboardInterrupt:
    print("Cancelled")
finally:
    base.vecIFclose()
    print("Stopped.")
 
