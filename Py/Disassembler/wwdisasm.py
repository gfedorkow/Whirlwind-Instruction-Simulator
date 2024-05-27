#!/usr/bin/python3
# #
# Analyze Whirlwind tapes
# g fedorkow, Dec 2, 2017
# revised Apr 30, 2018 to decode three tapes Al Kossow read at CHM several years ago
#
# Disassemble Whirlwind Core File
import os
import sys
import argparse
import re
import wwinfra
from typing import List, Dict, Tuple, Sequence, Union, Any


# sigh, I'll put this stub here so I can call Read Core without more special cases.
class WWCpuClass:
    def __init__(self, _cb):
        self.cb = _cb
        # putting this stuff here seems pretty darn hacky
        self.cpu_switches = None
        self.SymTab = {}
        self.CommentTab = [None] * 2048
        self.ExecTab = {}   # this table is for holding Python Exec statements interleaved with the WW code.

# defines

ErrorCount = 0


def breakp():
    print("breakpoint")


# this should be changed to reference the copy of this table in wwinfra.py
# ;categorize the operand part of the instruction
OPERAND_JUMP = 0  # the address is a jump target
OPERAND_WR_DATA = 1  # the address writes a data word to Core
OPERAND_RD_DATA = 2  # the address writes a data word from Core
OPERAND_PARAM = 3  # the operand isn't an address at all
OPERAND_UNUSED = 4  # the operand is unused; convert it into a .word

xop_code = [
    ["si",  "select input", OPERAND_PARAM],           # 0
    [".word", "<unused>", OPERAND_UNUSED],           # 1  # unused op code
    ["bi",  "block transfer in",   OPERAND_WR_DATA],   # 2
    ["rd",  "read",                OPERAND_PARAM],     # 3
    ["bo",  "block transfer out",  OPERAND_RD_DATA],   # 4
    ["rc",  "record",              OPERAND_PARAM],     # 5
    ["sd",  "sum digits - XOR",    OPERAND_RD_DATA],   # 6
    ["cf",  "change fields",       OPERAND_PARAM],     # 7
    ["ts",  "transfer to storage", OPERAND_WR_DATA],   # 10o, 8d
    ["td",  "transfer digits",     OPERAND_WR_DATA],   # 11o, 9d
    ["ta",  "transfer address",    OPERAND_WR_DATA],   # 12o, 10d
    ["ck",  "check",               OPERAND_RD_DATA],   # 13o, 11d
    ["ab",  "add B-Reg",           OPERAND_WR_DATA],   # 14o, 12d
    ["ex",  "exchange",            OPERAND_WR_DATA],   # 15o, 13d
    ["cp",  "conditional program", OPERAND_JUMP],      # 16o, 14d
    ["sp",  "sub-program",         OPERAND_JUMP],  # 17o, 15d
    ["ca",  "clear and add",       OPERAND_RD_DATA],  # 20o, 16d
    ["cs",  "clear and subtract",  OPERAND_RD_DATA],  # 21o, 17d
    ["ad",  "add",                 OPERAND_RD_DATA],  # 22o, 18d
    ["su",  "subtract",            OPERAND_RD_DATA],  # 23o, 19d
    ["cm",  "clear and add magnitude", OPERAND_RD_DATA],  # 24o, 20d
    ["sa",  "special add",         OPERAND_RD_DATA],           # 25o, 21d
    ["ao",  "add one",             OPERAND_RD_DATA],           # 26o, 22d
    ["dm",  "difference of magnitudes", OPERAND_RD_DATA],      # 27o, 23d
    ["mr",  "multiply and roundoff",   OPERAND_RD_DATA],       # 30o, 24d
    ["mh",  "multiply and hold",       OPERAND_RD_DATA],       # 31o, 25d
    ["dv",  "divide",                  OPERAND_RD_DATA],       # 32o, 26d
    ["SL",  "SL",                    OPERAND_PARAM],        # 33o, 27d
    ["SR",  "SR",                    OPERAND_PARAM],        # 34o, 28d
    ["sf",  "scale factor",          OPERAND_WR_DATA],      # 35o, 29d
    ["CL",  "CL",                    OPERAND_PARAM],        # 36o, 30d
    ["md",  "multiply digits no roundoff (AND)", OPERAND_RD_DATA]  # 37o, 31d aka "AND"
    ]

ext_op_code = {
    "SR": [["srr", "srh"], ["shift right and roundoff", "shift right and hold",]],
    "SL": [["slr", "slh"], ["shift left and roundoff", "shift left and hold"]],
    "CL": [["clc", "clh"], ["cycle left and clear", "cycle left and hold"]]
    }

flexocode_lcase = ["#", "#", "e", "8", "#", "|", "a", "3",
                        " ", "=", "s", "4", "i", "+", "u", "2",
                        "<color>", ".", "d", "5", "r", "l", "j", "7",
                        "n", ",", "f", "6", "c", "-", "k", "#",

                        "t", "#", "z", "<bs>", "l", "\\t", "w", "#",
                        "h", "\\n", "y", "#", "p", "#", "q", "#",
                        "o", "<stop>", "b", "#", "g", "#", "9", "#",
                        "m", "<upper>", "x", "#", "v", "<lower>", "0", "<null>"]


# go through the instructions and figure out which line is referenced by some other line
def label_code(w, pc):
    global cb
    op = w >> 11
    operand_type = cb.op_code[op][2]
    addr = w & cb.WW_ADDR_MASK
    if operand_type == OPERAND_JUMP:
        CoreReferredToByJump[addr].append(pc)
    if operand_type == OPERAND_RD_DATA:
        CoreReadBy[addr].append(pc)
    if operand_type == OPERAND_WR_DATA:
        CoreWrittenBy[addr].append(pc)


def cf_decode(pqr):
    op = ''
    if pqr & cb.WWBIT9:
        op += " MemGroupB=%o" % (pqr & 0o07)
    if pqr & cb.WWBIT8:
        op += " MemGroupA=%o" % ((pqr >> 3) & 0o07)
    if pqr & cb.WWBIT7:  # this seems to swap PC+1 and AC;   I think PC is already incremented at this point...
        op += " pc-swap"
    if pqr & cb.WWBIT6:  # read back bank selects to AC
        op += " read-back"
    return op



"""
I moved this routine into wwinfra so I could re-use it in the assembler
It *should* be safe to delete this copy!
def old_Decode_IO(lcb, io_address):
    devname = ''
    addr_info = (0, 0)
    for d in lcb.DevNameDecoder:
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
"""

def DecodeOp(w, pc, auto_sym, manual_sym, short=False):
    global cb
    if w is None:
        return 'None'
    if w == 0 or w == 1:
        # a zero or one could be a halt, but it's almost certainly a constant or initialized variable
        return ".word 0o%o" % w
    op = w >> 11
    op_name = cb.op_code[op][0]
    wordtype = ''
    addr = w & cb.WW_ADDR_MASK
    if manual_sym is not None and (pc in manual_sym):
        # don't try to decode this as an opcode if it's marked as "_word" in the symbol table,
        (l, wordtype) = manual_sym[pc]
    # if the word is marked as a data word, or if it's an unused op code, don't decode it as an instruction
    if (wordtype == '.word') | (cb.op_code[op][2] == OPERAND_UNUSED):
        return ".word 0o%06o" % w
    if wordtype == '.flex':
        if (w & ~0o77) != 0:
            print("Warning: out-of-range FlexoCharacter 0%o" % w)
            return ".word 0o%06o" % w
        return ".flex 0o%02o ; '%s'" % (w, flexocode_lcase[w])
    if cb.op_code[op][2] == OPERAND_PARAM:
        operand = "0o%o" % addr  # in these instructions, it's not an address, it's a param, e.g., number of bits ot shift
    else:
        operand = lookup_sym(addr, auto_sym, manual_sym, make_axx_label=False)

    long_op = "%3s  %5s" % (cb.op_code[op][0], operand)
    comment = "%s" % cb.op_code[op][1]

    if op_name in ["SL", "SR", "CL"]:   # there are three extended 6-bit op-codes; all use "params", not addresses
        if w & cb.WWBIT5:  # If this bit is on, it can't be a legal shift instruction; must be a data word
            return ".word 0o%06o" % w
        ext_op_bit = (w >> 9) & 0o1  # the extra op bit is the "512s" bit, not the MSB of address
        long_op = "%3s  0o%05o" % \
                  (ext_op_code[op_name][0][ext_op_bit], addr & 0o777)
        comment = ext_op_code[op_name][1][ext_op_bit]
    elif op_name == "cf":
        long_op = "%3s  %5s" % (cb.op_code[op][0], operand)
        comment = "cf" + cf_decode(addr)
    elif op_name == "si":
        comment = "select I/O: " + cb.Decode_IO(addr)

    if short:
        return op_name
    long = "%s   ; %s" % (long_op, comment)
    return long


# input for the simulation comes from a "core" file giving the contents of memory
# Sample core-file input format, from tape-decode or wwasm
# %File: <filename>
# *** Core Dump ***
# @0040: 0100261 0000402 0024000 0074045 0074042 0100000 0040212 0130212
# @0050: 0100311 0040052 0100312 0044055 0044072 0100317 0000402 0024000
# %JumpTo <Start_address>

#def dead_and_gone_read_core(filename):
#    global ErrorCount
#
#    print("Reading core file %s" % filename)
#    line_number = 1
#    jumpto_addr = None
#    ww_bin_file = None
#    ww_tapeid = None
#
#    coremem = [None] * CORE_SIZE
#    for l in open(filename, 'r'):
#        line = l.rstrip(' \t\n\r')  # strip trailing blanks and newline
#        line_number += 1
#        if len(line) == 0:  # skip blank lines
#            continue
#        all_tokens = re.split(" *;", line)  # strip comments
#        if len(all_tokens[0]) == 0:  # skip blank lines
#            continue
#        tokens = re.split("[: \t]*", all_tokens[0])
#        # print "tokens:", tokens
#        if re.match('^@C', tokens[0]):
#            address = int(tokens[0][2:], 8)
#            for token in tokens[1:]:
#                if token != "None":
#                    coremem[address] = int(token, 8)
#                    # print "address %oo: data %oo" % (address, CoreMem[address])
#                address += 1
#        elif tokens[0] == "%JumpTo":
#            jumpto_addr = int(tokens[1], 8)
#            print("Start at address 0%oo" % jumpto_addr)
#        elif tokens[0] == "%File":
#            ww_bin_file = tokens[1]
#            print("Bin File: %s" % ww_bin_file)
#        elif tokens[0] == "%TapeID":
#            ww_tapeid = tokens[1]
#            print("WW Tape ID: %s" % ww_tapeid)
#        else:
#            print("unexpected line '%s' in %s, Line %d" % (line, filename, line_number))
#            ErrorCount += 1
#    return coremem, jumpto_addr, ww_bin_file, ww_tapeid


# Manually-maintained symbol table
# This file is created with an editor to label code as it's unravelled
# @addr: <name> [.word|.flex] [*<n>] ; comment
#   Aug 6 - added another keyword to allow the .sym file to specify switch settings, such as
# those that control the behavior of the CK instruction, or those that set the initial CF banks.
#   This keyword (mis)uses the address field to be the octal value of the named switch setting.
# The simulator decides if the named switch and its value is valid or not.
# @val: <name> .switch
# [This *really* should be changed to ".switch <name> <val>" - sigh ]
# Return an empty symtab if there's no file.

def read_sym(filename):
    global cb

    line_number = 0
    symtab = {}
    switchtab = {}

    try:
        f = open(filename, 'r')
    except IOError:
        cb.log.info("no symbol file %s" % filename)
        return symtab, switchtab

    cb.log.info("symbols file %s" % filename)
    for line in f:
        line = line.rstrip(' \t\n\r')  # strip trailing blanks and newline
        line_number += 1
        repetition = 1  # allow a label to be applied to a series of sequential words with a "*<n>" tag
        switchtoken = False
        if len(line) == 0:  # skip blank lines
            continue
        all_tokens = re.split(";", line)  # strip comments
        if len(all_tokens[0]) == 0:  # skip blank lines
            continue
        tokens = re.split("[: \t]*", all_tokens[0])
        address = None
        label = None   # block a "possible use before set" error warning
        wordtype = ''  # block a "possible use before set" error warning
        print("symtab tokens:", tokens)
        if tokens[0][0] == '@':
            label = None
            wordtype = ''
            address = int(tokens[0][1:], 8)
            for token in tokens[1:]:
                if token == '':  # seems like if there's a comment, my parser puts a null on the end of the token list
                    continue
                if token == ".switch":
                    switchtoken = True
                    break
                elif token == ".word":
                    wordtype = ".word"
                elif token == ".flex":
                    wordtype = ".flex"
                elif token[0] == '*':
                    repetition = int(token[1:], 8)
                elif token[0].isalpha():
                    label = token
                else:
                    print("mystery symtab token = '%s' Line %d" % (token, line_number))
        else:
            print("symtab lines should start with '@address'; got %s" % tokens[0])
            exit(1)
        if address is None:
            print("Symtab Address = None, Line %d" % line_number)
            exit(1)
        if switchtoken is False:
            if repetition == 1:
                symtab[address] = (label, wordtype)
            else:
                for i in range(0, repetition):
                    symtab[address] = ((label + ("%02o" % i)), wordtype)
                    address += 1
        else:
            switchtab[label] = address

    return symtab, switchtab


# This routine looks up a label in the two symbols tables and resturns a string
# The make_axx_label flag says whether to make up an auto-label of the form a0031
# if the address is not in the sym tabs...  this is used when printing cross references,
# but not used when decoding instructions, which may not be instructions at all, but
# rather constant words.
def lookup_sym(addr, auto_sym, manual_sym, make_axx_label):
    if manual_sym is not None and addr in manual_sym:
        (label, dataword) = manual_sym[addr]
        if label is not None:
            return label
    if (auto_sym is not None) and (auto_sym[addr] is not None):
        return auto_sym[addr]
    if make_axx_label:
        return "a%04o" % addr
    return "0o%04o" % addr


# given a list of address cross references, convert them to labels
def list_to_address(coremem, name, lst, AutoSymTab, ManualSymTab):
    ret = ""
    if len(lst) == 0:
        return ret

    label_list = ""
    for addr in lst:
        if coremem.rd(addr, fix_none=False) is not None:
            label_list += "%s " % lookup_sym(addr, AutoSymTab, ManualSymTab, make_axx_label=True)
    if label_list != "":
        ret = "%s: %s" % (name, label_list)
    return ret


# w=current word; if the instruction has been jumped-to by something, and it's a TA to save
# the return address, it's probably a subroutine entry point.
def is_subroutine_entry(wrd):
    if DecodeOp(wrd, None, None, None, short=True) == 'ta':
        return True
    return False


# current word, plus a list of instructions that write the word
# it's likely a return from subroutine if it's a branch, and it's been written by a TA
def is_subroutine_return(coremem, wrd, lst):
    op = DecodeOp(wrd, None, None, None, short=True)
    if (op == 'cp') | (op == 'sp'):
        for from_addr in lst:
            from_word = coremem.rd(from_addr, fix_none=False)
            from_op = DecodeOp(from_word, None, None, None, short=True)
            if from_op == "ta":
                return True
    return False


# it's likely a call to a subroutine if it's a branch and the target is a TA
# it's likely a break in control flow if it's a branch to not a TA
def is_jump_to(coremem, wrd, to_sub=False):
    global cb
    op = DecodeOp(wrd, None, None, None, short=True)
    if (op == 'cp') | (op == 'sp'):
        branch_target = wrd & cb.WW_ADDR_MASK
        if branch_target == 0:  # the placeholder branches usually branch to zero
            return False
        if to_sub:
            if DecodeOp(coremem.rd(branch_target, fix_none=False), None, None, None, short=True) == 'ta':
                return True
        else:
            if DecodeOp(coremem.rd(branch_target, fix_none=False), None, None, None, short=True) != 'ta':
                return True
    return False


# scan the image to print a listing
# @0000:000000  label: op operand ; comment @@auto-comment
# Insert a .org statement if there's a discontinuity in the address sequence.
#  Whirlwind programs seem to depend on switch registers at addresses 00 and 01.  If set,
# the defzeroone flag forces those two constants into the core file.
def write_listing(fout, coremem, defzeroone, ww_filename, ww_tapeid, jumpto, switchtab, AutoSymTab, ManualSymTab):
    global ErrorCount
    global cb

    if defzeroone:
        if (coremem.rd(0, fix_none=False) is not None) | (coremem.rd(1, fix_none=False) is not None):
            print("CoreMem[0] or CoreMem[1] are already set to (%o, %o)" % \
                  (coremem.rd(0, fix_none=False), coremem.rd(1, fix_none=False)))
            ErrorCount += 1
        fout.write("                  .ORG 0\n")
        fout.write("@0000:000000  zero:  .word 0\n")
        fout.write("@0001:000001  one:   .word 1\n")

    # output the machine switch settings from the manual symbol file, if any
    if switchtab is not None:
        for s in switchtab:
            fout.write("               .SWITCH %s 0o%o\n" % (s, switchtab[s]))

    addr = 0
    last_addr = 0
    while addr < cb.CORE_SIZE:
        w = coremem.rd(addr, fix_none=False)
        line_label = None
        if w is not None:
            if addr != (last_addr + 1):
                fout.write("               .ORG 0o%05o\n" % addr)

            xrefs = ''
            extra_space = 0    # add an extra line feed for breaks in the flow
            # figure out if we can mark the instruction with any annotations
            if is_jump_to(coremem, w, to_sub=True):
                xrefs += 'Jump to Subroutine '
            if is_jump_to(coremem, w, to_sub=False):
                extra_space += 1
            if is_subroutine_return(coremem, w, CoreWrittenBy[addr]):
                xrefs += 'Return from Subroutine '
                extra_space += 1
            list1 = list_to_address(coremem, "JumpedToBy",   CoreReferredToByJump[addr], AutoSymTab, ManualSymTab)
            if list1 != '':                   # test to see if this is a subroutine entry point
                if is_subroutine_entry(w):    # it's a candidate entry point just 'cause someone jumped to it...
                    xrefs += "Subroutine Entry "
            list2 = list_to_address(coremem, "WrittenBy", CoreWrittenBy[addr], AutoSymTab, ManualSymTab)
            list3 = list_to_address(coremem, "ReadBy", CoreReadBy[addr], AutoSymTab, ManualSymTab)
            xrefs += list1 + list2 + list3
            if xrefs != '':
                xrefs = '@@ ' + xrefs
            local_label = lookup_sym(addr, AutoSymTab, ManualSymTab, make_axx_label=False)
            if local_label[0].isdigit():
                local_label = ''
            if local_label != '':
                local_label += ':'
            flex = ''
            if ((w & ~0o77) == 0) & (w != 0):  # test if it could be a single Flexo character
                flex = "@@Flexo:'" + flexocode_lcase[w] + "'"

            outputline = "@%04o:%06o %8s %s %s %s\n" % \
                         (addr, w, local_label, DecodeOp(w, addr, AutoSymTab, ManualSymTab), xrefs, flex)
            fout.write(outputline)
            if extra_space:
                fout.write('\n')

            last_addr = addr
        addr += 1
    if jumpto is not None:
        fout.write("                       .JumpTo 0o%o\n" % jumpto)
    if ww_filename is not None:
        fout.write("                       .WW_File %s\n" % ww_filename)
    if ww_tapeid is not None:
        fout.write("                       .WW_TapeID %s\n" % ww_tapeid)
    fout.close()


# Get Rid of these Globals!
CORE_SIZE = 2048
CoreReferredToByJump = [[] for _ in range(CORE_SIZE)]
CoreReadBy = [[] for _ in range(CORE_SIZE)]
CoreWrittenBy = [[] for _ in range(CORE_SIZE)]  # type: List[List[Any]]


# #############  Main  #################
# Read a binary image of a whirlwind tape.
# Guy Fedorkow, Apr 30, 2018
# The samples I'm using were seven track tapes read on an eight-track reader, so the 8th bit
# is always "1".
# tape blocks may be in Flexowriter text format, i.e., "ascii" text, or they may be in 556 binary
# format, in which three characters are combined to make a 16-bit word.

# 556 format has a word at the front to give the length, then the second word is a transfer-to-storage
# instruction with the start address for the block
# At the end is a checksum (which I still haven't figure out as of Apr 30, 2018)

def main():
    global cb
    parser = wwinfra.StdArgs().getParser ("Disassemble a Whirlwind Core File.")
    parser.add_argument("inputfile", help="file name of ww input core file")
    parser.add_argument('--outputfile', '-o', type=str, help="output file name ('-'=stdout)")
    parser.add_argument('--use_default_tsr', '-u',
                        help="pre-init core with default Toggle Switch Register settings", action="store_true")
    parser.add_argument("--DefZeroOne", '-z', help="Define core[0,1] as 0 and 1", action="store_true")
    parser.add_argument("--Debug", '-d', help="Print lotsa debug info", action="store_true")

    args = parser.parse_args()

    input_file_name = args.inputfile
    base_filename = re.sub('\\..*core$', '', input_file_name)
    if args.outputfile is None:
        wwdisasm_output_filename = base_filename + ".ww"
    else:
        wwdisasm_output_filename = args.outputfile

    # instantiate the class full of constants
    cb = wwinfra.ConstWWbitClass (corefile=os.path.basename(base_filename), args = args)
    wwinfra.theConstWWbitClass = cb
    cpu = WWCpuClass(cb)

    #  oops, this got a bit twisted...  use_default_tsr is intended simply to copy the default contents of
    #  the TSR into core, i.e., to put the boot loader into the image (if there should be one there)
    # for the Disassembler, the result should probably default to "don't", while for everything else it's
    # probably "do".  I should make this more explicit by copying defaults into core during disasm init
    # and getting rid of the special case flag.
    # But for now, we'll turn the flag off here and let the core-mem class default to On
    use_default_tsr = False
    if args.use_default_tsr is not None:
        use_default_tsr = args.use_default_tsr
    print("use_default_tsr=%d" % args.use_default_tsr)
    coremem = wwinfra.CorememClass(cb, use_default_tsr=use_default_tsr)
    cb.log = wwinfra.LogFactory().getLog (debug=args.Debug)

    AutoSymTab = [None] * CORE_SIZE  # automatically-generated labels for instructions that need them

    # read the core file from the tape-decoder
#    (CoreMem, jump_to, WW_file, WW_TapeID) = read_core(args.basename + ".tcore")
    ret = coremem.read_core(input_file_name, cpu, cb)
    (core_symtab, jump_to, WW_file, WW_TapeID, screen_debug_widgets) = ret

    ManualSymTab, SwitchTab = read_sym(base_filename + ".sym")
    ManualSymTab.update(core_symtab)  # combine the sym tabs

    cb.log.debug("debug")

    if jump_to is None:
        start = 0o40
    else:
        start = jump_to

    # scan the image to figure out which addresses are referenced as data or are the target
    # of a branch instruction
    addr = 0
    while addr < cb.CORE_SIZE:
        w = coremem.rd(addr, fix_none=False)
        if w is not None:
            # print "%04oo: %06oo %s" % (addr, w, DecodeOp(w, addr))
            label_code(w, addr)
        addr += 1

    # scan the image a second time to generate the automatic labels
    addr = 0
    while addr < cb.CORE_SIZE:
        w = coremem.rd(addr, fix_none=False)
        line_label = None
        if w is not None:
            if len(CoreReadBy[addr]) != 0:
                line_label = "r%04o" % addr
            if len(CoreWrittenBy[addr]) != 0:
                line_label = "w%04o" % addr
            if len(CoreReferredToByJump[addr]) != 0:
                line_label = "i%04o" % addr
            AutoSymTab[addr] = line_label
        addr += 1

    # scan the image a third time to print a listing
    # @0000:000000  label: op operand ; comment @@auto-comment
    # Insert a .org statement if there's a discontinuity in the address sequence
    if wwdisasm_output_filename[0] == '-':
        fout = sys.stdout
    else:
        print("Disassemble %s into %s" % (input_file_name, wwdisasm_output_filename))
        fout = None
        try:
            fout = open(wwdisasm_output_filename, 'wt')
        except IOError:
            print("can't open %s for writing" % wwdisasm_output_filename)
            exit(1)

    write_listing(fout, coremem, args.DefZeroOne, WW_file, WW_TapeID, start,
                  SwitchTab, AutoSymTab, ManualSymTab)

    if ErrorCount != 0:
        print("**ErrorCount = %d" % ErrorCount)


if __name__ == "__main__":
    main()
