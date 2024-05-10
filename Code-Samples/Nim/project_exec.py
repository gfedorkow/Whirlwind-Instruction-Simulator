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
        [("FF02Sw", 1), ("FF03Sw", 1)],  # remove up to [seven] pieces from one group per move
        [("RMIR", 4)],
        [("RMIR", 3)],
        [("RMIR", 2)],
        [("RMIR", 1)],
        [("RMIR", 0)],
        [("RMIR", 0)],
        [("RMIR", 0)],
        [("RMIR", 1)],
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
