
# Copyright 2026 Guy C. Fedorkow
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#   The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# This module serves to control the behavior of the simulator in the HNF museum exhibit.
# The exhibit hardware presents a set of eight "radio buttons" belonging to the low digit of the
# Right Manual Intervention Register (RMIR).
# At rest, the display should cycle through a series of short 'teasers' to form the "Attract Screen".
# When an MIR button is pressed, the simulator should run the corresponding demo program.  It will
# stay with the demo program as long as there's user input (button presses, mouse clicks, light-gun
# hits) but after a timeout, it will revert to the Attract screen.
#
# This mode is triggered with the arg --HnfProgramDispatcher
# g fedorkow, Mar 6, 2026


import time
import os

class HnfDispatchProgramClass:
    def __init__(self, file_dir=None, file_name=None, timeout=0, next_index=0,
                 switch_args=None, MIR_switch_number=None ):
        self.file_dir = file_dir
        self.file_name = file_name
        self.timeout = timeout
        self.next_index = next_index
        self.switch_args = switch_args
        self.MIR_switch_number = MIR_switch_number


class HnfDispatcherClass:
    def __init__(self, cb):
        self.default_app_timeout = 10  # user inactivity timeout, measured in seconds
        self.default_attract_timeout = 7  # Attract Screen cycle timer, measured in seconds
        # This dispatch table defines which programs should run on the exhibit.
        # Entries 0-7 are bound to the eight least-significant MIR buttons on the HNF display
        # Entries 8 and beyond are automatically selected by stepping through the default displays

        # The first entry in the table is the directory in which the program is found, the second is
        # the core-file name
        self.dispatch_table = []
        self.dispatch_table.append(HnfDispatchProgramClass(
            "Bounce/Bounce-Tape-with-Hole", "bounce-no-velocity.acore", self.default_app_timeout, 8))   # 0
        self.dispatch_table.append(HnfDispatchProgramClass(
            "Bounce/BlinkenLights-Bounce", "bounce-control-panel.acore", self.default_app_timeout, 8))  # 1
        self.dispatch_table.append(HnfDispatchProgramClass(
            "Vibrating-String", "knob-v97-closed-end.acore", self.default_attract_timeout, 8))          # 2
        self.dispatch_table.append(HnfDispatchProgramClass(
            "NewCode/Rocket", "number-display-annotated.acore", self.default_app_timeout, 8))           # 3
        self.dispatch_table.append(HnfDispatchProgramClass(
            "Tic-Tac-Toe", "tic-tac-toe.acore", self.default_app_timeout, 8))                           # 4
        self.dispatch_table.append(HnfDispatchProgramClass(
            "Blackjack", "bjack.acore", self.default_app_timeout, 8))                                   # 5
        self.dispatch_table.append(HnfDispatchProgramClass(
            "Mad-Game", "mad-game-annotated.acore", self.default_app_timeout, 8))                       # 6
        self.dispatch_table.append(HnfDispatchProgramClass(
            "Track-While-Scan-D-Israel", "annotated-track-while-scan.acore", self.default_app_timeout, 8)) # 7

        # The remainder form a state machine to step through all the demo apps
        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 8
            "NewCode/IdleScreen", "idle-msg.acore", self.default_attract_timeout, 9,
                    switch_args=[["FlipFlopPreset02", "0"]], MIR_switch_number = 0))
        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 9
            "Vibrating-String", "knob-v97-closed-end.acore", self.default_attract_timeout, 10,
                    MIR_switch_number = 0))

        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 10
            "NewCode/IdleScreen", "idle-msg.acore", self.default_attract_timeout, 11,
                    switch_args=[["FlipFlopPreset02", "1"]], MIR_switch_number = 1))
        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 11
            "Bounce/Bounce-Tape-with-Hole", "bounce-no-velocity.acore",
                self.default_attract_timeout, 12, MIR_switch_number = 1))

        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 12
            "NewCode/IdleScreen", "idle-msg.acore", self.default_attract_timeout, 13,
                    switch_args=[["FlipFlopPreset02", "2"]], MIR_switch_number = 2))
        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 13
            "Bounce/BlinkenLights-Bounce", "bounce-control-panel.acore",
                    self.default_attract_timeout, 14, MIR_switch_number = 2))

        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 14
            "NewCode/IdleScreen", "idle-msg.acore", self.default_attract_timeout, 15,
                    switch_args=[["FlipFlopPreset02", "3"]], MIR_switch_number = 3))
        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 15
            "Blackjack", "bjack.acore", self.default_attract_timeout, 16,
                    MIR_switch_number = 3))

        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 16
            "NewCode/IdleScreen", "idle-msg.acore", self.default_attract_timeout, 17,
                    switch_args=[["FlipFlopPreset02", "4"]], MIR_switch_number = 4))
        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 17
            "Tic-Tac-Toe", "tic-tac-toe.acore", self.default_attract_timeout, 18,
                    MIR_switch_number = 4))

        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 18
            "NewCode/IdleScreen", "idle-msg.acore", self.default_attract_timeout, 19,
                    switch_args=[["FlipFlopPreset02", "5"]], MIR_switch_number = 5))
        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 19
            "NewCode/Rocket", "rocket.acore", self.default_attract_timeout, 20,
                    MIR_switch_number = 5))

        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 20
            "NewCode/IdleScreen", "idle-msg.acore", self.default_attract_timeout, 21,
                    switch_args=[["FlipFlopPreset02", "6"]], MIR_switch_number = 6))
        self.dispatch_table.append(HnfDispatchProgramClass(                                             # 21
            "Mad-Game", "mad-game-annotated.acore", self.default_attract_timeout, 8,
                    MIR_switch_number = 6))



        self.default_dispatch = 8  # where to start the default screen
        self.next_app_to_run = self.dispatch_table[0].next_index   # what to run when the timeout times out
        self.last_dispatcher_press = self.default_dispatch
        self.stop_at_time = time.time() + self.default_attract_timeout
        # cache the length of the timeout allowed for the current program; set when the program is dispatched
        self.running_time = 0

        root = os.getenv("WWROOT")
        # root = "/home/guyfe/WW/GitHub"
        # root = "c:/Users/guyfe/Documents/guy/History-of-Computing/Whirlwind/GitHub"
        if root:
            self.code_root = root + "/Code-Samples/"
        else:
            cb.log.fatal("Please set env var WWROOT")

    def reset_inactivity_timer(self):
        if self.stop_at_time:
            self.stop_at_time = time.time() + self.running_time  # use this to extend the Inactivity timer

    def test_for_mir_change(self, cb):
        change = False
        if (self.stop_at_time):
            now = time.time()
            if now > self.stop_at_time:
                t1 = now - self.stop_at_time
                change = True
                cb.log.info(" Inactivity Timeout"  )
                #  If the next_app has a MIR Switch Value, write it to the LMIR
                if self.dispatch_table[self.next_app_to_run].MIR_switch_number is not None:
                    cb.panel.write_register("LMIR",
                            self.dispatch_table[self.next_app_to_run].MIR_switch_number, set_from_dispatcher=True)
                self.last_dispatcher_press = self.next_app_to_run

        if (change == False):
            # if current_switch_setting != self.last_dispatcher_press:
            if cb.panel.test_for_MIR_button_press():
                current_switch_setting = cb.panel.read_register("LMIR") & 0o7
                cb.panel.write_register("LMIR", current_switch_setting, set_from_dispatcher=True)
                change = True
                cb.log.info(" test_for_change: LeftInterventionReg = %d" % current_switch_setting)
                self.last_dispatcher_press = current_switch_setting
        return(change)

    def dispatch_to_core(self, cb):
        cb.sim_state = cb.SIM_STATE_READIN

        press = self.last_dispatcher_press
        if press >= len(self.dispatch_table):
            cb.log.warn(" Dispatcher Button Press %d is out of range" % press)
            press = 0

        dt = self.dispatch_table[press]
        dir = dt.file_dir
        filename = dt.file_name
        running_time = dt.timeout
        next_app_to_run = dt.next_index

        dir = self.code_root + dir
        self.running_time = running_time
        self.next_app_to_run = next_app_to_run
        print("Dispatcher ReadIn Directory and Filename: %s  %s" % (dir, filename))
        os.chdir(dir)
        cb.CoreFileName = filename
        if running_time:
            self.stop_at_time = time.time() + running_time  # use this to implement the Inactivity timer
        else:
            self.stop_at_time = 0
        return

    def apply_switch_presets(self, cpu):
        press = self.last_dispatcher_press
        if self.dispatch_table[press].switch_args:
            for sw in self.dispatch_table[press].switch_args:
                (sw_name, sw_val) = sw
                print("XXX Override switch %s to val 0o%s" % (sw_name, sw_val))
                cpu.cpu_switches.parse_switch_directive([sw_name, sw_val])
