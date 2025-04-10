


import subprocess
import sys

#WW_Root = "/cygdrive/c/Users/guyfe/Documents/guy/History-of-Computing/Whirlwind/GitHub"
#Sim_Path = WW_Root + "/Py/Sim/wwsim.py"
# WW_Root = "c:\\Users\\guyfe\\Documents\\guy\\History-of-Computing\\Whirlwind\\GitHub"
WW_Root = "/home/guyfe/History-of-Computing/Whirlwind/GitHub"
Sim_Path = WW_Root + "/Py/Sim/wwsim.py"
default_args = ["-q", "-p", "--Quick"]


class WwAppClass:
    def __init__(self, title, dir="none", exec=None, is_WW=True, args=[]):
        self.title = title
        self.directory = dir
        self.is_WW = is_WW
        self.executable_name = exec
        self.args = args

Programs = [
    WwAppClass("Exit" ),  # Assume this is always the first option, i.e., index 0, so I can make "q" also work
    WwAppClass("Random-Raster", dir="Py/Common", exec="random-lines.py", is_WW=False),
    WwAppClass("TicTacToe Two Person", exec="py", is_WW=False),
    WwAppClass("TicTacToe vs WW", dir="Code-Samples/Tic-Tac-Toe", exec="tic-tac-toe.acore", is_WW=True),
    WwAppClass("R-196 Bounce", dir="Code-Samples/Bounce/BlinkenLights-Bounce", exec="bounce-control-panel.acore", is_WW=True),
    WwAppClass("Bounce w/ Hole", dir="Code-Samples/Bounce/Bounce-Tape-with-Hole", exec="fb131-0-2690_bounce-annotated.acore", is_WW=True),
    WwAppClass("Mad Game", dir="Code-Samples/Mad-Game", exec="mad-game.acore", is_WW=True),
    WwAppClass("Black-Jack", dir="Code-Samples/Blackjack", exec="bjack.acore", is_WW=True),
    WwAppClass("CRT Test", dir="Code-Samples/Diags", exec="crt-test-68_001_fbl00-0-50.tcore", is_WW=True),
    WwAppClass("Vibrating String", dir="Code-Samples/Vibrating-String", exec="v97.acore", is_WW=True),
    WwAppClass("Nim", dir="Code-Samples/Nim", exec="nim-fb.acore", is_WW=True),
    WwAppClass("Number Display", dir="Code-Samples/Number-Display", exec="number-display-annotated.acore", is_WW=True),
    WwAppClass("Air Defense", dir="Code-Samples/Track-While-Scan-D-Israel", exec="annotated-track-while-scan.acore", 
               is_WW=True, args=["-D", "-r", "--CrtF 5", "--NoToggl", "--NoAlarmStop"]),
    WwAppClass("Vector Clock", dir="Code-Samples/Vector-Clock", exec="vector-clock.acore", is_WW=True),
    WwAppClass("Lorenz Attractor", dir="Code-Samples/Lorenz", exec="lorenz.acore", is_WW=True),
]


def exec_program(pgm, args):
    exec_dir = WW_Root + '/' + pgm.directory
    if pgm.is_WW:
        sim_cmd = [Sim_Path, pgm.executable_name] + args + pgm.args
        print("exec: ", ["python"] + sim_cmd)
        # subprocess.run(["ls -l"], shell=True, cwd=exec_dir)
        subprocess.run(["python"] + sim_cmd, shell=False, cwd=exec_dir)
    else:
        sim_cmd = [pgm.executable_name] + args + pgm.args
        subprocess.run(["python"] + sim_cmd, shell=True, cwd=exec_dir)


def main():
    args = sys.argv[1:]
    if len(args) == 0:
        args = default_args
    print("args=", args)
    while True:
        # print('\033[2J') #clear_screen
        print("\n\n\n")
        for index in range(0, len(Programs)):
            print("%2d: %s" % (index, Programs[index].title))
        choice = 0
        user_string = input("Type a number: ")
        if user_string == 'q' or user_string == 'Q':
            user_string = '0'
        try:
            choice = int(user_string)
        except ValueError:
            print("\nEnter a number please")
            continue
        if choice == 0:
            return
        elif choice >= len(Programs):
            print("\nEnter a number from the list above please")
            continue
        else:
            exec_program(Programs[choice], args)
main()
