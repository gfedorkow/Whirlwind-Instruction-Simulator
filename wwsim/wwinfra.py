
import re
from typing import List, Dict, Tuple, Sequence, Union, Any


def breakp():
    print("** Breakpoint **")

class LogClass:
    def __init__(self, program_name, quiet:bool=None, debug556:bool=None, debugtap:bool=None,
                 debugldr:bool=None, debug7ch:bool=None, debug:bool=None):
        self._debug = debug
        self._debug556 = debug556
        self._debug7ch = debug7ch
        self._debugtap = debugtap
        self._debugldr = debugldr
        self._quiet = quiet
        self._program_name = program_name

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

    def info(self, message):
        if not self._quiet:
            print("Info: %s" % message)

    def warn(self, message):
        print("Warning: %s" % message)

    def fatal(self, message):
        print("Fatal: %s" % message)
        exit(1)


# simple routine to print an octal number that might be 'None'
def octal_or_none(number):
    ret = " None "
    if number is not None:
        ret = "0o%06o" % number
    return ret


class ConstWWbitClass:
    def __init__(self):
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

        # use these vars to control how much Helpful Stuff emerges from the sim
        self.TracePC = False    # print a line for each instruction
        self.TraceALU = False   # print a line for add, multiply, negate, etc
        self.TraceBranch = True  # print a line for each branch
        self.TraceQuiet = False
        self.NoZeroOneTSR = False
        self.TraceDisplayScope = False
        self.PETRAfilename = None
        self.PETRBfilename = None
        self.log = None
        self.crt_fade_delay_param = 0

        # I/O addresses.  I've put them here so the disassembler can identify I/O devices using this shared module.
        self.PETR_BASE_ADDRESS = 0o210  # starting address of PETR device(s)
        self.PETR_ADDR_MASK = ~0o003  # sub-addresses cover PETR-A and PETR-B, word-by-word vs char-by-char

        self.CLEAR_BASE_ADDRESS = 0o17  # starting address of memory-clear device(s)
        self.CLEAR_ADDR_MASK = ~0000  # there aren't any sub-addresses

        self.DRUM_BASE_ADDRESS = 0o700  # starting address of Drum device(s)
        self.DRUM_ADDR_MASK = ~(0o1017)  # mask out the sub-addresses
        self.DRUM_SWITCH_FIELD_ADDRESS = 0o734

        self.DISPLAY_POINTS_BASE_ADDRESS = 0o0600   # starting address of point display
        self.DISPLAY_POINTS_ADDR_MASK = ~(0o077)    # mask out the sub-addresses
        self.DISPLAY_VECTORS_BASE_ADDRESS = 0o1600  # starting address of vector display
        self.DISPLAY_VECTORS_ADDR_MASK = ~(0o077)   # mask out the sub-addresses
        self.DISPLAY_CHARACTERS_BASE_ADDRESS = 0o2600  # starting address of vector display
        self.DISPLAY_CHARACTERS_ADDR_MASK = ~(0o1077)  # mask out the sub-addresses
        self.DISPLAY_EXPAND_BASE_ADDRESS = 0o0014   # starting address of vector display
        self.DISPLAY_EXPAND_ADDR_MASK = ~(0o001)    # mask out the sub-addresses

        self.INTERVENTION_BASE_ADDRESS = 0o300  # starting address of Intervention and Activate device(s)
        self.INTERVENTION_ADDR_MASK = ~(0o037)  # mask out the sub-addresses

        # the following are here to stake out territory, but I don't have drivers yet
        self.MAG_TAPE_BASE_ADDRESS = 0o100       # block of four mag tape drives
        self.MAG_TAPE_ADDR_MASK = ~(0o77)

        self.MECH_PAPER_TAPE_BASE_ADDRESS = 0o200  # starting address of mechanical paper tape device(s) (must be Flexo?)
        self.MECH_PAPER_TAPE_ADDR_MASK = ~0o003

        self.PUNCH_BASE_ADDRESS = 0o204       # paper tape punch
        self.PUNCH_ADDR_MASK = ~(0o03)

        self.PRINTER_BASE_ADDRESS = 0o225
        self.ANELEX_BASE_ADDRESS = 0o244      # Anelex line printer
        self.ANELEX_ADDR_MASK = ~(0o01)

        self.TELETYPE_BASE_ADDRESS = 0o402

        self.INDICATOR_LIGHT_BASE_ADDRESS = 0o510       # ?
        self.INDICATOR_LIGHT_ADDR_MASK = ~(0o07)

        self.IN_OUT_CHECK_BASE_ADDRESS = 0o500       # ?
        self.IN_OUT_CHECK_ADDR_MASK = ~(0o07)

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
            ((self.PRINTER_BASE_ADDRESS, ~0), "Printer"),
            ((self.ANELEX_BASE_ADDRESS, self.ANELEX_ADDR_MASK), "Anelex Line Printer"),
            ((self.TELETYPE_BASE_ADDRESS, ~0), "Teletype"),
            ((self.INDICATOR_LIGHT_BASE_ADDRESS, self.INDICATOR_LIGHT_ADDR_MASK), "Indicator Light Registers"),
            ((self.IN_OUT_CHECK_BASE_ADDRESS, self.IN_OUT_CHECK_ADDR_MASK), "In-Out Check Registers"),
        ]

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
    def __init__(self):

        self.SwitchNameDict = { \
            # name: [default_val, mask]
            "CheckAlarmSpecial": [0, 0o01],  # Controls the behavior of the CK instruction; see 2M-0277
                                            # "normal" is 'off'
        }

    def parse_switch_directive(self, args):    # return one for error, zero for ok.
        if len(args) != 2:
            print("Switch Setting: expected <name> <val>, got: ")
            print(args)
            return 1

        name = args[0]
        if name not in self.SwitchNameDict:
            print(("No machine switch named %s" % name))
            return 1

        try:
            val = int(args[1], 8)
        except:
            print((".SWITCH %s setting %s must be an octal number" % (name, args[1])))
            return 1
        mask = self.SwitchNameDict[name][1]
        if (~mask & val) != 0:
            print(("max value for switch %s is 0o%o, got 0o%o" % (name, mask, val)))
            return 1
        self.SwitchNameDict[name][0] = val
        print((".SWITCH %s set to 0o%o" % (name, val)))
        return 0

    def read_switch(self, name):
        return self.SwitchNameDict[name][0]


# collect a histogram of opcode frequency
class OpCodeHistogram:
    def __init__(self, cb):

        self.opcode_width = 5
        self.opcode_shift = 16 - self.opcode_width
        self.opcode_mask = (2 ** self.opcode_width) - 1
        self.opcode_histogram = [ 0 ] * (self.opcode_mask + 1)
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
                                        # ... False means to compute a global histogram over all likely code
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
        if self.local_histogram == True:  # if we're making histograms for each file, reset this var with each call.
            self.opcode_histogram = [0] * (self.opcode_mask + 1)
            self.init_opcode_histogram()
        else:
            if for_sure_code == False:
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
        sum = 0.0
        for i in range(0, self.opcode_mask + 1):
            diff = (sample[i] - self.basline_op_histogram[i]) ** 2
            sum += diff

        cov = sum / float(self.opcode_mask + 1)
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
class CorememClass:
    def __init__(self, cb):
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

        self.NBANKS = 6  # six 1K banks
        self._coremem = []
        for _i in range(self.NBANKS):
            self._coremem.append([None] * (cb.CORE_SIZE // 2))
        self.MemGroupA = 0  # I think Reset sets logical Group A to point to Physical Bank 0
        self.MemGroupB = 1  # I *think* Reset sets logical Group B to point to Physical Bank 1
        if cb.NoZeroOneTSR is False:
            self._coremem[0][0] = 0
            self._coremem[0][1] = 1
        self.cb = cb
        self.SymTab = None
        self.metadata = {}
#        self.metadata_hash = []
#        self.metadata_stats = []
#        self.metadata_goto = None
#        self.metadata_filename_from_core = []
#        self.metadata_ww_tapeid = []

    def wr(self, addr, val, force=False):   # 'force' arg overwrites the "read only" toggle switches
        if (addr & ~self._toggle_switch_mask) == 0:
            if not force and self._toggle_switch_mem_default[addr][1]:
                print("Warning: Can't write a read-only toggle switch at addr=0o%o" % addr)
                return
            if force:
                print("Warning: Overwriting a read-only toggle switch at addr=0o%o" % addr)

            self._toggle_switch_mem_default[addr][0] = val
        if addr & self.cb.WWBIT5:  # High half of the address space, Group B
            self._coremem[self.MemGroupB][addr & self.cb.WWBIT6_15] = val
        else:
            self._coremem[self.MemGroupA][addr & self.cb.WWBIT6_15] = val

    # memory is filled with None at the start, so read-before-write will cause a trap in my sim.
    #   Some programs don't seem to be too careful about that, so I fixed so most cases just get
    #   a warning, a zero and move on.  But returning a zero to an instruction fetch is not a good idea...
    # I don't know how to tell if the first 32 words of the address space are always test-storage, or if
    # it's only the first 32 words of Bank 0.  I'm assuming test storage is always accessible.
    def rd(self, addr, fix_none=True):
        if (addr & ~self._toggle_switch_mask) == 0:
            ret = self._toggle_switch_mem_default[addr][0]
            bank = 0
        elif addr & self.cb.WWBIT5:  # High half of the address space, Group B
            ret = self._coremem[self.MemGroupB][addr & self.cb.WWBIT6_15]
            bank = self.MemGroupB
        else:
            ret = self._coremem[self.MemGroupA][addr & self.cb.WWBIT6_15]
            bank = self.MemGroupA
        if fix_none and (ret is None):
            print("Reading Uninitialized Memory at location 0o%o, bank %o" % (addr, bank))
            ret = 0
        return ret

    # input for the simulation comes from a "core" file giving the contents of memory
    # Sample core-file input format, from tape-decode or wwasm
    # The image file contains symbols as well as a bit of metadata for where it came from
    # *** Core Image ***
    # @C00210: 0040000 0000100 0000001 0000100 0000000  None    None    None  ; memory load
    # @S00202: Yi                                                             ; symbol for location 202
    # %Switch: chkalarm 0o5
    def read_core(self, filename, switch_class, cb):

        cb.log.info("core file %s" % filename)
        line_number = 1
        jumpto_addr = None
        ww_file = None
        ww_tapeid = "(None)"
        ww_hash = ''
        ww_strings = ''
        ww_stats = ''

        symtab = {}
        try:
            filedesc = open(filename, 'r')
        except IOError:
            cb.log.fatal("read_core: Can't open file %s" % filename)
        for l in filedesc:
            line = l.rstrip(' \t\n\r')  # strip trailing blanks and newline
            line_number += 1
            if len(line) == 0:  # skip blank lines
                continue
            all_tokens = re.split(";", line)  # strip comments
            input_minus_comment = all_tokens[0].rstrip(' ')  # strip any blanks at the end of the line
            if len(input_minus_comment) == 0:  # skip blank lines
                continue
            if not re.match("^@C|^@S|^%[a-zA-Z]", input_minus_comment):
                continue     # ignore anything that doesn't start with @C, @S, %<something>
            if re.match("^@C", input_minus_comment):  # read a line of core memory contents
                tokens = re.split("[: \t][: \t]*", input_minus_comment)
                # print "tokens:", tokens
                if len(tokens[0]) == 0:
                    cb.log.warn("read_core parse error, read_core @C: tokens=", tokens)
                    continue
                address = int(tokens[0][2:], 8)
                for token in tokens[1:]:
                    if token != "None":
                        self.wr(address, int(token, 8), force=True)
                        # print "address %oo: data %oo" % (address, CoreMem.rd(address))
                    address += 1
            elif re.match("^@S", input_minus_comment):  # read a line with a single symbol
                tokens = re.split("[: \t][: \t]*", input_minus_comment)
                # print "tokens:", tokens
                if len(tokens) != 2:
                    cb.log.warn("read_core parse error, read_core @S: tokens=", tokens)
                    continue
                address = int(tokens[0][2:], 8)
                symtab[address] = tokens[1]

            elif re.match("^%Switch", input_minus_comment):
                tokens = input_minus_comment.split()
                switch_class.parse_switch_directive(tokens[1:])

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
                    cb.log.warn("read_core: missing arg to %String")
            elif re.match("^%String:", input_minus_comment):
                tokens = input_minus_comment.split()
                if len(tokens) > 1:
                    ww_strings += tokens[1] + '\n'
            elif re.match("^%Stats:", input_minus_comment):  # put the Colon back in here!
                tokens = input_minus_comment.split(' ', 1)
                if len(tokens) > 1:
                    ww_stats = tokens[1]
                else:
                    cb.log.warn("read_core: missing arg to %Stats")
            else:
                cb.log.warn("read_core: unexpected line '%s' in %s, Line %d" % (line, filename, line_number))

        self.metadata['strings'] = ww_strings
        self.metadata['hash'] = ww_hash
        self.metadata['stats'] = ww_stats
        self.metadata['jumpto'] = jumpto_addr
        self.metadata['filename_from_core'] = ww_file
        self.metadata['ww_tapeid'] = ww_tapeid

        return symtab, jumpto_addr, ww_file, ww_tapeid


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
            ["md",  "multiply digits no roundoff (AND)", self.OPERAND_RD_DATA] # 37o, 31d aka "AND"
            ]

        self.ext_op_decode = {
            "SR": [["srr", "srh"], ["shift right and roundoff", "shift right and hold",]],
            "SL": [["slr", "slh"], ["shift left and roundoff", "shift left and hold"]],
            "CL": [["clc", "clh"], ["cycle left and clear", "cycle left and hold"]]
            }






# See manual 2M-0277 pg 46 for flexowriter codes and addresses
class FlexoClass:
    def __init__(self, cb):
        self._uppercase = False  # Flexo used a code to switch to upper case, another code to return to lower
        self._color = False  # the Flexo had a two-color ribbon, I assume it defaulted to Black
        self.stop_on_zero = None
        self.packed = None
        self.null_count = 0
        self.FlexoOutput = []
        self.name = "Flexowriter"
        self.cb = cb   # what's the right way to do this??

        self.FLEXO_BASE_ADDRESS = 0o224  # Flexowriter printers
        self.FLEXO_ADDR_MASK = ~(0o013)  # mask out these bits to identify any Flexo address

        self.FLEXO3 = 0o010  # code to select which flexo printer.  #3 is said to be 'unused'
        self.FLEXO_STOP_ON_ZERO = 0o01  # code to select whether the printer "hangs" if asked to print a zero word
        self.FLEXO_PACKED = 0o02        # code to interpret three (six-bit) characters per word (??)

        self.FLEXO_UPPER = 0o071   # character to switch to upper case
        self.FLEXO_LOWER = 0o075   # character to switch to lower case
        self.FLEXO_COLOR = 0o020   # character to switch ribbon color
        self.FLEXO_NULLIFY = 0o077 # the character that remains on a tape after the typiest presses Delete


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


    def code_to_letter(self, code: int, show_unprintable=False, make_filename_safe=False) -> str:
        ret = ''
        if code == self.FLEXO_NULLIFY:
            self.null_count += 1

        if code == self.FLEXO_UPPER:
            self._uppercase = True
        elif code == self.FLEXO_LOWER:
            self._uppercase = False
        elif code == self.FLEXO_COLOR and show_unprintable == False:
            self._color = not self._color
            if self._color:
                return  "\033[1;31m"
            else:
                return "\033[0m"
        else:
            if self._uppercase:
                ret = self.flexocode_ucase[code]
            else:
                ret =  self.flexocode_lcase[code]

        if make_filename_safe is True:
            if ret == '\n':
                ret = ''
            elif ret == '\t':
                ret = ' '
            elif code == 0:
                ret = ''
            elif ret == '\b':
                ret = ' '
            elif ret == '<del>':
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

    def is_this_for_me(self, io_address):
        if (io_address & self.FLEXO_ADDR_MASK) == self.FLEXO_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, accumulator):
        # 0224  # select printer #2 test control by console.
        # 0234  # select printer #3
        if device & self.FLEXO3:
            print("Printer #3 not implemented")
            return cb.UNIMPLEMENTED_ALARM

        self.stop_on_zero = (device & self.FLEXO_STOP_ON_ZERO)
        self.packed = (device & self.FLEXO_PACKED)

        if self.packed:
            print("Flexowriter packed mode not implemented")
            return self.cb.UNIMPLEMENTED_ALARM

        print(("configure flexowriter #2, stop_on_zero=%o, packed=%o" % (self.stop_on_zero, self.packed)))
        return self.cb.NO_ALARM

    def rc(self, unused, acc):  # "record", i.e. output instruction to tty
        code = acc >> 10  # the code is in the upper six bits of the accumulator
        symbol = self.code_to_letter(code)  # look up the code, mess with Upper Case and Color
        self.FlexoOutput.append(symbol)
        if symbol == '\n':
            symbol = '\\n'
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

        print(("Block Transfer Write to Flexo: start address=0o%o, length=0o%o, str=%s" % \
              (address, acc, symbol_str)))
        return self.cb.NO_ALARM


    def get_saved_output(self):
        return self.FlexoOutput


class XwinCrt:
    def __init__(self, cb):
        self.cb = cb

        self.gfx = __import__("graphics")

        self.WIN_MAX_COORD = 800.0 # 1024.0 + 512.0  # size of window to request from the laptop window  manager

        self.WIN_MOUSE_BOX = self.WIN_MAX_COORD / 50.0

        self.win = self.gfx.GraphWin("Whirlwind Blackjack", self.WIN_MAX_COORD, self.WIN_MAX_COORD, autoflush=False)
        self.win.setBackground("Gray10")

        # coordinate definitions for Whirlwind CRT display
        self.WW_MAX_COORD = 1024.0
        self.WW_MIN_COORD = -self.WW_MAX_COORD
        self.WW_CHAR_HSTROKE = int(25.6 * (self.WIN_MAX_COORD / (self.WW_MAX_COORD * 2.0)))  # should be 20.0
        self.WW_CHAR_VSTROKE = int(19.2 * (self.WIN_MAX_COORD / (self.WW_MAX_COORD * 2.0)))  # should be 15.00

        self.BRIGHT = 20
        self.DARK = 0
        self.screen_brightness = {}  # a list of graphical elements, with corresponding brightness
        self.fade_delay_param = cb.crt_fade_delay_param
        self._fade_delay = self.fade_delay_param

        # The Whirlwind CRT character generator uses a seven-segment format with a bit in a seven-bit
        # word to indicate each segment.  This list defines the sequence in which the bits are
        # converted into line segments
        self.WW_CHAR_SEQ = ("down", "right", "up", "left", "up", "right", "down")

        # recall the most recent light gun display point so it can be erased when the next one comes up
        self.last_pen_point = None
        # remember the location of the last unprocessed mouse click
        self.last_mouse = None
        # remember the last character drawn
        self.last_crt_char = None

        # I've put a mouse zone in the top right corner to Exit the program, i.e., to synthesize a Whirlwind
        # alarm that causes the interpreter to exit.  Mark the spot with a red X
        l = self.gfx.Line(self.gfx.Point(self.WIN_MAX_COORD - self.WIN_MOUSE_BOX, self.WIN_MOUSE_BOX), self.gfx.Point(self.WIN_MAX_COORD, 0))
        l.setOutline("Red")
        l.setWidth(1)   # changed from 3 to 1, Apr 11, 2020
        l.draw(self.win)
        l = self.gfx.Line(self.gfx.Point(self.WIN_MAX_COORD - self.WIN_MOUSE_BOX, 0), self.gfx.Point(self.WIN_MAX_COORD, self.WIN_MOUSE_BOX))
        l.setOutline("Red")
        l.setWidth(3)
        l.draw(self.win)

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

    def ww_draw_char(self, ww_x, ww_y, mask):
        x0, y0 = self.ww_to_xwin_coords(ww_x, ww_y)
        obj = (x0, y0, 0, 0, 'C', mask)
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
    def ww_draw_line(self, ww_x0, ww_y0, ww_xd, ww_yd):

        x0, y0 = self.ww_to_xwin_coords(ww_x0, ww_y0)
        x1, y1 = self.ww_to_xwin_coords(ww_x0 + ww_xd, ww_y0 + ww_yd)

        obj = (x0, y0, x1, y1, 'L', 0)
        self.screen_brightness[obj] = self.BRIGHT

#        l = self.gfx.Line(self.gfx.Point(x0, y0), self.gfx.Point(x1, y1))
#        l.setOutline(color)
#        l.setWidth(4)
#        l.draw(self.win)

    def ww_draw_point(self, ww_x, ww_y, light_gun=False):
        x0, y0 = self.ww_to_xwin_coords(ww_x, ww_y)
        obj = (x0, y0, 0, 0, 'D', 0)
        self.screen_brightness[obj] = self.BRIGHT
        if light_gun:
            self.last_pen_point = obj  # remember the point so it can be undrawn later

    def XXXww_dim_previous_point(self):
        if self.last_pen_point is not None:
            self.last_pen_point.undraw()
            self.last_pen_point.setFill("Green")
            self.last_pen_point.draw(self.win)
            self.last_pen_point = None

    def ww_highlight_point(self):
        if self.last_pen_point is not None:
            x0 = self.last_pen_point[0]
            y0 = self.last_pen_point[1]
            c = self.gfx.Circle(self.gfx.Point(x0, y0), 5)  # the last arg is the circle dimension
            c.setFill("Red")
            c.draw(self.win)
            self.last_pen_point = None

    def ww_check_light_gun(self):
        pt = self.win.checkMouse()
        if pt is None:
            return self.cb.NO_ALARM, None
        if self.last_pen_point is None:
            print("Light Gun checked, but no dot displayed")
            return self.cb.QUIT_ALARM, None

        if (self.WIN_MAX_COORD - pt.getX() < self.WIN_MOUSE_BOX) & \
            (pt.getY() < self.WIN_MOUSE_BOX):
            print("**Quit**")
            return self.cb.QUIT_ALARM, None

        print(("dot (%d, %d);  mouse (%d, %d)" % (self.last_pen_point[0], self.last_pen_point[1], \
                                                 pt.getX(), pt.getY())))
        return self.cb.NO_ALARM, pt


    def _render_char(self, x, y, mask, color):
        last_x = x
        last_y = y
        for i in range(0, 7):
            if self.WW_CHAR_SEQ[i] == "down":
                y = last_y + self.WW_CHAR_VSTROKE
            elif self.WW_CHAR_SEQ[i] == "up":
                y = last_y - self.WW_CHAR_VSTROKE
            elif self.WW_CHAR_SEQ[i] == "left":
                x = last_x - self.WW_CHAR_HSTROKE
            elif self.WW_CHAR_SEQ[i] == "right":
                x = last_x + self.WW_CHAR_HSTROKE
            else:
                print(("OMG its a bug! WW_CHAR_SEQ[%d]=%s " % (i, self.WW_CHAR_SEQ[i])))

            if mask & 1 << (6 - i):
                seg_color = color
            else:
                seg_color = "Grey15"

            l = self.gfx.Line(self.gfx.Point(last_x, last_y), self.gfx.Point(x, y))
            l.setOutline(seg_color)
            l.setWidth(4)
            l.draw(self.win)
            last_x = x
            last_y = y


    # This routine should be called "periodically", i.e., at constant-time intervals
    # For now, I think that means "every N instruction cycles"
    def ww_scope_update(self):
        for_deletion = []
        for i in range(self.DARK, self.BRIGHT+1):
            for obj in self.screen_brightness:
                x0 = obj[0]
                y0 = obj[1]
                x1 = obj[2]
                y1 = obj[3]
                graphical_type = obj[4]  # L=line, D=dot, C=char
                char_mask = obj[5]  # ascii character
                intensity = self.screen_brightness[obj]
                if intensity == i:
                    # print("draw", obj, intensity)
                    green = intensity * (256 / (self.BRIGHT - self.DARK))  # I'm sure I'm not scaling the color properly
                    if green > 255:
                        green = 255
                    color = self.gfx.color_rgb(0, int(green), 0)
                    if graphical_type == 'D':  # it's a Dot
                        c = self.gfx.Circle(self.gfx.Point(x0, y0), 3)  # was 5 # the last arg is the circle dimension
                        c.setFill(color)
                        c.draw(self.win)
                    elif graphical_type == 'L':  # it's a line
                    #    self._ww_draw_line(x0, y0, x1, y1, color)
                        l = self.gfx.Line(self.gfx.Point(x0, y0), self.gfx.Point(x1, y1))
                        l.setOutline(color)
                        l.setWidth(4)
                        l.draw(self.win)

                    elif graphical_type == 'C':  # it's a char
                        self._render_char(x0, y0, char_mask, color)
        self.gfx.update()
        # step two, decay the brightness of each object
        if self._fade_delay <= 0:
            self._fade_delay = self.fade_delay_param
            for obj in self.screen_brightness:
                intensity = self.screen_brightness[obj]
                # print("decay", obj, intensity)
                intensity -= 1
                if intensity < 0:
                    for_deletion.append(obj)
                else:
                    self.screen_brightness[obj] = intensity
            for obj in for_deletion:
                del self.screen_brightness[obj]
        self._fade_delay -= 1
