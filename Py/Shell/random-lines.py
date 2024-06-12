

# Draw a grid of boxes using short vectors.
# But draw the vectors in random order

# G Fedorkow, May 26, 2024
RasPi = False

import sys
import time
import random

if RasPi:
    import vecIFbase as base

# Take one entry out of a list
# I'm sure there's a builtin function for this, but there's no wifi to look it up!
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


    def build_display_list(self, points):
        self.list = []
        return self.list


    def show_display_list(self, disp_list):
        return

def main():
    global RasPi
    if RasPi:
        try:
            base.VecIFopen()
        except:
            print("can't open the Rainer-Board")
            sys.exit()

    dpc = DisplayPoints(4)
    dpc.scramble_display_list()
    dp = dpc.scrambled_list

    for p in dp:
        print("pt: %d %d %s" % (p[0], p[1], p[2]))

main()
