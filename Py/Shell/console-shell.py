

import time
import subprocess

#WW_Root = "/cygdrive/c/Users/guyfe/Documents/guy/History-of-Computing/Whirlwind/GitHub"
#Sim_Path = WW_Root + "/Py/Sim/wwsim.py"
WW_Root = "c:\\Users\\guyfe\\Documents\\guy\\History-of-Computing\\Whirlwind\\GitHub"
Sim_Path = WW_Root + "\\Py/Sim/wwsim.py"


class WwAppClass:
    def __init__(self, title, dir="none", exec=None, is_WW=True, args=[]):
        self.title = title
        self.directory = dir
        self.is_WW = is_WW
        self.executable_name = exec
        self.args = args

Programs = [
    WwAppClass("Exit" ),  # Assume this is always the first option, i.e., index 0
    WwAppClass("TicTacToe vs WW", dir="Code-Samples/Tic-Tac-Toe", exec="tic-tac-toe.acore", is_WW=True, args=["-q", "-p", "--Quick"]),
    WwAppClass("TicTacToe Two Person", exec="py", is_WW=False),
    WwAppClass("Vibrating String", dir="Code-Samples\\Vibrating-String", exec="v97.acore", is_WW=True, args=["-q", "-p", "--Quick"]),
]


def exec_program(pgm):
    if pgm.is_WW:
        acore_dir = WW_Root + '\\' + pgm.directory
        sim_cmd = [Sim_Path, pgm.executable_name] + pgm.args
        subprocess.run(["python"] + sim_cmd, shell=True, cwd=acore_dir)
    else:
        print("can't run py cmd %s yet" % pgm.executable_name)


def main():
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
            exec_program(Programs[choice])
main()
