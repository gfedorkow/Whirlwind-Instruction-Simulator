#!/usr/bin/env python3
# vi: ts=4
""" TIC TAC TOE game for WWI
    
    Simple version with one display and light gun
    
    
    A 3x3 grid of points, crosses and circles is display.
    If a point is hit by any light gun, 
    it is changed to X  or O, depending on the player's number.
    A point is shown in the bottom middle to restart at any time.
    
    A small X or O is displayed in the upper left resp. right corner
    indicating the player to draw.
    A score counter (number of wins) is shown nearby.
    
    If a row, column or diagonal of the same signs is found,
    the game is over:
    - score count is incremented
    - only restart point is selectable
    
    If the round is a draw, no points except the restart point will show
    
    To reset the score, restart the programme.
    
    The Q button (on interface and each tap board) restarts is presssed short (<0.3s),
    terminates else
    
"""

# 
import math
import random
import time
import vecIFbase as base

def drawNumber(x, y, num):
    base.drawCharacter(x, y, base.digits[num // 10])
    base.drawCharacter(x+0.1, y, base.digits[num % 10])

oxo_state = [0, 0, 0, 0, 0, 0, 0, 0, 0]
 
oxo_rad = 0.10

winner = 0
player = 1
wincount = [0, 0]
        
 
def drawCross(x, y, oxo_rad):
    base.drawVector(x, y, x+oxo_rad, y+oxo_rad)
    base.drawVector(x, y, x+oxo_rad, y-oxo_rad)
    base.drawVector(x, y, x-oxo_rad, y+oxo_rad)
    base.drawVector(x, y, x-oxo_rad, y-oxo_rad)


def oxo_show(player):
    """ show the situation
        if player's lightgun hits, return state index (0..8)
        if he hits the restart point, return -2
        otherwise return -1
    """	
    global winner
    # show the situation
    for i in range(0, 9):
        x = 0.5 * (-1 + i % 3)
        y = 0.5 * (1 - i // 3)
        state = oxo_state[i]
        if state == 0 and winner == 0:  # free
            # need a point for the light gun
            base.setOutLine(player)
            base.drawPoint(x, y)
            base.setOutLine(3)
            # if player == base.getLightGuns():
            if 0 < base.getLightGuns():
                return i
        if state == 1:
            base.drawCircle(x, y , oxo_rad)
        if state == 2:
            drawCross(x, y, oxo_rad)

    # show score and next to draw
    if player == 1:
        base.drawCircle(-0.7, 0.8, oxo_rad/2)
    if player == 2:
        drawCross(0.7, 0.8, oxo_rad/2)
    
    # show scores ....
    drawNumber(-0.5, 0.8, wincount[0])
    drawNumber(0.4, 0.8, wincount[1])
        
    # restart button
    base.setOutLine(player)
    base.drawPoint(0.0, 0.8)
    base.setOutLine(3)
    # if player == base.getLightGuns():
    if 0 < base.getLightGuns():
        winner = 0
        player = 1 + player % 2
        return -2	
    return -1	
        

# all diagonals, rows and columns
checks = ( (4, 0, 8),
           (4, 1, 7),
           (4, 2, 6),
           (4, 3, 5),
           (0, 1, 2),
           (0, 3, 6),
           (8, 2, 5),
           (8, 6, 7))
            
def check(state):
    """ check if win or full
        if win, return index to checks table (0..8)
        if full, return -2
        otherwise -1
    """
        
    # check diagonals, rows and columns via check table
    for i in range(0, len(checks)):
        cks  = checks[i]
        x = cks[0]
        v = state[x]
        if v == 0: continue
        y = cks[1]
        w = state[y]
        if v != w: continue
        y = cks[2]
        w = state[y]
        if v != w: continue
        # found three in a row, column or diagonal
        return i
    
    # check if full
    for i in range(0, 9) :
        if state[i] == 0 :
            return -1
    # full
    return -2
    
def do_oxo() :
    global player, winner
    # clear pattern and scores
    for i in range(0, 9):
        oxo_state[i] = 0
    wincount[0] = 0
    wincount[1] = 0
        
    # one round
    while 0 == base.getKeys() & 1:   	# until abort
        hit = oxo_show(player)
        if hit == -2:		# restart
            winner = 0
            player = 1 + player % 2
            for i in range(0, 9):
                oxo_state[i] = 0
            continue
        if hit >= 0:
            oxo_state[hit] = player
            ck = check(oxo_state)
            if ck == -2:     # full, draw
                continue	 		
            if ck >= 0:		# player wins
                wincount[player-1] += 1
                winner = player
                print("wins:", winner)
                continue
            player = 1 + player % 2
         
    return 0

def loop():
    while 0 == (base.getKeys() % 2):
        print(base.getKeys())
        do_oxo()
        # short keypress restarts, long stops
        time.sleep(0.3)
        if 1 == (base.getKeys() % 2):
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
