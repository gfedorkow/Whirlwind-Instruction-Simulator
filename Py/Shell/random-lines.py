

# Draw a grid of boxes using short vectors.
# But draw the vectors in random order

# G Fedorkow, May 26, 2024

import sys
import time
import vecIFbase as base

class DisplayPoints():
    def __init__(self):
        self.dimension = 10
        
        self.list = []
        for x in range(0, self.dimension):
            for y in range(0, self.dimension):
                self.list.append([x, y])

    def build_display_list(self, points):
        self.list = []

        return self.list


    def show_display_list(self, disp_list):
        return

def main():
    try:
        base.VecIFopen()
    except:
        print("can't open the Rainer-Board")
        sys.exit()

    dpc = DisplayPoints()
    dp = dpc.list

    for p in dp:
        print("pt: %d %d" % (p[0], p[1]))

main()
