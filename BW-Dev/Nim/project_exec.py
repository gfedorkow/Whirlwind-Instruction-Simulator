# project-specific python
# These project-specific files would usually contain functions called by .exec statements
# embedded in ww source code.


import wwinfra


def breakp():
    print("breakpoint")

def project_exec_init():
    print("project exec init")

AutoConfigState = 0

def auto_config_switches(cb):
    global AutoConfigState

    switch_settings_by_state = [
        [(None, 0)],
        [("FF02Sw", 4), ("FF03Sw", 5)],  # remove up to 4 pieces from each group per move; can alter up to 5 groups per move
        [("RMIR", 2)],	# initial A
        [("RMIR", 2)],	# initial B
        [("RMIR", 4)],	# initial C	
        [("RMIR", 4)],	# initial D
        [("RMIR", 5)],  # initial E
        [("RMIR", 5)],	# initial F
        [("RMIR", 7)],	# initial G
        [("RMIR", 7)],	# initial H
        # human moves
        [("LMIR",0), ("RMIR", 1)],	# take 1 piece from group A
        [("LMIR",1), ("RMIR", 0)],  # take 0 pieces from group B
        [("LMIR",2), ("RMIR", 0)],  # take 0 pieces from group C
        [("LMIR",3), ("RMIR", 0)],  # take 0 pieces from group D
        [("LMIR",4), ("RMIR", 0)],  # take 0 pieces from group E
        # press UAB to get machine to move
        [("ActivationReg0", 0o100000)],
        # next human move
#        [("LMIR",7), ("RMIR", 2)],	# take 2 pieces from group H
#        [("LMIR",6), ("RMIR", 1)],  # take 1 piece from group G
         # press UAB to get machine to move a second time
#        [("ActivationReg0", 0o100000)],
   ]

    if AutoConfigState >= len(switch_settings_by_state):
        return

    setting_list = switch_settings_by_state[AutoConfigState]
    for setting in setting_list:
        if cb.panel and setting[0] is not None:
            cb.panel.write_register(setting[0], setting[1])
            cb.panel.write_register("ActivationReg0", 0o100000)

        print("auto_config state %d: Set Sw %s to val 0o%o" % (AutoConfigState, setting[0], setting[1]))

    AutoConfigState += 1
