#!/usr/bin/env python
# vi: ts=4

# Demo Program Dispatcher for microWhirlwind
# guy fedorkow, Apr 12, 2025


import subprocess
import sys
import os

#WW_Root = "/cygdrive/c/Users/guyfe/Documents/guy/History-of-Computing/Whirlwind/GitHub"
#Sim_Path = WW_Root + "/Py/Sim/wwsim.py"
WW_Root_Win = "c:\\Users\\guyfe\\Documents\\guy\\History-of-Computing\\Whirlwind\\GitHub"
WW_Root_Linux = "/home/guyfe/History-of-Computing/Whirlwind/GitHub"
WW_Root = None
Sim_Path = "/Py/Sim/wwsim.py"
default_args = ["-q", "-p", "--Quick"]

UseRMIR = True

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
    WwAppClass("TicTacToe Two Person", dir="Py/Shell", exec="tictactoe.py", is_WW=False),
    WwAppClass("TicTacToe vs WW", dir="Code-Samples/Tic-Tac-Toe", exec="tic-tac-toe.acore", is_WW=True),
    WwAppClass("R-196 Bounce", dir="Code-Samples/Bounce/BlinkenLights-Bounce", exec="bounce-control-panel.acore", is_WW=True),
    WwAppClass("Bounce w/ Hole", dir="Code-Samples/Bounce/Bounce-Tape-with-Hole", exec="fb131-0-2690_bounce-annotated.acore", is_WW=True),
    WwAppClass("Mad Game", dir="Code-Samples/Mad-Game", exec="mad-game.acore", is_WW=True),
    WwAppClass("Black-Jack", dir="Code-Samples/Blackjack", exec="bjack.acore", is_WW=True),
    WwAppClass("CRT Test", dir="Code-Samples/Diags", exec="crt-test-68_001_fbl00-0-50.tcore", is_WW=True),
    WwAppClass("Vibrating String, fixed ends", dir="Code-Samples/Vibrating-String", exec="v97-closed-end.acore", is_WW=True, args=["--NoWarn"]),
    WwAppClass("Vibrating String, open end", dir="Code-Samples/Vibrating-String", exec="v204-open-end.acore", is_WW=True, args=["--NoWarn"]),
    WwAppClass("Nim", dir="Code-Samples/Nim", exec="nim-fb.acore", is_WW=True, args=["--CrtFade", "3"]),
    WwAppClass("Number Display", dir="Code-Samples/Number-Display", exec="number-display-annotated.acore", is_WW=True),
    WwAppClass("Air Defense", dir="Code-Samples/Track-While-Scan-D-Israel", exec="annotated-track-while-scan.acore", 
               is_WW=True, args=["-D", "-r", "--CrtF", "5", "--NoToggl", "--NoAlarmStop"]),
    WwAppClass("Vector Clock", dir="Code-Samples/Vector-Clock", exec="vector-clock.acore", is_WW=True),
    WwAppClass("Lorenz Attractor", dir="Code-Samples/Lorenz", exec="lorenz.acore", is_WW=True),
]


def exec_program(pgm, args):
    global Sim_Path
    exec_dir = WW_Root + '/' + pgm.directory
    sim_path = WW_Root + Sim_Path
    if pgm.is_WW:
        sim_cmd = [sim_path, pgm.executable_name] + args + pgm.args
        # subprocess.run(["ls -l"], shell=True, cwd=exec_dir)
        ret = subprocess.run(["python"] + sim_cmd, shell=False, cwd=exec_dir)
    else:
        sim_cmd = [pgm.executable_name] + args + pgm.args
        ret = subprocess.run(["python"] + sim_cmd, shell=False, cwd=exec_dir)
    print("return code=", ret.returncode)

def main():
    global WW_Root
    global Sim_Path
    args = sys.argv[1:]
    if len(args) == 0:
        args = default_args
    if len(args) > 1:    # if the first arg on the cmd line is '+' then tack the rest of the args onto the end of the default arg string.
        if args[0] == '+':
            args = default_args + args[1:0]
    host_os = os.getenv("OS")
    if host_os == "Windows_NT":
        WW_Root = WW_Root_Win
    else:
        WW_Root = WW_Root_Linux

    print("args=", args, "  os=", host_os)
    while True:
        # print('\033[2J') #clear_screen
        print("\n\n\n")
        for index in range(0, len(Programs)):
            print("%2o: %s" % (index, Programs[index].title))
        choice = 0
        if UseRMIR:
            print("\nEnter a number from the list in RMIR, then press Upper Activate")
            exec_dir = WW_Root + '/' + "Py/Shell"
            sim_path = WW_Root + Sim_Path
            sim_cmd = [sim_path, "mir-pgm-selector.acore"] + ["-q", "-p", "--QuickStart"]
            ret = subprocess.run(["python"] + sim_cmd, shell=False, cwd=exec_dir)
            choice = ret.returncode
            print("selection choice = 0o%o" % choice)
        else:
            user_string = input("Type a number: ")
            if user_string == 'q' or user_string == 'Q':
                user_string = '0'
            try:
                choice = int(user_string, 8)
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
