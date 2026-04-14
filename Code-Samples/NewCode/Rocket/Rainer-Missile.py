

"""
  Simple ballistic Rocket launch
  without air resistance
"""
def do_rocket(mode) :
    # gravitation 
    grav = 0.003
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
    accel = 0.005
    # 
    burn = 0.05
    
    # upon launch, set inital speeds
    xspeed = 0.01 * math.cos(math.radians(launchdir))
    yspeed = 0.01 * math.sin(math.radians(launchdir))

    
    # main loop: accelerate while fuel, show fuel and speed
    while ypos >= -0.1 and ypos < 1.0 and xpos < 1.0 :
        speed = math.sqrt(xspeed*xspeed + yspeed*yspeed)
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
        drawPoint(xpos, ypos)
        drawVector(-1.0, 0.0, 1.0, 0.0)
        drawCharacter(0.0, -0.8, digits[mode])

        # show fuel as bar at the left side
        if fuel > 0.0:
            drawVector(-0.99, 0.0, -0.99, fuel)
        # drawPoint(-0.99, fuel)   # show end point
        
        
        # mode 0 and 1: 
        if mode == 0 or mode == 1 :
            # show velocity
            drawVector(0.99, 0.0, 0.99, speed*10.0)
            #drawPoint(0.99, 0.0 + speed*10.0)

        fueli = int(fuel*100)
        speedi = int(speed*1000)
        
        # mode 1 and 2:
        if mode == 1 or mode == 2 :
           drawCharacter(-0.9, -0.3, digits[fueli // 10])
           drawCharacter(-0.8, -0.3, digits[fueli % 10])
           drawCharacter(0.8, -0.3, digits[speedi // 10])
           drawCharacter(0.9, -0.3, digits[speedi % 10])
         

        # mode 2: speed vector 
        if mode == 2 :
            drawVector(xpos, ypos, xpos + 8*xspeed, ypos + 8*yspeed)          
        
        if gpio.input(pin_isKey) == 0:
            return


