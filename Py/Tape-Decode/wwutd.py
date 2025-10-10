#!/usr/bin/python

# Copyright 2021 Guy C. Fedorkow
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

# guy fedorkow, Dec 9, 2019
# decode Whirlwind mag tape

import sys
# sys.path.append('K:\\guy\\History-of-Computing\\Whirlwind\\Py\\Common')
import argparse
import re
import wwinfra
import hashlib
from typing import List, Dict, Tuple, Sequence, Union, Any
from wwflex import FlexToFc, FlexToFilenameSafeFlascii, FlexToCsyntaxFlascii, AsciiFlexCodes, FlexToFlascii
import traceback


DebugTAP = False
Debug556 = False
DebugXsum = False
# DrumOffset = 0o40    # optional argument for (I think) loading 'drum dump' tapes
DrumOffset = 0o00    # optional argument for (I think) loading 'drum dump' tapes
#cb = wwinfra.ConstWWbitClass()
#cb = None

#hist = wwinfra.OpCodeHistogram(cb)
hist = None

def breakp(why: str):
    print("breakpoint: %s" % why)


def scan_for_strings(corelist, byte_stream):
    global cb
    string_list = []
    flexCodes = AsciiFlexCodes()
    flexToFlascii = FlexToCsyntaxFlascii()
    # Scan twice, using these fcns to access the high and low parts of the word
    for fcns in [[lambda m: m & 0o001777, lambda m: (m >> 10) & 0o77],
                 [lambda m: m & 0o177700, lambda m: m & 0o77]]:
        maskFcn = fcns[0]
        shiftFcn = fcns[1]
        for coremem in corelist:
            memLimit = len (coremem) if byte_stream else cb.CORE_SIZE 
            addr = 0
            flexCnt = 0 # Number of contiguous flex codes seen
            while addr <= memLimit:
                m = coremem[addr] if addr != memLimit else None
                validCode = False
                if m is not None and maskFcn (m) == 0:
                    flexCode = shiftFcn (m)
                    if flexCodes.isValidCode (flexCode):
                        validCode = True
                if validCode:
                    flexToFlascii.addCode (flexCode)
                    flexCnt += 1
                else:
                    if flexCnt > 2:
                        flexo_string_high = flexToFlascii.getFlascii()
                        string_list.append (flexo_string_high)
                    flexToFlascii = FlexToCsyntaxFlascii()
                    flexCnt = 0
                addr += 1

    if Debug556 and (len(string_list) > 0):
        print("String Dump")
        for s in string_list:
            print("   String: %s" % s)

    return string_list

# This routine writes out a series of octal blocks as if it were an independent paper tape file.
def write_petra_file(block_list, filename_7ch, base_output_filename, min_file_size, starting_seq: int = 1):
    sequence = starting_seq
    ww_file = WWFileClass(cb)
    ww_file.is_octal_block = True
    ww_file.is_petra_file = True
    ww_file.octal_block_list = block_list
    ignored_files = write_core_wrapper(filename_7ch, base_output_filename, ww_file, sequence, "", min_file_size)
    sequence += 1
    stats = {'good_xsum_count': 0, 'bad_xsum_count': 0, 'no_xsum_count': 0,
             'jump_to_count': 0, 'outputfile_sequence': sequence,
             'ignored_files_count': ignored_files, "non_556_block_count": len(block_list)}
    return stats, "None", sequence


def write_core_wrapper(input_file: str, base_filename: str, ww_file, sequence: int, xsum_str: str, min_file_size):
    global hist
    global cb
    core = ww_file.core
    jump_to = ww_file.jump_to
    ww_flexo_block_num = ww_file.validated_title_block_number
    ww_556_block_num = ww_file.validated_code_block_number
    is_octal_block = ww_file.is_octal_block
    is_556 = ww_file.is_556
    is_petra_file = ww_file.is_petra_file
    core_list = []
    ignored_files = 0

    if (is_octal_block ^ is_556) is False:
        print("Error: Write_core(): 556=%d and Octal=%d: Pick one or the other!!" % (is_556, is_octal_block))
    file_extension = "tcore"
    if is_octal_block:
        if is_petra_file:
            file_extension = "petrA"
        else:
            file_extension = "ocore"
    title = ww_file.title
    if title is None:
        title = ''
    else:
        title = '_' + title
    title = title.replace('\\n', '')
    if base_filename is not None:
        core_file_name = "%s_gs%03d%s.%s" % (base_filename, sequence, title, file_extension)
        core_file_name = core_file_name.replace(" ", "#")
        input_file += '/' + core_file_name  # "input file" is a comment that goes into the core file
        if DebugTAP:
            print("(write core file %s)" % core_file_name)
    else:
        core_file_name = None  # None sends output to stdout

    if is_556:
        core_list.append(core)
    else:
        core_list = ww_file.octal_block_list

    if ww_flexo_block_num is not None and ww_556_block_num is not None and (ww_flexo_block_num == ww_556_block_num):
        block_msg = "Complete WW Tape Block 0o%o" % ww_flexo_block_num
        for_sure_code = True
    else:
        block_msg = "WW Tape Block Numbers: Flexo-Block-Num=%s, 556-Block-Num=%s" % \
                    (wwinfra.octal_or_none(ww_flexo_block_num), wwinfra.octal_or_none(ww_556_block_num))
        for_sure_code = False
    core_len = hist.collect_histogram(core_list, for_sure_code)
    block_msg += "; xsum=%s" % xsum_str
    block_msg += '\n'

    stats_string = ''
    if (hist.local_histogram is True) and (core_len > min_file_size):
        # "covariance" on core images with only a handful of words seems
        # pointless...  they're almost certainly not code anyway.  The
        # threshold should probably be at least 100, but who knows...
        cov = hist.figure_hist_covariance(hist.normalize_histogram())
        io_summary = hist.summarize_io_histogram()
        if cov is not None:
            stats_string = "Covariance=%f, Size=%d, %s" % (cov, core_len, io_summary)

    if min_file_size is None or (for_sure_code or core_len >= min_file_size):
        string_list = scan_for_strings(core_list, is_octal_block)
        wwinfra.write_core(cb, core_list, 0, is_octal_block, input_file, title, jump_to, core_file_name, string_list,
                   block_msg, stats_string)
    else:
        ignored_files += 1
    return ignored_files


# copied and simplified ww-sa-add() from WW-Sim ones-complement add routine
# This routine does the ones-complement "Special Add" normally used by WW for
# multiple-precision addition.
# The 'Specialness' is that it can't generate an overflow alarm.  In the general
# simulation, it takes a Carry In bit and generates a Carry Out, but neither are
# used for checksum calculation.
WWBIT0 = 0x8000
WWBIT0_15 = 0xffff
WW_MODULO = 0x10000


def ww_sa_add(a: int, b: int) -> int:
    """ Add ones-complement WW numbers
    :param: a, b: 16-bit ones-complement inputs
    :return: ones-complement sum, new SAM, Alarm Status
    """
    # you can't get overflow adding two numbers of different sign
    could_overflow_pos = ((a & WWBIT0) == 0) & ((b & WWBIT0) == 0)  # if both sign bits are off
    could_overflow_neg = ((a & WWBIT0) != 0) & ((b & WWBIT0) != 0)   # if both sign bits are on

    ww_sum = a + b

    if ww_sum >= WW_MODULO:  # end-around carry;
        ww_sum = (ww_sum + 1) % WW_MODULO

    if could_overflow_pos & ((ww_sum & WWBIT0) != 0):
        ww_sum &= ~WWBIT0  # clear the sign bit; the result is considered Positive
    if could_overflow_neg & ((ww_sum & WWBIT0) == 0):
        ww_sum |= WWBIT0  # set the sign bit
    ww_sum &= WWBIT0_15   # this just makes sure the answer fits the word...  I don't think this ever does anything
    return ww_sum


static_partial_xsum = 0
def decode_556_block(words, ww_file, ditto_count: int) -> Tuple[bool, Union[int, Any]]:
    global static_partial_xsum

    offset = 0
    xsum =  static_partial_xsum
    jump_to = None
    good_xsum = False
    bad_xsum = False
    title = ww_file.title
    core = ww_file.core
    is_556 = True
    debug_count_init = 8
    debug_556_str = "New Block: len=0o%o " % len(words)
    i = 0
    for i in range(0, debug_count_init):
        debug_556_str += "0o%o " % words[i]
        if i == len(words) - 1:
            break
    if i < (len(words) - 1):
        debug_556_str += "..."
    cb.log.debug556(debug_556_str)

    while True:
        if words[offset] & 0x8000:  # test for negative in the word-count field
            debug_count = debug_count_init  # This would normally be small so that it prints the first couple words
            remaining_words = len(words) - offset
            count = ((words[offset] ^ 0xffff) + 1) &0x7fff
            cb.log.debug556("Starting WW 556 word-count Block; title=%s, len=%d(d)" % (title, count))
            if count < 1 or count >= remaining_words or count > 2048:
                cb.log.warn("suspicious WW block length: count=%d(d), remaining_words=%d(d), actual block length=%d(d)"
                            % (count, remaining_words, len(words)))
                is_556 = False
                break
            if count == 0:
                break
            addr = words[offset + 1] & 0x07ff
            xsum = words[offset + 1]
            if DrumOffset != 0:
                cb.log.warn("** Adding 0o40 to Address 0o%o" % addr)
                addr += DrumOffset
            cb.log.debug556("Block Start_Address=0o%o; len=0o%o, Last_Address=0o%o; Initial xsum 0o%o" %
                            (addr, count, (addr + count - 1), xsum))
            offset += 2
            debug_556_str = "StoreAt %o: " % addr
            for j in range(0, ditto_count):
                if (addr + count) >= len(core):
                    cb.log.warn("Writing beyond end of Core address at addr=0o%o, offset=0o%o, core-size=0o%o" %
                                (addr + count, offset + count, len(core)))
                for i in range(0, count):
                    if offset >= len(words):
                        cb.log.warn("unexpected end of block at addr=0o%o, offset=0o%o, block_len=0o%o" %
                                    (addr+i, offset + i, len(words)))
                        is_556 = False
                        break

                    if (offset + i) >= len(words):
                        cb.log.warn("556 block ran out of words")
                        break
                    if core[(addr + i) & cb.WW_ADDR_MASK] is not None:
                        cb.log.warn("556 Decode overwriting core location 0o%o: was 0o%o, changed to 0o%o" %
                                    (addr + i, core[(addr + i) & cb.WW_ADDR_MASK], words[offset + i]))
                    if addr + i < len(core):
                        #  *Actually* store the word!! #
                        core[(addr + i) & cb.WW_ADDR_MASK] = words[offset + i]
                    else:
                        cb.log.warn("556 Decode word 0o%06o at NXM core address 0o%o *ignored*" %
                                    (words[offset + i], addr + i))
                    # this calculation should be separated out, but we only calculate the checksum on the first pass
                    # Note that there may be a bug in the case of "ditto zero times", where the xsum is not
                    # collected at all.  Never seen an example to test...
                    if j == 0:
                        xsum = ww_sa_add(xsum, words[offset + i])
                        if DebugXsum:
                            cb.log.info("update xsum to 0o%o" % xsum)

                    if debug_count > 0:
                        debug_556_str += "0o%06o " % words[offset + i]
                        debug_count -= 1
                    elif debug_count == 0:
                        debug_556_str += '...'
                        debug_count -= 1
                addr += count
            offset += count
            ditto_count = 1  # at the end of the ditto loop
            cb.log.debug556(debug_556_str)
        elif words[offset] & 0o177000 == 0o055000:  # a "Ditto" instruction
            # I think there were two implementations.
            #   - the early one just duplicated the next word on the tape
            #   - the subsequent one would duplicate the entire next block
            # The new one works with the old assumption if the Ditto instruction is the last
            # word in a block, and the following block is only one word (as is the case with Jingle demo)
            # Documentation on the new form is shown in:
            # THE NEW WHIRLWIND UTILITY CONTROL PROGRAM
            # http://www.bitsavers.org/pdf/mit/whirlwind/wolf_research/\
            #    LW-9_The_New_Whirlwind_Utility_Control_Program_Jan59.pdf   pdf pg 12
            # 0.55000           - ck 1000: Ignore the next Program Block (Literally, Ditto 0)
            # 0.55001           - ck 1001: Literally, Ditto 1. This Control Word has no effect
            # 0.55002 - 0.56000 - ck 1000 + M: Ditto m: Repeat the next block m times
            ditto_count = words[offset] & 0o777  # it's possible that the offset could be as large as 0o01000
            cb.log.debug556("Ditto %d times" % ditto_count)
            offset += 1

        # the op-code below is a "Check Location Five" instruction, conventional signal of xsum
        # not sure why there are two versions.  The CK 005 is the "standard" xsum indicator, but CK 3755 turned up too.
        elif words[offset] == 0o054004 or words[offset] == 0o054005:  # or   # backed out some experiments here...
            #  words[offset] == 0o057755 :  # or words[offset] == 0o055077:
            if offset + 1 >= len(words):
                cb.log.warn("WW Block Checksum check failed: xsum_instruction=0o%06o, but no following word" %
                            words[offset])
                bad_xsum = True
                offset += 1
            elif words[offset + 1] == xsum:
                good_xsum = True
                offset += 2
                cb.log.debug556("WW Block Checksum check passed; xsum = 0o%o" % xsum)
            else:
                bad_xsum = True
                cb.log.warn("WW Block Checksum check failed: calculated xsum=0o%06o, tape says:0o%06o" %
                            (xsum, words[offset + 1]))
                offset += 2
        elif words[offset] & 0xf800 == 0o74000:
            if offset + 1 < len(words):
                # two-word jump-to
                jump_to = words[offset + 1] & 0o3777  # get rid of the op code
                w0str = "0o%o" % words[offset]
                w1str = "0o%o" % words[offset + 1]
                offset += 2
                cb.log.debug556("556 JumpTo block: jump_to 0o%06o  (word[0]=%s, word[1]=%s)" %
                                (jump_to, w0str, w1str))
            else:
                cb.log.warn("JumpTo short by one word")
            break
        elif words[offset] <= 0o12:
            cb.log.info("Drum Group DA word: w0=0o%o" % (words[offset]))
            offset += 1
        elif 0o40 <= words[offset] < 0o54000:
            cb.log.info("DA Aux Group Program Block Address Word: w0=0o%o" % (words[offset]))
            addr = words[offset] & cb.WW_ADDR_MASK
            if offset + 1 >= len(words):
                cb.log.warn("DA Aux Group Program Block short one word, addr=0o%o" % addr)
            else:
                if core[addr] is not None:
                    cb.log.warn("556 Decode overwriting core location 0o%o: was 0o%o, changed to 0o%o" %
                                (addr, core[addr], words[offset + 1]))
                core[addr] = words[offset + 1]
            offset += 2
        else:
            cb.log.warn("556 Decode: leftover word 0o%06o" % words[offset])
            offset += 1

        if offset >= len(words):
            break
    ww_file.good_xsum = good_xsum
    ww_file.bad_xsum = bad_xsum
    if not good_xsum and not bad_xsum:
        cb.log.debug556("No checksum at end of block; accumulated xsum = 0o%o" % xsum)
    if jump_to is not None and offset != len(words):
        cb.log.warn("loader_block error?  jump_to not at end of block: offset=%d, len=%d" % (offset, len(words)))
        is_556 = False
    if jump_to is not None:
        if ww_file.jump_to is not None:
            cb.log.warn("More than one Jump_to: 0o%o and 0o%o" % (ww_file.jump_to, jump_to))
            is_556 = False
        ww_file.jump_to = jump_to
    ww_file.is_556 = is_556
    # note-to-self - ditto_count and static_partial_xsum are both preserved essentially as static local
    # variables, one in a global, one in the call stack.
    # Please pick one!  Like maybe stick them both in the file class or something
    static_partial_xsum = xsum
    return is_556, ditto_count


def little_endian_bytes_to_int(octets):
    ret = octets[0] + (octets[1] << 8) + (octets[2] << 16) + (octets[3] << 24)
    return ret


def validate_ww_block_number_list(bl):
    head = bl[0]
    ret = False
    if len(bl) == 2:
        head = bl[0]
        tail = bl[1]
        rev = 0
        for i in range(0, 16, 2):
            two_bits = (tail >> (14 - i)) & 0o3
            rev |= (two_bits << i)
        if rev == head:
            msg = "Validated WW Block Number 0o%06o" % head
            ret = True
        else:
            msg = "leading and trailing WW block numbers don't match: head=0o%06o tail=0o%06o" % (head, tail)
    else:
        msg = "Expected two entries in WW block number list, got %d(d): " % len(bl)
        for i in bl:
            msg += " 0o%o" % i
    return ret, head, msg


# decode a tape record in WW tape format
# According to DCL-022 pg 20, a "file" on the tape has the following structure
#     Block [Tape] mark
#     can Block number recorded in the forward direction
#     fblOO-O-O Logging title
#     can Block number recorded in the reverse direction
#     Block [Tape] mark
#     can Block number recorded in the forward direction
#     Binary tape
#     can Block number recorded in the reverse direction
# DCL-012 pg 7 has a longer explanation of the format, with hand-drawn pictures
# that won't copy into Python!
# In this context,
#    a block is a series of records between tape marks
#    a record is one contiguous batch of bytes from the tape
#    I'm calling a title followed by some executable code a "file"
class WWFileClass:
    def __init__(self, cbl):
        global Debug556
        self.title = None
        self.is_556 = False
        self.is_octal_block = False
        self.is_petra_file = False
        self.current_block_is_flexo_type = None
        # Whirlwind "blocks" are supposed to begin and end with one-word records giving the index number on the tape,
        # called a Block Number in DCL-012.  "Validated" here means the one at the start and the one at the end
        # matched up (although one is written bit-reversed for reading the tape backwards)
        self.validated_title_block_number = None  # validated block-num that can then be attached to title
        self.validated_code_block_number = None   # validated block-num that can then be attached to to code
        self.ww_block_number_list = []
        self.good_xsum = False
        self.bad_xsum = False
        self.jump_to = None
        self.core = [None for _ in range(cbl.CORE_SIZE)]
        self.octal_block_list = []   # this is a list of blocks, not all blocks concatenated into one array
        if Debug556:
            print(" ** New FileClass ** ")


def decode_ww_loader_format(word_record, ww_file, long_octal_dump):
    """ word_record: array of 16-bit words read from the tape
    core: core memory object to store the results of a decode
    """
    global Debug556, cb

    word_record_len = len(word_record)
    block_num = False
    stop_dump_at_col = 8
    flexo_string = ''
    ditto_count = 1     # this Ditto command acts as a "no op" if it's set to one, i.e., the next block should
                        # be processed just once, not multiple times (or zero times)

    # Rules
    # if it's a one-word block, it's probably a block index number
    # if it's longer than two words, starts with a negative count that's not too big or small
    #   (and I think followed by a positive address)
    #   then it might be a 556 block
    # if it's all less than 0o77, it's probably flexo text like a title (not an embedded string in code)
    # Otherwise, I think it's one of those binary-dump things, or a data record
    is_556 = False
    flexo_block = True
    if word_record_len == 1:  # one-word blocks on tape are usually Whirlwind block numbers
        ww_file.current_ww_block_number = word_record[0]
        ww_file.ww_block_number_list.append(ww_file.current_ww_block_number)
        if DebugTAP:
            print("WW Block Number 0o%06o" % word_record[0])
        flexo_block = False
        block_num = True
    else:
        for wrd in word_record:
            # Zero or greater than 0o77 means it's not a valid Flexo char
            if wrd & 0xffc0:  # assume a string is Not Flexo on the first out-of-range character
                flexo_block = False
        ww_file.current_block_is_flexo_type = flexo_block

    if flexo_block:
        # LAS -- Originally this used show_unprintable=True, which in the new
        # classes means use FlexToCsyntaxFlascii. But that results in many
        # nulls. So it looks like filename_safe is really best here.
        # flexo_string = FlexToCsyntaxFlascii().addCodes([word & 0x3f for word in word_record]).getFlascii()
        flexo_string = FlexToFilenameSafeFlascii().addCodes([word & 0x3f for word in word_record]).getFlascii()
        flexo_string = flexo_string.rstrip()
        if DebugTAP:
            print("flexo code=%s" % flexo_string)
        ww_file.title = flexo_string

    elif not block_num:  # continue here if it's not flexo, and not a block_num
        dump_str = ''
        for i in range(0, len(word_record)):
            dump_str += '  0o%06o' % word_record[i]
            if i == stop_dump_at_col and i < len(word_record):
                dump_str += '...'
                break

        if len(word_record) == 1:  # we shouldn't ever get here; delete this test once proven
            print("huh?  how'd get here??")
            exit(-1)
        if len(word_record) > 2 and (word_record[0] & 0x8000):  # test for negative length field
            code_len = (word_record[0] ^ 0xffff) + 1
            code_addr = word_record[1] & 0x07ff
            if DebugTAP:
                print("   WW 556 decode len=%d(d), addr=0o%o: %s" % (code_len, code_addr, dump_str))
            is_556, ditto_count = decode_556_block(word_record, ww_file, ditto_count)
        if not is_556:
            if DebugTAP:
                print("   Octal Dump: %s" % dump_str)
            ww_file.is_octal_block = True
            if ww_file.is_556 is True:
                print("   Error: both 556 and Octal in the same tape record; ignore this block")
                return
            ww_file.octal_block_list.append(word_record)
#            dump_octal_block(word_record, long_octal_dump)


# decode a file which is formatted in SIMH Mag Tape Format
#  http://simh.trailing-edge.com/docs/simh_magtape.pdf
# This format is a series of bytes with four-byte control words embedded.
# Tape block boundaries are defined by control words containing word counts
def read_tap_file(tap_filename, base_output_filename, min_file_size, read_past_end_flag=False,
                  stop_on_tap_block_error=False, long_octal_dump=False):
    global DebugTAP, Debug556, cb
    fd = None
    outputfile_sequence = 1
    xsum_str = "bugbug"  # this var *should* get changed before it's used

    try:
        fd = open(tap_filename, "rb")
    except IOError:
        print("Can't open Tape Image file %s" % tap_filename)
        exit(1)
    tap_file_content = fd.read()  # type: bytes
    tap_file_len = len(tap_file_content)
    good_xsum_count = 0
    bad_xsum_count = 0
    no_xsum_count = 0
    ignored_files_count = 0
    jump_to_count = 0   # count of how many jump-to directives we see

    if DebugTAP:
        print("Using .TAP file %s, length=%d(d)" % (tap_filename, tap_file_len))
    if (tap_file_len % 2) != 0:
        cb.log.warn("TAP warning: total tape length is odd : len=%d" % tap_file_len)

    ww_file = WWFileClass(cb)   # class to hold the core image and some metadata
    saw_tape_mark = False  # We need to detect the "double tape mark" as end of the useful file, so this is the marker
    tape_offset = 0
    while tape_offset < tap_file_len:
        # tap files start with a 32-bit marker that's interpreted as either a file mark or byte count
        nextword = little_endian_bytes_to_int(tap_file_content[tape_offset:tape_offset+4])
        tape_offset += 4
        if nextword == 0:   # Tape Mark indicator
            if len(ww_file.ww_block_number_list) > 0:
                is_validated, bn, msg = validate_ww_block_number_list(ww_file.ww_block_number_list)
                print(msg)
                if is_validated:
                    if ww_file.current_block_is_flexo_type:
                        ww_file.validated_title_block_number = bn
                    else:
                        ww_file.validated_code_block_number = bn
            ww_file.ww_block_number_list = []  # forget the current list of proto-block-numbers
            if saw_tape_mark:
                print("\n mag tape offset %d of %d bytes: Double Tape Mark WW EOF" %
                      (tape_offset, len(tap_file_content)))
                if read_past_end_flag is False:
                    return 0, 0, 0, 0, ("%3.1f%%" % 100.0 * (float(tape_offset)/float(tap_file_len)))
            else:
                print("\ntape offset %d: Tape Mark" % tape_offset)

            # if we're at a Tape Mark and we saw a Jump_to, that's a clear sign that it's time to write out
            # the core file and move on.
            # This test probably needs elaboration for non-556-format files
            if ww_file.is_556 is True or ww_file.is_octal_block is True:
                if ww_file.jump_to:
                    jump_to_count += 1
                if DebugTAP and ww_file.is_556 is True:
                    if ww_file.jump_to is not None:
                        print("jump_to=0o%o" % ww_file.jump_to)
                    else:
                        print("No JumpTo")
                ignored_files_count += write_core_wrapper(tap_filename, base_output_filename, ww_file,
                                                          outputfile_sequence, xsum_str, min_file_size)
                ww_file = WWFileClass(cb)  # jump_to signifies that we're on to the next core image
                outputfile_sequence += 1

            continue     # advance to the next word right away

        elif (nextword == 0xffffff) or (nextword == 0xfffffe):
            print("tape offset %d: tape mark - end-of-medium %x" % (tape_offset, nextword))
            break        # bail out; Len's TAP files don't have an end of medium marker
        elif (nextword & 0xff000000) == 0xff000000:
            print("tape offset %d: reserved metadata %x" % (tape_offset, nextword))
            break        # bail out
        else:
            block_error = nextword & 0x80000000
            nextword &= 0x7fffffff  # nextword now contains the word count for this block, so continue with this block

        # at this point, we know we're past the TAP block header and on to the actual tape record.
        # tap format repeats the block length at the end of the block.  So the current word is the "leading"
        # block length marker; the one at the end is the "trailing" block length marker.  Make sure they're
        # the same...
        saw_tape_mark = False
        leading_record_len = nextword
        if DebugTAP:
            print("\nStarting TAP record at tape offset %d(d): record_len: %d(d)" % (tape_offset, leading_record_len))
        if leading_record_len + tape_offset > tap_file_len:
            print("TAP Decode: record length is longer than the file!")
            break
        record = bytearray(tap_file_content[tape_offset:tape_offset+leading_record_len])
        padded_record_len = leading_record_len
        if leading_record_len & 0o1:  # odd length record should be padded with zero
            cb.log.warn("Odd-length record; tape block starts at %d(d) byte offset, record len = %d(d)" %
                  (tape_offset, len(record)))
            if stop_on_tap_block_error:
                break
            padded_record_len += 1
            record.append(0)
        word_record = []
        byte_offset = 0
        # copy the tap record into a new array of words
        while byte_offset < len(record):
            wrd = int(record[byte_offset+1]) + (int(record[byte_offset]) << 8)
            word_record.append(wrd)
            byte_offset += 2

        # clean up the end of the TAP block, get ready to find the next one once we're done
        # with the word_record array
        tape_offset += padded_record_len
        trailing_record_len = little_endian_bytes_to_int(tap_file_content[tape_offset:tape_offset+4])
        tape_offset += 4
        block_error = block_error | trailing_record_len & 0x80000000
        trailing_record_len &= 0x7fffffff

        # mismatch between first and last TAP records "shouldn't happen", so bail out if it does
        if trailing_record_len != leading_record_len:
            print(
                "TAP record length mismatch: tape_offset=%d(d), leading_len=%d(d)=0x%x, trailing_len=%d(d)=0x%x" %
                (tape_offset, leading_record_len, leading_record_len, trailing_record_len, trailing_record_len))
            break
        # block errors can happen if Len figures there's a dropout or something; if so, we just go on to the next
        if block_error != 0:
            print(
                "TAP record error: tape_offset=%d(d), leading_len=%d(d), trailing_len=%d(d), block_error = 0x%x" %
                 (tape_offset, leading_record_len, trailing_record_len, block_error))
            if stop_on_tap_block_error:
                break

        decode_ww_loader_format(word_record, ww_file, long_octal_dump)

        if ww_file.is_556:
            if ww_file.good_xsum:
                good_xsum_count += 1
                xsum_str = "good"
            if ww_file.bad_xsum:
                bad_xsum_count += 1
                xsum_str = "bad"
            if (not ww_file.good_xsum) and (not ww_file.bad_xsum):
                no_xsum_count += 1
                xsum_str = "none"
        if ww_file.is_octal_block:
            xsum_str = "none"

    if tape_offset == tap_file_len:
        completion_string = "Every Last Byte"
    else:
        completion_string = "%3.1f%%" % (float(tape_offset)/float(tap_file_len))

    stats = {'good_xsum_count': good_xsum_count, 'bad_xsum_count': bad_xsum_count, 'no_xsum_count': no_xsum_count,
             'jump_to_count': jump_to_count, 'outputfile_sequence': outputfile_sequence,
             'ignored_files_count': ignored_files_count, 'non_556_block_count': 0}
    return stats, completion_string


# ############## Paper Tape Reader  ###############################################

# test a string of bytes to see if they're flexo characters.
# My table returns '#' for characters that aren't defined in the WW Flexo char set
# There aren't many -- of the 64 possible codes, most are used.
def block_is_all_flexo(b: List[int]):
    flexCodes = AsciiFlexCodes()
    for c in b:
        if not flexCodes.isValidCode (c):
            return False
    return True

def write_flexo_file(block_array: List[List[int]], input_filename: str, base_filename: str, ascii_only: bool):
    flexToFc = FlexToFc (asciiOnly=ascii_only)
    for block in block_array:
        for flexCode in block:
            flexToFc.addCode (flexCode)
    ascii_str = flexToFc.getFlascii()

    fout = sys.stdout
    if base_filename is not None:
        txt_filename = base_filename
        if re.search(".*\\.fc$", txt_filename) is None:
            txt_filename += ".fc"
        cb.log.info("Flexo Output File: %s" % txt_filename)
        try:
            fout = open(txt_filename, 'wt')
        except IOError:
            cb.log.fatal("can't open %s for writing" % txt_filename)

    fout.write("%%File %s\n" % input_filename)
    fout.write(ascii_str)


# decode 556 blocks until we hit end of file
# A JumpTo causes the current core file to be written and a new one started
def decode_556_file(block_array: List[List[int]],
                    filename_7ch: str, base_output_filename: str, min_file_size: int, starting_seq: int = 1):
    global cb
    outputfile_sequence = starting_seq
    xsum_str = "bugbug"  # this var will get changed before it's used

    good_xsum_count = 0
    bad_xsum_count = 0
    no_xsum_count = 0
    ignored_files_count = 0
    non_556_block_count = 0
    jump_to_count = 0   # count of how many jump-to directives we see
    ditto_count = 1
    voffset = 0

    ww_file = None

    tape_header = True
    for block in block_array:
        if ww_file is None:
            ww_file = WWFileClass(cb)
        w0 = 0
        if len(block) >= 3:
            w0 = decode_556_word(block[0:3])
        # check if it's 556 or flexo, i.e., title or code
        # on paper tape, I've never seen a single block that contains the title and 556 code, although
        # it's possible that such a thing could exist
        # If it's a 556 block, the first word should be a negative word-count
        if tape_header and block_is_all_flexo(block) and (w0 & 0o100000 == 0) and ww_file.title is None:
            # LAS
            ww_file.title = FlexToFilenameSafeFlascii().addCodes(block).getFlascii()
            cb.log.debug556("556 tape header title: %s" % ww_file.title)
            continue

        tape_header = False     # once we get past the header, we're done; the rest had better be 556
                                # ...at least until there's a Jump_to

        # I don't know what these are for, but 077 is a Del (rubout) character and is often ignored
        if len(block) == 3 and block[0] == 0o77 and block[2] == 0o77 and block[2] == 0o77:
            cb.log.warn("Ignoring (0o77, 0o77, 0o77) block")
            continue

        # convert the list of bytes in the block to words
        words = convert_556_block_to_words(block, voffset)
        voffset += len(block)


        is_556, ditto_count = decode_556_block(words, ww_file, ditto_count)

        if is_556 is False:  # This "shouldn't happen"
            cb.log.warn("Non-556 Block in decode_556_file")
            non_556_block_count += 1

        if ww_file.jump_to or (block == block_array[len(block_array) - 1]):  # this would be set by decode_556_blocks
            jump_to_count += 1
            if jump_to_count > 1:
                cb.log.warn("more than one jumpto in decode_556_file")
            if ww_file.jump_to:
                cb.log.debug556("jump_to=0o%o" % ww_file.jump_to)
            else:
                cb.log.info("ending 556 file without a jump-to")
            # set the block number to the sequence number.  This doesn't matter for paper tape, but
            # it does matter for mag tape, so write_core_wrapper checks if they line up.
            ww_file.validated_title_block_number = outputfile_sequence
            ww_file.validated_code_block_number = outputfile_sequence
            ignored_files_count += write_core_wrapper(filename_7ch, base_output_filename, ww_file,
                                                      outputfile_sequence, xsum_str, min_file_size)
            ww_file = None   # jump_to signifies that we're on to the next core image
            tape_header = True          # get ready to read the next title block
            outputfile_sequence += 1

            continue     # advance to the next tape block right away

        if ww_file.is_556:
            if ww_file.good_xsum:
                good_xsum_count += 1
                xsum_str = "good"
            if ww_file.bad_xsum:
                bad_xsum_count += 1
                xsum_str = "bad"
            if (not ww_file.good_xsum) and (not ww_file.bad_xsum):
                no_xsum_count += 1
                xsum_str = "none"
        if ww_file.is_octal_block:
            xsum_str = "none"

    stats = {'good_xsum_count': good_xsum_count, 'bad_xsum_count': bad_xsum_count, 'no_xsum_count': no_xsum_count,
             'jump_to_count': jump_to_count, 'outputfile_sequence': outputfile_sequence,
             'ignored_files_count': ignored_files_count, "non_556_block_count": non_556_block_count}
    return stats, "no-completion-string", outputfile_sequence


def classify_paper_tape_blocks(block_array: List[List[int]], bt_list: List[List[str]],
                         filename_7ch: str, base_output_filename: str, min_file_size: int):
    block_type_list = bt_list  # Block Type List
    block_type_list.append(["end"])  # we're going to peek ahead past the last block in the list
    block_array.append([0, 0, 0])  # we're going to peek ahead past the last block in the list
    loader_block_lists = []
    data_block_lists = []
    block_lists = {"loader": loader_block_lists, "data": data_block_lists}
    current_list = []
    last_btype = block_type_list[0]
    if "unknown" in block_type_list[0]:
        current_list_type = "data"
    else:
        current_list_type = "loader"
    summary_str = ''
    btype_debug_string = '000(d): '
    change_type = None
    sequence = 1
    good_xsum_count = 0
    bad_xsum_count = 0
    no_xsum_count = 0
    jump_to_count = 0
    ignored_files = 0

    for i in range(0, len(block_array)):
        block = block_array[i]
        btype = block_type_list[i]
        nbtype = btype
        if (i + 1 < len(block_array)):   # don't fall off the end on the last trip through with type=='end'
            nbtype = block_type_list[i + 1]
        btype_txt = ''
        for b in btype:
            btype_txt += b + ','
        if last_btype != btype:
            if 'end' in btype:
                change_type = 'end'
            elif current_list_type == 'data':
                # a chain of loader blocks must (I think) start with a word-count (i.e., not a GoTo, Ditto, DA, etc)
                if "b556" in btype  or ('fc' in btype and 'b556' in nbtype):
                    change_type = 'loader'
            elif current_list_type == 'loader':
                 # changed Jan 2, 2022 to only end a loader sequence after a JumpTo block
                 # This section really needs a rework.  But Loader sequences only end with a JumptTo.  If the last
                 # block had a jumpto, then we must "change type", even if it's to the next loader block
                if 'jumpto' in last_btype:
                    if 'b556' not in btype:
                        change_type = 'data'
                    else:
                        change_type = 'loader'

            else:
                cb.log.fatal("classify_paper_tape_blocks: unexpected type %s, %s" % (current_list_type, btype_txt))

        if change_type:
            if current_list_type == "loader":
                stats, completion_str, sequence = decode_556_file(current_list, filename_7ch, base_output_filename,
                                                                  min_file_size, starting_seq=sequence)
            else:
                stats, completion_str, sequence = write_petra_file(current_list, filename_7ch, base_output_filename,
                                                                   min_file_size, starting_seq=sequence)

            block_lists[current_list_type] += current_list
            summary_str += "%8s: %s\n" % (current_list_type, btype_debug_string)
            current_list = [block]
            current_list_type = change_type
            btype_debug_string = "%03d(d): %s " % (i, btype_txt)
            change_type = None

            good_xsum_count += stats['good_xsum_count']
            bad_xsum_count += stats['bad_xsum_count']
            no_xsum_count += stats['no_xsum_count']
            jump_to_count += stats['jump_to_count']
            ignored_files += stats['ignored_files_count']

        else:
            current_list.append(block)
            btype_debug_string += btype_txt + ' '

        last_btype = btype

    #    block_lists[current_list_type].append(current_list)  # pick up the last chain
    #    summary_str += "%8s: %s\n" % (current_list_type, btype_debug_string)

    cb.log.info("Block Type Summary: \n%s%8s: %s" % (summary_str, current_list_type, btype_debug_string))
    cb.log.info("%d(d) Loader Block Chains, %d(d) Data Block Chains" %
                (len(loader_block_lists), len(data_block_lists)))

    completion_string = "Every Last Byte"
    stats = {'good_xsum_count': good_xsum_count, 'bad_xsum_count': bad_xsum_count, 'no_xsum_count': no_xsum_count,
             'jump_to_count': jump_to_count, 'outputfile_sequence': sequence,
             'ignored_files_count': ignored_files, 'non_556_block_count': 0}
    return stats, completion_string



def just_convert_556_blocks(block_array: List[List[int]], filename_7ch: str, base_output_filename: str):
    start_addr = 0o40   # we'll assume that if it's code at all, it starts at 0o40
    addr = start_addr
    ww_file = WWFileClass(cb)   # class to hold the core image and some metadata

    for block in block_array:
        # convert the list of bytes in the block to words
        words = convert_556_block_to_words(block)

        for w in words:
            ww_file.core[addr] = w
            print("word 0o%o = 0o%o" % (addr, w))
            addr += 1

    completion_string = "No-Header-556-Blocks: %d blocks, %d words" % (len(block_array), (addr - start_addr))
    cb.log.info(completion_string)

    sequence = 0  # we're only making one output file
    ww_file.is_556 = True
    write_core_wrapper(filename_7ch, base_output_filename, ww_file, sequence, "", 0)

    stats = {'good_xsum_count': 0, 'bad_xsum_count': 0, 'no_xsum_count': 0,
             'jump_to_count': 0, 'outputfile_sequence': 0,
             'ignored_files_count': 0, 'non_556_block_count': 0}
    return stats, completion_string





# Paper tape is formatted as 5-5-6 format, that is, three paper tape characters to make one 16-bit word
# here are a couple routines to detect and decode 5-5-6
def decode_556_word(cc: List[int], warn: bool = False, voffset: int = None) -> int:
    global cb
    if voffset is not None:
        voff_str = "Offset: 0o%0o(%d), " % (voffset, voffset)
    else:
        voff_str = ''

    if len(cc) < 3:
        cb.log.warn("%sdecode_556_word needs 3 char, but called with %d characters; returning zero" %
                    (voff_str, len(cc)))
        return 0
#    if (cc[2] == 0o77) and (cc[1] == 0o77) and (cc[0] == 0o77):
#        breakp("all sevens in decode_556_words")   # special purpose trap to see why there's a block of 77's in Calendar

    if warn and (cc[1] & 1) or (cc[0] & 1):
        cb.log.info("%sdecode_556_word: non-zero LSBs in c0 or c1: c0=0o%o, c1=0o%o, c2=0o%o" %
                    (voff_str, cc[0], cc[1], cc[2]))
    c2 = cc[2]
    c1 = cc[1] >> 1
    c0 = cc[0] >> 1
    w = c2 | (c1 << 6) | (c0 << 11)
    return w


def convert_556_block_to_words(block: List[int], block_offset=None) -> List[int]:
    global cb
    blen = len(block)
    offset = 0
    words = []
    while offset < blen:
        words.append(decode_556_word(block[offset:offset + 3], warn = True, voffset = block_offset))
        offset += 3
        if block_offset is not None:
            block_offset += 3
        if 0 < offset < 3:
            cb.log.warn("convert_556_to_words called with block not divisible by three")
            break
    return words


# This routine makes a quick guess as to what's in a block, based on a couple of
# heuristic rules
# Return a list of keywords that it might be
# I think that a block that's divisble by three and contains only valid flexo bytes
# would be the only one that returns two types.
def guess_block_type(b) -> List[str]:
    ret = []
    blen = len(b)
    blen_remainder = blen % 3
    w0 = 0
    if blen >= 3:
        w0 = decode_556_word(b[0:3])   # first word in the block may be a count
    w0_len = (w0 ^ 0xffff) + 1

    if blen_remainder == 0:
        words = convert_556_block_to_words(b)
        if (w0 & 0o100000) and (w0_len <= blen//3):
            ret += ["b556", "b556wc"]
        # the following is an ad-hoc observation of a "Drum Group Address" I think.
        # See LW-9_The_New_Whirlwind_Utility_Control_Program_Jan59.pdf pdf-pg 12
        elif 0o00040 <= w0 <= 0o53777:
            ret += ["b556", "da"]
        elif w0 <= 0o00012:
            ret += ["b556", "da"]

        elif (len(words) == 2) and (words[0] & 0o174000 == 0o74000) and (words[1] & 0o174000 == 0o74000):
            ret += ["b556", "jumpto"]
        elif w0 & 0o55000:
            ret += ["b556", "ditto"]   # it's probably a Ditto
        elif (len(words) >= 2) and (w0 == 0o54005):
            ret += ["b556", "ck5"]  # Checksum
    if block_is_all_flexo(b):
        ret.append("fc")

    # print("Block type=%-4s, blen=%03d, blen//3=%03d, msb=%s, w0=0o%06o, W0_len=0d%04d, %%3=%d" %
    #       (ret, blen, blen//3, msb, w0, w0_len, blen_remainder))
    return ret


# this routine reads binary images of paper tapes as transcribed by Al Kossow at CHM,
# converts them into conventional whirlwind format.
# Al's tapes seem to be read with the bits in a byte reversed, ans shifted.
# The routine returns an list of lists, with each tape block as a separate list of bytes
def read_7ch(cb, filename:str):
    cb.log.info("FileName: %s" % filename)
    try:
        fd = open(filename, "rb")   # open as a file of bytes, not characters
    except IOError:
        fd = None  # this prevents an uninitialized var warning in fd.read below
        cb.log.fatal("Can't open tape file %s" % filename)

    block_array = []
    block = []
    offset = 0          # count characters from the start of the tape
    valid_offset = 0    # count characters with the Valid bit from the start of tape
    invalid_count = 0   # Counting invalids is not a War Thing -- we need to count the characters which are not Valid
    while True:
        ch = fd.read(1)
        if len(ch) == 0:
            break

        by = ord(ch)
        binary_string = format((by & 0x7f), 'b').zfill(8)
        sevenbitr = binary_string[1:8]
        sevenbit = sevenbitr[::-1]
        lsn = int(sevenbit[3:6], 2)
        msn = int(sevenbit[0:3], 2)
        tape_code = lsn + (msn << 3)
        valid_bit = sevenbit[6]
        if valid_bit == '1':
            if invalid_count != 0:
                cb.log.debug7ch("(%d(d) characters with Valid=0)" % invalid_count)
                invalid_count = 0
            cb.log.debug7ch("voffset=%05d(d) hex_from_tape=%x (Valid=%s) octal_result=%o" %
                            (valid_offset, by, valid_bit, tape_code))

        else:
            invalid_count += 1

        if valid_bit == '1':
            block.append(tape_code)
            valid_offset += 1
        else:
            if len(block) > 0:
                block_array.append(block)
                block = []

        offset += 1

    # cleanup in case there's no punch-out after the last byte
    if len(block) > 0:
        block_array.append(block)

    return block_array


# ################### End of Paper-Tape-Specific Routines ##########################################
# Pythonic entry point
def main():
    global DebugTAP, Debug556, hist
    global cb

    # instantiate the class full of constants
    parser = wwinfra.StdArgs().getParser ('Decode a Whirlwind tape image.')

    parser.add_argument("tape_file", help="file name of tape image in .tap or .7ch format")
    parser.add_argument("--Ch7Format", help="interpret the file as .7ch paper tape", action="store_true")
    parser.add_argument("--TapFormat", help="interpret the file as .tap magnetic tape", action="store_true")
    parser.add_argument("-F", "--FlexoForce", help="treat the file as Flex Characters", action="store_true")
    parser.add_argument("-o", "--OutputFile", type=str, help="Base name for output core file(s)")
    parser.add_argument("-q", "--Quiet", help="Suppress run-time message", action="store_true")
    parser.add_argument("-T", "--DebugTAP", help="TAP record debug info", action="store_true")
    parser.add_argument("-5", "--Debug556", help="WW 556 block debug info", action="store_true")
    parser.add_argument("-7", "--Debug7ch", help="WW paper tape code debug info", action="store_true")
    parser.add_argument("-C", "--DebugCore", help="WW corefile debug info", action="store_true")
    parser.add_argument("-X", "--DebugXsum", help="556 checksum debug", action="store_true")
    parser.add_argument("-d", "--DumpOctalBlocks", help="Dump out unknown octal tape blocks", action="store_true")
    parser.add_argument("--No556Header", help="Don't decode the 556 state machine; just assemble 556 words from bytes",
                        action="store_true")
    parser.add_argument("-P", "--NoReadPastEOF", help="Stop reading at mag-tape double-tape-mark", action="store_true")
    parser.add_argument("-B", "--BlockErrorStop", help="Stop reading at TAP Block Error", action="store_true")
    parser.add_argument("-g", "--GlobalHistogram", help="Compute a baseline opcode histogram across all files",
                        action="store_true")
    parser.add_argument("-m", "--MinFileSize", type=int, help="Ignore objects smaller than MinFileSize words")
    parser.add_argument("-a", "--ASCIIonly", help="Suppress unprintable characters in FC conversion",
                        action="store_true")

    args = parser.parse_args()

    cb = wwinfra.ConstWWbitClass(get_screen_size=True, args=args)
    wwinfra.theConstWWbitClass = cb
    cb.log = wwinfra.LogFactory().getLog(quiet=args.Quiet)
    hist = wwinfra.OpCodeHistogram(cb)

    if args.DebugTAP:
        DebugTAP = True
    if args.Debug556:
        Debug556 = True
    if args.DebugXsum:
        DebugXsum = True
    read_past_eof = not args.NoReadPastEOF

    log = wwinfra.LogClass(sys.argv[0], factory=cb.log.factory, quiet=args.Quiet, debug556=args.Debug556, debug7ch=args.Debug7ch)
    cb.log = log

    file_type = None
    for file_type_instance in ("7ch", "tap"):
        if re.search('\\.' + file_type_instance + '$', args.tape_file):
            file_type = file_type_instance

    if args.Ch7Format:
        file_type = "7ch"
    if args.TapFormat:
        file_type = "tap"

    if file_type is None:
        cb.log.fatal("Please specify either .7ch or .tap file, or --TapFormat or --Ch7Format")

    if args.OutputFile:
        base_output_filename = args.OutputFile
    else:
        base_output_filename = re.sub('\\.' + file_type + '$', '', args.tape_file)
        if re.match(".*/", base_output_filename):    #strip off a file path to get just the filename itself.
            base_output_filename = re.sub(".*/", "", base_output_filename)

    if args.DebugCore:  # send output to stdout
        base_output_filename = None


    hist.local_histogram = not args.GlobalHistogram

    if args.MinFileSize is None:
        min_file_size = 30
    else:
        min_file_size = args.MinFileSize

    cb.log.info("input file: %s, type: %s, output basename: %s" % (args.tape_file, file_type, base_output_filename))
    stats = {}
    completion_string = 'all'
    block_type_list = []

    if file_type == "tap":
        if args.FlexoForce:
            cb.log.fatal("Write Some Code:  Flexo mag tape not implemented yet!")
        # good_xsum, bad_xsum, no_xsum, jump_tos, ignored_files
        stats, completion_string = read_tap_file(args.tape_file, base_output_filename,
                                                 min_file_size, read_past_eof,
                                                 args.BlockErrorStop,
                                                 args.DumpOctalBlocks)
    elif file_type == "7ch":
        block_array = read_7ch(cb, args.tape_file)
        cb.log.info("block_array contains %d elements" % len(block_array))

        its_all_flexo = True
        if not args.FlexoForce:   # skip the block-type guessing if we're gonna treat it as flexo no matter what
            for b in block_array:
                btype = guess_block_type(b)   # guess_block_type returns a list of strings
                if "fc" not in btype:
                    its_all_flexo = False
                block_type_list.append(btype)

        if its_all_flexo or args.FlexoForce:
            write_flexo_file(block_array, args.tape_file, base_output_filename, args.ASCIIonly)
        else:
            if args.No556Header:
                stats, completion_string = just_convert_556_blocks(block_array,
                                                                      args.tape_file, base_output_filename)
            else:
                stats, completion_string = classify_paper_tape_blocks(block_array, block_type_list,
                                                                  args.tape_file, base_output_filename, min_file_size)

    else:
        cb.log.fatal("?? how'd we get here? file_type=%s" % file_type)

    cb.log.info("Completed %s of tape %s" % (completion_string, base_output_filename))
    if len(stats) > 0:
        cb.log.info("   Wrote %d files; Ignored %d files due to size less than %d words" %
                    ((stats['outputfile_sequence'] - stats["ignored_files_count"] - 1),  # numbering starts at one
                     stats["ignored_files_count"], min_file_size))
        cb.log.info("556 Checksum summary: Good=%d(d), Bad=%d(d), Missing=%d(d), Jump_To's=%d(d), Non_556_blocks=%d(d)"
                    % (stats['good_xsum_count'], stats['bad_xsum_count'], stats['no_xsum_count'],
                        stats['jump_to_count'], stats['non_556_block_count']))

    if hist.local_histogram is False:
        hist_list = hist.normalize_histogram()
        op = 0
        hstr = ''
        for h in hist_list:
            hstr += "%9.8f, " % h
            op += 1
        print("Op Code Histogram: %s" % hstr)


if __name__ == "__main__":
    main()
