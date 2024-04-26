

# Copyright 2024 Guy C. Fedorkow
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

# Support routines for simulating the Whirlwind instruction set,
# based on Whirlwind Instruction Set Manual 2M-0277
# g fedorkow, Dec 30, 2017


import re
import hashlib
import sys
import analog_scope
import control_panel
import os
from screeninfo import get_monitors

from typing import List, Dict, Tuple, Sequence, Union, Any



def breakp():
    print("** Breakpoint **")

# sigh, I'll put this stub here so I can call Read Core without more special cases.
# the simulator has a much larger CpuClass definition which would override this one
# But due to lack of partitioning skill, several other of my ww programs need a stub
class CpuClass:
    def __init__(self, cb, core_mem):
        self.cb = cb
        # putting this stuff here seems pretty darn hacky
        self.cpu_switches = None
        self.SymTab = {}
        self.ExecTab = {}
        self.CommentTab = [None] * 2048
        self.cm = core_mem


class LogClass:
    def __init__(self, program_name, quiet: bool = None, debug556: bool = None, debugtap: bool = None,
                 debugldr: bool = None, debug7ch: bool = None, debug: bool = None):
        self._debug = debug
        self._debug556 = debug556
        self._debug7ch = debug7ch
        self._debugtap = debugtap
        self._debugldr = debugldr
        self._quiet = quiet
        self._program_name = program_name
        self.error_count = 0

    def log(self, message):  # unconditionally log a message
        print("Log: %s" % message)

    def debug(self, message):
        if self._debug:
            print("Debug: %s" % message)

    def debug7ch(self, message):
        if self._debug7ch:
            print("Debug 7ch: %s" % message)

    def debug556(self, message):
        if self._debug556:
            print("Debug 556: %s" % message)

    def debugldr(self, message):
        if self._debugldr:
            print("Debug Loader: %s" % message)

    def debugtap(self, message):
        if self._debugtap:
            print("Debug TAP: %s" % message)

    # the log-class "error" is specifically meant for error messages from the assembler
    # or similar tools, which report findings that are not fatal, but should be counted
    # and identified in an input file as 'input errors'.
    def error(self, line_number, message):
        print("Line %d: %s" % (line_number, message))
        self.error_count += 1

    def info(self, message):
        if not self._quiet:
            print("Info: %s" % message)

    def warn(self, message):
        print("Warning: %s" % message)

    def fatal(self, message):
        print("Fatal: %s" % message)
        sys.exit(1)


# simple routine to print an octal number that might be 'None'
def octal_or_none(number):
    ret = " None "
    if number is not None:
        ret = "0o%06o" % number
    return ret

# This class is used to hold Python Vars that can be viewed and modified via the on-screen Debug Widget
# at sim run time
class DebugWidgetPyVarsClass:
    def __init__(self, cb):
        if cb.radar:
            self.TargetHeading = cb.radar.adjust_target_heading



class ConstWWbitClass:
    def __init__(self, args=None, get_screen_size=False):
        # This state variable controls whether the simulator simply moves ahead to execute
        # each instruction, or if it pauses to wait for a person to click a button (or run single-step).
        self.SIM_STATE_STOP = 0
        self.SIM_STATE_RUN = 1
        self.SIM_STATE_SINGLE_STEP = 2
        self.sim_state = self.SIM_STATE_STOP

        # Caution -- Whirlwind puts bit 0 to the left (Big Endian, no?)
        self.WWBIT0 = 0o100000
        self.WWBIT1 = 0o040000
        self.WWBIT5 = 0o02000   # Bit 5 is the most-significant bit of the address field
        self.WWBIT6 = 0o01000   # this is Bit 6 starting from Zero on the left in a 16-bit word
        self.WWBIT7 = 0o00400
        self.WWBIT8 = 0o00200
        self.WWBIT9 = 0o00100
        self.WWBIT10_12 = 0o00070  # used in CF instruction
        self.WWBIT13_15 = 0o00007
        self.WWBIT6_15 = 0o01777  # half the address space, used in mem bank decode
        self.WW_ADDR_MASK = 0o03777

        self.WWBIT1_15 = 0o077777
        self.WWBIT0_15 = 0o177777
        self.WWBIT0_14 = 0o177776
        self.WW_MODULO = self.WWBIT0 << 1

        self.pyBIT30 = (1 << 30)  # little-endian bits for concatenated AC and BR

        self.pyBIT30 = (1 << 30)  # little-endian bits for concatenated AC and BR
        self.pyBIT15 = (1 << 15)  # little-endian bits for concatenated AC and BR
        self.pyBIT15_0 = 0x0000FFFF  # I can't count that many octal digits
        self.pyBIT29_0 = 0x3FFFFFFF  # I can't count that many octal digits
        self.pyBIT31_0 = 0xFFFFFFFF  # I can't count that many octal digits

        self.CORE_SIZE = 2048

        self.SHIFT_RIGHT = 1
        self.SHIFT_LEFT = 2

        # Instruction execution would screech to a halt if any of the various alarms went off
        # The first few are defined by the instruction set

        self.NO_ALARM = 0
        self.OVERFLOW_ALARM = 1
        # Then there are some synthetic alarms I've added as part of the sim
        self.UNIMPLEMENTED_ALARM = 2       # hit an unimplemented instruction
        self.READ_BEFORE_WRITE_ALARM = 3   # tried to operate on a "none" operand, i.e., uninitualized memory
        self.UNKNOWN_IO_DEVICE_ALARM = 4   # hit an unimplemented I/O Device
        self.HALT_ALARM = 5                # hit a "halt" instruction, aka "si 0" or "si 1"
        self.CHECK_ALARM = 6               # alarm if the machine fails a Check instruction
        self.QUIT_ALARM = 7                # synthetic alarm to stop the sim
        self.IO_ERROR_ALARM = 8  # guy's alarm for an instruction that tries to read beyond the end of tape media
        self.DIVIDE_ALARM = 9    # a real alarm for an overflow in Divide

        self.AlarmMessage = {self.NO_ALARM: "No Alarm",
                             self.OVERFLOW_ALARM: "Overflow Alarm",
                             self.UNIMPLEMENTED_ALARM: "Unimplemented Instruction",
                             self.READ_BEFORE_WRITE_ALARM: "Operation on Uninitialized Variable",
                             self.UNKNOWN_IO_DEVICE_ALARM: "Unknown I/O Device",
                             self.HALT_ALARM: "Program Halt",
                             self.CHECK_ALARM: "Check Instruction Alarm",
                             self.QUIT_ALARM: "Quit Simulation",
                             self.IO_ERROR_ALARM: "I/O Error Alarm",
                             self.DIVIDE_ALARM: "Divide Error Alarm",
                             }

        self.COLOR_BR = "\033[93m"  # Yellow color code for Branch Instructions in console trace if color_trace is True
        self.COLOR_IO = "\033[92m"  # Green color code for I/O Instructions
        self.COLOR_CF = "\033[96m"  # Cyan color code for CF Instruction
        self.COLOR_default = "\033[0m"  # Reset to default color

        # Some programs use two separate scopes; these constants identify which one to use
        # 2M-0277 says that this number selects one of "256" select lines (which must actually be 64, 'cause it's
        # six bits) and then switches determine which scope is hooked to which combination of Select lines.
        self.SCOPE_MAIN = 1
        self.SCOPE_AUX  = 2  # aka "F Scope"

        # configure the displays
        self.analog_display = False   # set this flag to display on an analog oscilloscope instead of an x-window
        self.use_x_win = True         # clear this flag to completely turn off the xwin display, widgets and all
        self.ana_scope = None   # this is a handle to the methods for operating the analog scope
        self.argAutoClick = False
        if args and args.AutoClick:
            self.argAutoClick = True
        self.panel = None
        if args and args.Panel:
            self.panel = control_panel.PanelClass()

        # use these vars to control how much Helpful Stuff emerges from the sim
        self.color_trace = True
        self.museum_mode = None  # command line switch to enable a repeating demo mode.
        self.slow_execution_demo_mode = False  # When True, this flag makes the graphics a bit more visible
        if get_screen_size:
            (self.screen_x, self.screen_y, self.gfx_scale_factor) = self.get_display_size()
        self.TracePC = 0        # print a line for each instruction if this number is non-zero; decrement it if pos.
        self.LongTraceFormat = True  # prints more CPU registers for each trace line
        self.TraceALU = False   # print a line for add, multiply, negate, etc
        self.TraceBranch = True  # print a line for each branch
        self.TraceQuiet = False
        self.tracelog = None     # set this to a value if we're supposed to keep logs for a flow graph
        self.decimal_addresses = False  # default is to print all addresses in Octal; this switches to decimal notation
        self.TraceCoreLocation = None
        self.NoZeroOneTSR = False
        self.TraceDisplayScope = False
        self.PETRAfilename = None
        self.PETRBfilename = None
        self.CoreFileName = None
        self.log = None
        self.cpu = None

        self.dbwgt = None  # This list gives all the currently active Debug Widgets
        self.DebugWidgetPyVars = None   # this class links up the Python-based debug widget methods, it any

        self.host_os = os.getenv("OS")
        self.crt_fade_delay_param = 0
        self.radar = None   # set this if we're doing a radar-style display
        self.no_toggle_switch_warn = False  # Apologies for the double-negative, but the warning should normally
                                            # be issued if code tries to write to a TSR.

        self.OPERAND_JUMP = 0  # the address is a jump target
        self.OPERAND_WR_DATA = 1  # the address writes a data word to Core
        self.OPERAND_RD_DATA = 2  # the address writes a data word from Core
        self.OPERAND_PARAM = 3  # the operand isn't an address at all
        self.OPERAND_UNUSED = 4  # the operand is unused; convert it into a .word
        self.op_code = [
            ["si", "select input", self.OPERAND_PARAM],  # 0
            [".word", "<unused>", self.OPERAND_UNUSED],  # 1  # unused op code
            ["bi", "block transfer in", self.OPERAND_WR_DATA],  # 2
            ["rd", "read", self.OPERAND_PARAM],  # 3
            ["bo", "block transfer out", self.OPERAND_RD_DATA],  # 4
            ["rc", "record", self.OPERAND_PARAM],  # 5
            ["sd", "sum digits - XOR", self.OPERAND_RD_DATA],  # 6
            ["cf", "change fields", self.OPERAND_PARAM],  # 7
            ["ts", "transfer to storage", self.OPERAND_WR_DATA],  # 10o, 8d
            ["td", "transfer digits", self.OPERAND_WR_DATA],  # 11o, 9d
            ["ta", "transfer address", self.OPERAND_WR_DATA],  # 12o, 10d
            ["ck", "check", self.OPERAND_RD_DATA],  # 13o, 11d
            ["ab", "add B-Reg", self.OPERAND_WR_DATA],  # 14o, 12d
            ["ex", "exchange", self.OPERAND_WR_DATA],  # 15o, 13d
            ["cp", "conditional program", self.OPERAND_JUMP],  # 16o, 14d
            ["sp", "sub-program", self.OPERAND_JUMP],  # 17o, 15d
            ["ca", "clear and add", self.OPERAND_RD_DATA],  # 20o, 16d
            ["cs", "clear and subtract", self.OPERAND_RD_DATA],  # 21o, 17d
            ["ad", "add", self.OPERAND_RD_DATA],  # 22o, 18d
            ["su", "subtract", self.OPERAND_RD_DATA],  # 23o, 19d
            ["cm", "clear and add magnitude", self.OPERAND_RD_DATA],  # 24o, 20d
            ["sa", "special add", self.OPERAND_RD_DATA],  # 25o, 21d
            ["ao", "add one", self.OPERAND_RD_DATA],  # 26o, 22d
            ["dm", "difference of magnitudes", self.OPERAND_RD_DATA],  # 27o, 23d
            ["mr", "multiply and roundoff", self.OPERAND_RD_DATA],  # 30o, 24d
            ["mh", "multiply and hold", self.OPERAND_RD_DATA],  # 31o, 25d
            ["dv", "divide", self.OPERAND_RD_DATA],  # 32o, 26d
            ["SL", "SL", self.OPERAND_PARAM],  # 33o, 27d
            ["SR", "SR", self.OPERAND_PARAM],  # 34o, 28d
            ["sf", "scale factor", self.OPERAND_WR_DATA],  # 35o, 29d
            ["CL", "CL", self.OPERAND_PARAM],  # 36o, 30d
            ["md", "multiply digits no roundoff (AND)", self.OPERAND_RD_DATA]  # 37o, 31d aka "AND"
        ]
        # I/O addresses.  I've put them here so the disassembler can identify I/O devices using this shared module.
        self.PTR_BASE_ADDRESS = 0o200  # starting address of mechanical paper tape reader
        self.PTR_ADDR_MASK = ~0o003  # sub-addresses cover PETR-A and PETR-B, word-by-word vs char-by-char
        self.PETR_BASE_ADDRESS = 0o210  # starting address of PETR device(s)
        self.PETR_ADDR_MASK = ~0o003  # sub-addresses cover PETR-A and PETR-B, word-by-word vs char-by-char

        self.CLEAR_BASE_ADDRESS = 0o17  # starting address of memory-clear device(s)
        self.CLEAR_ADDR_MASK = ~0000  # there aren't any sub-addresses

        self.FFCLEAR_BASE_ADDRESS = 0o10  # device address for reloading FF Regs from switches(s)
        self.FFCLEAR_ADDR_MASK = ~0000  # there aren't any sub-addresses

        self.DRUM_BASE_ADDRESS = 0o700  # starting address of Drum device(s)
        self.DRUM_ADDR_MASK = ~0o1017  # mask out the sub-addresses
        self.DRUM_SWITCH_FIELD_ADDRESS = 0o734

        self.DISPLAY_POINTS_BASE_ADDRESS = 0o0600   # starting address of point display
        self.DISPLAY_POINTS_ADDR_MASK = ~0o077    # mask out the sub-addresses
        self.DISPLAY_VECTORS_BASE_ADDRESS = 0o1600  # starting address of vector display
        self.DISPLAY_VECTORS_ADDR_MASK = ~0o077   # mask out the sub-addresses
        self.DISPLAY_CHARACTERS_BASE_ADDRESS = 0o2600  # starting address of vector display
        self.DISPLAY_CHARACTERS_ADDR_MASK = ~0o1077  # mask out the sub-addresses
        self.DISPLAY_EXPAND_BASE_ADDRESS = 0o0014   # starting address of vector display
        self.DISPLAY_EXPAND_ADDR_MASK = ~0o001    # mask out the sub-addresses

        self.INTERVENTION_BASE_ADDRESS = 0o300  # starting address of Intervention and Activate device(s)
        self.INTERVENTION_ADDR_MASK = ~0o037  # mask out the sub-addresses

        # the following are here to stake out territory, but I don't have drivers yet
        self.MAG_TAPE_BASE_ADDRESS = 0o100       # block of four mag tape drives
        self.MAG_TAPE_ADDR_MASK = ~0o77

        self.MECH_PAPER_TAPE_BASE_ADDRESS = 0o200  # starting address of mechanical Flexo paper tape device(s)
        self.MECH_PAPER_TAPE_ADDR_MASK = ~0o003

        self.PUNCH_BASE_ADDRESS = 0o204       # paper tape punch
        self.PUNCH_ADDR_MASK = ~0o03

        self.PRINTER_BASE_ADDRESS = 0o225     # Flexowriter
        self.ANELEX_BASE_ADDRESS = 0o244      # Anelex line printer
        self.ANELEX_ADDR_MASK = ~0o01

        self.TELETYPE_BASE_ADDRESS = 0o402

        self.INDICATOR_LIGHT_BASE_ADDRESS = 0o510       # ?
        self.INDICATOR_LIGHT_ADDR_MASK = ~0o07

        self.IN_OUT_CHECK_BASE_ADDRESS = 0o500       # ?
        self.IN_OUT_CHECK_ADDR_MASK = ~0o07

        self.CAMERA_INDEX_BASE_ADDRESS = 0o04   # one address that advances the film in the camera one frame

        self.DevNameDecoder = [
            ((self.CLEAR_BASE_ADDRESS, self.CLEAR_ADDR_MASK), "Memory-Clear Device"),
            ((self.INTERVENTION_BASE_ADDRESS, self.INTERVENTION_ADDR_MASK), "Intervention and Activate Device"),
            ((self.PETR_BASE_ADDRESS, self.PETR_ADDR_MASK), "PhotoElectric Reader"),
            ((self.DRUM_BASE_ADDRESS, self.DRUM_ADDR_MASK), "Storage Drum"),
            ((self.DRUM_SWITCH_FIELD_ADDRESS, ~0), "Storage Drum Switch Field"),

            ((self.DISPLAY_POINTS_BASE_ADDRESS, self.DISPLAY_POINTS_ADDR_MASK), "Display Points"),
            ((self.DISPLAY_VECTORS_BASE_ADDRESS, self.DISPLAY_VECTORS_ADDR_MASK), "Display Vectors"),
            ((self.DISPLAY_CHARACTERS_BASE_ADDRESS, self.DISPLAY_CHARACTERS_ADDR_MASK), "Display Characters"),
            ((self.DISPLAY_EXPAND_BASE_ADDRESS, self.DISPLAY_EXPAND_ADDR_MASK), "Expand Display"),

            ((self.MAG_TAPE_BASE_ADDRESS, self.MAG_TAPE_ADDR_MASK), "Magnetic Tape"),
            ((self.MECH_PAPER_TAPE_BASE_ADDRESS, self.MECH_PAPER_TAPE_ADDR_MASK), "Mechanical Paper Tape Reader"),
            ((self.PUNCH_BASE_ADDRESS, self.PUNCH_ADDR_MASK), "Paper Tape Punch"),
            ((self.PRINTER_BASE_ADDRESS, ~0), "FlexoPrinter"),
            ((self.ANELEX_BASE_ADDRESS, self.ANELEX_ADDR_MASK), "Anelex Line Printer"),
            ((self.TELETYPE_BASE_ADDRESS, ~0), "Teletype"),
            ((self.INDICATOR_LIGHT_BASE_ADDRESS, self.INDICATOR_LIGHT_ADDR_MASK), "Indicator Light Registers"),
            ((self.IN_OUT_CHECK_BASE_ADDRESS, self.IN_OUT_CHECK_ADDR_MASK), "In-Out Check Registers"),
            ((self.CAMERA_INDEX_BASE_ADDRESS, ~0), "Camera Index"),
        ]


    def Decode_IO(self, io_address):
        devname = ''
        addr_info = (0, 0)
        for d in self.DevNameDecoder:
            addr_info = d[0]
            addr_base = addr_info[0]
            addr_mask = addr_info[1]
            if (io_address & addr_mask) == addr_base:
                devname = d[1]
        #            print "device-place-holder base=%o, mask=%o, name=%s" % (addr_info[0], ~addr_info[1], devname)
        if devname != '':
            ret = "Device %s base=0o%o, mask=0o%o" % (devname, addr_info[0], ~addr_info[1])
        else:
            ret = "Unknown Device"
        return ret


    # read the size of the display itself from Windows
    def get_display_size(self):
        # default to the dimensions for my surface pro built-in screen
        # The OS reports a kinda useless number when there's an external monitor plugged in
        self.screen_x = 1372
        self.screen_y = 893

        # Cygwin depends on the xwin DISPLAY var; if it's not there, there's no point in
        # asking about screens
        display = self.use_x_win and os.getenv("DISPLAY")
        if display:
            screens = get_monitors()
            for s in screens:
                # print(s)
                if s.is_primary:
                    self.screen_x = s.width
                    self.screen_y = s.height

        # there must be a cleaner way of finding what scale-factor the OS is using
        # As a heuristic, if it's bigger than 1280x800, it's probably hi-res, probably 200%
        self.gfx_scale_factor = 1.0
        if self.screen_x > 1400:
            self.gfx_scale_factor = 2.0

        # (screen_x, screen_y) = win.master.maxsize()
        # print("screen size: %d by %d, scale=%d" % (self.screen_x, self.screen_y, self.gfx_scale_factor))

        return(self.screen_x, self.screen_y, self.gfx_scale_factor)

    def int_str(self, n):   # convert an int address to a string in either Octal or Decimal notation
        if self.decimal_addresses:
            return "%03d" % n
        else:
            return "0o%04o" % n

    def Decode_IO(self, io_address):
        devname = "unknown i/o device"
        for d in self.DevNameDecoder:
            addr_info = d[0]
            addr_base = addr_info[0]
            addr_mask = addr_info[1]
            if (io_address & addr_mask) == addr_base:
                devname = d[1]
    #            print "device-place-holder base=%o, mask=%o, name=%s" % (addr_info[0], ~addr_info[1], devname)
        return devname


class WWSwitchClass:
    def __init__(self, cb):
        self.cb = cb
        # I modified this routine to accept any Flip Flop Preset Switch as a directive
        #  FF Presets are numbered by the address at which they appear
        # I actually don't know what they configured to tell which of the five FF Reg's showed up at which address...
        # Modified Jan 2024 to support PanelClass().
        #   Part of that modification was (for better or worse) naming the switches and registers inside the simulator
        # with shorter names that the Assembler uses, basically to reduce typing.  This is done by adding an "internal
        # name" field to the dictionary below...
        self.SwitchNameDict = {
            # name: [default_val, mask, internal_name]
            "CheckAlarmSpecial": [0, 0o01, None],  # Controls the behavior of the CK instruction; see 2M-0277
                                             # "normal" is 'off'
            "LeftInterventionReg":  [0, 0xffff, "LMIR"],   # Left Manual Intervention Register - aka LMIR
            "RightInterventionReg": [0, 0xffff, "RMIR"],  # Right Manual Intervention Register - aka RMIR
            "ActivationReg0":       [0, 0xffff, "ActivationReg0"],  #
            "ActivationReg1":       [0, 0xffff, "ActivationReg1"],  #
        }
        for s in range(2, 32):
            name = "FlipFlopPreset%02o" % s
            self.SwitchNameDict[name] = [None, 0xffff, "FF%02oSw" % s]

    # The five Flip Flop Registers could be assigned to different locations in the lower
    # 32 words of the address space.  I can't imagine why they did that, and I haven't found
    # any clues as to how it was done.  Early in the program, the assignments seemed to change
    # for each program, but by later on, there were commonly-used defaults.
    #  In the simulator, the toggle switches are enforced as read-only, as it seems that some
    # programs write to read-only TSRs, knowing the write will be ignored.  But of course the FF's
    # must be read-write.
    # This oddball bit of config allows wwsim's compiled-in FF assignments to be overwritten.
    # The argument is a comma-separated list of small octal numbers identifying which addresses
    # should be treated as Writable.
    # Note that the calling parser has already split the incoming string on white-space boundaries,
    # so I'm actually gluing the arg list back together into one unit with no white space before
    # splitting again on commas.
    #   Experiment:  I'm trying to call this same routine from the assembler and sim, to avoid
    # writing the parser twice...  If this works, it might be possible to share more stuff.
    # So the routine returns an array of True/False for the sim, and a cleaned and validated
    # arg list for the assembler
    def parse_ff_reg_assignment(self, name, args):
        ffreg_str = ''
        validated_str = ''
        for arg in args:
            ffreg_str += arg
        ffreg_list = ffreg_str.split(',')

        write_protect_list = [True] * 32   # default is that all 32 words are write-protected, i.e. toggle switches
        mask = 0o37
        for ffreg in ffreg_list:
            ffreg = re.sub('^0o', '', ffreg)   # assume it's octal; everything else in a .core file is
            try:
                val = int(ffreg, 8)
            except:
                self.cb.log.warn((".SWITCH %s setting %s must be an octal number" % (name, ffreg)))
                return None, ''
            if (~mask & val) != 0:
                self.cb.log.warn(("max value for switch %s is 0o%o, got 0o%o" % (name, mask, val)))
                return None, ''
            if len(validated_str) != 0:
                validated_str += ','   # make a new comma-separated list
            validated_str += "0o%o" % val
            write_protect_list[val] = False
        return write_protect_list, validated_str


    def parse_switch_directive(self, args):    # return one for error, zero for ok.
        if args[0] == "FFRegAssign":  # special case syntax for assigning FF Register addresses
            args.append('')   # cheap trick; add a null on the end to make sure the next statement doesn't trap
            write_protect_list, ffreg_str = self.parse_ff_reg_assignment(args[0], args[1:])
            if write_protect_list is None:
                return 1
            self.cb.cpu.cm.set_ff_reg_mask(write_protect_list)
            self.cb.log.info("Assigning Flip Flop Registers to addresses: %s" % ffreg_str)
            return 0

        if len(args) != 2:
            self.cb.log.warn("Switch Setting: expected <name> <val>, got: ")
            print(args)
            return 1

        name = args[0]
        if name not in self.SwitchNameDict:
            self.cb.log.warn(("No machine switch named %s" % name))
            return 1

        try:
            val = int(args[1], 8)
        except:
            self.cb.log.warn((".SWITCH %s setting %s must be an octal number" % (name, args[1])))
            return 1
        mask = self.SwitchNameDict[name][1]
        panel_name = self.SwitchNameDict[name][2]
        if (~mask & val) != 0:
            self.cb.log.warn(("max value for switch %s is 0o%o, got 0o%o" % (name, mask, val)))
            return 1
        self.SwitchNameDict[name][0] = val
        if self.cb.panel:
            self.cb.panel.write_register(panel_name, val)
        self.cb.log.info((".SWITCH %s (%s) set to 0o%o" % (name, panel_name, val)))
        return 0

    def read_switch(self, name):
        if name in self.SwitchNameDict:
            if self.cb.panel and name in self.SwitchNameDict and self.SwitchNameDict[name][2]:
                # call the Panel object to read switches, should it be present, and if it's a switch
                # that's represented on the panel.  Use the internal name string (i.e., offset 2 in the dict)
                ret = self.cb.panel.read_register(self.SwitchNameDict[name][2])
                return ret
            else:
                return self.SwitchNameDict[name][0]
        return None

# collect a histogram of opcode frequency
class OpCodeHistogram:
    def __init__(self, cb):

        self.opcode_width = 5
        self.opcode_shift = 16 - self.opcode_width
        self.opcode_mask = (2 ** self.opcode_width) - 1
        self.opcode_histogram = [0] * (self.opcode_mask + 1)
        self.io_opcode_histogram = {}
        self.cb = cb
        # the following distribution was measured from about 30,000 instructions of WW code
        self.basline_op_histogram = [0.31739999, 0.00640848, 0.00962659, 0.00679687, 0.00560395, 0.01253953,
                                     0.00405038, 0.00521556, 0.07221328, 0.03121012, 0.01475892, 0.00305166,
                                     0.00579815, 0.00923820, 0.04413805, 0.10955446, 0.11732231, 0.01445375,
                                     0.06522222, 0.02008545, 0.00463297, 0.00307940, 0.02186096, 0.00957110,
                                     0.00493813, 0.00546524, 0.00188648, 0.00707429, 0.00887755, 0.00205293,
                                     0.02424680, 0.03162626, ]
        self.local_histogram = False  # set this to compute the opcode histogram of each core image
        #                               ... False means to compute a global histogram over all likely code
        self.init_opcode_histogram()

    def init_opcode_histogram(self):
        for d in self.cb.DevNameDecoder:
            io_info = d[1]
            self.io_opcode_histogram[io_info] = 0
        self.io_opcode_histogram['unknown i/o device'] = 0

    def collect_histogram(self, corelist, for_sure_code):
        # scan the current sequence of memory blocks to collect a histogram of op-codes
        # We compute a baseline over all the modules that are likely to be code
        # return the total length of the core image
        core_len = 0
        if self.local_histogram is True:  # if we're making histograms for each file, reset this var with each call.
            self.opcode_histogram = [0] * (self.opcode_mask + 1)
            self.init_opcode_histogram()
        else:
            if for_sure_code is False:
                return 0

        for core in corelist:
            for wrd in core:
                if wrd is not None:
                    bucket = wrd >> self.opcode_shift & self.opcode_mask
                    self.opcode_histogram[bucket] += 1
                    core_len += 1
                    if bucket == 0 and wrd != 0:  # yeah, ok, op zero is the SI instruction, but all-zero is a halt
                        self.collect_io_op_histogram(wrd)
        return core_len

    def normalize_histogram(self):
        histogram_result = [0.0] * (self.opcode_mask + 1)
        total = 0

        for i in range(0, self.opcode_mask + 1):
            total += self.opcode_histogram[i]

        for i in range(0, self.opcode_mask + 1):
            histogram_result[i] = float(self.opcode_histogram[i]) / float(total)

        return histogram_result

    def figure_hist_covariance(self, sample):
        cov = None
        hist_sum = 0.0
        for i in range(0, self.opcode_mask + 1):
            diff = (sample[i] - self.basline_op_histogram[i]) ** 2
            hist_sum += diff

        cov = hist_sum / float(self.opcode_mask + 1)
        return cov

    def collect_io_op_histogram(self, word):
        addr = word & self.cb.WW_ADDR_MASK
        io_op_name = self.cb.Decode_IO(addr)
        if io_op_name is not None:
            self.io_opcode_histogram[io_op_name] += 1
#            op_name += ' ' + io_op_name

    def summarize_io_histogram(self):
        display_count = 0
        ret = ''
        for i in self.io_opcode_histogram:
            if "Display" in i:
                display_count += self.io_opcode_histogram[i]
        if display_count != 0:
            ret = "Display-Ops, %d, " % display_count
        return ret


# CoreReadBy           = [[] for _ in xrange(CORE_SIZE)]
# WW ended up with 6K words of memory, but a 2K word address space.  Overlays and bank
# switching were the order of the day
# The address space was divided into a high group and low group, each of which could
# be mapped to one of six 1K word pages.
# Mapping is controlled by the CF instruction
# I added a hack Jul 19, 2019 to print a warning and return zero for reading uninitialized memory
# the hack for mapping default switch values or not needs to be cleaned.
class CorememClass:
    def __init__(self, cb, use_default_tsr=True):
        # the following array defines the contents of "Test Storage", or toggle switch memory.
        # The first value is the initial setting for each of the 32 locations
        # the second value says if the location has been configured to replace a switch register
        # with a flip-flop (read-write) location, of which there can be no more than 5.  "True"
        # means the location is Read-Only.
        # Here are the presets from the switch diagnostic t02_gs007_fbl00-0-7l.tcore
        # 06 reads 0.00000        should read 0.l4l74
        # 08 reads 0.00000        should read l.30007
        # 09 reads 0.00000        should read l.30003
        # l0 reads 0.00000        should read l.50006
        # ll reads 0.00000        should read 0.40024
        # l2 reads 0.00000        should read 0.50002
        # l3 reads 0.00000        should read l.30024
        # l4 reads 0.00000        should read 0.00337
        # l5 reads 0.00000        should read 0.l4000
        # l6 reads 0.00000        should read l.34003
        # l7 reads 0.00000        should read 0.7000l
        # l8 reads 0.00000        should read 0.74002
        # l9 reads 0.00000        should read 0.40024
        # 2l reads 0.00000        should read 0.74007
        # 22 reads 0.00000        should read l.44036
        # 23 reads 0.00000        should read l.04023
        # 24 reads 0.00000        should read 0.74036
        # 25 reads 0.00000        should read 0.50003
        # 26 reads 0.00000        should read l.00032
        # 27 reads 0.00000        should read 0.00707
        # 28 reads 0.00000        should read 0.20032
        # 29 reads 0.00000        should read l.l0026
        # 30 reads 0.00000        should read 0.00703
        # 3l reads 0.00000        should read 0.l0036

        # the first 32 memory locations are "Toggle Switch Storage", a manually-programmed "ROM" with five RAM locations
        self._toggle_switch_mask = 0o37
        self._toggle_switch_mem_default =\
            [[0o000000,  True], [0o000001,  True], [0o000000, False], [0o000000, False],  # 0d
             [0o100065,  True], [0o000000, False], [0o014174,  True], [0o000000, False],  # 4d
             [0o130007,  True], [0o130003,  True], [0o150006,  True], [0o040024,  True],  # 8d
             [0o050002,  True], [0o130024,  True], [0o000337,  True], [0o014000,  True],  # 12d
             [0o134003,  True], [0o070001,  True], [0o074002,  True], [0o040024,  True],  # 16d
             [0o000000, False], [0o074007,  True], [0o144036,  True], [0o104023,  True],  # 20d
             [0o074036,  True], [0o050003,  True], [0o100032,  True], [0o000707,  True],  # 24d
             [0o020032,  True], [0o110026,  True], [0o000703,  True], [0o010036,  True],  # 28d
             ]

        self.cb = cb
        self.NBANKS = 6  # six 1K banks
        self.use_default_tsr = use_default_tsr

        self.clear_mem()  # this call instantiates the memory banks themselves
        # self._coremem = []
        # for _i in range(self.NBANKS):
        #     self._coremem.append([None] * (cb.CORE_SIZE // 2))
        # self.MemGroupA = 0  # I think Reset sets logical Group A to point to Physical Bank 0
        # self.MemGroupB = 1  # I *think* Reset sets logical Group B to point to Physical Bank 1
        # if cb.NoZeroOneTSR is False:
        #     self._coremem[0][0] = 0
        #     self._coremem[0][1] = 1
        self.SymTab = None
        self.tsr_callback = [None] * 32
        self.metadata = {}  # a dictionary for holding assorted metadata related to the core image
#        self.metadata_hash = []
#        self.metadata_stats = []
#        self.metadata_goto = None
#        self.metadata_filename_from_core = []
#        self.metadata_ww_tapeid = []
        self.exec_directives = {}  # keep a dictionary of all the python exec directives found in the core file
                                   #   indexed by bank and address
        self.mem_addr_reg = 0       # store the most recent memory access address and data for blinkenlights
        self.mem_data_reg = 0
    # the WR method has two optional args
    # 'force' arg overwrites the "read only" toggle switches
    # 'track' is used only in the case of initializing the drum storage
    def wr(self, addr, val, force=False, track=0):
        self.mem_addr_reg = addr
        self.mem_data_reg = val
        if self.cb.TraceCoreLocation == addr:  # (I bet this var should be stored locally for faster access)
            self.cb.log.log("Write to core memory; addr=0o%05o, value=0o%05o" % (addr, val))
        if (addr & ~self._toggle_switch_mask) == 0 and self.use_default_tsr:   # toggle_switch_mask is a constant 0o37
            if self.tsr_callback[addr] is not None:
                self.tsr_callback[addr](addr, val)  # calling the callback with a non-null value causes a 'write'
            # we have various rules about writes to the Toggle Switch Registers, but if the write would
            # put exactly what's there already right back again, we'll just skip the whole deal and
            # take a victory lap
            else:
                if self._toggle_switch_mem_default[addr][0] != val:
                    if not force and self._toggle_switch_mem_default[addr][1]:
                        if not self.cb.no_toggle_switch_warn:
                            self.cb.log.warn("Can't write a read-only toggle switch at addr=0o%o" % addr)
                        return
                    if force and self._toggle_switch_mem_default[addr][1]:  # issue a warning if it's Read Only
                        self.cb.log.warn("Overwriting a read-only toggle switch at addr=0o%o, was 0o%o, is 0o%o" %
                                         (addr, self._toggle_switch_mem_default[addr][0], val))

                    self.write_ff_reg(addr, val)
        if addr & self.cb.WWBIT5:  # High half of the address space, Group B
            self._coremem[self.MemGroupB][addr & self.cb.WWBIT6_15] = val
        else:
            self._coremem[self.MemGroupA][addr & self.cb.WWBIT6_15] = val


    # memory is filled with None at the start, so read-before-write will cause a trap in my sim.
    #   Some programs don't seem to be too careful about that, so I fixed so most cases just get
    #   a warning, a zero and move on.  But returning a zero to an instruction fetch is not a good idea...
    # I don't know how to tell if the first 32 words of the address space are always test-storage, or if
    # it's only the first 32 words of Bank 0.  I'm assuming test storage is always accessible.
    def rd(self, addr, fix_none=True, skip_mar=False):
        if (addr & ~self._toggle_switch_mask) == 0 and self.use_default_tsr:
            if self.tsr_callback[addr] is not None:
                ret = self.tsr_callback[addr](addr, None)
            else:
                ret = self._toggle_switch_mem_default[addr][0]
            bank = 0
        elif addr & self.cb.WWBIT5:  # High half of the address space, Group B
            ret = self._coremem[self.MemGroupB][addr & self.cb.WWBIT6_15]
            bank = self.MemGroupB
        else:
            ret = self._coremem[self.MemGroupA][addr & self.cb.WWBIT6_15]
            bank = self.MemGroupA
        if fix_none and (ret is None):
            self.cb.log.warn("Reading Uninitialized Memory at location 0o%o, bank %o" % (addr, bank))
            ret = 0
        if self.cb.TraceCoreLocation == addr:
            self.cb.log.log("Read from core memory; addr=0o%05o, value=%s" % (addr, octal_or_none(ret)))
        if not skip_mar:
            self.mem_addr_reg = addr    # save the results for blinkenlights
            self.mem_data_reg = ret     # But _don't_ save when the rd() is from the control panel reading FF reg!
        return ret

    def clear_mem(self):
        self._coremem = []
        for _i in range(self.NBANKS):
            self._coremem.append([None] * (self.cb.CORE_SIZE // 2))
        self.MemGroupA = 0  # I think Reset sets logical Group A to point to Physical Bank 0
        self.MemGroupB = 1  # I *think* Reset sets logical Group B to point to Physical Bank 1
        if self.cb.NoZeroOneTSR is False:
            self._coremem[0][0] = 0
            self._coremem[0][1] = 1


    # entry point to read a core file into 'memory'
    def read_core(self, filename, cpu, cb, file_contents=None):
        return read_core_file(self, filename, cpu, cb, file_contents)


    # call this method to change the default for which Toggle Switch Registers are replaced by
    # Flip Flop Registers.  What this actually does is simply to rearrange the "read-only" bits
    # attached to toggle switches, but not FF Reg's.
    # The arg is a 32-bit binary mask.  In keeping with WW Style, bit Zero is on the left, and
    # influencs Toggle Switch Zero.  Rightmost bit is TSR address 31.
    # a One says Writable.  In the tsr array, a True means Read-only.
    def set_ff_reg_mask(self, write_protect_list):
        for addr in range(0, 32):
            self._toggle_switch_mem_default[addr][1] = write_protect_list[addr]


    # store a new value in a flip-flop reg
    # This is simply updating a table entry unless the Panel Display is enabled, in which
    # case it needs to be updated in two places...
    def write_ff_reg(self, addr, val):
        self._toggle_switch_mem_default[addr][0] = val
        # if self.cb.panel:  #Mar 28, 2024 - I used to "push" ff changes to the panel, but I think it's better
        #    self.cb.panel.write_register(addr, val)    # to "pull" them when updating other registers


    # integration with the Control Panel is kinda crude here...
    def reset_ff(self, cpu):
        reset_info_string = "Reset FF%02o at address 0o%o to %s"
        if self.cb.panel:
            self.cb.panel.reset_ff_registers(self.write_ff_reg, self.cb.log, reset_info_string)

        else:
            for addr in range(0, self._toggle_switch_mask + 1):
                val = cpu.cpu_switches.read_switch("FlipFlopPreset%02o" % addr)
                if val is not None:
                    # [addr][1] is True for Read-only addrs, False for FF Reg
                    if self._toggle_switch_mem_default[addr][1] is True and \
                        self._toggle_switch_mem_default[addr][0] != val:
                        self.cb.log.warn("Resetting 'read-only' toggle-switch register %02o from %o to %o" %
                                         (addr, self._toggle_switch_mem_default[addr][0], val))
                    self.write_ff_reg(addr, val)  # None for switches not found in the core file
                    val_str = "0o%o" % val
                    self.cb.log.info(reset_info_string % (addr, addr, val_str))


    # this callback is here specifically to manage the Light Gun used in the 1952 Track and Scan,
    # when the light gun was hooked into the sign bit of one of the Flip Flop Registers
    def add_tsr_callback(self, cb, address, function):
        if address >= 32:
            cb.log.fatal("Toggle Switch Callback to out-of-bounds address 0o%o" % address)
        self.tsr_callback[address] = function


# input for the simulation comes from a "core" file giving the contents of memory
# Sample core-file input format, from tape-decode or wwasm
# The image file contains symbols as well as a bit of metadata for where it came from
# *** Core Image ***
# @C00210: 0040000 0000100 0000001 0000100 0000000  None    None    None  ; memory load
# @S00202: Yi                                                             ; symbol for location 202
# %Switch: chkalarm 0o5
def read_core_file(cm, filename, cpu, cb, file_contents=None):
    line_number = 1
    jumpto_addr = None
    ww_file = None
    ww_tapeid = "(None)"
    ww_hash = ''
    ww_strings = ''
    ww_stats = ''
    blocknum = 0
    core_word_count = 0
    screen_debug_widgets = []
    isa = "1958"   # assume it's the 1958 instruction set unless there's a directive saying otherwise
    file_type = '?'  # default, assume it's a "core" file, not a tape stream (which would be 'T')

    symtab = {}
    switch_class = cpu.cpu_switches
    commenttab = cpu.CommentTab
    exectab = cpu.ExecTab
    filedesc = None
    address = 0   # for 'tape' / .ocore files, we don't have addresses, so just start at zero

    # note hack for a specialized use when the WW image to be punched is passed in as an array of
    # strings, one string per line, formatted as a core file, not as the name of a file which
    # would contain the same string.
    if file_contents == None:   # This would be the normal case, so we use the file name to open the file.
        try:
            filedesc = open(filename, 'r')
        except IOError:
            cb.log.fatal("read_core: Can't open file %s" % filename)
        cb.log.info("core file %s" % filename)
    else:
        filedesc = file_contents
        cb.log.info("core core_string_array, starting with %s" % file_contents[0])
    # Note at this point, the filedesc might be a pointer to an open file, or it might be a pointer
    # to the head of an array of strings, one per line, representing what would otherwise be a core file.
    for ln in filedesc:
        line = ln.rstrip(' \t\n\r')  # strip trailing blanks and newline
        line_number += 1
        if len(line) == 0:  # skip blank lines
            continue
        if len(line) and line[0] == ';':  # skip comment lines
            continue
        input_minus_comment = line
        if not re.match("^@N|^@C|^@T|^@S|^@E|^%[a-zA-Z]", input_minus_comment):
            cb.log.warn("ignoring line %d: %s" % (line_number, line))
            continue     # ignore anything that doesn't start with:
                         # @C - code, @T - tape-stream, @N - comment, @S - symbol, %<something> - directive

        if re.match("^@C|^@T", input_minus_comment):  # read a line of core memory contents
            if re.match("^@C", input_minus_comment) and file_type == 'T' or \
               re.match("^@T", input_minus_comment) and file_type == 'C':
                cb.log.fatal("how can 'T' and 'C' be in the same file??")
            file_type = input_minus_comment[1]
            tokens = re.split("[: \t][: \t]*", input_minus_comment)
            # print "tokens:", tokens
            if len(tokens[0]) == 0:
                cb.log.warn("read_core parse error, read_core @C/@T: tokens=%s" % tokens)
                continue
            # if it's actually a binary core file, pick up the address from @C or @T
            if re.match("^@C|^@T", input_minus_comment):
                address = int(tokens[0][2:], 8)
            for token in tokens[1:]:
                if token != "None":
                    cm.wr(address, int(token, 8), force=True, track=blocknum)
                    core_word_count += 1
                address += 1
        elif re.match("^@S", input_minus_comment):  # read a line with a single symbol
            tokens = re.split("[: \t][: \t]*", input_minus_comment)
            # print "tokens:", tokens
            if len(tokens) != 2:
                cb.log.warn("read_core parse error, read_core @S: tokens=%s" % tokens)
                continue
            address = int(tokens[0][2:], 8)
            symtab[address] = (tokens[1], '')  # save the name, and a marker saying we don't know the type
        elif re.match("^@N", input_minus_comment):  # read a line with a comment indexed by the core address
            tokens = re.split("[: \t][: \t]*", input_minus_comment, maxsplit = 1)
            # print "tokens:", tokens
            if len(tokens) != 2:
                cb.log.warn("read_core parse error, read_core @N: tokens=%s" % tokens)
                continue
            address = int(tokens[0][2:], 8)
            commenttab[address] = tokens[1]  # save the string

        elif re.match("^@E", input_minus_comment):
            tokens = re.split("[: \t][: \t]*", line, maxsplit = 1)
            address = int(tokens[0][2:], 8)
            exec = tokens[1]
            exectab[address] = exec
            cb.log.info("ExecAddr=0o%02o: Python Exec Statement: %s" %(address, exec) )

        elif re.match("^%Switch", input_minus_comment):
            tokens = input_minus_comment.split()
            if switch_class is None:
                cb.log.fatal("Read Core File: %%Switch directive, but no switch_class")
            ret = switch_class.parse_switch_directive(tokens[1:])
            if ret != 0:
                cb.log.warn("Errors setting switches")

        elif re.match("^%JumpTo", input_minus_comment):
            tokens = input_minus_comment.split()
            jumpto_addr = int(tokens[1], 8)
            cb.log.info("corefile JumpTo address = 0%oo" % jumpto_addr)
        elif re.match("^%File", input_minus_comment):
            tokens = input_minus_comment.split()
            if len(tokens) > 1:
                ww_file = tokens[1]
                cb.log.info("Whirlwind tape file name: %s" % ww_file)
        elif re.match("^%TapeID", input_minus_comment):
            tokens = input_minus_comment.split()
            if len(tokens) > 1:
                ww_tapeid = tokens[1]
                cb.log.info("Whirlwind tape identifier: %s" % ww_tapeid)
        elif re.match("^%Hash:", input_minus_comment):
            tokens = input_minus_comment.split()
            if len(tokens) > 1:
                ww_hash = tokens[1]
            else:
                cb.log.warn("read_core: missing arg to %Hash")
        # identifies any thing that might be a Flexo Character string in the image
        elif re.match("^%String:", input_minus_comment):
            tokens = input_minus_comment.split()
            if len(tokens) > 1:
                ww_strings += tokens[1] + '\n'
            else:
                cb.log.warn("read_core: missing arg to %String")
        elif re.match("^%Stats:", input_minus_comment):  # put the Colon back in here!
            tokens = input_minus_comment.split(' ', 1)
            if len(tokens) > 1:
                ww_stats = tokens[1]
            else:
                cb.log.warn("read_core: missing arg to %%Stats")
        elif re.match("^%Blocknum", input_minus_comment):
            tokens = input_minus_comment.split()
            blocknum = int(tokens[1], 8)
            cb.log.info("starting corefile blocknum 0%oo" % blocknum)
        elif re.match("^%ISA:", input_minus_comment):
            tokens = input_minus_comment.split()
            isa = tokens[1]
            cb.log.info("Setting instruction set architecture to '%s'" % isa)

        elif re.match("^%DbWgt:", input_minus_comment):  # On-screen Debug Widget
            # This directive says to put a real-time debug widget on the screen if the CRT is opened
            # We have to parse the items later to get all the symbolic addresses and their translations at once
            # Format:  %DbWgt: <addr> [increment]
            args = input_minus_comment.split()[1:]
            if len(args) < 1 or len(args) > 3:
                cb.log.warn("read_core: %%DbWgt takes one, two or three args, got %d" % len(args))
            screen_debug_widgets.append(args)

        else:
            cb.log.warn("read_core: unexpected line '%s' in %s, Line %d" % (line, filename, line_number))

    cm.metadata['strings'] = ww_strings
    cm.metadata['hash'] = ww_hash
    cm.metadata['stats'] = ww_stats
    cm.metadata['jumpto'] = jumpto_addr
    cm.metadata['filename_from_core'] = ww_file
    cm.metadata['ww_tapeid'] = ww_tapeid
    cm.metadata['core_word_count'] = core_word_count
    cm.metadata['isa'] = isa   # return a string with the instruction set to be used
    cm.metadata['file_type'] = file_type

    return symtab, jumpto_addr, ww_file, ww_tapeid, screen_debug_widgets


# used only in write_core to output a hash of the core image as metadata
def hash_to_fingerprint(hash_obj, word_count):
    # complete the fingerprint
    # convert the hash into a short string to use as a fingerprint
    fp = ''
    h = hash_obj.hexdigest()
    for i in range(0, len(h)):
        c = h[i]
        fp += "%s" % c
        if i == 5:
            fp += '-'
        if i == 11:
            break
    fp += "-%d" % word_count
    return fp


# Output the Core Image
# I modified this routine May 22, 2019 to retain its original function of writing out a memory image, but
# also to write out an array of bytes simply representing the stream of bytes on a tape, with no decoding.
# In that case, "offset" simply represents the number of bytes from the start of the tape.
#  [Careful, there's another write_core in wwasm.py.  oops.]
def write_core(cb, corelist, offset, byte_stream, ww_filename, ww_tapeid,
               jump_to, output_file, string_list, block_msg=None, stats_string=''):
    flexo_table = FlexoClass(cb)  # instantiate the class to get a copy of the code translation table
    op_table = InstructionOpTable()
    hash_obj = hashlib.md5()  # create an object to store the hash of the file contents

    file_size = 0
    for coremem in corelist:
        file_size += len(coremem)

    if byte_stream is False:
        filetype = "Core Image"
        tag = "@C"  # lines that start with %C go at specific addresses in core
    else:
        filetype = "Tape Bytestream"
        tag = "@T"  # lines that start with %T are simply streams of bytes at an offset from the tape start
    if output_file is None:
        fout = sys.stdout
    else:
        fout = open(output_file, 'wt')
        print("%s %d(d) words, output to file %s" % (filetype, file_size, output_file))
    fout.write("\n; *** %s ***\n" % filetype)
    if block_msg is not None:
        fout.write("; %s" % block_msg)
    fout.write("%%File: %s\n" % ww_filename)
    ww_tapeid = ww_tapeid.replace(" ", "")  # strip the spaces inside the string
    fout.write("%%TapeID: %s\n" % ww_tapeid)
    if jump_to is not None:
        fout.write('%%JumpTo 0%o\n' % jump_to)
    if stats_string != '':
        fout.write('%%Stats: %s\n' % stats_string)
    word_count = 0
    blocknum = 0
    for coremem in corelist:
        columns = 8
        addr = 0
        fout.write("%%Blocknum 0o%0o\n" % blocknum)
        while (byte_stream is False and addr < cb.CORE_SIZE) or (byte_stream is True and addr < len(coremem)):
            i = 0
            non_null = 0  # count the non-null characters in each line
            row = ''
            flexo_string_low = ''
            flexo_string_high = ''
            op_string = ''
            while i < columns:
                if (addr+i) < len(coremem):
                    m = coremem[addr+i]
                else:
                    m = None
                    if byte_stream:
                        break
                if m is not None:
                    row += "%07o " % m
                    hash_obj.update(m.to_bytes(2, byteorder='big'))   # if the word is not Null, include it in the hash
                    word_count += 1
                    non_null += 1
                    flexo_string_low += '%s' % flexo_table.code_to_letter(m & 0x3f, show_unprintable=True)
                    flexo_string_high += '%s' % flexo_table.code_to_letter((m >> 10) & 0x3f,
                                                                           show_unprintable=True)
                    op = op_table.op_decode[m >> 11]
                    op_string += '%s ' % op[0]
                else:
                    row += " None   "
                    flexo_string_low += '  '
                    flexo_string_high += '  '
                    op_string += '  '
                i += 1
            if non_null:
                fout.write('%s%05o: %s ; %24s : %16s : %16s\n' %
                           (tag, addr + offset, row, op_string, flexo_string_low, flexo_string_high))
                # ok, this is a bit weird, but I'm including the address in the hash.  WW code is not Position Indep!
                hash_obj.update((addr + offset).to_bytes(2, byteorder='big'))

            addr += columns
            # core files may have embedded "None" values, but a bytestream ends
            # with the first Null character in the array
            if non_null == 0 and byte_stream is True:
                break
        blocknum += 1

    h = hash_to_fingerprint(hash_obj, word_count)
    fout.write("\n%%Hash: %s\n" % h)

    if len(string_list) > 0:
        fout.write("\n")
        for s in string_list:
            fout.write("%%String: %s\n" % s)

    if output_file is not None:  # don't close stdout!
        fout.close()


class InstructionOpTable:
    def __init__(self):
        # ;categorize the operand part of the instruction
        self.OPERAND_JUMP = 0  # the address is a jump target
        self.OPERAND_WR_DATA = 1  # the address writes a data word to Core
        self.OPERAND_RD_DATA = 2  # the address writes a data word from Core
        self.OPERAND_PARAM = 3  # the operand isn't an address at all
        self.OPERAND_UNUSED = 4  # the operand is unused; convert it into a .word

        self.op_decode = [
            ["si",  "select input",        self.OPERAND_PARAM],     # 0
            [".word", "<unused>",          self.OPERAND_UNUSED],    # 1  # unused op code
            ["bi",  "block transfer in",   self.OPERAND_WR_DATA],   # 2
            ["rd",  "read",                self.OPERAND_PARAM],     # 3
            ["bo",  "block transfer out",  self.OPERAND_RD_DATA],   # 4
            ["rc",  "record",              self.OPERAND_PARAM],     # 5
            ["sd",  "sum digits - XOR",    self.OPERAND_RD_DATA],   # 6
            ["cf",  "change fields",       self.OPERAND_PARAM],     # 7
            ["ts",  "transfer to storage", self.OPERAND_WR_DATA],   # 10o, 8d
            ["td",  "transfer digits",     self.OPERAND_WR_DATA],   # 11o, 9d
            ["ta",  "transfer address",    self.OPERAND_WR_DATA],   # 12o, 10d
            ["ck",  "check",               self.OPERAND_RD_DATA],   # 13o, 11d
            ["ab",  "add B-Reg",           self.OPERAND_WR_DATA],   # 14o, 12d
            ["ex",  "exchange",            self.OPERAND_WR_DATA],   # 15o, 13d
            ["cp",  "conditional program", self.OPERAND_JUMP],      # 16o, 14d
            ["sp",  "sub-program",         self.OPERAND_JUMP],  # 17o, 15d
            ["ca",  "clear and add",       self.OPERAND_RD_DATA],  # 20o, 16d
            ["cs",  "clear and subtract",  self.OPERAND_RD_DATA],  # 21o, 17d
            ["ad",  "add",                 self.OPERAND_RD_DATA],  # 22o, 18d
            ["su",  "subtract",            self.OPERAND_RD_DATA],  # 23o, 19d
            ["cm",  "clear and add magnitude", self.OPERAND_RD_DATA],  # 24o, 20d
            ["sa",  "special add",         self.OPERAND_RD_DATA],           # 25o, 21d
            ["ao",  "add one",             self.OPERAND_RD_DATA],           # 26o, 22d
            ["dm",  "difference of magnitudes", self.OPERAND_RD_DATA],      # 27o, 23d
            ["mr",  "multiply and roundoff",   self.OPERAND_RD_DATA],       # 30o, 24d
            ["mh",  "multiply and hold",       self.OPERAND_RD_DATA],       # 31o, 25d
            ["dv",  "divide",                  self.OPERAND_RD_DATA],       # 32o, 26d
            ["SL",  "SL",                    self.OPERAND_PARAM],        # 33o, 27d
            ["SR",  "SR",                    self.OPERAND_PARAM],        # 34o, 28d
            ["sf",  "scale factor",          self.OPERAND_WR_DATA],      # 35o, 29d
            ["CL",  "CL",                    self.OPERAND_PARAM],        # 36o, 30d
            ["md",  "multiply digits no roundoff (AND)", self.OPERAND_RD_DATA]  # 37o, 31d aka "AND"
            ]

        self.ext_op_decode = {
            "SR": [["srr", "srh"], ["shift right and roundoff", "shift right and hold"]],
            "SL": [["slr", "slh"], ["shift left and roundoff", "shift left and hold"]],
            "CL": [["clc", "clh"], ["cycle left and clear", "cycle left and hold"]]
            }


# See manual 2M-0277 pg 46 for flexowriter codes and addresses
# This class is primarily the Flexowriter output driver, but it's also used
# other places for translating characters between ASCII and Flexo code.
class FlexoClass:
    def __init__(self, cb):
        self._uppercase = False  # Flexo used a code to switch to upper case, another code to return to lower
        self._color = False  # the Flexo had a two-color ribbon, I assume it defaulted to Black
        self.stop_on_zero = None
        self.packed = None
        self.null_count = 0
        self.FlexoOutput = []  # this is the accumulation of all output from the Flexowriter
        self.FlexoLine = ""    # this one accumulates one line of Flexo output for immediate printing
        self.name = "Flexowriter"
        self.cb = cb   # what's the right way to do this??

        self.FLEXO_BASE_ADDRESS = 0o224  # Flexowriter printers
        self.FLEXO_ADDR_MASK = ~0o013  # mask out these bits to identify any Flexo address

        self.FLEXO3 = 0o010  # code to select which flexo printer.  #3 is said to be 'unused'
        self.FLEXO_STOP_ON_ZERO = 0o01  # code to select whether the printer "hangs" if asked to print a zero word
        self.FLEXO_PACKED = 0o02        # code to interpret three (six-bit) characters per word (??)

        self.FLEXO_UPPER = 0o071   # character to switch to upper case
        self.FLEXO_LOWER = 0o075   # character to switch to lower case
        self.FLEXO_COLOR = 0o020   # character to switch ribbon color
        self.FLEXO_NULLIFY = 0o077  # the character that remains on a tape after the typist presses Delete

        #  From "Making Electrons Count:
        # "Even the best of typists make mistakes. The error is nullified by pressing the "delete" button. This
        # punches all the holes resulting in a special character ignored by the computer"

        self.flexocode_lcase = ["#", "#", "e", "8", "#", "|", "a", "3",
                                " ", "=", "s", "4", "i", "+", "u", "2",
                                "<color>", ".", "d", "5", "r", "1", "j", "7",
                                "n", ",", "f", "6", "c", "-", "k", "#",

                                "t", "#", "z", "<bs>", "l", "\t", "w", "#",
                                "h", "\n", "y", "#", "p", "#", "q", "#",
                                "o", "<stop>", "b", "#", "g", "#", "9", "#",
                                "m", "<upper>", "x", "#", "v", "<lower>", "0", "<del>"]

        self.flexocode_ucase = ["#", "#", "E", "8", "#", "_", "A", "3",
                                " ", ":", "S", "4", "I", "/", "U", "2",
                                "<color>", ")", "D", "5", "R", "1", "J", "7",
                                "N", "(", "F", "6", "C", "-", "K", "#",

                                "T", "#", "Z", "<bs>", "L", "\t", "W", "#",
                                "H", "\n", "Y", "#", "P", "#", "Q", "#",
                                "O", "<stop>", "B", "#", "G", "#", "9", "#",
                                "M", "<upper>", "X", "#", "V", "<lower>", "0", "<del>"]

        self.flexocode_alphanum = ['\b', '\b', "e", "8", '\b',   '\b', "a", "3",
                                   ' ',  ':',  "s", "4",  "i", '/', "u", "2",
                                   '',  ".",  "d", "5", "r", "1", "j", "7",
                                   "n", ",",  "f", "6", "c", "-", "k", '',

                                   "t", '\b', "z", '\b', "l", '\b', "w", '\b',
                                   "h", '\b', "y", '\b', "p", '\b', "q", '\b',
                                   "o", '\b', "b", '\b', "g", '\b', "9", '\b',
                                   "m", '',   "x", '\b', "v", '',   "0", '\b']

        self.flexo_ascii_lcase_dict = self.make_ascii_dict(upper_case=False)
        self.flexo_ascii_ucase_dict = self.make_ascii_dict(upper_case=True)

    # This routine takes a flexo character and converts it to an ascii character or string
    # Show_unprintable instructs this routine to make various invisible characters like tabs, newlines and nulls
    # visible as \t, \n etc
    # ascii_only returns null strings for Rubout (aka Nullify) and color-change flexo codes so that FC programs
    # can be edited with a standard text editor
    def code_to_letter(self, code: int, show_unprintable=False, make_filename_safe=False, ascii_only=False) -> str:
        ret = ''
        if code == self.FLEXO_NULLIFY:
            self.null_count += 1

        if code == self.FLEXO_UPPER:
            self._uppercase = True
        elif code == self.FLEXO_LOWER:
            self._uppercase = False
        elif code == self.FLEXO_COLOR and (show_unprintable == False) and (ascii_only == False):
            self._color = not self._color
            if self._color:
                return "\033[1;31m"
            else:
                return "\033[0m"
        else:
            if self._uppercase:
                ret = self.flexocode_ucase[code]
            else:
                ret = self.flexocode_lcase[code]

        if ascii_only:
            if code == self.FLEXO_NULLIFY or code == self.FLEXO_COLOR:
                ret = ''

        if make_filename_safe is True:
            if ret == '\n':
                ret = ''
            elif ret == '\t':
                ret = ' '
            elif code == 0:
                ret = ''
            elif ret == '\b':
                ret = ' '
            elif ret[0] == '<':   # if we're making a file name, ignore all the control functions in the table above
                ret = ''
        elif show_unprintable is True:
            if ret == '\n':
                ret = '\\n'
            if ret == '\t':
                ret = '\\t'
            if code == 0:
                ret = '\\0'
            if ret == '':
                ret = '<cntl>'
        return ret


    # when "printing" ASCII to flexo, compile a dictionary of flexo codes indexed
    # by ASCII
    def make_ascii_dict(self, upper_case: bool = False):
        ascii_dict = {}
        for flex in range(1, 64):
            if upper_case:
                ascii = self.flexocode_ucase[flex]
            else:
                ascii = self.flexocode_lcase[flex]
            ascii_dict[ascii] = flex
        return ascii_dict

    # this routine converts an ASCII leter into a Flexocode
    # The routine should be extended to accept and return a string, probably
    # by returning an array of flexocodes, not just one for one.
    # Aside from being a convenient way to define a string in a program
    # binary, this would allow upper and lower case to work!
    def ascii_to_flexo(self, ascii_letter):
        upper_case = False
        flexo_code = None
        a = ascii_letter
        if a in self.flexo_ascii_lcase_dict:
            flexo_code = self.flexo_ascii_lcase_dict[a]
        elif a in self.flexo_ascii_ucase_dict:
            flexo_code = self.flexo_ascii_ucase_dict[a]
            upper_case = True
        else:
            self.cb.log.warn("no flexo translation for '%s'" % a)
        return flexo_code


    def is_this_for_me(self, io_address):
        if (io_address & self.FLEXO_ADDR_MASK) == self.FLEXO_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, _accumulator, _cm):
        # 0224  # select printer #2 test control by console.
        # 0234  # select printer #3
        if device & self.FLEXO3:
            print("Printer #3 not implemented")
            return self.cb.UNIMPLEMENTED_ALARM

        self.stop_on_zero = (device & self.FLEXO_STOP_ON_ZERO)
        self.packed = (device & self.FLEXO_PACKED)

        if self.packed:
            print("Flexowriter packed mode not implemented")
            return self.cb.UNIMPLEMENTED_ALARM

        print(("configure flexowriter #2, stop_on_zero=%o, packed=%o" % (self.stop_on_zero, self.packed)))
        return self.cb.NO_ALARM

    def rc(self, _unused, acc):  # "record", i.e. output instruction to tty
        code = acc >> 10  # the code is in the upper six bits of the accumulator
        symbol = self.code_to_letter(code)  # look up the code, mess with Upper Case and Color
        self.FlexoOutput.append(symbol)
        self.FlexoLine += symbol
        if symbol == '\n':
            symbol = '\\n'   # convert the newline into something that can go in a Record status message
            print("Flexo: %s" % self.FlexoLine[0:-1])   # print the full line on the console, ignoring the line feed
            self.FlexoLine = ""                         # and start accumulating the next line
        return self.cb.NO_ALARM, symbol

    def bo(self, address, acc, cm):  # "block transfer out"
        """ perform a block transfer output instruction
            address: starting address for block
            acc: contents of accumulator (the word count)
            cm: core memory instance
        """
        symbol_str = ''
        if address + acc > self.cb.WW_ADDR_MASK:
            print("block-transfer-out Flexo address out of range")
            return self.cb.QUIT_ALARM
        for m in range(address, (address + acc)):
            wrd = cm.rd(m)  # read the word from mem
            self.rc(0, wrd)
            code = wrd >> 10   # code in top six bits contain the character
            symbol_str += self.code_to_letter(code)  # look up the code, mess with Upper Case and Color

        print(("Block Transfer Write to Flexo: start address=0o%o, length=0o%o, str=%s" %
              (address, acc, symbol_str)))
        return self.cb.NO_ALARM

    def get_saved_output(self):
        return self.FlexoOutput


# The following class prints debug text on the CRT to display and adjust memory values
# while the program runs.
# This mechanism is mostly-disabled now when using the analog oscilloscope display; although
# it might turn out to be useful in the future, so I'm not turning it completely off...
class ScreenDebugWidgetClass:
    def __init__(self, cb, coremem, analog_scope):
        if not analog_scope:
            self.point_size = 10 * int(cb.gfx_scale_factor)
            self.gfx_scale_factor = cb.gfx_scale_factor
        else:
            self.point_size = 10
            self.gfx_scale_factor = 1
        self.xpos = 15 * self.point_size   # default Centers the text; I wish it were Left
        self.ypos = self.point_size
        self.y_delta = self.point_size + 5
        # core mem debug widgets
        self.mem_addrs = []   # physical address to be monitored
        self.labels = []      # label that matches the address, if any
        self.py_labels = []      # label that matches the address, if any
        self.increments = []  # amount to be added when the 'increment' key is hit
        self.format_str = []  # how to format the widget value when printing; should be "%d", "%o", etc

        # screen print lines (i.e., not from core memory, but strings created by a python stmt)
        self.screen_print_text = {}   # dict of text strings indexed by line number
        self.screen_title = None

        # more overhead
        self.txt_objs = []    # the gfx text object created for this widget
        self.input_selector = None  # current offset for which widget is incremented/decremented
#        if not analog_scope:  # I used to only import the xwin graphics module when Not --AnaScope, now I'm using both
#       #  But it won't work without a DISPLAY

        # the following stanza will dump the complete environment to help debug
        # for name, value in os.environ.items():
        #     print("{0}: {1}".format(name, value))

        if cb.use_x_win and os.getenv("DISPLAY"):
            self.gfx = __import__("graphics")
        else:
            if not analog_scope:
                cb.log.fatal("can't display debug widgets with no display; analog_scope=%d" % analog_scope)
        self.cm = coremem
        self.win = None
        self.cb = cb   # keep this around so we can find the parent python env

    # the emulated CRT display scope is added only if there's an SI instruction that threatens to actually
    # use the display.  At which point, scale_factors should already have been set.
    def add_scope(self, win):
        self.win = win
        self.point_size = 10 # * int(self.gfx_scale_factor)
        self.xpos = 15 * self.point_size * int(self.gfx_scale_factor)  # default Centers the text; I wish it were Left
        self.ypos = self.point_size * int(self.gfx_scale_factor)
        self.y_delta = (self.point_size + 5) * int(self.gfx_scale_factor)


    def add_widget(self, cb, addr, label, py_label, increment, format_str):
        self.mem_addrs.append(addr)
        self.labels.append(label)
        self.py_labels.append(py_label)
        self.increments.append(increment)
        self.format_str.append(format_str)
        self.input_selector = 0

    def add_screen_print(self, line, text):
        self.screen_print_text[line] = text

    def eval_py_var(self, var_name, direction_up=None, incr=1):
        if direction_up is None:
            op = ".rd()"
        elif direction_up == True:
            op = ".incr(%d)" % incr
        else:
            op = ".incr(%d)" % -incr
        name_and_context = "self.cb.DebugWidgetPyVars." + var_name + op
        val = eval(name_and_context)
        return val


    def wgt_format(self, val, format_str):
        if val is None:
            val_str = "None"
        else:
            val_str = format_str % val
        return val_str


    def refresh_widgets(self):
        # don't refresh this part of the display unless there's something to see, and there's a display to see
        # it on!
        if self.win is None or len(self.mem_addrs) == 0:
            return
        for txt in range(0, len(self.txt_objs)):
            self.txt_objs[txt].undraw()
        y = 0
        self.txt_objs = []
        cm = self.cm
        for wgt in range(len(self.mem_addrs) - 1, -1, -1):  # wgt = widget number offset
            val = 0
            if self.py_labels[wgt]:
                lbl = self.py_labels[wgt]
                val = self.eval_py_var(self.py_labels[wgt])
            else:
                if len(self.labels) > 0:
                    lbl = self.labels[wgt]
                else:
                    lbl = "core@0o%04o" % self.mem_addrs[wgt]
                val = cm.rd(self.mem_addrs[wgt])
            val_str = self.wgt_format(val, self.format_str[wgt])
            m = self.gfx.Text(self.gfx.Point(self.xpos, self.ypos + y), "w%d: %s = %s" %
                     (wgt, lbl, val_str))
            m.config['justify'] = 'left'   # this doesn't seem to work...
            # m.config['align'] = 'e'   # this Really doesn't work...
            m.setSize(self.point_size)
            if wgt == self.input_selector:
                m.setTextColor("pink")
            else:
                m.setTextColor("light sky blue")
            m.draw(self.win)
            self.txt_objs.append(m)
            y += self.y_delta

        for line in self.screen_print_text:
            m = self.gfx.Text(self.gfx.Point(self.xpos, self.ypos + y), self.screen_print_text[line])
            # m.config['justify'] = 'left'
            m.setTextColor("light sky blue")
            m.draw(self.win)
            self.txt_objs.append(m)
            y += self.y_delta

        if self.screen_title:
            m = self.gfx.Text(self.gfx.Point(self.xpos + (20 * self.point_size * int(self.gfx_scale_factor)), self.ypos + 10), self.screen_title)
            m.config['justify'] = 'right'
            s = 2 * self.point_size
            if s > 36:
                s = 36
            m.setSize(s)  #36 is the max
            m.setTextColor("light salmon")
            m.draw(self.win)
            self.txt_objs.append(m)


    def select_next_widget(self, direction_up = False):
        if direction_up:
            self.input_selector += 1
        else:
            self.input_selector -= 1

        if self.input_selector >= len(self.mem_addrs):
            self.input_selector = 0
        if self.input_selector < 0:
            self.input_selector = len(self.mem_addrs) - 1

    def increment_addr_location(self, direction_up = False):
        cm = self.cm
        wgt = self.input_selector
        addr = self.mem_addrs[wgt]
        if addr >= 0:  # a normal WW memory reference has a non-negative address; PyVars are signalled with addr=-1
            #  For a WW var, read the current value, add or subtract (and wrap), then write it back
            rd = cm.rd(addr)
            incr = self.increments[wgt]
            if direction_up:
                wr = rd + incr
                if rd <= 0o77777 and wr >= 0o77777:  # don't roll over from Max-Plus to Max-Minus
                    wr = 0o77777
                if wr >= 0o177777:
                    wr = (wr + 1) & 0o77777  # this corrects for ones-complement going from -1 to +0
            else:
                wr = rd - incr
                if rd >= 0o100000 and wr <= 0o77777:  # don't roll over from Max-Minus to Max-Plus
                    wr = 0o100000
                if wr < 0:   # if it turns to a Pythonic negative, subtract one for 1's comp, and mask to 16 bits
                    wr = (wr - 1) & 0o177777  # this corrects for ones-complement going from +0 to -1

            cm.wr(self.mem_addrs[wgt], wr)
        else:
            self.eval_py_var(self.py_labels[wgt], direction_up=direction_up, incr=self.increments[wgt])

# This routine should probably go somewhere else...  it's a general-purpose number
# converter, but I need it in call the analog scope modules.
# Convert a ones-complement Whirlwind integer into a twos-comp Python number
def wwint2py(ww_num):
    if ww_num & 0o100000:
        ww_num ^= 0o177777  # invert all the bits, including the sign
        sign = -1
    else:
        sign = 1
    ret = ww_num * sign
    return ret


class XwinCrtObject:
    def __init__(self, x0, y0, x1, y1, graphical_type, char_mask, expand = 1.0):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.graphical_type = graphical_type  # L=line, D=dot, C=char
        self.char_mask = char_mask  # ascii character
        self.expand = expand
        self.red = 0     # RGB color range is zero to one
        self.green = 1.0   # default color is full green
        self.blue = 0


# This class manages the emulation of the Whirlwind "scope" display
class XwinCrt:
    def __init__(self, cb):
        self.cb = cb
        self.win = None

        widgets_only_on_xwin = False
        if cb.analog_display:
            if cb.ana_scope is None:  # first time there's a CRT SI instruction, we'll init the display modules
                cb.ana_scope = analog_scope.AnaScope(cb.host_os, cb)
            self.WW_CHAR_HSTROKE = 8  # should be 7    (2M-0277 p.61)
            self.WW_CHAR_VSTROKE = 9  # should be 8.5
            widgets_only_on_xwin = True

        # The graphics package won't work if you don't have DISPLAY=<something> in the environment
        # So don't bother even trying if there isn't a DISPLAY var already set
        display = os.getenv("DISPLAY")
        if display and cb.use_x_win and (cb.analog_display == False or widgets_only_on_xwin): # display on the laptop CRT using xwindows
            self.gfx = __import__("graphics")

            cb.log.info("opening XwinCrt")
            # gfx_scale_factor comes from Windows and depends on the display.  I think it's usually between 1.0 and 2.0
            self.WIN_MAX_COORD = 600.0 * cb.gfx_scale_factor # 1024.0 + 512.0  # size of window to request from the laptop window  manager
            win_y_size = self.WIN_MAX_COORD
            if widgets_only_on_xwin:
                win_y_size = win_y_size / 4

            self.WIN_MOUSE_BOX = self.WIN_MAX_COORD / 50.0

            win_name = "Whirlwind CoreFile: %s" % cb.CoreFileName
            self.win = self.gfx.GraphWin(win_name, self.WIN_MAX_COORD, win_y_size, autoflush=False)

            self.win.setBackground("Gray10")
            if cb.museum_mode:
                cb.museum_mode.museum_gfx_window_size(cb, self.win)

            # coordinate definitions for Whirlwind CRT display
            self.WW_MAX_COORD = 1024.0
            self.WW_MIN_COORD = -self.WW_MAX_COORD

            self.BRIGHT = 20
            self.DARK = 0
            self.screen_brightness = {}  # a list of graphical elements, with corresponding brightness
            self.fade_delay_param = cb.crt_fade_delay_param
            self._fade_delay = self.fade_delay_param

            # changed Feb 18, 2022 to make the "expand" feature (2M-0277, pg 63) work (I think)
            # normal size would be "expand = 1", large size, expand = 2
            # Expand Mode is used in blackjack, not used in the Everett tape (I think)
            # so the base value of the stroke lengths here is divided by two, so it comes out right when doubled in bjack
            # If the xwin is just for debug_widgets, then the anascope section above should set character stroke sizes
            if cb.analog_display == False:
                self.WW_CHAR_HSTROKE = int(25.6 / 2.0 * (self.WIN_MAX_COORD / (self.WW_MAX_COORD * 2.0)))  # should be 20.0 in 'expand'
                self.WW_CHAR_VSTROKE = int(19.2 / 2.0 * (self.WIN_MAX_COORD / (self.WW_MAX_COORD * 2.0)))  # should be 15.00

        # The Whirlwind CRT character generator uses a seven-segment format with a bit in a seven-bit
        # word to indicate each segment.  This list defines the sequence in which the bits are
        # converted into line segments
        self.WW_CHAR_SEQ = ("down", "right", "up", "left", "up", "right", "down")

        # recall the most recent light gun display point so it can be erased when the next one comes up
        self.last_pen_point = None
        # remember the location of the last unprocessed mouse click
        self.last_mouse = None
        self.last_button = 0
        # remember the last character drawn
        self.last_crt_char = None

        # keep a tag in this struct that says if the program itself is reading the Light Gun / Mouse
        # If so, the regular reads to the light gun will watch for hits to the Red-X exit box
        # on the simulated crt -- if not, we'll poll it separately when painting the display
        self.polling_mouse = False

        if cb.use_x_win and not cb.analog_display:
            self.draw_red_x_and_axis(cb)



    def draw_red_x_and_axis(self, cb):
        # I've put a mouse zone in the top right corner to Exit the program, i.e., to synthesize a Whirlwind
        # alarm that causes the interpreter to exit.  Mark the spot with a red X
        xline = self.gfx.Line(self.gfx.Point(self.WIN_MAX_COORD - self.WIN_MOUSE_BOX, self.WIN_MOUSE_BOX),
                              self.gfx.Point(self.WIN_MAX_COORD, 0))
        xline.setOutline("Red")
        xline.setWidth(1)   # changed from 3 to 1, Apr 11, 2020
        xline.draw(self.win)
        xline = self.gfx.Line(self.gfx.Point(self.WIN_MAX_COORD - self.WIN_MOUSE_BOX, 0),
                              self.gfx.Point(self.WIN_MAX_COORD, self.WIN_MOUSE_BOX))
        xline.setOutline("Red")
        xline.setWidth(3)
        xline.draw(self.win)

        if cb.radar is not None:
            cb.radar.draw_axis(self)


    def get_mouse_blocking(self):
        #block until there's a mouse click
        # The call returns (pt, button)
        return(self.win.getMouse())


    def close_display(self):
        print("close display...")
        if self.win is not None:
            self.win.close()

    # convert the zero-centered WW coords into scaled xwin top-left zero coords
    def ww_to_xwin_coords(self, ww_x, ww_y):
        """ change coordinates from WW to Windows
        WW coords have zero at the center, and go to +/- 1023.  Plus is up and to the right
        X-Windows coords have 0,0 in the top left corner.  More Positive is down and to the right
        """
        xwin_y = -float(ww_y)/self.WW_MAX_COORD * (self.WIN_MAX_COORD/2.0) + self.WIN_MAX_COORD/2.0
        xwin_x = float(ww_x)/self.WW_MAX_COORD * (self.WIN_MAX_COORD/2.0) + self.WIN_MAX_COORD/2.0

        return int(xwin_x), int(xwin_y)

    def ww_draw_char(self, ww_x, ww_y, mask, expand, scope=None):
        if scope is None:
            scope = self.cb.SCOPE_MAIN
        if self.cb.ana_scope:
            self.cb.ana_scope.drawChar(ww_x, ww_y, mask, expand, self, scope=scope)
        else:
            x0, y0 = self.ww_to_xwin_coords(ww_x, ww_y)
            obj = XwinCrtObject(x0, y0, 0, 0, 'C', mask, expand = expand)
            # obj = (x0, y0, 0, 0, 'C', mask)
            self.screen_brightness[obj] = self.BRIGHT


    # Display Scope Vector Generator
    # From 2m-0277
    # si u
    # selects a scope intensification line for vector display. Sets
    # the vertical deflection for all scopes to a value corresponding
    # to the contents of digits O - 10 of AC.

    # rc v
    # sets the horizontal deflection at all scopes to a value corresponding
    # to the contents of digits O - 10 of AC. Intensifies a
    # vector starting at the point whose coordinates have just been
    # established, where the sign and length of the horizontal component
    # are given by the first six digits of v, and the sign and length
    # of the vertical component are given by digits 8 to 13 of this
    # register. About 166 microseconds will elapse before the computer
    # can perform another in-out instruction. Any number of instructions
    # other than in-out instructions may precede each rc. Each
    # vector to be displayed is programmed in a similar manner.
    def ww_draw_line(self, ww_x0, ww_y0, ww_xd, ww_yd, scope=None):
        if scope is None:
            scope = self.cb.SCOPE_MAIN
        self.cb.log.info("ww_draw_line: pt=(%d,%d) len=(%d,%d), scope=%d" % (ww_x0, ww_y0, ww_xd, ww_yd, scope)) 
        if self.cb.ana_scope:
                self.cb.ana_scope.drawVector(ww_x0, ww_y0, ww_xd>>2, ww_yd>>2, scope=scope)
        else:
            x0, y0 = self.ww_to_xwin_coords(ww_x0, ww_y0)
            x1, y1 = self.ww_to_xwin_coords(ww_x0 + ww_xd, ww_y0 + ww_yd)

            # obj = (x0, y0, x1, y1, 'L', 0)
            obj = XwinCrtObject(x0, y0, x1, y1, 'L', 0)
            self.screen_brightness[obj] = self.BRIGHT


    def ww_draw_point(self, ww_x, ww_y, color=(0.0, 1.0, 0.0), scope=None, light_gun=False):  # default color is green
        if scope is None:
            scope = self.cb.SCOPE_MAIN
        self.cb.log.info("ww_draw_point: x=%d, y=%d, scope=%d, gun_enable=%d" % (ww_x, ww_y, scope, light_gun)) 
        if self.cb.ana_scope:
            self.cb.ana_scope.drawPoint(ww_x, ww_y, scope=scope)
            if light_gun:
                self.last_pen_point = True  # remember the point was seen; not sure this really matters...
        else:
            x0, y0 = self.ww_to_xwin_coords(ww_x, ww_y)
            # obj = (x0, y0, 0, 0, 'D', 0)
            obj = XwinCrtObject(x0, y0, 0, 0, 'D', 0)
            obj.red = color[0]
            obj.green = color[1]
            obj.blue = color[2]
            self.screen_brightness[obj] = self.BRIGHT
            if light_gun:
                self.last_pen_point = obj  # remember the point so it can be undrawn later

    def ww_highlight_point(self):
        if self.last_pen_point is not None:
            x0 = self.last_pen_point.x0
            y0 = self.last_pen_point.y0
            c = self.gfx.Circle(self.gfx.Point(x0, y0), 5)  # the last arg is the circle dimension
            c.setFill("Red")
            c.draw(self.win)
            self.last_pen_point = None


    # check the light gun for a hit
    # Note that management of the Mouse 'light gun' is quite different from the optical gun on an analog scope.
    # With the mouse, this routine has to check the position of the mouse to see if it's inside the bounding box
    # for the last point drawn.  To highlight the point for some (non-authentic) visual feedback, we return the
    # coordinates of the hit as well.
    # With the Analog scope, it simply reports whether the last point caused a flash or not.  And there's no
    # handy mechanism to offer any visual feedback.
    # Both functions return a None for 'no hit', but the mouse version returns a co-ord object, and the optical
    # gun simply returns a "true'.  It's up to the caller to know which response is for what...
    def ww_check_light_gun(self, cb):
        self.cb.log.info("ww_check_light_gun") 
        self.polling_mouse = True
        if self.cb.ana_scope:
            pt = None
            button = 0
            if self.cb.ana_scope.checkGun() == 1:  # check only for LighGun1
                button = 1      # default is to return "mouse button one"
                if self.cb.ana_scope.getGunPushButton():
                    button = 3  # return 'button 3' to emulate the PC Mouse right-click
                pt = True       # if it were the CRT, we'd have to return an actual point, but here, it's just "hit"
                print("Light Gun Hit: button=%d" % button)
            self.last_pen_point = None  # we don't need this var, but I don't want to break the xwin version

        else:
            pt, button = self.win.checkMouse()
            if pt is None:
                return self.cb.NO_ALARM, None, 0
            if self.last_pen_point is None:
                cb.log.warn("Light Gun checked, but no dot displayed")
                return self.cb.QUIT_ALARM, None, 0

            if (self.WIN_MAX_COORD - pt.getX() < self.WIN_MOUSE_BOX) and \
                    (pt.getY() < self.WIN_MOUSE_BOX) and (button == 1):
                cb.log.info("**Quit**")
                return self.cb.QUIT_ALARM, None, 0

            cb.log.info(("dot (%d, %d);  mouse (%d, %d)" % (self.last_pen_point.x0, self.last_pen_point.y0,
                                                      pt.getX(), pt.getY())))
        return self.cb.NO_ALARM, pt, button

    def _render_char(self, x, y, mask, color, expand):
        last_x = x
        last_y = y
        for i in range(0, 7):
            if self.WW_CHAR_SEQ[i] == "down":
                y = last_y + self.WW_CHAR_VSTROKE * expand
            elif self.WW_CHAR_SEQ[i] == "up":
                y = last_y - self.WW_CHAR_VSTROKE * expand
            elif self.WW_CHAR_SEQ[i] == "left":
                x = last_x - self.WW_CHAR_HSTROKE * expand
            elif self.WW_CHAR_SEQ[i] == "right":
                x = last_x + self.WW_CHAR_HSTROKE * expand
            else:
                print(("OMG its a bug! WW_CHAR_SEQ[%d]=%s " % (i, self.WW_CHAR_SEQ[i])))

            if mask & 1 << (6 - i):
                seg_color = color
            else:
                seg_color = "Blue"

            char_segment = self.gfx.Line(self.gfx.Point(last_x, last_y), self.gfx.Point(x, y))
            char_segment.setOutline(seg_color)
            if expand < 1.0 :
                expand = 1.0
            char_segment.setWidth(int(expand))
            char_segment.draw(self.win)
            last_x = x
            last_y = y

    # This routine should be called "periodically", i.e., at constant-time intervals
    # For now, I think that means "every N instruction cycles"
    # Step One is to check if the Red-X has been hit, if the program is not already polling
    # the mouse (I mean, the light gun!).
    # Then go on to refresh the screen

    def ww_scope_update(self, cm, cb):
        if self.win is None:   # all this stuff only works on a laptop display, not a CRT display
            return self.cb.NO_ALARM

        dbwgt = cb.dbwgt
        if self.polling_mouse is False:
            pt, button = self.win.checkMouse()
            if (pt is not None) and (button == 1):
                if (self.WIN_MAX_COORD - pt.getX() < self.WIN_MOUSE_BOX) and \
                        (pt.getY() < self.WIN_MOUSE_BOX):
                    self.cb.log.log("** Quit due to Red-X Click **")
                    return self.cb.QUIT_ALARM

        # fixed a big memory leak here in Nov 2020, where I was continuously drawing
        # new objects but never freeing the old ones.
        # So for now, it redraws the whole works
        # I don't actually want to delete the Red X...  oops, we'll replace it below
        for item in self.win.items[:]:
            item.undraw()

        self.draw_red_x_and_axis(cb)    # replace the Red-X for exit symbol
        # and the screen-debug widget undraws its own objects, so that's being done twice now.
        dbwgt.refresh_widgets()

        if cb.analog_display:
            return self.cb.NO_ALARM

        for i in range(self.DARK, self.BRIGHT+1):
            for obj in self.screen_brightness:
                x0 = obj.x0
                y0 = obj.y0
                x1 = obj.x1
                y1 = obj.y1
                graphical_type = obj.graphical_type  # L=line, D=dot, C=char
                char_mask = obj.char_mask  # bit map of seven-seg character
                intensity = self.screen_brightness[obj]
                if intensity == i:
                    # print("draw", obj, intensity)
                    red = obj.red * intensity * (256 / (self.BRIGHT - self.DARK))  # I'm sure I'm not scaling the color properly
                    green = obj.green * intensity * (256 / (self.BRIGHT - self.DARK))
                    blue = obj.blue * intensity * (256 / (self.BRIGHT - self.DARK))
                    if red > 255:
                        red = 255
                    if green > 255:
                        green = 255
                    if blue > 255:
                        blue = 255
                    color = self.gfx.color_rgb(int(red), int(green), int(blue))
                    if graphical_type == 'D':  # it's a Dot
                        # We've played some with the size of the spot.
                        # for Air Defense, I wanted the yellow spot representing the second WW display to be
                        # prominent, so I made it larger.
                        # Once we added "Slow Motion" mode, the active Green spot became too hard to see too, so
                        # I'm making that larger too.  Once the spot fades, it returns to the small size.
                        spot_size = 2 * cb.gfx_scale_factor  # default circle diameter
                        if red != 0 or blue != 0 or green > 254:  # hack alert ; if the color is not All Green, expand the size
                            spot_size *= 2
                        c = self.gfx.Circle(self.gfx.Point(x0, y0), spot_size)  # was 5 # the last arg is the circle dimension
                        c.setFill(color)
                        c.draw(self.win)
                        # print("Draw-Dot (%d,%d) rgb=%3.2f;%3.2f;%3.2f, intensity=%d" %
                        #       (x0, y0, red, green, blue, intensity))

                    elif graphical_type == 'L':  # it's a line
                        #    self._ww_draw_line(x0, y0, x1, y1, color)
                        scope_line = self.gfx.Line(self.gfx.Point(x0, y0), self.gfx.Point(x1, y1))
                        scope_line.setOutline(color)
                        scope_line.setWidth(4)
                        scope_line.draw(self.win)

                    elif graphical_type == 'C':  # it's a char
                        self._render_char(x0, y0, char_mask, color, obj.expand)
        self.gfx.update()
        # step two, decay the brightness of each object
        # In the normal case, we dim each object one step at a time until it goes dark,
        # then put it on a list for deletion.
        # If Normal Fade is turned off, we'll just leave the dots as they are and never erase them
        # Used either for debug, or to produce a record of how multiple refreshes evolve over time
        normal_fade = True
        for_deletion = []
        if normal_fade:
            if self._fade_delay <= 0:
                self._fade_delay = self.fade_delay_param
                for obj in self.screen_brightness:
                    intensity = self.screen_brightness[obj]
                    # print("CRT decay (%d,%d) rgb=%3.1f;%3.1f;%3.1f, intensity=%d" %
                    #       (obj.x0, obj.y0, obj.red, obj.green, obj.blue, intensity))
                    # When in "Museum Mode" and "Slow Motion" state, we want to fade the
                    # image, but not all the way to zero.
                    mm = cb.museum_mode
                    slow = mm and mm.states[mm.state].name == "Slow"
                    if not slow or intensity > 10:
                        intensity -= 1
                    if intensity < 0:
                        for_deletion.append(obj)
                    else:
                        self.screen_brightness[obj] = intensity
                for obj in for_deletion:
                    del self.screen_brightness[obj]
            self._fade_delay -= 1
        else:
            self.screen_brightness = {}

        return self.cb.NO_ALARM
