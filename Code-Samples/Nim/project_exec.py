# project-specific python
# These project-specific files would usually contain functions called by .exec statements
# embedded in ww source code.

# Brian White & Guy Fedorkow
# Sept 13, 2024
# This helper script "automatically" switches switches and pushes buttons to get the Nim game
# initialized.  It's not hard to do, but does require ten steps before the first "real" move can
# be made
# The script optionally will go on to make "human" game moves, i.e., to run an entire game
#  Each 'move' in the Settings tables is accompanied by a 



import wwinfra


def breakp():
    print("breakpoint")

def project_exec_init():
    print("project exec init")

AutoConfigState = 0
SetupOnly = True

SetupSwitchSettings = [
    [(None, 0)],    # a 'no-op' state to make sure the we don't start before the game is Ready to Go...  Not sure this is necessary, but it reduces confusion...
    [("FF02Sw", 2), ("FF03Sw", 1)],  # remove up to seven pieces from one group per move; must alter 2 groups per move
    [("RMIR", 3)],	# initial A
    [("RMIR", 2)],	# initial B
    [("RMIR", 0)],	# initial C	
    [("RMIR", 0)],	# initial D
    [("RMIR", 0)],  # initial E
    [("RMIR", 0)],	# initial F
    [("RMIR", 0)],	# initial G
    [("RMIR", 0)],	# initial H
    ]

GamePlaySwitchSettings = [
    # human moves
    [("LMIR",0), ("RMIR", 2)],	# take 2 pieces from group A
    [("LMIR",1), ("RMIR", 1)],  # take 1 piece from group B
    # press Upper Activate Button to get machine to move
    [("ActivationReg0", 0o100000)],
    # next human move
     [("LMIR",7), ("RMIR", 2)],	# take 2 pieces from group H
     [("LMIR",6), ("RMIR", 1)],  # take 1 piece from group G
     # press UAB to get machine to move a second time
     [("ActivationReg0", 0o100000)],
     ]

switch_settings_by_state = SetupSwitchSettings
if not SetupOnly:
    switch_settings_by_state += GamePlaySwitchSettings



def auto_config_switches(cb):
    global AutoConfigState
    global switch_settings_by_state


    if AutoConfigState >= len(switch_settings_by_state):
        return

    setting_list = switch_settings_by_state[AutoConfigState]
    for setting in setting_list:
        if cb.panel and setting[0] is not None:
            cb.panel.write_register(setting[0], setting[1])
            cb.panel.write_register("ActivationReg0", 0o100000)

        print("auto_config state %d: Set Sw %s to val 0o%o" % (AutoConfigState, setting[0], setting[1]))

    AutoConfigState += 1
