#!/home/guyfe/ww-venv/bin/python

# ******************************************************************** #
# Interface to wwsim and Diagnostic for MicroWhirlwind hardware
#
# g fedorkow, Feb 2025

RasPi = True
try:
    import RPi.GPIO as gpio
    # we'll import https://pypi.org/project/smbus2/
    import smbus2  # also contains i2c support
except ModuleNotFoundError:
#    print("no GPIO library found")
    import smbus_replacement as smbus2
    import gpio_replacement as gpio
#    gpio = gpio_replacement.gpioClass()
#    import msvcrt
    RasPi = False


import argparse
import blinkenlights
import control_panel
import time
import wwinfra

MwwPanelDebug = False    # turn on to see what's going on with the control panel code

IS31_1_ADDR_U1 = 0x74    # U1
IS31_1_ADDR_U5 = 0x75    # U5
IS31_1_ADDR_U2 = 0x77    # U2
TCA8414_0_ADDR = 0x34 # 34
TCA8414_1_ADDR = 0x3b #3B
pin_pwr_ctl = 19
pin_tca_reset = 26  # keyboard scanner reset pin; low for reset
pin_tca_interrupt  = 16

pin_gpio_LED1 = 5
pin_gpio_LED2 = 6
pin_gpio_LED3 = 20
pin_gpio_LED4 = 21
pin_gpio_isKey = 27


Verbose = False
Debug_I2C = False  # specific to low-level I2c
Debug = False

I2CBusTimeout = 0

def breakp():
    pass

class localCpuClass:
    def __init__(self):
        self._BReg = 0
        self._AC = 0o123    # Accumulator
        self._AReg = 2    # Address Register, used for subroutine return address
        self._SAM = 1   # Two-bit carry-out register; it's only legal values appear to be 1, 0, -1
                        # SAM is set by many instructions, but used only by ca cs and cm
        self.PC = 0o40  # Program Counter; default start address



# ==============================================


class PanelMicroWWClass:
    def __init__(self, cb, sim_state_machine_arg=None, left_init=0, right_init=0):

        cb.RasPi = RasPi

        self.log = cb.log
        self.sim_state_machine = sim_state_machine_arg
        self.micro_ww_module_present = True
        self.i2c_bus = None
        if MwwPanelDebug: self.log.info("I2C init: ")
        try:
            i2c_bus = I2C(1)
            bus = i2c_bus.bus
            gp_sw = gpio_switches(self.log)  # these are the switches and LEDs on Rainer's "Tap Board"
        except IOError:
            self.micro_ww_module_present = False
            self.log.warn("No MicroWhirlwind Panel I2C/gpio Found")
            return

        try:
            pwr_ctl = PwrCtlClass(self.log)
            pwr_ctl.pwr_on()
            time.sleep(0.3)

            self.pin_audio_click = 12  # audio pin
            gpio.setup(self.pin_audio_click, gpio.OUT)

            self.md = MappedRegisterDisplayClass(self.log, i2c_bus)  # pass in cb.log for printing log messages
            self.sw = MappedSwitchClass(self.log, i2c_bus, self.md)
            # I think there's only one set of lights that need to be initialized from CB
            # The rest come from the ReadIn operation
            if MwwPanelDebug: self.log.info("Preset D/F Scope Selector switches to %d" % cb.which_scope)
            self.md.set_scope_selector_leds(cb.which_scope)
        except IOError:
            self.micro_ww_module_present = False
            self.log.warn("Missing MicroWhirlwind Panel drivers")
            return

        self.local_state_change_buttons = ("Stop-on-Addr", "Stop-on-CK", "Stop-on-S1")


#        # the first element in the dict is the switch Read entry point, the second is the one to set the switches
#        self.dispatch = {"LMIR":[self.md.read_left_register, self.md.set_left_register],
#                    "RMIR": [self.md.read_right_register, self.md.set_right_register],
#                    "ActivationReg0": [self.activate_reg_read, self.activate_reg_write],
#                    "FF02": [self.md.read_ff2_register, self.md.write_ff2_register],
#                    "FF02Sw": [self.md.read_ff2_switch_register, self.md.set_ff2_switch_register],
#                    "FF03": [self.md.read_ff3_register, self.md.write_ff3_register],
#                    "FF03Sw": [self.md.read_ff3_switch_register, self.md.set_ff3_switch_register],
#                    }

    def check_buttons(self):
        button_press = self.sw.check_buttons()
        return button_press

    # def set_cpu_state_lamps(self, cb, sim_state, alarm_state):

    def update_panel(self, cb, bank, alarm_state=0, standalone=False, init_PC=None):
        cpu = cb.cpu
        mdr = cpu.cm.mem_data_reg
        if mdr is None:   # Python "core memory" can read as None; translate that to zero
            mdr = 0

        mar = cpu.cm.mem_addr_reg

        ff2 = cpu.cm.rd(2, skip_mar=True)   # 'skip_mar' says to _not_ update the MAR/PAR with this read
        ff3 = cpu.cm.rd(3, skip_mar=True)
        self.md.set_cpu_reg_display(cpu=cpu, mdr=mdr, mar=mar, mar_bank=0, ff2=ff2, ff3=ff3,
                                    run_state=cb.sim_state != cb.SIM_STATE_STOP, alarm_state=alarm_state)
        bn = self.check_buttons()
        if bn:
            if bn in self.local_state_change_buttons:
                self.local_state_change(bn)
            else:
                presets = self.md.read_preset_switch_leds()
                pc_preset = presets["pc"]
                self.sim_state_machine(bn, cb, pc_preset, set_scope_selector_leds=self.md.set_scope_selector_leds) # the third arg should be the PC Preset switch register

        if init_PC:
            self.write_register("PC", init_PC)

        if self.md.stop_on_addr_state:  # Test the Stop on Address button on the panel
            #  This is not a very efficient way to retrieve the PC Preset switch register
            cpu.stop_on_address = self.md.read_preset_switch_leds()["pc"]  # if activated, set the address for the cpu to watch
        else:
            cpu.stop_on_address = None  # otherwise, deactivate the Stop on PC function

        if gpio.input(pin_gpio_isKey) == 0:   #
            return False
        return True


   # read a register from the switches and lights panel.
    # It would normally be called with a string giving the name.  Inside the simulator
    # sometimes it's easier to find a number for the flip-flop registers
    def read_register(self, which_one):
        if type(which_one) is int:
            which_one = "FF%02oSw" % which_one

        ret = None
        match which_one:
            case "FF02Sw":
                presets = self.md.read_preset_switch_leds()
                ret = presets["ff2"]
            case "FF03Sw":
                presets = self.md.read_preset_switch_leds()
                ret = presets["ff3"]
            case "PC":  # This is actually the PC Preset switches/lights
                presets = self.md.read_preset_switch_leds()
                ret = presets["pc"]
            case "LMIR":
                ret = self.md.mir_state[0]
            case "RMIR":
                ret = self.md.mir_state[1]
            case "ActivationReg0":
                # internally, the two Activate bits are stored as Py Bits 0 & 1;  In WW, it's bits 15, 14
                ret = self.md.clear_activate_switch_leds() << 14
            case "CheckAlarmSpecial":
                ret = self.md.check_alarm_special_state
            case "StopOnS1":
                ret = self.md.stop_on_s1_state
            case "StopOnAddr":
                ret = self.md.stop_on_addr_state
            case _:
                self.log.warn("Panel.read_register: unknown register %s" % which_one)
                exit()
        return ret


    # write a register to the switches and lights panel.
    # It would normally be called with a string giving the name.  Inside the simulator
    # sometimes it's easier to find a number for the flip-flop registers
    def write_register(self, which_one, value):
        if type(which_one) is int:
            which_one = "FF%02o" % which_one

        if MwwPanelDebug: self.log.info("mWWPanelClass: write_register %s, val 0o%o" % (which_one, value))
        match which_one:
            case "FF02Sw":
                self.md.set_preset_switch_leds(ff2=value)
            case "FF03Sw":
                self.md.set_preset_switch_leds(ff3=value)
            case "FF05Sw":
                if MwwPanelDebug: self.log.info("ignore Set to preset %s" % which_one)
                return
            case "FF06Sw":
                if MwwPanelDebug: self.log.info("ignore Set to preset %s" % which_one)
                return
            case "FF010Sw":
                if MwwPanelDebug: self.log.info("ignore Set to preset %s" % which_one)
                return
            case "PC":  # this is actually the pc_preset LEDs
                self.md.set_preset_switch_leds(pc=value)
            case "LMIR":
                self.md.mir_state[0] = value
                self.md.set_mir_preset_switch_leds()
            case "RMIR":
                self.md.mir_state[1] = value
                self.md.set_mir_preset_switch_leds()
            case "ActivationReg0":
                # internally, the two Activate bits are stored as Py Bits 0 & 1;  In WW, it's bits 15, 14
                # The Write Activate function is only used by Python Automation, i.e., the simulator can't turn
                # on an Activate bit as a result of an instruction.
                self.md.set_activate_switch_leds(value >> 14)
            case "CheckAlarmSpecial":
                self.md.check_alarm_special_state = value
                self.md.update_exec_switch_leds()
            case "StopOnS1":
                self.md.stop_on_s1_state = value
                self.md.update_exec_switch_leds()
            case "StopOnAddr":
                self.md.stop_on_addr_state = value
                self.md.update_exec_switch_leds()
            case _:
                self.log.info("MicroWhirlwind panel doesn't have register %s" % which_one)



    def reset_ff_registers(self, function, log=None, info_str=''):

        # This call returns a dict with the state of various preset registers
        # The 'actual' state is read back from LED shadow registers, as the "toggle switch" state is stored
        # there, not in the switches!
        presets = self.md.read_preset_switch_leds()
        for sw in ("ff2", "ff3"):
            val = presets[sw]
            # print("copy 0o%o into %s" % (val, sw))
            addr = sw[2]   # 2 or 3
            function(int(addr), val)  # calls Coremem.write_ff_reg()
            if log:
                log.info(info_str % (addr, addr, val))

    def local_state_change(self,bn):
        match bn:
            case "Stop-on-Addr":
                self.md.stop_on_addr_state ^= 1
            case "Stop-on-CK":
                self.md.check_alarm_special_state ^= 1
            case "Stop-on-S1":
                self.md.stop_on_s1_state ^= 1
            case _:
                self.log.info("mWWPanel.local_state_change: unknown button %s" % bn)
        if MwwPanelDebug: self.log.info("local_state_change: stop-on-addr=%d, stop-on-ck=%d, stop-on-S1=%d" %
            (self.md.stop_on_addr_state, self.md.check_alarm_special_state, self.md.stop_on_s1_state))
        self.md.update_exec_switch_leds()

    def set_audio_click(self, acc):
        val = (acc & 0o4) != 0
        gpio.output(self.pin_audio_click, val)


# ==============================================================


# see https://stackoverflow.com/questions/12681945/reversing-bits-of-python-integer
def bit_reverse_16(x):
    x = ((x & 0x5555) << 1) | ((x & 0xAAAA) >> 1)
    x = ((x & 0x3333) << 2) | ((x & 0xCCCC) >> 2)
    x = ((x & 0x0F0F) << 4) | ((x & 0xF0F0) >> 4)
    x = ((x & 0x00FF) << 8) | ((x & 0xFF00) >> 8)
    return x


# This array of LED brightness is global so it can be called by the diagnostic as well as operational code
RdB = 20
WhB = 2
BlB = 30
                #  MAR                     MDR                 ACC                  BR
u1_brightness = [WhB]*16 + [RdB]*16 + [WhB]*16 + [RdB]*16 + [WhB]*16 + [RdB]*16 + [WhB]*16 + [RdB]*16 + \
                [WhB]*8  + [RdB] + [WhB] + [RdB] + [WhB] + [RdB]*4   # IND + SAM + run/stop
u2_brightness = [BlB]*192
                #  PC                     FF3                 FF3                  unused
u5_brightness = [RdB]*16 + [WhB]*16 + [RdB]*16 + [WhB]*16 + [RdB]*16 + [WhB]*16 + [RdB]*16 + [WhB]*16 + \
                [WhB]*16   # unused


class MappedRegisterDisplayClass:
    def __init__(self, log, i2c_bus):
        global RdB, WhB, BlB, u1_brightness, u2_brightness, u5_brightness
        self.log = log
        self.run_state = 0
        self.alarm_state = 0
        self.ind_register = 0   # this is the eight-bit "user" indicator light display
        self.activate = 0       # local storage of the state of the two Activate buttons
        self.check_alarm_special_state = 0
        self.stop_on_s1_state = 0
        self.stop_on_addr_state = 0

        self.u1_is31 = Is31(log, i2c_bus, IS31_1_ADDR_U1, brightness=u1_brightness)
        self.u2_is31 = Is31(log, i2c_bus, IS31_1_ADDR_U2, brightness=u2_brightness)
        self.u5_is31 = Is31(log, i2c_bus, IS31_1_ADDR_U5, brightness=u5_brightness)
        self.u1_led = [0] * 9
        self.u2_led = [0] * 9
        self.u5_led = [0] * 9
        # in most cases, the actual state for preset registers is stored in the LED arrays, so that write and 
        # read both go to the same place.  There's only one set of LEDs for the two MIRs, so that state is
        # stored here, and the LEDs are nothing but display.
        self.mir_state = [0]*2  # two element array to remember the MIR settings, Left=0, Right=1
        self.which_mir = 1      # this element remembers which MIR value to display

    def set_IndReg_leds(self, ind_register):
        self.ind_register = bit_reverse_16(ind_register) & 0xff
        self.set_cpu_reg_display()

    def set_cpu_reg_display(self, cpu=None, mdr=0, mar=0, mar_bank=0, ff2=0, ff3=0, run_state=0, alarm_state=None):
        if cpu:
            acc_r = bit_reverse_16(cpu._AC)
            pc_r = bit_reverse_16(cpu.PC & 0o3777)
            b_reg_r = bit_reverse_16(cpu._BReg)
            mdr_par_r = bit_reverse_16(mdr)
            mar_r = bit_reverse_16(mar & 0o3777 | (mar_bank & 0o7) << 12)

            # try to save a few cycles here...  the FF registers usually stay at zero; no need to bit-reverse zero!
            if ff2 != 0:
                ff2r = bit_reverse_16(ff2)
            else:
                ff2r = ff2
            if ff3 != 0:
                ff3r = bit_reverse_16(ff3)
            else:
                ff3r = ff3

            self.u1_led[0] = ~mar_r
            self.u1_led[1] = mar_r
            self.u1_led[2] = ~mdr_par_r
            self.u1_led[3] = mdr_par_r
            self.u1_led[4] = ~acc_r
            self.u1_led[5] = acc_r
            self.u1_led[6] = ~b_reg_r
            self.u1_led[7] = b_reg_r

            self.u5_led[0] = pc_r
            self.u5_led[1] = ~pc_r
            self.u5_led[2] = ff3r
            self.u5_led[3] = ~ff3r
            self.u5_led[4] = ff2r
            self.u5_led[5] = ~ff2r

            # Carry-Out / SAM register
            # Bit 8 -  0x0100 -> red -1 carry
            # Bit 9 -  0x0200 -> white -1 carry
            # Bit 10 - 0x0400 -> red +1 carry
            # Bit 11 - 0x0800 -> white +1 carry
            if cpu._SAM > 0:
                state_leds = 0x600
            elif cpu._SAM < 0:
                state_leds = 0x900
            else:
                state_leds = 0xa00
        else:
            state_leds = 0
        # Bit 13 - 0x2000 -> red Alarm
        # Bit 14 - 0x4000 -> red Stop
        # Bit 15 - 0x8000 -> red Run
        if run_state is not None:
            if run_state:
                state_leds |= 0x8000  #  Run led
            else:
                state_leds |= 0x4000  #  Stop led
            self.run_state = run_state
        if alarm_state is not None:
            self.alarm_state = alarm_state
        if self.alarm_state:
            state_leds |= 0x2000
        self.u1_led[8] = self.ind_register | state_leds

        self.u1_is31.is31.write_16bit_led_rows(0, self.u1_led)
        self.u5_is31.is31.write_16bit_led_rows(0, self.u5_led, len=6)


    # bytes for this set of switch-LED registers is all scrambled, so I have to mask-and-or for each one
    #
    # Register  High Byte           Low Byte
    #  PC Preset  R0-[8-10]         R1-[8-15]
    #  PC bank    R0-[12-14]
    #  FF2        R2-[8-15]         R3-[8-15]
    #  FF3        R4-[8-15]         R5-[8-15]
    def set_preset_switch_leds(self, pc=None, pc_bank=None, ff2=None, ff3=None, bank_test=False):
        bank = 0
        if pc is not None:
            self.u2_led[0] = pc & 0o003400 | bank & 0o7 << 12 | self.u2_led[0] & 0o377   # pc is only 11 bits
            self.u2_led[1] = ((pc & 0o377) << 8) | self.u2_led[1] & 0o377
            # print("set_preset_switch_leds: preset LEDs PC set to 0o%o" % pc)

        if ff2 is not None:
            self.u2_led[2] = (ff2 & 0o177400)     | self.u2_led[2] & 0o377
            self.u2_led[3] = ((ff2 & 0o377) << 8) | self.u2_led[3] & 0o377
            # print("set_preset_switch_leds: preset LEDs FF2 set to 0o%o" % ff2)

        if ff3 is not None:
            self.u2_led[4] = (ff3 & 0o177400)     | self.u2_led[4] & 0o377
            self.u2_led[5] = ((ff3 & 0o377) << 8) | self.u2_led[5] & 0o377
            # print("set_preset_switch_leds: preset LEDs FF3 set to 0o%o" % ff3)

        # send new settings to all u2 LEDs at once
        self.u2_is31.is31.write_16bit_led_rows(0, self.u2_led, len=6)


    # read back whatever the preset registers are set to
    def read_preset_switch_leds(self):
        ret = {}
        # self.u2_led[0] = pc & 0o003400 | bank & 0o7 << 12 | self.u2_led[0] & 0o377   # pc is only 11 bits
        # self.u2_led[1] = ((pc & 0o377) << 8) | self.u2_led[1] & 0o377
        pc = (self.u2_led[1] >> 8) & 0o377 | self.u2_led[0] & 0o003400
        ret["pc"] = pc
        # print("read_preset_switch_leds: preset LEDs PC set to 0o%o" % pc)

        # self.u2_led[2] = (ff2 & 0o177400)     | self.u2_led[2] & 0o377
        # self.u2_led[3] = ((ff2 & 0o377) << 8) | self.u2_led[3] & 0o377
        ff2 = (self.u2_led[3] >> 8) & 0o377 | self.u2_led[2] & 0o177400
        ret["ff2"] = ff2
        # print("read_preset_switch_leds: preset LEDs FF2 set to 0o%o" % ff2)

        # self.u2_led[4] = (ff3 & 0o177400)     | self.u2_led[4] & 0o377
        # self.u2_led[5] = ((ff3 & 0o377) << 8) | self.u2_led[5] & 0o377
        ff3 = (self.u2_led[5] >> 8) & 0o377 | self.u2_led[4] & 0o177400
        ret["ff3"] = ff3
        # print("read_preset_switch_leds: preset LEDs FF3 set to 0o%o" % ff3)
        return ret

    #
    # MIR [0-2]    U2_R5-[0-7]
    # MIR [3-5]    U2_R4-[0-7]
    # MIR [0-8]    U2_R3-[0-7]
    # MIR [0-11]   U2_R2-[0-7]
    # MIR [0-14]   U2_R1-[0-7]
    # MIR [15]     U2_R0-[0-1]
    # LMIR, RMIR   U2_R0-[2-3]
    # U, L Activate U2_R0-[4-5]

    def set_mir_preset_switch_leds(self):
        if self.which_mir:
            which_led = 4  # bit 2
        else:
            which_led = 8  # bit 3
        self.u2_led[0] = which_led | (self.u2_led[0] & 0o0177763)   #
                # Sigh, I still do not understand why Activate buttons turned up where they did...
        self.u2_led[7] = self.activate & 1        | (self.u2_led[7] & 0o177776)     # Lower Activate
        self.u2_led[8] = (self.activate >> 1) & 1 | (self.u2_led[8] & 0o177776)     # Upper Activate
        # self.u2_led[0] = (self.activate & 3) << 6  | (self.u2_led[0] & 0o0177477)   #
        # print("activate led = %o, led[0] = 0o%06o" % ((self.activate & 3 << 6), self.u2_led[0]))

        mir = self.mir_state[self.which_mir]
        mir &= 0o177777
        self.u2_led[0] = 1 << ((mir >> 15) & 1)   | (self.u2_led[0] & 0o0177774)   #
        self.u2_led[1] = 1 << ((mir >> 12) & 0o7) | (self.u2_led[1] & 0o0177400)   #
        self.u2_led[2] = 1 << ((mir >>  9) & 0o7) | (self.u2_led[2] & 0o0177400)   #
        self.u2_led[3] = 1 << ((mir >>  6) & 0o7) | (self.u2_led[3] & 0o0177400)   #
        self.u2_led[4] = 1 << ((mir >>  3) & 0o7) | (self.u2_led[4] & 0o0177400)   #
        self.u2_led[5] = 1 << ((mir      ) & 0o7) | (self.u2_led[5] & 0o0177400)   #

        msg = ''
        for i in range(0, 6):
            msg += "%d:0o%06o, " % (i, self.u2_led[i])

        if MwwPanelDebug: self.log.info("Setting U2 LEDs to %s; mir[0]=0o%o, mir[1]=0o%o, mir=0o%o, which=%d, activate=%d" %
            (msg, self.mir_state[0], self.mir_state[1], mir, self.which_mir, self.activate))
        self.u2_is31.is31.write_16bit_led_rows(0, self.u2_led, len=9)  # ought to be six, no?


    # The Activate buttons are represented as two bits out of an integer.  In this call, the
    # two bits are used to Set the respective bits, but not reset/clear them
    def set_activate_switch_leds(self, which):
        self.activate |= which
        self.set_mir_preset_switch_leds()

    # read back and clear the Activate LEDs.  If they're already zero, do nothing
    def clear_activate_switch_leds(self):
        ret = self.activate
        if ret:
            self.activate = 0
            self.set_mir_preset_switch_leds()
        return ret

    def update_exec_switch_leds(self):
        self.u2_led[7] = self.u2_led[7] & 0o174377 | \
                         self.stop_on_s1_state << 10 | self.check_alarm_special_state << 9 | self.stop_on_addr_state << 8
        self.u2_is31.is31.write_16bit_led_rows(0, self.u2_led, len=9)  # just need to write one word

    # write two bits to the LED array to indicate which 'scope (D and/or F) is enabled
    def set_scope_selector_leds(self, which):
        # Bits 11 & 12 of offset 7 in the LED array
        self.u2_led[7] = (which & 0o3) << 11 | (self.u2_led[7] & 0o163777)
        self.u2_is31.is31.write_16bit_led_rows(0, self.u2_led, len=9)  # just write one word


class MappedSwitchClass:
    def __init__(self, log, i2c_bus, mapped_display):
        self.log = log
        self.tca84_u3 = tc_init_u3(log, i2c_bus.bus, TCA8414_0_ADDR)
        self.tca84_u4 = tc_init_u4(log, i2c_bus.bus, TCA8414_1_ADDR)
        # self.i2c_bus = smbus2.SMBus(1)
        if MwwPanelDebug: self.log.info("  tca init done")

        self.tca84_u4.init_gp_out()
        if MwwPanelDebug: self.log.info("  TCA8414 init done")

        # push button switches can be classified first by the "column" number, 0-9
        self.u3_switch_map = (
            self.fn_mir_sw,  # 0
            self.fn_mir_sw,  # 1
            self.fn_mir_sw,  # 2
            self.fn_mir_sw,  # 3
            self.fn_mir_sw,  # 4
            self.fn_mir_sw,  # 5
            self.fn_ff2_sw,  # 6
            self.fn_ff2_sw,  # 7
            self.fn_ff3_sw,  # 8
            self.fn_ff3_sw,  # 9
        )
        self.u4_switch_map = (
            self.fn_sw,  # 0  - function switches - Clear Alarm through to Examine
            self.fn_sw,  # 1  - function switches - Stop-on-X
            self.fn_pc_sw,  # 2  - PC Preset switches
            self.fn_pc_sw,  # 3  - PC Preset switches
            self.fn_no_sw,  # 4
            self.fn_no_sw,  # 5
            self.fn_no_sw,  # 6
            self.fn_no_sw,  # 7
            self.fn_no_sw,  # 8
            self.fn_no_sw,   # 9
        )
        self.md = mapped_display
        self.fn_buttons_def = (("Examine", "Read In", "Order-by-Order", "Start at 40", "Start Over", "Restart", "Stop", "Clear"),
                               ("Stop-on-Addr", "Stop-on-CK", "Stop-on-S1", "F-Scope", "D-Scope", "unused", "unused", "Rotary Push"))
        self.ff_preset_state = [0, 0]        # ff2 and ff3 preset values
        self.encoder_state = [0,0]


    def check_buttons(self):
        button_press = None
        if self.tca84_u3.available() > 0:
            key = self.tca84_u3.getEvent()
            pressed = key & 0x80
            if pressed:     # I'm ignoring "released" events
                key &= 0x7F
                key -= 1
                row = key // 10
                col = key % 10
                button_press = self.u3_switch_map[col](row, col)
                if MwwPanelDebug: self.log.info("Pressed U3 %s: row=%d, col=%d" % (button_press, row, col))
                if button_press:
                    return button_press
        elif self.tca84_u4.available() > 0:
            key = self.tca84_u4.getEvent()
            pressed = key & 0x80
            key &= 0x7F
            if (key == 111 or key == 112):   # siphon off rotary encoder actions from U4 first,
                                            # then get the rest of the buttons
                button_press = self.fn_rotary_decode(pressed, key - 111)  # the two codes come in as 111 and 112

            elif pressed:     # I'm ignoring "released" events
                key -= 1
                row = key // 10
                col = key % 10
                button_press = self.u4_switch_map[col](row, col)
                if MwwPanelDebug: self.log.info("Pressed U4 %s: row=%d, col=%d" % (button_press, row, col))
#        else:
#            if RasPi == False:
#                if msvcrt.kbhit():
#                    print("you pressed ", msvcrt.getch(), " so now i will sleep")
#                    time.sleep(3)
#                    button_press = input("type function button name: ")
        return button_press

    def fn_no_sw(self, row, col):
        self.log.warn("unknown switch row %d, col %d" %(row, col))
        return None

    def fn_sw(self, row, col):
        button = None
        try:
            button = self.fn_buttons_def[col][row]
        except:
            button = "undefined mWW button col=%d, row=%d" % (col, row)
        if MwwPanelDebug: self.log.info("function switch %s: row %d, col %d" %(button, row, col))
        return button

    def fn_ff2_sw(self, row, col):
        if MwwPanelDebug: self.log.info("ff2 switch row %d, col %d" %(row, col))
        self.ff_preset_flip_bit(0, row, col)
        return None

    def fn_ff3_sw(self, row, col):
        if MwwPanelDebug: self.log.info("ff3 switch row %d, col %d" %(row, col))
        self.ff_preset_flip_bit(1, row, col)
        return None

    def fn_pc_sw(self, row, col):
        button = "PC Preset"
        self.pc_preset_flip_bit(row, col)
        if MwwPanelDebug: self.log.info("pc switch '%s': row %d, col %d" %(button, row, col))
        return None


    # flip-flop numbers are given here as offset into a two-entry array
    #  i.e. ff==0 -> ff2, ff==1 -> ff3
    def ff_preset_flip_bit(self, ff, row, col):
        bit_num = row
        if col & 1 == 0:  # even-numbered registers are the most-significant bits of Column numbers
            bit_num += 8
        reg = self.ff_preset_state[ff]
        regf = reg ^ (1 << bit_num)         # flip the designated bit
        self.ff_preset_state[ff] = regf
        if MwwPanelDebug: self.log.info("ff flip bit: ff=%d, bit_num=%d, reg=0o%o, regf=0o%o" % (ff, bit_num, reg, regf))
        if ff == 0:
            self.md.set_preset_switch_leds(pc=None, pc_bank=None, ff2=regf, ff3=None, bank_test=False)
        else:
            self.md.set_preset_switch_leds(pc=None, pc_bank=None, ff2=None, ff3=regf, bank_test=False)

    def pc_preset_flip_bit(self, row, col):
        bit_num = row
        if col & 1 == 0:  # even-numbered registers are the most-significant bits of Column numbers
            bit_num += 8
        presets = self.md.read_preset_switch_leds()

        reg = presets["pc"]
        regf = reg ^ (1 << bit_num)         # flip the designated bit
        if MwwPanelDebug: self.log.info("pc flip bit: bit_num=%d, reg=0o%o, regf=0o%o" % (bit_num, reg, regf))
        self.md.set_preset_switch_leds(pc=regf, pc_bank=None)


    def fn_mir_sw(self, row, col):
        # mir buttons are columns 0-5, rows 0-7
        activate = 0
        if col == 0 and row >= 2:  # four buttons in Col 0 are function keys
            if row == 2:
                self.md.which_mir = 1    # switch to Right MIR
                self.md.set_mir_preset_switch_leds()
                if MwwPanelDebug: self.log.info("Set display to RMIR; self.md.which_mir=%d" % self.md.which_mir)
            elif row == 3:
                self.md.which_mir = 0    # switch to Left MIR
                self.md.set_mir_preset_switch_leds()
                if MwwPanelDebug: self.log.info("Set display to LMIR; self.md.which_mir=%d" % self.md.which_mir)
            elif row == 4:   # Lower_Activate
                self.md.set_activate_switch_leds(1)
                if MwwPanelDebug: self.log.info("Lower Activate Button")
            elif row == 5:  # Upper_Activate
                self.md.set_activate_switch_leds(2)
                if MwwPanelDebug: self.log.info("Upper Activate Button")
        else:
            # if MwwPanelDebug: self.log.info("mir switch row %d, col %d" %(row, col))
            reg = self.md.mir_state[self.md.which_mir]
            val = row & 7  # it can't be more than three bits anyways...
            mask = 0o177777 ^ (7 << 3 * ((5 - col)))   # mir switches are col 0-5

            regf = (reg & mask) | (val << (3 * (5 - col)))       # insert the three designated bits
            self.md.mir_state[self.md.which_mir] = regf
            self.md.set_mir_preset_switch_leds()
            if MwwPanelDebug: self.log.info("preset LMIR = 0o%06o, RMIR = 0o%06o, MIR=%d" %
                (self.md.mir_state[0], self.md.mir_state[1], self.md.which_mir))

    # =============== Rotary Encoder  ==================================
    # The following routine decodes the two signals from a Rotary Encoder to
    # figure out which way the knob is being turned.
    # The code relies on the key scanner to deliver an 'interrupt' when either pin
    # changes state.
    # We're relying completely on the scanner to debounce the signals!
    # 'which_key' is which one of the two Rotary phases changed.
    def fn_rotary_decode(self, pressed, which_key):

        self.encoder_state[which_key] = (pressed != 0)

        direction = 33  # this is here because PyCharm figures it _could_ be uninitialized.
        if pressed:
            if which_key == 0:
                direction = self.encoder_state[1]
            if which_key == 1:
                direction = self.encoder_state[0] == 0
        else:
            if which_key == 0:
                direction = self.encoder_state[1] == 0
            if which_key == 1:
                direction = self.encoder_state[0]

        if direction:
            push_str = "Rotary Up"
        else:
            push_str = "Rotary Down"
        if MwwPanelDebug: print("%s: key=%d dir=%d" % (push_str, which_key, direction))
        return push_str


# ******************************************************************** #
# Classes to run the hardware I/O devices to make up the Micro-Whirlwind
# Guy Fedorkow, Jun 2024

class gpio_switches:
    def __init__(self, log):
        self.log = log
        gpio.setmode(gpio.BCM)

        gpio.setup(pin_gpio_LED1, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.setup(pin_gpio_LED2, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.setup(pin_gpio_LED3, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.setup(pin_gpio_LED4, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.setup(pin_gpio_isKey, gpio.IN, pull_up_down=gpio.PUD_UP)
        self.count = 0
        self.last_sw_state = 0

    def getKeys(self):
        """ [from Rainer] Key inquiry for the push button on the interface board
        and the four switches on the tap board(s).
        Result in a bit pattern with LSB for the push button
        and the other four keys, left to right, with 2, 4, 8, and 16.
        Note that setKeys() can virtually set a key
        """
        res = 0
        if gpio.input(pin_gpio_isKey) == 0:
            res = 1
        if gpio.input(pin_gpio_LED1) == 0:
            res += 2
        if gpio.input(pin_gpio_LED2) == 0:
            res += 4
        if gpio.input(pin_gpio_LED3) == 0:
            res += 8
        if gpio.input(pin_gpio_LED4) == 0:
            res += 16
        return res

    def setKey(self, n, b):
        """
            [from Rainer] Set virtual key (i.e. the LED) on (1) or off (0)
        """
        if n == 0:
            return  # ignore key 0
        LEDs = [pin_gpio_LED1, pin_gpio_LED2, pin_gpio_LED3, pin_gpio_LED4]
        led = LEDs[n - 1]
        if b == 0:
            gpio.setup(led, gpio.IN, pull_up_down=gpio.PUD_UP)
            self.last_sw_state &= ~(1 << (n - 1))
        else:
            gpio.setup(led, gpio.OUT)
            gpio.output(led, 0)
            self.last_sw_state |= 1 << (n - 1)
        if MwwPanelDebug: self.log.info("set last_sw_state to 0x%x" % self.last_sw_state)

    def step(self, delay):
        # Note that Rainer numbered the LEDs 1-4, not 0-3
        led = self.count & 3
        on = self.count & 4
        self.setKey(led + 1, on)
        self.count += 1

        sw = self.getKeys()
        if sw != self.last_sw_state:
            if MwwPanelDebug: self.log.info("gpio switches: new state = 0x%x" % sw)
            self.last_sw_state = sw

        time.sleep(delay)




# =============== TCA8414 Keypad Scanner ==================================

class TCA8414:
    def __init__(self, log, bus, i2c_addr):
        self.bus = bus
        self.log = log
        self.i2c_addr = i2c_addr
        self.TCA8418_REG_CFG = 0x01  # < Configuration register
        self.TCA8418_REG_INT_STAT = 0x02  # < Interrupt status
        self.TCA8418_REG_KEY_LCK_EC = 0x03  # < Key lock and event counter
        self.TCA8418_REG_KEY_EVENT_A = 0x04  # < Key event register A
        self.TCA8418_REG_KEY_EVENT_B = 0x05  # < Key event register B
        self.TCA8418_REG_KEY_EVENT_C = 0x06  # < Key event register C
        self.TCA8418_REG_KEY_EVENT_D = 0x07  # < Key event register D
        self.TCA8418_REG_KEY_EVENT_E = 0x08  # < Key event register E
        self.TCA8418_REG_KEY_EVENT_F = 0x09  # < Key event register F
        self.TCA8418_REG_KEY_EVENT_G = 0x0A  # < Key event register G
        self.TCA8418_REG_KEY_EVENT_H = 0x0B  # < Key event register H
        self.TCA8418_REG_KEY_EVENT_I = 0x0C  # < Key event register I
        self.TCA8418_REG_KEY_EVENT_J = 0x0D  # < Key event register J
        self.TCA8418_REG_KP_LCK_TIMER = 0x0E  # < Keypad lock1 to lock2 timer
        self.TCA8418_REG_UNLOCK_1 = 0x0F  # < Unlock register 1
        self.TCA8418_REG_UNLOCK_2 = 0x10  # < Unlock register 2
        self.TCA8418_REG_GPIO_INT_STAT_1 = 0x11  # < GPIO interrupt status 1
        self.TCA8418_REG_GPIO_INT_STAT_2 = 0x12  # < GPIO interrupt status 2
        self.TCA8418_REG_GPIO_INT_STAT_3 = 0x13  # < GPIO interrupt status 3
        self.TCA8418_REG_GPIO_DAT_STAT_1 = 0x14  # < GPIO data status 1
        self.TCA8418_REG_GPIO_DAT_STAT_2 = 0x15  # < GPIO data status 2
        self.TCA8418_REG_GPIO_DAT_STAT_3 = 0x16  # < GPIO data status 3
        self.TCA8418_REG_GPIO_DAT_OUT_1 = 0x17  # < GPIO data out 1
        self.TCA8418_REG_GPIO_DAT_OUT_2 = 0x18  # < GPIO data out 2
        self.TCA8418_REG_GPIO_DAT_OUT_3 = 0x19  # < GPIO data out 3
        self.TCA8418_REG_GPIO_INT_EN_1 = 0x1A  # < GPIO interrupt enable 1
        self.TCA8418_REG_GPIO_INT_EN_2 = 0x1B  # < GPIO interrupt enable 2
        self.TCA8418_REG_GPIO_INT_EN_3 = 0x1C  # < GPIO interrupt enable 3
        self.TCA8418_REG_KP_GPIO_1 = 0x1D  # < Keypad/GPIO select 1
        self.TCA8418_REG_KP_GPIO_2 = 0x1E  # < Keypad/GPIO select 2
        self.TCA8418_REG_KP_GPIO_3 = 0x1F  # < Keypad/GPIO select 3
        self.TCA8418_REG_GPI_EM_1 = 0x20  # < GPI event mode 1
        self.TCA8418_REG_GPI_EM_2 = 0x21  # < GPI event mode 2
        self.TCA8418_REG_GPI_EM_3 = 0x22  # < GPI event mode 3
        self.TCA8418_REG_GPIO_DIR_1 = 0x23  # < GPIO data direction 1
        self.TCA8418_REG_GPIO_DIR_2 = 0x24  # < GPIO data direction 2
        self.TCA8418_REG_GPIO_DIR_3 = 0x25  # < GPIO data direction 3
        self.TCA8418_REG_GPIO_INT_LVL_1 = 0x26  # < GPIO edge/level detect 1
        self.TCA8418_REG_GPIO_INT_LVL_2 = 0x27  # < GPIO edge/level detect 2
        self.TCA8418_REG_GPIO_INT_LVL_3 = 0x28  # < GPIO edge/level detect 3
        self.TCA8418_REG_DEBOUNCE_DIS_1 = 0x29  # < Debounce disable 1
        self.TCA8418_REG_DEBOUNCE_DIS_2 = 0x2A  # < Debounce disable 2
        self.TCA8418_REG_DEBOUNCE_DIS_3 = 0x2B  # < Debounce disable 3
        self.TCA8418_REG_GPIO_PULL_1 = 0x2C  # < GPIO pull-up disable 1
        self.TCA8418_REG_GPIO_PULL_2 = 0x2D  # < GPIO pull-up disable 2
        self.TCA8418_REG_GPIO_PULL_3 = 0x2E  # < GPIO pull-up disable 3
        # #define TCA8418_REG_RESERVED          0x2F

        # FIELDS CONFIG REGISTER  1

        self.TCA8418_REG_CFG_AI = 0x80  # < Auto-increment for read/write
        self.TCA8418_REG_CFG_GPI_E_CGF = 0x40  # < Event mode config
        self.TCA8418_REG_CFG_OVR_FLOW_M = 0x20  # < Overflow mode enable
        self.TCA8418_REG_CFG_INT_CFG = 0x10  # < Interrupt config
        self.TCA8418_REG_CFG_OVR_FLOW_IEN = 0x08  # < Overflow interrupt enable
        self.TCA8418_REG_CFG_K_LCK_IEN = 0x04  # < Keypad lock interrupt enable
        self.TCA8418_REG_CFG_GPI_IEN = 0x02  # < GPI interrupt enable
        self.TCA8418_REG_CFG_KE_IEN = 0x01  # < Key events interrupt enable

        # FIELDS INT_STAT REGISTER  2
        self.TCA8418_REG_STAT_CAD_INT = 0x10  # < Ctrl-alt-del seq status
        self.TCA8418_REG_STAT_OVR_FLOW_INT = 0x08  # < Overflow interrupt status
        self.TCA8418_REG_STAT_K_LCK_INT = 0x04  # < Key lock interrupt status
        self.TCA8418_REG_STAT_GPI_INT = 0x02  # < GPI interrupt status
        self.TCA8418_REG_STAT_K_INT = 0x01  # < Key events interrupt status

        # FIELDS  KEY_LCK_EC REGISTER 3
        self.TCA8418_REG_LCK_EC_K_LCK_EN = 0x40  # < Key lock enable
        self.TCA8418_REG_LCK_EC_LCK_2 = 0x20  # < Keypad lock status 2
        self.TCA8418_REG_LCK_EC_LCK_1 = 0x10  # < Keypad lock status 1
        self.TCA8418_REG_LCK_EC_KLEC_3 = 0x08  # < Key event count bit 3
        self.TCA8418_REG_LCK_EC_KLEC_2 = 0x04  # < Key event count bit 2
        self.TCA8418_REG_LCK_EC_KLEC_1 = 0x02  # < Key event count bit 1
        self.TCA8418_REG_LCK_EC_KLEC_0 = 0x01  # < Key event count bit 0

    def writeRegister(self, command, val):
        if Debug_I2C: print("writeRegister: cmd=%x val=%x" % (command, val))
        self.bus.write_byte_data(self.i2c_addr, command, val)

    def readRegister(self, command):
        global I2CBusTimeout
        try:
            val = self.bus.read_byte_data(self.i2c_addr, command)
        except IOError:
            I2CBusTimeout += 1
            print("***  bus.read_byte_data I2C addr 0x%x Bus Timeout #%d at %s ***" % (self.i2c_addr, I2CBusTimeout,  time.asctime()))
        if Debug_I2C: print("readRegister: cmd=%x val=%x" % (command, val))
        return val

    def i2c_reg_test(self):
        val = 0x55
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_1, val)
        nval = self.readRegister(self.TCA8418_REG_GPIO_DIR_1)
        print(" I2C=0x%0x, Reg %x: val=%x, read=%x" % 
            (self.i2c_addr, self.TCA8418_REG_GPIO_DIR_1, val, nval))

    def init_tca8414(self, rows, columns):
        self.writeRegister(self.TCA8418_REG_CFG, 0x20)   # Interrupt for buffer overflow
        val = self.readRegister(self.TCA8418_REG_CFG)
        if val == 0x20:
            if MwwPanelDebug: self.log.info("TCA8414 at 0x%x config_reg = 0x%x" % (self.i2c_addr, val))
        else:
            self.log.warn("TCA8414 at 0x%x failed; val should be 0x20, is 0x%x" % (self.i2c_addr, val))

        #  GPIO
        #  set default all GIO pins to INPUT
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_1, 0x00)
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_2, 0x00)
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_3, 0x00)

        #  add all pins to key events
        self.writeRegister(self.TCA8418_REG_GPI_EM_1, 0xFF)
        self.writeRegister(self.TCA8418_REG_GPI_EM_2, 0xFF)
        self.writeRegister(self.TCA8418_REG_GPI_EM_3, 0x00)

        #  set all pins to FALLING interrupts
        self.writeRegister(self.TCA8418_REG_GPIO_INT_LVL_1, 0x00)
        self.writeRegister(self.TCA8418_REG_GPIO_INT_LVL_2, 0x00)
        self.writeRegister(self.TCA8418_REG_GPIO_INT_LVL_3, 0x00)

        #  add all pins to interrupts
        self.writeRegister(self.TCA8418_REG_GPIO_INT_EN_1, 0xFF)
        self.writeRegister(self.TCA8418_REG_GPIO_INT_EN_2, 0xFF)
        self.writeRegister(self.TCA8418_REG_GPIO_INT_EN_3, 0xFF)

        self.matrix(rows, columns)

    """ from: /**
     *  @file Adafruit_TCA8418.cpp
     *
     * 	I2C Driver for the Adafruit TCA8418 Keypad Matrix / GPIO Expander Breakout
     *
     * 	This is a library for the Adafruit TCA8418 breakout:
     * 	https://www.adafruit.com/product/XXXX
     *

    /**
     * @brief configures the size of the keypad matrix.
     *
     * @param [in] rows    number of rows, should be <= 8
     * @param [in] columns number of columns, should be <= 10
     * @return true is rows and columns have valid values.
     *
     * @details will always use the lowest pins for rows and columns.
     *          0..rows-1  and  0..columns-1
     */
    """

    def matrix(self, rows, columns):
        if (rows > 8) or (columns > 10):
            return False

        # skip zero size matrix
        if (rows != 0) and (columns != 0):
            # set up the keypad matrix.
            mask = 0x00
            for r in range(0, rows):
                mask <<= 1
                mask |= 1
            self.writeRegister(self.TCA8418_REG_KP_GPIO_1, mask)
            if MwwPanelDebug: self.log.info("matrix GPIO_1 set to 0x%x" % mask)

            mask = 0x00
            for c in range(0, 8):  # (int c = 0; c < columns && c < 8; c++) {
                if c < columns:
                    mask <<= 1
                    mask |= 1
            self.writeRegister(self.TCA8418_REG_KP_GPIO_2, mask)
            if MwwPanelDebug: self.log.info("matrix GPIO_2 set to 0x%x" % mask)

            mask = 0
            if columns > 8:
                if columns == 9:
                    mask = 0x01
                else:
                    mask = 0x03
            self.writeRegister(self.TCA8418_REG_KP_GPIO_3, mask)
            if MwwPanelDebug: self.log.info("matrix GPIO_3 set to 0x%x" % mask)
        return True

    # hack -- config two pins as output to blink an LED
    def init_gp_out(self):
        # column 8 and 9 pins
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_3, 0x3)

    def set_gp_out(self, val):
        self.writeRegister(self.TCA8418_REG_GPIO_DAT_OUT_3, val)

    """ ... from Adafruit
    /**
     * @brief flushes the internal buffer of key events
     *        and cleans the GPIO status registers.
     *
     * @return number of keys flushed.
     */    """

    def flush(self):
        count = 0
        while self.getEvent() != 0:
            count += 1
        #  flush gpio events
        self.readRegister(self.TCA8418_REG_GPIO_INT_STAT_1)
        self.readRegister(self.TCA8418_REG_GPIO_INT_STAT_2)
        self.readRegister(self.TCA8418_REG_GPIO_INT_STAT_3)
        #  //  clear INT_STAT register
        self.writeRegister(self.TCA8418_REG_INT_STAT, 3)
        return count

    """
    /**
     * @brief gets first event from the internal buffer
     *
     * @return key event or 0 if none available
     *
     * @details
     *     key event 0x00        no event
     *               0x01..0x50  key  press
     *               0x81..0xD0  key  release
     *               0x5B..0x72  GPIO press
     *               0xDB..0xF2  GPIO release
     */
    """
    def getEvent(self):
        return self.readRegister(self.TCA8418_REG_KEY_EVENT_A)

    """
    /**
     * @brief checks if key events are available in the internal buffer
     * @return number of key events in the buffer
     */
    """

    def available(self):
        eventCount = self.readRegister(self.TCA8418_REG_KEY_LCK_EC)
        eventCount &= 0x0F  # //  lower 4 bits only
        return eventCount


# =============== Rotary Encoder Test ==================================
# The following routine decodes the two signals from a Rotary Encoder to
# figure out which way the knob is being turned.
# The code relies on the key scanner to deliver an 'interrupt' when the pin
# changes state.
# We're also relying completely on the scanner to debounce the signals!
EncoderState = [0,0]
# 'which_key' is which one of the two Rotary phases changed.
def rotary_decode_test(pressed, which_key):
    global EncoderState

    EncoderState[which_key] = (pressed != 0)
    push_str = "Released"
    if pressed:
        push_str = "Pushed  "

    direction = 33
    if pressed:
        if which_key == 0:
            direction = EncoderState[1]
        if which_key == 1:
            direction = EncoderState[0] == 0
    else:
        if which_key == 0:
            direction = EncoderState[1] == 0
        if which_key == 1:
            direction = EncoderState[0]

    print("%s: key=%d dir=%d" % (push_str, which_key, direction))


# =============== IS31FL3731 LED Mux ==================================
    # This class was derived from an Adafruit example
class IS31FL3731:
    def __init__(self, log, i2c_bus, i2c_addr):
        self.bus = i2c_bus.bus
        self.log = log
        self.i2c_addr = i2c_addr
        # converted from Adafruit library
        self.ISSI_REG_CONFIG = 0x00
        self.ISSI_REG_CONFIG_PICTUREMODE = 0x00
        self.ISSI_REG_CONFIG_AUTOPLAYMODE = 0x08
        self.ISSI_REG_CONFIG_AUDIOPLAYMODE = 0x18
        self.ISSI_CONF_PICTUREMODE = 0x00
        self.ISSI_CONF_AUTOFRAMEMODE = 0x04
        self.ISSI_CONF_AUDIOMODE = 0x08
        self.ISSI_REG_PICTUREFRAME = 0x01
        self.ISSI_REG_SHUTDOWN = 0x0A
        self.ISSI_REG_AUDIOSYNC = 0x06
        self.ISSI_COMMANDREGISTER = 0xFD
        self.ISSI_BANK_FUNCTIONREG = 0x0B  # helpfully called 'page nine'

    # this routine is used to transmit an easy-to-recognize pattern on
    # the I2C bus, for watching with a logic analyzer.  It doesn't make
    # the display do anything...
    def i2c_bus_test(self):
        msg = [2]
        self.bus.write_i2c_block_data(self.i2c_addr, 1, msg)
        msg = [4]
        self.bus.write_i2c_block_data(self.i2c_addr, 3, msg)
        msg = [6, 7]
        self.bus.write_i2c_block_data(self.i2c_addr, 5, msg)
        msg = [0xa, 0xb, 0xc]
        self.bus.write_i2c_block_data(self.i2c_addr, 9, msg)


    # write an IS31 control register.  Start by selecting "Page 9", the one that
    # has control registers instead of pixels.
    def writeRegister8(self, register, command, val=None):
        global PassCount
        if MwwPanelDebug: self.log.info("%05d: writeRegister: reg=%x, cmd=%x " % (PassCount, register, command), "val=", val)
        msg = [register]
        self.bus.write_i2c_block_data(self.i2c_addr, self.ISSI_COMMANDREGISTER, msg)

        if val is not None:
            msg = [val]
        else:
            msg = []
        self.bus.write_i2c_block_data(self.i2c_addr, command, msg)


    def writeMultiRegister(self, register, val_list):
        #print("writeMultiRegister: reg=%x, " % (register), "val=", val_list)
        self.bus.write_i2c_block_data(self.i2c_addr, self.ISSI_COMMANDREGISTER, [0])
        self.bus.write_i2c_block_data(self.i2c_addr, register, val_list)


    def selectFrame(self, frame):
        msg = [frame]
        self.bus.write_i2c_block_data(self.i2c_addr, self.ISSI_COMMANDREGISTER, msg)

    def displayFrame(self, frame):
        self.writeRegister8(self.ISSI_BANK_FUNCTIONREG, self.ISSI_REG_PICTUREFRAME, val=frame)

    def set_brightness(self, bright):
        #for (uint8_t i = 0; i < 6; i++) {
        #  erasebuf[0] = 0x24 + i * 24;
        #  _i2c_dev->write(erasebuf, 25);
        #}
        IS31_LEDS = 192
        I2C_BLOCK = 24    # break the 192 LED settings into nine blocks of 24 bytes
        if bright is None:
            bright = [4]*IS31_LEDS

        # There's a one-byte register to set brightness for each individual LED, starting at offset 0x24
        for i in range(0, IS31_LEDS // I2C_BLOCK):
            self.writeMultiRegister(i*I2C_BLOCK + 0x24, bright[I2C_BLOCK*i:I2C_BLOCK*(i+1)])
        # onoff = [0x5C] * (IS31_LEDS // 8)  # 8 bits per byte of on/off status
        # print("set on-status to ", onoff)
        # for i in range(0, 18):
        # self.writeMultiRegister(0, onoff)   # each 8 LEDs on (off)

    # convert an array of 16-bit ints into a list of bytes to turn LEDs on or off
    # The longest string we can send is 9 words, so this routine goes until
    # either it runs out of words or exceeds nine
    # First_row gives the offset into the IS31 display registers
    def write_16bit_led_rows(self, first_row, int_list, len=9):
        global I2CBusTimeout
        byte_list = []
        i = 0
        for val in int_list:
            byte_list.append(val & 0xff)
            byte_list.append(val >> 8)
            i += 1
            if (i > len):
                break
        #self.writeMultiRegister(row * 2, byte_list)   # 16 bits in two bytes
        try:
            self.bus.write_i2c_block_data(self.i2c_addr, first_row * 2, byte_list)
        except IOError:
            I2CBusTimeout += 1
            print("***  bus.write_i2c_block_data I2C addr 0x%x Bus Timeout #%d at %s ***" % (self.i2c_addr, I2CBusTimeout,  time.asctime()))

    def init_IS31(self):
        global MwwPanelDebug
        _frame = 0
        # shutdown
        if MwwPanelDebug: self.log.info("Shutdown")
        self.writeRegister8(self.ISSI_BANK_FUNCTIONREG, self.ISSI_REG_SHUTDOWN, val=0x00)
        time.sleep(0.01)

        # out of shutdown
        if MwwPanelDebug: self.log.info("unShutdown")
        self.writeRegister8(self.ISSI_BANK_FUNCTIONREG, self.ISSI_REG_SHUTDOWN, val=0x01)
        #time.sleep(1)

        # picture mode
        if MwwPanelDebug: self.log.info("picture mode")
        self.writeRegister8(self.ISSI_BANK_FUNCTIONREG, self.ISSI_REG_CONFIG,
                 val=self.ISSI_REG_CONFIG_PICTUREMODE)

        #time.sleep(1)
        if MwwPanelDebug: self.log.info("display frame")
        self.displayFrame(_frame)

        #time.sleep(1)






# =============== Devices and Tests ==================================

class I2C:
    def __init__(self, bus_number):
        if Debug_I2C: print("I2C init bus #%d: " % bus_number)
        # bus = I2Cclass(channel = 1)
        self.bus = smbus2.SMBus(bus_number)
        if Debug_I2C: print("  done")
        self.test_step = 0

    def writeRegister(self, i2c_addr, command, val):
        if Debug_I2C: print("writeRegister: addr=%x, cmd=%x val=%x" % (i2c_addr, command, val))
        self.bus.write_byte_data(i2c_addr, command, val)

    def readRegister(self, i2c_addr, command):
        val = self.bus.read_byte_data(i2c_addr, command)
        if Debug_I2C: print("readRegister:  addr=%x, cmd=%x val=%x" % (i2c_addr, command, val))
        return val

    def i2c_reg_test(self, addr_str):
        addr = int(addr_str, 16)
        val = 0x55
        self.writeRegister(addr, val, 0)
        nval = self.readRegister(addr, 0)
        print(" Reg %x: val=%x, read=%x" % (addr, val, nval))


class PwrCtlClass:
    def __init__(self, log):
        self.pwr_state: int = 0
        self.log = log

    def pwr_on(self) -> None:
        global pin_pwr_ctl, pin_tca_reset, pin_tca_interrupt

        self.pwr_state = 1

        gpio.setmode(gpio.BCM)
        gpio.setup(pin_pwr_ctl, gpio.OUT)
        gpio.setup(pin_tca_reset, gpio.OUT)
        gpio.setup(pin_tca_interrupt, gpio.IN, pull_up_down=gpio.PUD_UP)

        gpio.output(pin_pwr_ctl, self.pwr_state)
        gpio.output(pin_tca_reset, 0)  # turn on the reset signal
        time.sleep(0.3)
        gpio.output(pin_tca_reset, 1)  # Enable the key scanners

        if MwwPanelDebug: self.log.info("power control pin %d set to one" % pin_pwr_ctl)


    def step(self):
        self.pwr_state ^= 1  # flip the power state pin
        gpio.output(pin_pwr_ctl, self.pwr_state)




# initialize a test instance for LED patterns.
class Is31:
    def __init__(self, log, i2c_bus, addr, brightness=None, reverse_bits=False):
        self.is31 = IS31FL3731(log, i2c_bus, addr)
        self.i2c_bus = i2c_bus
        self.log = log
        if MwwPanelDebug: self.log.info("IS31 at 0x%0x Init" % addr)
        self.addr = addr
        # is31.i2c_reg_test()
        self.is31.init_IS31()
        if MwwPanelDebug: self.log.info("set brightness")
        self.is31.set_brightness(brightness)

        self.is31.selectFrame(0)   # do this once, so it doesn't have to be done with each write of the LEDs
        self.is31.write_16bit_led_rows(0, [0, 0, 0, 0, 0, 0, 0, 0, 0])  # clear all the LEDs
        if MwwPanelDebug: self.log.info("  IS31 init done")
        self.test_step = 0
        self.previous_test_step = 0
        self.previous_word_offset = 0
        self.bits_on = 1
        self.test_state = [0] * 18  # up to nine 16-bit registers
        self.exclusion = None
        self.register_range = 9     # default highest register number
        self.swap_size = 16
        self.reverse_bits = reverse_bits

        # there are some unpopulated LEDs that "shouldn't" be turned on to avoid a sneak-path
        # Each LED driver has a different list...
        self.u1_exclusion = {0: 0b10001, 1: 0b10001, 8: 0x1000}
        self.u5_exclusion = {0: 0b10001, 1: 0b10001}
        self.u2_exclusion = {}
        if addr == 0x74:   # LED driver U1
            self.exclusion =  self.u1_exclusion
            if MwwPanelDebug: log.info("U1 Exclusion List")
        if addr == 0x75:   # LED driver U5
            self.exclusion =  self.u5_exclusion
            self.register_range = 6
            if MwwPanelDebug: log.info("U5 Exclusion List")
        if addr == 0x77:   # LED driver U2
            self.exclusion =  self.u2_exclusion
            self.swap_size = 1
            if MwwPanelDebug: log.info("U2 Exclusion List")



    # bit-reverse a 16-bit word
    def bit_reverse(self, word):
        wsize = self.swap_size
        new_word = 0
        if wsize == 16:        # reverse the bits in a 16-bit word
            for i in range(0, wsize):
                new_word |= (word >> i) & 1
                if i < wsize - 1:
                    new_word = new_word << 1
        elif wsize == 8:        # reverse the bits in two 8-bit bytes
            for i in range(0, wsize):
                new_word |= (word >> i) & 0x101
                if i < wsize - 1:
                    new_word = new_word << 1
        elif wsize == 1:       # swap bytes, leave bits in the same order
            new_word = ((word << 8) & 0xff00) | ((word >> 8) & 0xff)
        else:
            self.log.warn("unexpected word length %d in bit_reverse" % wsize)
        return new_word



    def swap_bits_and_write_word(self, reg_offset, word_reg):
        if self.reverse_bits:
            reversed_word = self.bit_reverse(word_reg)
            if self.exclusion:
                if reg_offset in self.exclusion:
                    exc = self.exclusion[reg_offset]
                    if (exc & reversed_word) != 0:
                        print("Exclusion: Reg 0x%x, 0x%x" % (reg_offset, self.exclusion[reg_offset]))
                    reversed_word &= ~exc
            int_list = [reversed_word]
        else:
            int_list = [word_reg]
        self.is31.write_16bit_led_rows(reg_offset, int_list)



    def step(self, delay, pattern):
        global PassCount

        word_reg = 0
        word_offset = 0
        if pattern == 0 or pattern == 1:
            word_offset = self.test_step >> 4
            bit_num = self.test_step & 0xf
            word_reg = self.test_state[word_offset]  # Last-written state of the registers
        else:  # Patterns two and three blink adjacent LEDs, 2 is 'horizontaly adjacent', 3 is 'vertically adjacent'
            pattern23_addr = pattern >> 4
            pattern &= 0xf    # convert this into "pattern 2 or 3", i.e., separate command and address
            if pattern == 2:
                word_offset = pattern23_addr >> 4
                bit_num = pattern23_addr & 0xe   # round to the next lower even number
            elif pattern == 3:
                word_offset = (pattern23_addr >> 4) & 0xe   # in Pattern Three, we blink corresponding bits in adjacent registers
                bit_num = pattern23_addr & 0xf
            else:
                bit_num = 0  # suppress an error message
                self.log.warn("unexpected pattern")


        # with the Wave pattern, we just turn on bits one at a time until they're all on, then turn them off one at a time
        if pattern == 0:
            if self.bits_on:
                word_reg |= 1 << bit_num
            else:
                word_reg &= ~(1 << bit_num)

        elif pattern == 1:         # The one-hot pattern turns LEDs on one a time but turns off the previous one first
            word_offset = self.previous_test_step >> 4
            word_reg = 0
            self.swap_bits_and_write_word(word_offset,  word_reg)  # turn off the previous bit
            # int_list = [word_reg]  # turn off the last bit
            # self.is31.write_16bit_led_rows(word_offset, int_list)

            word_offset = self.test_step >> 4
            bit_num = self.test_step & 0xf
            word_reg = 1 << bit_num

        elif pattern == 2:    # blink back and forth between LEDs 0 and 1 of the register
            if self.test_step == 0:
                word_reg = 1 << bit_num
            else:
                word_reg = 2 << bit_num

        elif pattern == 3:    # blink back and forth between LEDs in two registers
            word_reg = 0
            self.swap_bits_and_write_word(word_offset,  word_reg)  # turn off the previous bit
            # int_list = [word_reg]  # turn off the last bit
            # self.is31.write_16bit_led_rows(self.previous_word_offset, int_list)

            word_reg = 1 << bit_num
            if self.test_step > 0:
                word_offset +=1

        else:
            print("Unexpected blink pattern %d" % pattern)

        if Verbose: print("%05d: write LED reg %d at 0x%x to 0x%x" % (PassCount, word_offset, self.addr, word_reg))
        self.test_state[word_offset] = word_reg

        self.swap_bits_and_write_word(word_offset,  word_reg)  # turn off the previous bit
        # int_list = [word_reg]  # pass in a list of one word
        # self.is31.write_16bit_led_rows(word_offset, int_list)


        restart_cycle = False
        self.previous_test_step = self.test_step
        self.previous_word_offset = word_offset
        if pattern == 0 or pattern == 1:
            # Pattern generator - sweep across all bits turning them on one a time, then
            # turn them all off one at a time, or turn on one at a time
            self.test_step += 1
            if self.test_step >= 16 * self.register_range:
                self.test_step = 0
                self.bits_on = self.bits_on ^ 1
                restart_cycle = True
        elif pattern == 2 or pattern == 3:   # alternate two LEDs
            self.test_step += 1
            if self.test_step > 1:
                self.test_step = 0
        else:
            print("unexpected blink pattern %d" % pattern)

        time.sleep(delay)
        return restart_cycle


def tc_init_u4(log, bus, addr):
    tca84 = TCA8414(log, bus, addr)
    if MwwPanelDebug: log.info("TCA8414 @0x%x U4 Test" % tca84.i2c_addr)
    # tca84.i2c_reg_test()
    tca84.init_tca8414(8, 4)  # scan 8 rows, 4 columns
    # tca84.init_gp_out()
    # flush the internal buffer
    tca84.flush()
    if MwwPanelDebug: log.info("  TCA8414 U4 at 0x%x init done" % tca84.i2c_addr)
    return tca84


def tc_init_u3(log, bus, addr):
    tca84 = TCA8414(log, bus, addr)
    if MwwPanelDebug: log.info("TCA8414 @0x%x U3 Test" % tca84.i2c_addr)
    # tca84.i2c_reg_test()
    tca84.init_tca8414(8, 10) #was 8  # scan 8 rows, 10 columns
    # tca84.init_gp_out()  # hack test
    # flush the internal buffer
    tca84.flush()
    if MwwPanelDebug: log.info("  TCA8414 U3 at 0x%x init done" % tca84.i2c_addr)
    return tca84


def run_pong(is31):
    pp = _init_pongs()
    int_val = [0] * _NPONGS
    i = 0
    while True:
        for j in range(0, _NPONGS):
            int_val[j] = pp[j].pingpong()
        is31.write_16bit_led_rows(0, int_val)


def run_tca(tca84):
    if tca84.available() > 0:
        key = tca84.getEvent()
        pressed = key & 0x80
        key &= 0x7F
        if (key == 111 or key == 112) and tca84.i2c_addr == TCA8414_1_ADDR:
            rotary_decode_test(pressed, key - 111)  # the two codes come in as 111 and 112

        else:
            key -= 1
            row = key // 10
            col = key % 10
            push_str = "Released"
            if pressed:
                push_str = "Pressed "
            print("%s: I2C=0x%0x, key=%d; row=%d, col=%d" % (push_str, tca84.i2c_addr, key + 1, row, col))




# =============== Test Framework ==================================


class RegListClass:
    def __init__(self, num_bits=0, var_name=None, fn="?"):
        self.fn = fn
        self.num_bits = num_bits
        self.var_name = var_name

class MappedDisplayTestDriverClass:
    def __init__(self, log, i2c_bus):
        self.cpu = localCpuClass()
        self.mar = 0
        self.mdr = 0
        self.AC = 0
        self.BReg = 0
        self.PC = 0
        self.PC_preset = 0
        self.ff2_preset = 0
        self.ff3_preset = 0
        self.mir_preset = 0


        self.reg_disp = MappedRegisterDisplayClass(log, i2c_bus)
        self.reg_disp.set_cpu_reg_display(self.cpu)  # default everything to zero
        self.bit_num = 0
        self.reg_num = 0

        self.reg_list = []
        self.reg_list.append(RegListClass(var_name=self.mar,  num_bits=11, fn="cpu"))       # 0
        self.reg_list.append(RegListClass(var_name=self.mdr,  num_bits=16, fn="cpu"))       # 1
        self.reg_list.append(RegListClass(var_name=self.AC,   num_bits=16, fn="cpu"))       # 2
        self.reg_list.append(RegListClass(var_name=self.BReg, num_bits=16, fn="cpu"))       # 3
        self.reg_list.append(RegListClass(var_name=self.PC,   num_bits=11, fn="cpu"))       # 4

        self.reg_list.append(RegListClass(var_name=self.PC_preset,   num_bits=11, fn="preset"))  # 5
        self.reg_list.append(RegListClass(var_name=self.ff2_preset,  num_bits=16, fn="preset"))  # 6
        self.reg_list.append(RegListClass(var_name=self.ff3_preset,  num_bits=16, fn="preset"))  # 7

        self.reg_list.append(RegListClass(var_name=self.mir_preset,  num_bits=16, fn="mir_preset"))  # 8


    def step(self, delay):

        self.reg_list[self.reg_num].var_name = 1 << self.bit_num
        self.bit_num += 1
        if self.bit_num >= self.reg_list[self.reg_num].num_bits:
            self.bit_num = 0
            self.reg_num = (self.reg_num + 1) % len(self.reg_list)

        self.cpu.PC = self.reg_list[4].var_name
        self.cpu._AC = self.reg_list[2].var_name
        self.cpu._BReg = self.reg_list[3].var_name
        self.cpu._SAM = 0

        if self.reg_list[self.reg_num].fn == "cpu":
            self.reg_disp.set_cpu_reg_display(self.cpu, mar=self.reg_list[0].var_name, mdr=self.reg_list[1].var_name)
        elif self.reg_list[self.reg_num].fn == "preset":
            self.reg_disp.set_preset_switch_leds(pc = self.reg_list[5].var_name, pc_bank= 0,
                                              ff2=self.reg_list[6].var_name, ff3=self.reg_list[7].var_name)
        elif self.reg_list[self.reg_num].fn == "mir_preset":
            self.reg_disp.set_mir_preset_switch_leds(self.reg_list[8].var_name)
        else:
            print("unknown register set type %s" % self.reg_list[self.reg_num].fn)

        time.sleep(delay)


# --------------------
# this module gives a standalone test program that exercises
# the IS31 LED driver
# July 7, 2024

class PingPongStruct():
    def __init__(self, i):
        print("pong_struct preset = ", i)

        self.delay_count = 0
        self.delay_preset = i
        self.incr = 1
        self.invert = 0
        self.val = 0

    def pingpong(self):
        self.delay_count -= 1
        if self.delay_count < 0:
            self.delay_count = self.delay_preset

            self.val += self.incr
            if self.val < 0:
                self.val = 1
                self.incr = 1
                self.invert = 0

            if self.val > 15:
                self.val = 14
                self.incr = -1
                self.invert = ~self.invert

        return((1 << self.val) ^ self.invert)


_NPONGS = 9
def _init_pongs():
    pp = []
    for i in range(0, _NPONGS):
        pp.append(PingPongStruct(i))
    return pp

# =============== Main ==================================

PassCount = 0


def main():
    global PassCount, Verbose
    global RdB, WhB, BlB, u1_brightness, u2_brightness, u5_brightness

    parser = argparse.ArgumentParser(description='Diagnostic for MicroWhirlwind PCB')
    parser.add_argument("-v", "--Verbose", help="Print lots of chatter", action="store_true")
    parser.add_argument("-d", "--Delay", help="wait time between steps", type=str)
    parser.add_argument("-g", "--GPIO_Switches", help="Activate GPIO switches/LEDs", action="store_true")
    parser.add_argument("--NoPowerControl", help="Don't mess with power control", action="store_true")
    parser.add_argument("--PowerControl_Loop", help="Loop power control on/off", action="store_true")
    parser.add_argument("--SMBus_Loop", help="Loop on SMBus addr read/write test", type=str) # hex number
    parser.add_argument("--U1_LED_Mux_Loop", help="Exercise LED Mux chip @ 0x74", action="store_true")
    parser.add_argument("--U5_LED_Mux_Loop", help="Exercise LED Mux chip @ 0x75", action="store_true")
    parser.add_argument("--U2_LED_Mux_Loop", help="Exercise LED Mux chip @ 0x77", action="store_true")
    parser.add_argument("--Key_0_Scan", help="Exercise Key Scanner chip @ 0x?", action="store_true")
    parser.add_argument("--Key_1_Scan", help="Exercise Key Scanner chip @ 0x?", action="store_true")
    parser.add_argument("--P0_wave", help="LED Pattern - Wave", action="store_true")
    parser.add_argument("--P1_hot", help="LED Pattern - One Hot scan", action="store_true")
    parser.add_argument("--P2H_blink", help="LED Pattern - Alternate two horizontal LEDs at hex-addr", type=str)
    parser.add_argument("--P3V_blink", help="LED Pattern - Alternate two vertical LEDs at hex-addr", type=str)
    parser.add_argument("-l", "--LED_Mapped", help="Scan CPU State", action="store_true")
    parser.add_argument("-s", "--SW_Mapped", help="Scan CPU State", action="store_true")
    parser.add_argument("-m", "--MicroWhirlwind", help="Test microWW drivers", action="store_true")

    args = parser.parse_args()

    tests = 0
    stop = False
    is31_U1 = None
    is31_U5 = None
    is31_U2 = None
    tca84_0 = None
    tca84_1 = None

    cb = wwinfra.ConstWWbitClass()
    cb.cpu = localCpuClass()
    cb.cpu.cm = wwinfra.CorememClass(cb)
    cb.log = wwinfra.LogFactory().getLog (quiet=False, no_warn=args.NoWarnings)

    pwr_ctl = PwrCtlClass(cb.log)
    # not much can happen if we can't initialize the i2c bus...
    i2c_bus = I2C(1)
    bus = i2c_bus.bus
    gp_sw = gpio_switches(cb.log)  # these are the switches and LEDs on Rainer's "Tap Board"
    md = None
    sw = None
    mWW = None

    if args.Verbose:
        Verbose = True

    if args.Delay:  # set the length of the delay time for each test step
        delay = float(args.Delay)
    else:
        delay = 0.04  # seconds

    if args.NoPowerControl is False:
        pwr_ctl.pwr_on()
        time.sleep(0.3)

    # Hack
    # args.U1_LED_Mux_Loop = True

    if args.SMBus_Loop:
        tests +=1

    if args.U1_LED_Mux_Loop:
        is31_U1 = Is31(cb.log, i2c_bus, IS31_1_ADDR_U1, u1_brightness)
        tests += 1

    if args.U5_LED_Mux_Loop:
        is31_U5 = Is31(cb.log, i2c_bus, IS31_1_ADDR_U5, u5_brightness)
        tests += 1

    if args.U2_LED_Mux_Loop:
        is31_U2 = Is31(cb.log, i2c_bus, IS31_1_ADDR_U2, u2_brightness)
        tests += 1

    if args.Key_0_Scan:
        tca84_0 = tc_init_u3(cb.log, bus, TCA8414_0_ADDR)
        tests += 1

    if args.Key_1_Scan:
        tca84_1 = tc_init_u4(cb.log, bus, TCA8414_1_ADDR)
        tests += 1

    # These test options don't need specific intialization
    if args.PowerControl_Loop or args.GPIO_Switches:
        tests += 1

    if args.LED_Mapped:
        md = MappedDisplayTestDriverClass(cb.log, i2c_bus)
        tests += 1

    if args.SW_Mapped:
        md = MappedDisplayTestDriverClass(cb.log, i2c_bus)
        sw = MappedSwitchClass(cb.log, i2c_bus, md)
        tests += 1

    if args.MicroWhirlwind:
        mWW = control_panel.PanelClass(cb.log, None, panel_microWW=True)
        tests += 1



    if tests == 0:
        print("no tests?")
        exit(1)

    led_pattern = 1    # default is one-hot
    if args.P0_wave:
        led_pattern = 0
    if args.P1_hot:
        led_pattern = 1
    if args.P2H_blink:
        try:
            register = int(args.P2H_blink, 16)
        except ValueError:
            register = 0
            print("can't decode hex num %s" % args.P2H_blink)
        led_pattern = 2 | (register << 4)
    if args.P3V_blink:
        try:
            register = int(args.P3V_blink, 16)
        except ValueError:
            register = 0
            print("can't decode hex num %s" % args.P3V_blink)
        led_pattern = 3 | (register << 4)



    while not stop:
        if args.PowerControl_Loop:
            pwr_ctl.step()
        if args.SMBus_Loop:
            i2c_bus.i2c_reg_test(args.SMBus_Loop)
        if args.U1_LED_Mux_Loop:
            is31_U1.step(delay, led_pattern)
        if args.U5_LED_Mux_Loop:
            is31_U5.step(delay, led_pattern)
        if args.U2_LED_Mux_Loop:
            is31_U2.step(delay, led_pattern)
        if args.Key_0_Scan:
            run_tca(tca84_0)
        if args.Key_1_Scan:
            run_tca(tca84_1)
        if args.GPIO_Switches:
            gp_sw.step(delay)
        if args.LED_Mapped:
            md.step(delay)
        if args.SW_Mapped:
            sw.check_buttons()
        if args.MicroWhirlwind:
            mWW.update_panel(cb, 0, 0, True)
            mWW.write_register("FF02Sw", 0o55)
            val = mWW.read_register("FF02Sw")
            print("read back value for FF2 Preset = 0o%o" % val)
            stop = True
        #           run_pong(is31_U2)
        PassCount += 1
        # print("%05d" % PassCount)

    input("CR to Shutdown")
    # is31.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_SHUTDOWN, val=0x00)
    time.sleep(1)

""" 
class BlinkenLights:
    def __init__(self):
        print("I2C init: ")
        # bus = I2Cclass(channel = 1)
        self.i2c_bus = smbus2.SMBus(1)
        print("  done")

        self.is31_U5 = IS31FL3731(self.i2c_bus, IS31_1_ADDR)
        print("I2C Test")
        # is31.i2c_reg_test()
        self.is31_1.init_IS31()
        print("  IS31 init done")

    def update_panel(self, cb, bank, alarm_state=0, standalone=False, init_PC=None):
        cpu = cb.cpu
        lights = []
        lights.append(cpu.PC)
        lights.append(cpu._AC)
        lights.append(cpu._BReg)
        self.is31_1.write_16bit_led_rows(0, lights)
"""


if __name__ == "__main__":
    main()
