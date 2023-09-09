# Whirlwind I/O Device Simulation
# This file contains classes to simulate various Whirlwind I/O devices
# Function is mostly based on Whirlwind Manual 2M-0277
# Guy Fedorkow, July 2018

# Copyright 2020 Guy C. Fedorkow
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


import wwinfra
import re


# this class is a template for new I/O devices
#  Add a new device to this file, plus put its name in IODeviceList in wwsim.py,
#  and put its addresses in wwinfra.py
class DummyIoClass:
    def __init__(self, cb):
        self.cb = cb

        self.DUMMY_BASE_ADDRESS = 0o10000  # starting address of Drum device(s)
        self.DUMMY_ADDR_MASK = ~0o001  # mask out the sub-addresses
        self.name = "Dummy"

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if (io_address & self.DUMMY_ADDR_MASK) == self.DUMMY_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, acc, _cm):
        print("SI: configured device ; decode more params")
        return self.cb.NO_ALARM

    def rc(self, unused, acc):  # "record", i.e. output instruction to device
        print("unimplemented %s Record" % self.name)
        return self.cb.UNIMPLEMENTED_ALARM, 0



class CameraClass:
    def __init__(self, cb):
        self.cb = cb

        self.CAMERA_INDEX_BASE_ADDRESS = 0o04  # starting address of Drum device(s)
        self.CAMERA_INDEX_ADDR_MASK = ~0o001  # mask out the sub-addresses
        self.name = "Camera Index Control"

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if (io_address & self.CAMERA_INDEX_ADDR_MASK) == self.CAMERA_INDEX_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, acc, _cm):
        print("SI: Index Camera to next frame")
        return self.cb.NO_ALARM

    def rc(self, unused, acc):  # "record", i.e. output instruction to device
        print("unimplemented %s Record" % self.name)
        return self.cb.UNIMPLEMENTED_ALARM, 0


# From 2M-0277
# 3.3 PHOTOEIECTRIC TAPE READER
# The Ferranti photoelectric tape reader, abbreviated PETR, reads the seven hole
# paper tape punched by the Flexowriter. The maximum reading speed of the
# PETR is between 190 and 220 lines per second. If the motor is OFF when PETR is
# selected by the computer, approximately 15 seconds is necessary for the reader to
# attain its maximum speed. After the PETR bas been deselected, its motor continues
# to run for from 30 to 45 seconds. If PETR is reselected within this time, the
# reader is at full speed in 2 or 3 milliseconds. PETR is a free-running unit;
# that is, once selected, it continues to run until deselected by an si instruction.
# # 3.3.5 si Addresses for the Photoelectric Reader
#                      PETR
# read line-by-line:
#    si 210 (o)           A
#    si 211 (o)           B
# read word-by-word:
#    si 212 (o)           A
#    si 213 (o)           B

# I am assuming that the machine could be programmed to alternate between PETRA and PETRB, although
# I'm not really sure PETRB was even used.
# I am also assuming that the tape doesn't get changed during operation of the program; i.e., we can read
# in the whole tape at the first reference.
class PhotoElectricTapeReaderClass:
    def __init__(self, cb):
        global petrAfile
        global petrBfile
        self.cb = cb


        self.name = "PhotoElectricTapeReader"
        self.PETR_device = 'A'
        self.PETR_mode = 'Word'
        self.PETR_fd = {'A':None, 'B':None}   # we won't try to open the file until the device is first accessed.
        # But if we open the file, we'll read all of it into an array of bytes for later use, indexed by unit letter
        self.PETR_tape_image = {'A':None, 'B':None}  # two arrays containing the contents of the tape
        # we assume the paper tape cannot be rewound; start the offset at zero and go up from there!
        self.PETR_read_offset = {'A': 0, 'B': 0}

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if (io_address & self.cb.PETR_ADDR_MASK) == self.cb.PETR_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, acc, _cm):  # the device's mode of operation comes hidden in the Device field
        if device & 0o1:
            self.PETR_device = 'B'
            filename = self.cb.PETRBfilename
        else:
            self.PETR_device = 'A'
            filename = self.cb.PETRAfilename
        if device & 0o2:
            self.PETR_mode = 'Word'
        else:
            self.PETR_mode = 'Char'

        if self.PETR_fd[self.PETR_device] is None:
            try:
                self.PETR_fd[self.PETR_device] = open(filename, "r")
                fd = self.PETR_fd[self.PETR_device]
                print("Using file %s for PETR %s" % (filename, self.PETR_device))
            except:
                print("Can't open paper tape file %s" % filename)
                exit(1)
            self.PETR_tape_image[self.PETR_device] = self.read_tape_file(fd, filename)
            fd.close()

        print("SI: PhotoElectricTapeReader %s initialized in %s mode " % (self.PETR_device, self.PETR_mode))
        return self.cb.NO_ALARM

    def rc(self, unused, acc):  # "record"
        print("unimplemented rc: Punch to PhotoElectric Reader")
        return self.cb.UNIMPLEMENTED_ALARM, 0

    def rd(self, code, acc):  # "read"
        if self.PETR_mode == "Char":
            offset = self.PETR_read_offset[self.PETR_device]
            if offset >= len(self.PETR_tape_image[self.PETR_device]):
                print('PETR Overrun at Offset %d' % offset)
                return self.cb.IO_ERROR_ALARM, 0
            ret = self.PETR_tape_image[self.PETR_device][offset]
            self.PETR_read_offset[self.PETR_device] += 1
            print("RD: PhotoElectricTapeReader %s read character 0o%o " % (self.PETR_device, ret))
            return self.cb.NO_ALARM, ret
        print("unimplemented rd: PhotoElectric Read from file %s, mode %s" % (self.PETR_device, self.PETR_mode))
        return self.cb.UNIMPLEMENTED_ALARM, 0

    def bi(self, address, acc, cm):  # "block transfer in"
        """ {2) Reading Word-by-Word by Block-Transfer Instruction
            A bi instruction may take the place of a series of rd instructions. The address
            of tbe bi must be the initial address of the block of registers in MCM to
            which the words will be transferred, and +n, the number of words to be read, must
            be stored (times 2-15) in AC. The time required for the block transfer is the
            same as the total time required to perform the rd instructions it replaces. Any
            sequence of rd and bi instructions may follow a single si.
        """
        print("block transfer PETR: start address 0o%o, length 0o%o Unimplemented" % (address, acc))
        return self.cb.UNIMPLEMENTED_ALARM
#        if address + acc > self.cb.WW_ADDR_MASK:
#            print "block transfer in PETR out of range"
#            return self.cb.QUIT_ALARM
#        for m in range(address, (address + acc)):
#            w = 0
#            cm.wr(m, w)  # write zero
#        return self.cb.NO_ALARM

    # Once a WW program has started, it may go back to read the remaining characters on the paper tape.
    # This routine inhales the rest of the tape from a file, storing it in an array to be doled out
    # later to individual RD instructions.
    # Sample tape-file input format, from tape-decode
    # *** Tape Image ***
    # @T00210: 0040000 0000100 0000001 0000100 0000000  None    None    None  ; memory load
    # unlike Core files, this format doesn't express addresses.  It does include an offset from the
    # start of the tape, but that's just for debug.
    # There are no directives in this file.
    def read_tape_file(self, filedesc, filename):

        LineNumber = 1
        offset = 0

        tape_image = []

        for ln in filedesc:
            line = ln.rstrip(' \t\n\r')  # strip trailing blanks and newline
            LineNumber += 1
            if len(line) == 0:  # skip blank lines
                continue
            all_tokens = re.split(";", line)  # strip comments
            input_minus_comment = all_tokens[0].rstrip(' ')  # strip any blanks at the end of the line
            if len(input_minus_comment) == 0:  # skip blank lines
                continue
            if input_minus_comment[0] == '%':
                continue   # skip the name directives
            if re.match("^@T", input_minus_comment):  # read a line of tape bytes
                tokens = re.split("[: \t][ \t]*", input_minus_comment)
                # print "tokens:", tokens
                if len(tokens[0]) == 0:
                    print("parse error, read_tape @C: tokens=", tokens)
                    continue
                offset = int(tokens[0][2:], 8)
                for token in tokens[1:]:
                    if token != "None":
                        tape_image.append(int(token, 8))
                    offset += 1

            else:
                print("unexpected line '%s' in %s, Line %d" % (line, filename, LineNumber))

        print("read Tape File %s, length=%d characters (%3.1f words)" % (filename, offset, float(offset)/3.0))
        return tape_image


# this class is a "device" that can be used to clear a block of memory
# From 2M-0277

# 4.7 PROGRAMMED CORE CLEARING
# A special mde of clearing magnetic core memory can be selected by the
# use of this instruction si 17 (o) which initiates the process of readng +O
# into a block of registers, thereby clearing them. A bi y, where y is the
# initial addess of the block, then clears the block length determined by
# +/-n in the accumulator, where n is the number of registers to be cleared.
# For example, the following octal program:
#    si 17
#    ca RCn  (n is numebr of words in AC)
#    bi RCy  (y is initial register adress of the block)
class CoreClearIoClass:
    def __init__(self, cb):
        self.cb = cb
        self.name = "CoreClear"

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if (io_address & self.cb.CLEAR_ADDR_MASK) == self.cb.CLEAR_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, acc, _cm):
        print("SI: 'Clear Memory' device initialized ")
        return self.cb.NO_ALARM

    def rc(self, unused, acc):  # "record"
        print("unimplemented rc: Core Clear Record")
        return self.cb.UNIMPLEMENTED_ALARM, 0

    def rd(self, code, acc):  # "read"
        print("unimplemented rd: Core Clear Read")
        return 0

    def bi(self, address, acc, cm):  # "block transfer in"
        """ perform a block transfer input instruction
            address: starting address for block
            acc: contents of accumulator (the word count)
            cm: core memory instance
        """
        print("block transfer Clear Memory: start address 0o%o, length 0o%o" % (address, acc))
        if address + acc > self.cb.WW_ADDR_MASK:
            print("block transfer in Clear Mem out of range")
            return self.cb.QUIT_ALARM
        for m in range(address, (address + acc)):
            cm.wr(m, 0)  # write zero
        return self.cb.NO_ALARM


class FFResetIoClass:
    def __init__(self, cb):
        self.cb = cb
        self.name = "FlipFlopRegisterReset"
        self.cm = None

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if (io_address & self.cb.FFCLEAR_ADDR_MASK) == self.cb.FFCLEAR_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, acc, cm):
        self.cb.log.info("SI: Select Flip-Flop Storage Reset ")
        self.cm = cm
        self.cm.reset_ff(self.cb.cpu)  # it seems that just 'selecting' the FF Register Reset makes it happen
        return self.cb.NO_ALARM

    def rc(self, unused, acc):  # "record"   Not sure this case can ever happen
        self.cb.log.info("RC: Activate Flip-Flop Storage Reset ")
        self.cm.reset_ff(self.cb.cpu)
        return self.cb.NO_ALARM, 0

    def rd(self, code, acc):  # "read"
        print("unimplemented rd: FF Reset")
        return 0

    def bi(self, address, acc, cm):  # "block transfer in"
        print("unimplemented rd: FF Reset")
        return self.cb.NO_ALARM


# Whirlwind had a teletype system in addition to the Flexowriter
class tty_class:
    def __init__(self, cb):
        self.cb = cb
        self.FigureShift = False
        #  2M-0277_Whirlwind_Programming_Manual_Oct58.pdf
        #  pg 94 for the teletype code chart
        #  Watch for the typo in Fig 18 -- Two 'Z', no 'A'
        #  Page 95 also says that the Record instruction increments the PC
        #  by two if the printer is busy, the instruction is always followed
        # by two branch instructions, (often one forward, one back)
        #  ls = Letter Shift
        #  fs = Figure Shift
        tty_letters = ["<null>", "T", "\n", 'O', " ", "H", "N", "M",
                       "lf", "L", "R", "G", "I", "P", 'C', 'V',
                       'E', 'Z', 'D', 'B', 'S', 'Y', 'F', 'X',
                       'A', 'W', 'J', 'fs', 'U', 'Q', 'K', 'ls']

        tty_figures = ['00', '5', '\n', '9', ' ', '#', '7/8', '.',
                       'lf', '3/4', '4', '&', '8', '0', '1/8', '3/8',
                       '3', '"', '$', '5/8', '^g', '6', '1/4', '/',
                       '-', '2', "'", 'fs', '7', '1', '1/2', 'ls']

        self.tty_charset = [tty_letters, tty_figures]
        self.IO_ADDRESS_TTY = 0o402
        self.TTYoutput = []
        self.name = "Teletype"

    def code_to_letter(self, w):  # input is a 16-bit word with three packed 5-bit characters
        wstr = ""
        for shift in range(2, -1, -1):
            code = (w >> shift * 5) & 0o37
            if code == 0o33:
                self.FigureShift = True
            elif code == 0o37:
                self.FigureShift = False
            else:
                wstr += self.tty_charset[self.FigureShift][code]
        return wstr

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if io_address == self.IO_ADDRESS_TTY:
            return self
        else:
            return None

    def si(self, _device, _acc, _cm):   # the tty device needs no further initialization
        return self.cb.NO_ALARM

    def rc(self, _unused, acc):  # "record", i.e. output instruction to tty
        code = acc
        symbol = self.code_to_letter(code)  # this actually returns three symbols
        self.TTYoutput.append(symbol)
        return self.cb.NO_ALARM, symbol

    def get_saved_output(self):
        return self.TTYoutput


class DrumClass:
    def __init__(self, cb):
        self.cb = cb
        self.word_address = None      # this would have to be angular offset from the index point of the drum
        self.group_address = None     # this would have to be track number
        self.drum_unit = None         # 1 for "Buffer Drum", 0 for "Aux Drum"
        self.drum_name = None
        self.wrap_address = None
        self.record_mode = None
        self.buffer_drum_field = 'A'  # alternate between A and B
        self.dirty = False   # keep a bit to say if the contents of the drum might have been changed
        self.metadata = {}

        # drum capacity
        self.DRUM_NUM_GROUPS = 12         # 12 tracks
        self.DRUM_NUM_WORDS = 2048        # words per track
        self._drum_content = [[None] * self.DRUM_NUM_WORDS for _i in range(self.DRUM_NUM_GROUPS)]

        # drum address decode
        self.DRUM_SI_WORD_ADDRESS = 0o001
        self.DRUM_SI_GROUP_ADDRESS = 0o002
        self.DRUM_SI_RECORD_MODE = 0o004
        self.DRUM_SI_BUFFERDRUM = 0o010
        self.DRUM_SI_WRAP_ADDRESS = 0o01000

        self.name = "Drum"

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if io_address & self.cb.DRUM_ADDR_MASK == self.cb.DRUM_BASE_ADDRESS:
            return self
        elif io_address == self.cb.DRUM_SWITCH_FIELD_ADDRESS:
            return self
        else:
            return None

    # 2M-0277, pg 25/26
    # The drum address to be selected is determined by the si instruction and
    # by any necessary portions of the contents of AC at the time the si is executed.
    # The si instruction may call for a new group number, a new initial storage
    # address, neither, or both. When a new group number is needed, it is taken
    # from digits l - 4 of AC. When a new initial storage address is needed, it is
    # taken from digits 5 - 15 of AC. Either the group selected on the drum can remain
    # selected until an si instruction specifically calls for a change of group
    # or, by adding 1000 to the original auxiliary drum si, a block transfer is permitted
    # to run off the end of one drum group to the beginning of the next drum
    # group. The next storage address selected will be one greater than the storage
    # address most recently referred to, unless an si instruction specifically calls
    # for a new initial storage address
    #
    # guy adds: we must note that the doc seems ambiguous about how to tell if it's Buffer or Aux drum
    # # sheesh; Now I don't see what's ambiguous, as of June 6, 2019 !!!  RATS!!!
    def si(self, device, acc, _cm):  # the drum's mode of operation is in the Device field, with address in the acc
        if device == self.cb.DRUM_SWITCH_FIELD_ADDRESS:
            old_field = self.buffer_drum_field
            if old_field == 'A':
                new_field = 'B'
            else:
                new_field = 'A'
            self.buffer_drum_field = new_field
            self.cb.log.fatal("haven't implemented SI: switch Buffer Drum Field %s to %s" % (old_field, new_field))
            return self.cb.NO_ALARM

        # the 'normal' drum addressing comes in here...
        self.wrap_address = (device & self.DRUM_SI_WRAP_ADDRESS)
        self.record_mode = (device & self.DRUM_SI_RECORD_MODE)
        if device & self.DRUM_SI_GROUP_ADDRESS:
            self.group_address = (acc >> 11) & 0o17
        if device & self.DRUM_SI_WORD_ADDRESS:
            self.word_address = acc & 0o3777
        if device & self.DRUM_SI_BUFFERDRUM != 0:
            self.drum_name = "Buf"
        else:
            self.drum_name = "Aux"

#        if (device & self.DRUM_SI_BUFFERDRUM != 0) & (acc & self.cb.WWBIT0 != 0):
#            self.drum_unit = 1
#        elif (device & self.DRUM_SI_BUFFERDRUM == 0) & (acc & self.cb.WWBIT0 == 0):
#            self.drum_unit = 1
#        else:
#            print "Ambiguous Drum Unit Number: acc = 0o%o, Device = 0o%o" % (acc, device)
        print("SI: configured %s drum; Group (track)=0o%o, DrumWordAddress=0o%o" %
              (self.drum_name, self.group_address, self.word_address))
        return self.cb.NO_ALARM

    def rc(self, _unused, acc):  # "record", i.e. output instruction to drum
        cb = self.cb
        cb.log.info("RC: write-to-%s-drum; Field=%s, Word=0o%o, Group (track)=0o%o, DrumWordAddress=0o%o" %
              (self.drum_name, self.buffer_drum_field, acc, self.group_address, self.word_address))
        self._drum_content[self.group_address][self.word_address] = acc
        self.dirty = True
        self.word_address += 1
        if self.word_address > self.DRUM_NUM_WORDS:
            cb.log.fatal("Haven't implemented Drum Address Wrap")
            return cb.UNIMPLEMENTED_ALARM, 0
        return cb.NO_ALARM, 0

    def rd(self, _unused, acc):  # read one byte from the drum
        cb = self.cb
        cb.log.info("RD: read-from-%s-drum; Field=%s, Word=0o%o, Group (track)=0o%o, DrumWordAddress=0o%o" %
              (self.drum_name, self.buffer_drum_field, acc, self.group_address, self.word_address))
        val = self._drum_content[self.group_address][self.word_address]
        self.word_address += 1
        if self.word_address > self.DRUM_NUM_WORDS:
            cb.log.fatal("Haven't implemented Drum Address Wrap")
            return self.cb.UNIMPLEMENTED_ALARM, 0
        if val is None:
            cb.log.warn("Read None from Drum Group (track)=0o%o, DrumWordAddress=0o%o" %
                        (self.group_address, self.word_address))
        return cb.NO_ALARM, val

    def bi(self, address, acc, cm):  # "block transfer in"
        """ perform a block transfer input instruction
            address: starting address for block
            acc: contents of accumulator (the word count)
            cm: core memory instance
        """
        # The Book does not say that the word-count is masked to 11 bits, but it sure looks like it
        # should be.
        cb = self.cb
        bi_len = acc & self.cb.WW_ADDR_MASK
        cb.log.info("BI: block transfer Read from %s Drum: Field=%s, DrumGroup=0o%o, DrumAddr=0o%o, start at CoreAddr=0o%o, length=0o%o" %
              (self.drum_name, self.buffer_drum_field, self.group_address, self.word_address, address, bi_len))
        if address + bi_len > self.cb.WW_ADDR_MASK:
            cb.log.warn("block-transfer-in Drum address out of range")
            return self.cb.QUIT_ALARM
        for m in range(address, (address + bi_len)):
            wrd = self._drum_content[self.group_address][self.word_address]  # read the word from drum
            self.word_address += 1
            if self.word_address > self.DRUM_NUM_WORDS:
                cb.log.warn("Haven't implemented Drum Address Wrap")
                return self.cb.UNIMPLEMENTED_ALARM, 0
            cm.wr(m, wrd)  # write the word to mem
        return self.cb.NO_ALARM

    def bo(self, address, acc, cm):  # "block transfer out"
        """ perform a block transfer output instruction to write stuff to drum
            address: starting address for block
            acc: contents of accumulator (the word count)
            cm: core memory instance
        """
        cb = self.cb
        bo_len = acc & self.cb.WW_ADDR_MASK
        print("BO: block transfer Write to %s Drum: Field=%s, DrumGroup=0o%o, DrumAddr=0o%o, start at CoreAddr=0o%o, length=0o%o" %
              (self.drum_name, self.buffer_drum_field, self.group_address, self.word_address, address, bo_len))
        if address + bo_len > self.cb.WW_ADDR_MASK:
            cb.log.warn("block-transfer-out Drum address out of range")
            return self.cb.QUIT_ALARM
        for m in range(address, (address + bo_len)):
            wrd = cm.rd(m)  # read the word from mem
            self._drum_content[self.group_address][self.word_address] = wrd  # write the word to drum
            self.dirty = True   # we changed the state of the drum; needs to be saved on exit
            self.word_address += 1
            if self.word_address > self.DRUM_NUM_WORDS:
                print("Haven't implemented Drum Address Wrap")
                return self.cb.UNIMPLEMENTED_ALARM, 0
        return self.cb.NO_ALARM

    def save_drum_state(self, drum_state_file_name):
        cb = self.cb
        if self.dirty is False:
            cb.log.info("Drum State unchanged; state not saved")
            return

        cb.log.info("Saving Drum State in file %s" % drum_state_file_name)
        drumlist = self._drum_content
        offset = 0
        byte_stream = False
        jump_to = None
        string_list = ''
        ww_tapeid = 'drum'
        ww_filename = 'drum'
        wwinfra.write_core(cb, drumlist, offset, byte_stream, ww_filename, ww_tapeid,
                   jump_to, drum_state_file_name, string_list)

    def restore_drum_state(self, drum_state_file_name):
        cb = self.cb
        cb.log.info("Restoring Drum State from file %s" % drum_state_file_name)
        return wwinfra.read_core(self, drum_state_file_name, None, cb)

    # the wr method is used only to allow the drum state to be restored using the
    # generic memory "core" reader
    def wr(self, drum_address, value, track=0, force=False):
        cb = self.cb
        # cb.log.info("write a word=0o%o into the drum store, track=0o%o, drum_addr=0o%o" % (value, track, drum_address))
        self._drum_content[track][drum_address] = value


# The Oscilloscope Display contains a character generator that can draw arbitrary seven segment
# characters at a screen location based on a bit map supplied by the programmer
# This routine renders the bit map in ASCII Art, returning an array of lines with dashes, spaces
# and bars to render the glyph.
# See page 60 of 2M-277 for a picture of the segment layout
class SevenSegClass:
    def __init__(self):
        self.TOP_RIGHT = 0o001
        self.TOP = 0o002
        self.TOP_LEFT = 0o004
        self.MIDDLE = 0o0010
        self.BOTTOM_RIGHT = 0o0020
        self.BOTTOM = 0o0040
        self.BOTTOM_LEFT = 0o0100

        self.HORIZ_STROKE = "-----"
        self.HORIZ_BLANK = "     "
        self.HORIZ_SPACER = "   "

    def render_char(self, bits):
        # do the three horizontal strokes
        self.lines = []
        self.line = [''] * 5
        i = 0
        for mask in (self.TOP, self.MIDDLE, self.BOTTOM):
            if bits & mask:
                self.line[i] = self.HORIZ_STROKE
            else:
                self.line[i] = self.HORIZ_BLANK
            i += 2

        # do the two vertical strokes
        i = 1
        for mask in ((self.TOP_LEFT, self.TOP_RIGHT), (self.BOTTOM_LEFT, self.BOTTOM_RIGHT)):
            if bits & mask[0]:
                self.line[i] = "|"
            else:
                self.line[i] = " "
            self.line[i] += self.HORIZ_SPACER
            if bits & mask[1]:
                self.line[i] += "|"
            else:
                self.line[i] += " "
            i += 2

        # glue the result together into an array of strings
        self.lines.append(self.line[0])
        self.lines.append(self.line[1])
        self.lines.append(self.line[1])
        self.lines.append(self.line[2])
        self.lines.append(self.line[3])
        self.lines.append(self.line[3])
        self.lines.append(self.line[4])
        return self.lines


# Whirlwind had a number of display scopes attached, but it appears that the same basic picture was
# displayed on all of them, with some variation.  So each command selects a subset of the scopes for
# display of the next point, line or character.
# Similarly, there were a number of light guns, each of which can detect the same point when/if it's
# drawn on the holder's display.
# See 2M-0277
#
# I revised this substantially June 2019 to come closer to emulating the real phosphor; so each object
# we draw goes into a display list, which eventually get aged out by a 'background' scan that runs
# every N simulation cycles.
#  I also got rid of the ascii character display function, as the graphics display has been
# pretty reliable.

class DisplayScopeClass:
    def __init__(self, cb):
        # instantiate the class full of constants; what's the Right way to do this??
        self.cb = cb

        # self.DISPLAY_POINTS_BASE_ADDRESS = 00600   # starting address of point display
        # self.DISPLAY_POINTS_ADDR_MASK = ~(0077)    # mask out the sub-addresses
        # self.DISPLAY_VECTORS_BASE_ADDRESS = 01600  # starting address of vector display
        # self.DISPLAY_VECTORS_ADDR_MASK = ~(0077)   # mask out the sub-addresses
        # self.DISPLAY_CHARACTERS_BASE_ADDRESS = 02600  # starting address of vector display
        # self.DISPLAY_CHARACTERS_ADDR_MASK = ~(01077)  # mask out the sub-addresses
        # self.DISPLAY_EXPAND_BASE_ADDRESS = 00014   # starting address of vector display
        # self.DISPLAY_EXPAND_ADDR_MASK = ~(0001)    # mask out the sub-addresses

        self.DISPLAY_MODE_POINTS = 1
        self.DISPLAY_MODE_VECTORS = 2
        self.DISPLAY_MODE_CHARACTERS = 3
        self.ModeNames = ["No Mode", "Points", "Vectors", "Characters"]

        self.name = "DisplayScope"
        self.scope_select = None  # identifies which of the zillion oscilloscopes to brighten for the next op
        self.scope_mode = None    # Points, Vectors or Characters
        self.scope_expand = 1.0   # by default, characters are not "expanded" (See 2M-0277 pg 63)
        self.scope_vertical = None   # scope coords are stored here as Pythonic numbers from -1023 to +1023
        self.scope_horizontal = None

#        self.crt = wwinfra.XwinCrt(cb)
        self.crt = None  # don't open the xwin display until the WW application actually tries to select it.

    def convert_scope_coord(self, ac):
        # the vertical axis for stuff coming up is stored in the left-most 11 bits of the accumulator.
        # convert the coords from ones complement into Pythonic Numbers
        # see pg 59 of 2M-0277

        # 3.8.2 Scope Deflection
        # The left-hand 11 digits of AC (including the sign digit), at the time a
        # display instruction is given, determine the direction and amount of deflection.
        # The positive direction of horizontal deflection is to the right ad positive
        # vertical deflection is upward. The value 1 - 2**10 or its negative will produce
        # the maximum deflection. The center of the scope represents the origin with zero
        # horizontal and vertical deflection.
        if ac & self.cb.WWBIT0:  # test the sign bit for Negative
            extra_deflection_bits = ~ac & 0o37
            ret = -(ac ^ self.cb.WWBIT0_15) >> 5
        else:
            extra_deflection_bits = ac & 0o37
            ret = ac >> 5

        # I checked "underflow" in the graphics value, but I don't think WW programmers cared.  It underflows
        #  All The Time...
        # if extra_deflection_bits != 0:
        #     print("Warning:  bits lost in scope deflection; AC=0o%o" % ac)
        return ret

    # ...vector starting at the point whose coordinates have just been
    # established, where the sign and length of the horizontal component
    # are given by the first six digits of v, and the sign and length
    # of the vertical component are given by digits 8 to 13 of this
    # register.
    def convert_delta_scope_coord(self, ww_delta):
        ww_xd = (ww_delta >> 10) & 0o77
        if ww_xd & 0o40:  # the short coordinate form is used in vector generation, and is a six bit signed number
            ww_xd = -(ww_xd ^ 0o37)  # so we flip the sign if negative...
        ww_yd = (ww_delta >> 2) & 0o77
        if ww_yd & 0o40:  # the short coordinate form is used in vector generation, and is a six bit signed number
            ww_yd = -(ww_yd ^ 0o37)  # so we flip the sign if negative...
        return ww_xd, ww_yd

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if ((io_address & self.cb.DISPLAY_POINTS_ADDR_MASK) == self.cb.DISPLAY_POINTS_BASE_ADDRESS) | \
                ((io_address & self.cb.DISPLAY_VECTORS_ADDR_MASK) == self.cb.DISPLAY_VECTORS_BASE_ADDRESS) | \
                ((io_address & self.cb.DISPLAY_CHARACTERS_ADDR_MASK) == self.cb.DISPLAY_CHARACTERS_BASE_ADDRESS) | \
                ((io_address & self.cb.DISPLAY_EXPAND_ADDR_MASK) == self.cb.DISPLAY_EXPAND_BASE_ADDRESS):
            return self
        else:
            return None

    def si(self, io_address, acc, _cm):
        # If this is the first reference to the CRT Display,
        # open one of the two possible graphical displays, either the XWin laptop display, or the hardware
        # interface to an analog scope display using Rainer Glaschik's RasPi I/O module
        if self.crt is None:  # first time there's a CRT SI instruction, we'll init the display modules
            self.crt = wwinfra.XwinCrt(self.cb)
            if not self.cb.analog_display:  # can't show Widgets on an analog scope
                self.cb.dbwgt.add_scope(self.crt.win)  # tell the debug widget that there's a display available

        if (io_address & self.cb.DISPLAY_EXPAND_ADDR_MASK) == self.cb.DISPLAY_EXPAND_BASE_ADDRESS:
            # See 2M-0277 Page 63; not clear exactly how this Expand thing works!
            expand_op = io_address & self.cb.DISPLAY_EXPAND_ADDR_MASK  # o14=Expand, o15=UnExpand
            if self.cb.TraceQuiet is False:
                print("DisplayScope SI: Display Expand Operand set to 0o%o; Expand=0o14, UnExpand=0o15" % expand_op)
            if expand_op == 0o14:
                self.scope_expand = 2.0
            else:
                self.scope_expand = 1.0
            return self.cb.NO_ALARM

        if (io_address & self.cb.DISPLAY_POINTS_ADDR_MASK) == self.cb.DISPLAY_POINTS_BASE_ADDRESS:
            self.scope_mode = self.DISPLAY_MODE_POINTS
        elif (io_address & self.cb.DISPLAY_VECTORS_ADDR_MASK) == self.cb.DISPLAY_VECTORS_BASE_ADDRESS:
            self.scope_mode = self.DISPLAY_MODE_VECTORS
        elif (io_address & self.cb.DISPLAY_CHARACTERS_ADDR_MASK) == self.cb.DISPLAY_CHARACTERS_BASE_ADDRESS:
            if io_address & 0o01000 and self.cb.TraceQuiet is False:
                print("DisplayScope SI: set scope selection to 0o%o; ignoring ioaddr bit 001000..." % io_address)
            self.scope_mode = self.DISPLAY_MODE_CHARACTERS

        self.scope_select = ~self.cb.DISPLAY_POINTS_ADDR_MASK & io_address
        self.scope_vertical = self.convert_scope_coord(acc)

        if self.cb.TraceQuiet is False:
            print("DisplayScope SI: configured display mode %s, scope 0o%o, vertical=0o%o" %
                  (self.ModeNames[self.scope_mode], self.scope_select, self.scope_vertical))
        return self.cb.NO_ALARM

    def rc(self, operand, acc):  # "record", i.e. output instruction to scope.
        # Plot something on the Oscilloscope
        # if it's a point, the vertical was previously specified in an SI instruction
        #   and the ACC contains the horizontal
        # if it's a character, the operand address part of the instruction gives the address of a
        #   memory location containing the bit mask of the seven-segment character to be rendered,
        #   in bits 1-7.
        self.scope_horizontal = self.convert_scope_coord(acc)
        if self.scope_mode == self.DISPLAY_MODE_CHARACTERS:
            # add each new character to a Pending list; draw them when the program asks for light gun input
            mask = (operand >> 8) & 0o177  # it's a seven-bit quantity to turn on character segments
            if not self.cb.TraceQuiet:
                print("DisplayScope RC: record to scope, mode=Character, x=0o%o, y=0o%o, char-code=0o%o" %
                      (self.scope_horizontal, self.scope_vertical, mask))
            self.crt.ww_draw_char(self.scope_horizontal, self.scope_vertical, mask, self.scope_expand)

        elif self.scope_mode == self.DISPLAY_MODE_POINTS:
            if not self.cb.TraceQuiet:
                print("DisplayScope RC: record to scope, mode=Point, x=0o%o, y=0o%o" %
                      (self.scope_horizontal, self.scope_vertical))
            self.crt.ww_draw_point(self.scope_horizontal, self.scope_vertical, light_gun=True)

        elif self.scope_mode == self.DISPLAY_MODE_VECTORS:
            # lines are like points, but with an additional delta in the RC instruction
            ww_xd, ww_yd = self.convert_delta_scope_coord(operand)

            if self.cb.TraceQuiet is False:
                print("DisplayScope RC: record to scope, mode=Vector, x=0o%o, y=0o%o, xd=0o%o, yd=0o%o" %
                  (self.scope_horizontal, self.scope_vertical, ww_xd, ww_yd))
            self.crt.ww_draw_line(self.scope_horizontal, self.scope_vertical, ww_xd, ww_yd)

        return self.cb.NO_ALARM, 0

    # doing a "read" operation on the CRT display returns the status of the Light Gun, indicating if the
    #   trigger was pulled when the last spot was displayed
    # The sign bit will be off if the trigger was not pulled and the gun didn't see anything.
    # If the sign bit is on, the return code can be analyzed to figure out which gun had been triggered.
    # See 2M-0277 pg 72 for grubby details
    def rd(self, _code, _acc):

        # self.crt.ww_dim_previous_point()
        self.crt.ww_draw_point(self.scope_horizontal, self.scope_vertical, light_gun=True)
        # self.crt.ww_scope_update()  # flush pending display commands
        alarm, pt, button = self.crt.ww_check_light_gun(self.cb)

        if alarm == self.cb.QUIT_ALARM:
            return alarm, 0

        val = 0  # default return value is "nothing happening here"
        if self.cb.ana_scope:
            if pt is not None:   # don't care what it is, just not None
                val = 0o177777  # or  0o177777 for a light gun hit

        else:
            if pt is not None:
                self.crt.last_mouse = pt
                self.crt.last_button = button

            # check to see if the most recent mouse click was near the last dot to be drawn on the screen; if so,
            # count it as a hit, otherwise its a miss.  One it hits, "forget" the last mouse click
            if self.crt.last_mouse is not None and (
                    abs(self.crt.last_pen_point.x0 - self.crt.last_mouse.getX()) < self.crt.WIN_MOUSE_BOX) & \
                    (abs(self.crt.last_pen_point.y0 - self.crt.last_mouse.getY()) < self.crt.WIN_MOUSE_BOX):
                print("**Hit at x=0d%d, y=0d%d**" %(self.crt.last_pen_point.x0, self.crt.last_pen_point.y0))
                if self.crt.last_button == 3:   # I'm returning 0o1000000 for Button Three on the mouse
                    val = 0o100000              #  ... added specifically for radar tracking
                else:
                    val = 0o177777           # or  0o177777 for Button One (or anything else that we shouldn't get!)
                self.crt.ww_highlight_point()
                self.crt.last_mouse = None
                self.crt.last_button = 0
                return self.cb.NO_ALARM, val

        return self.cb.NO_ALARM, val

    # ################ 1950 QH/QD/QF Scope control #####################
    def init_qhqd_scope(self):
        self.crt = wwinfra.XwinCrt(self.cb)
        self.cb.dbwgt.add_scope(self.crt.win)  # tell the debug widget that there's a display available

        self.scope_mode = self.DISPLAY_MODE_POINTS
        self.scope_select = 0o77

        return 0


    # qh x h-axis-set  6 00110
    # Transfer contents of AC to register x; set the horizontal position of the display scope beam to
    # correspond to the numerical value of the contents of AC.
    # Guy says: I think QH has to be called before QD, but I can't find the rule book!  (probably M-1083)
    def qh(self, address, acc):
        if self.crt is None:  # first time there's a CRT instruction, we'll init the display modules
            self.init_qhqd_scope()

        self.scope_horizontal = self.convert_scope_coord(acc)

        if self.cb.TraceQuiet is False:
            print("DisplayScope QH: configured display mode %s, scope 0o%o, horizontal=0o%o" %
                  (self.ModeNames[self.scope_mode], self.scope_select, self.scope_horizontal))
        return self.cb.NO_ALARM

    # qd x display  7  00111
    # Transfer contents of AC to register x; set the vertical position of the display scope beam to
    # correspond to the numerical value of the contents of AC; intensify the beam to display a spot on
    # the face of the display scope.
    # guy says: I'm assuming that QF is like QD except that it shows on a different scope
    #  (note M-1083 Interim Display Equipment and Temporary Operation qf: F - Scope Display)
    def qd_qf(self, _operand, acc, scope):
        color=(0.0, 1.0, 0.0)  # default to green
        self.scope_vertical = self.convert_scope_coord(acc)
        if not self.cb.TraceQuiet:
            print("DisplayScope QD/QF: record to scope, mode=Point, x=0o%o, y=0o%o" %
                  (self.scope_horizontal, self.scope_vertical))
        self.crt.ww_draw_point(self.scope_horizontal, self.scope_vertical, color=color, scope=scope, light_gun=True)
        return self.cb.NO_ALARM


# this device emulates the Activate and Intervention registers
# Activate is a set of latching bits triggered by pushbuttons, cleared by reading
# Intervention Registers are sets of sixteen toggle switches
# Both were intended to be spread around among the consoles for various operator-intervention tasks.
# See 2M-0277 pg 68
class InterventionAndActivateClass:
    def __init__(self, cb, cpu_class):
        self.cb = cb

        self.name = "Intervention-and-Activate"
        self.acvtivate_reg = None
        self.intervention_reg = None
        self.cpu_class = cpu_class
        self.intervention_reg_name = {0o36: "LeftInterventionReg",
                                      0o37: "RightInterventionReg",
                                      }

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if (io_address & self.cb.INTERVENTION_ADDR_MASK) == self.cb.INTERVENTION_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, _acc, _cm):
        self.acvtivate_reg = None
        self.intervention_reg = None

        device = device & ~self.cb.INTERVENTION_ADDR_MASK
        if (device == 0) | (device == 1):  # i.e., if the device is #0 or #1, it's an Activate register
            self.acvtivate_reg = device
            print("SI: configured Activate device %o" % self.acvtivate_reg)
            return self.cb.NO_ALARM
        else:  # i.e., if the device is #2 to #32d, it's an Activate register
            self.intervention_reg = device
            if device in self.intervention_reg_name:
                name = self.intervention_reg_name[device]
            else:
                name = "Switch-%d" % device
            print("SI: configured Intervention device 0o%o  %s" %
                  (self.intervention_reg, name))
            return self.cb.NO_ALARM

    def rc(self, _operand, _acc):  # "record", i.e. output instruction to device
        print("unimplemented %s Record" % self.name)
        return self.cb.UNIMPLEMENTED_ALARM, 0

    # Read from the switches should return something
    # This stub simply returns zero for all Activate and Intervention registers
    def rd(self, operand, acc):  # "read", i.e. input instruction from device
        reg = self.intervention_reg
        ret = 0
        if reg in self.intervention_reg_name:
            ret = self.cpu_class.cpu_switches.read_switch(self.intervention_reg_name[reg])
        else:
            print("unimplemented Intervention Register %s Read; return Zero" % self.name)
        return self.cb.NO_ALARM, ret


class IndicatorLightRegistersClass:
    def __init__(self, cb):
        self.cb = cb
        self.name = "Indicator Light Registers"
        self.indicator_reg = None

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if (io_address & self.cb.INDICATOR_LIGHT_ADDR_MASK) == self.cb.INDICATOR_LIGHT_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, acc, _cm):
        device = device & ~self.cb.INDICATOR_LIGHT_ADDR_MASK
        self.indicator_reg = device
        print("SI: configured Indicator device %o" % self.indicatator_reg)
        return self.cb.NO_ALARM

    def rc(self, operand, acc):  # "record", i.e. output instruction to device
        print("unimplemented %s Record to Indicator Lights" % self.name)
        return self.cb.UNIMPLEMENTED_ALARM, 0

    # Read from the switches should return something
    # This stub simply returns zero for all Activate and Intervention registers
    def rd(self, operand, acc):  # "read", i.e. input instruction from device
        print("unimplemented %s Read; return Zero" % self.name)
        return self.cb.NO_ALARM, 0


class InOutCheckRegistersClass:
    def __init__(self, cb):
        self.cb = cb
        self.name = "In-Out Check Registers"
        self.in_out_check_reg = None

    # each device needs to identify its own unit number.
    def is_this_for_me(self, io_address):
        if (io_address & self.cb.IN_OUT_CHECK_ADDR_MASK) == self.cb.IN_OUT_CHECK_BASE_ADDRESS:
            return self
        else:
            return None

    def si(self, device, acc, _cm):
        device = device & ~self.cb.IN_OUT_CHECK_ADDR_MASK
        self.in_out_check_reg = device
        print("SI: configured In-Out Check device %o" % self.in_out_check_reg)
        return self.cb.NO_ALARM

    def rc(self, operand, acc):  # "record", i.e. output instruction to device
        print("unimplemented %s Record" % self.name)
        return self.cb.UNIMPLEMENTED_ALARM, 0

    # Read from the switches should return something
    # This stub simply returns zero for all Activate and Intervention registers
    def rd(self, operand, acc):  # "read", i.e. input instruction from device
        print("unimplemented %s Read; return Zero" % self.name)
        return self.cb.NO_ALARM, 0
