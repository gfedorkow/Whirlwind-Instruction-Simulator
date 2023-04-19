# #!/bin/python3

# Assemble Whirlwind source
# g fedorkow, Dec 22, 2017

# Converted to Python 3, Apr 23, 2020

# Whirlwind Computer Source Code Assembler
# Sample Input Data

#    .ORG 40
# start: ta label  ;here's a comment
#       si 5
#       ck 5
#       .ORG 210
# label: .WORD 15
#       .SWITCH ckalarm 00

# Here's an example of the output from the assembler, which can be
# recycled as input to the assembler.
#    .WORD 123
#
# @0000:000000  label: op operand ; comment @@auto-comment
#
# ;strip autocomment
# ;save ;comment
# ;strip @addr:val
# ;save and strip label:
# ;look up op and operand
#
# @0040:040000label2a: ad L201 ; comment 2a @@auto-comment
# @0040:040000  label2b: ad L201 ; comment 2b@@auto-comment
# @0040:040000   label2c:    ad L201 bogus_arg; comment 2c @@auto-comment
#
# label2: ad L202  ;; comment on label2
#
# ad L203  @@autocomment on unlabeled add
#
#    ad L204 ;missing label following line with blanks
#    .WORD 123


import sys
# sys.path.append('K:\\guy\\History-of-Computing\\Whirlwind\\Py\\Common')
import re
import argparse
import wwinfra

def breakp(log):
    print("hit breakpoint %s" % log)


# defines
ADDRESS_MASK = 0o3777
WORD_MASK = 0o177777
CORE_SIZE = 2048

OPERAND_MASK_5BIT = 0o03777
OPERAND_MASK_6BIT = 0o01777
OPERAND_MASK_SHIFT = 0o777  # shifts can go from 0 to 31, i.e., five bits, but the field has room for 9 bits

Debug = False
LexDebug = False
Legacy_Numbers = False

class DebugWidgetClass:
    def __init__(self, linenumber, addr_str, incr_str):
        self.linenumber = linenumber
        self.addr_str = addr_str
        self.incr_str = incr_str
        self.addr_binary = None
        self.incr_binary = None


def strip_space(s1):
    s2 = re.sub("^[ \t]*", '', s1)
    s3 = re.sub("[ \t]*$", '', s2)
    return s3


# Source line Lexer; break the components of a single line into constituent components
# Modified Jan 10 2020 to add .w, .fl, .fh directives

# Line format looks like this:
# @0000:000000  label: op operand ; comment @@auto-comment
#
# ;strip autocomment
# ;save ;comment
# ;strip @addr:val
# ;save and strip label:
# ;look up op and operand
def lex_line(line, line_number):
    global Legacy_Numbers

    comment = ''
    label = ''
    op = ''
    operand = ''
    directive = 0

    # sample line:
    # @0061.49:140001     w0061: mr   0001      ; multiply and roundoff @@WrittenBy a0045 a0101 ReadBy a0101

    if len(line) == 0:  # skip blank lines
        # I had the assembler case-insensitive earlier, just in case, as it were.  But it seems like
        # the original was case-sensitive so I took out an "op.lower()" here to leave well enough alone
        return LexedLine(line_number, label, op, operand, comment, directive)

    if LexDebug:
        print(line_number, "Line=", line)

    # Special Case for .exec directive
    # I'm adding a directive to the assembler to pass a string to the simulator that should be interpreted
    # and executed as a python statement
    # e.g.    .exec print("time=%d" % cm.rd(0o05))
    # The statement can't have a label, and must not start in column zero.  But other than that, we'll bypass
    # the rest of the parser checks, as the python statement could have "anything"
    # The .exec directive will follow a 'real' instruction; the assumption is that it is executed after
    # the preceding instruction, before the next 'real' instruction.
    exec_match = "^[ \t][ \t]*(.exec)"
    if re.search(exec_match, line):
        exec_stmt = re.sub(exec_match, '', line)
        exec_stmt = exec_stmt.lstrip().rstrip()
        op = '.exec'
        operand = exec_stmt
        # as above, .lower() removed
        return LexedLine(line_number, label, op, operand, comment, directive)


    # strip the initial "@address:data" tag
    #    pattern = "(^@[0-7][0-9\.]*:[0-7][0-7]*) *([a-zA-Z][a-z[A-Z[0-7]*) *"
    addr_data_tag = "(^@[0-7][0-9.]*:[0-7][0-7]*) *"
    r1 = re.sub(addr_data_tag, '', line)
    if LexDebug:
        print(line_number, "RS1=", r1)

    # strip auto-comment
    r2 = re.sub(" *@@.*", '', r1)
    if LexDebug:
        print(line_number, "remaining r2:", r2)

    # if there's nothing but a comment on the line, strip the semicolon and return it now
    if r2[0] == ';':
        comment = r2[1:]
        return LexedLine(line_number, label, op, operand, comment, directive)

    # split op and comment
    rl3 = re.split(";", r2, 1)
    r3 = r2
    if LexDebug:
        print(line_number, "RL3:", rl3)
    if len(rl3) > 1:
        comment = strip_space(rl3[1])
        r3 = strip_space(rl3[0])

    # split label and op
    rl4 = re.split(":", r3)
    r4 = strip_space(r3)
    if LexDebug:
        print(line_number, "RL4:", rl4)
    if len(rl4) > 1:
        r4 = strip_space(rl4[1])
        label = strip_space(rl4[0])

    # at this point, we should have nothing but an operator and operand
    # With the one special case of an editing directive in the source file...
    # If the source line contains .w, .fl, .fh, convert the line into a constant, either
    # a number or flexo characters in the low or high bit positions.  Record the directive
    # but don't keep it as part of the source file.
    # added Jan 10, 2020
    if (len(r4) > 0) and (r4[0] == '.'):
        if r4.find(".w ") == 0:
            directive = DOT_WORD_OP
            r4 = re.sub("\.w *", '', r4)
        if r4.find(".fl ") == 0:
            directive = DOT_FLEXL_OP
            r4 = re.sub("\.fl *", '', r4)
        if r4.find(".fh ") == 0:
            directive = DOT_FLEXH_OP
            r4 = re.sub("\.fh *", '', r4)

    # split the operator and operand
    rl5 = re.split(" ", r4, maxsplit=1)
    op = r4
    if LexDebug:
        print(line_number, "RL5:", rl5)
    if len(rl5) > 1:
        operand = strip_space(rl5[1])
        op = strip_space(rl5[0])
        if Legacy_Numbers:   # guy's "legacy numbers" were purely and totally octal; the asm is now more flexible.
            if operand.isnumeric():
                operand = "0o" + operand

    return LexedLine(line_number, label, op, operand, comment, directive)


def ww_int(nstr, line_number, relative_base=None):
    global Legacy_Numbers
    if Legacy_Numbers:
        return ww_int_adhoc(nstr)
    return ww_int_csii(nstr, line_number, relative_base)


# This was guy's first try at WW Number Conversion, replaced in Oct 2020 with
#   In Whirlwind-speak, constants were viewed as fractional, i.e. 0 <= n < 1.0
# and expressed as o.ooooo  - a sign bit followed by 5 octal digits
# This routing accepts either ordinary octal ints, or WW fractional format.
def ww_int_adhoc(nstr):
    if re.match('0o', nstr):  # try Pythonic octal conversion
        octal_str = nstr[2:]
        if re.search('^[0-7][0-7]*$', octal_str) is None:
            print("Expecting 0onnnnn octal number; got %s" % nstr)
            return None
        return int(octal_str, 8)

    if nstr.find(".") == -1:
        return int(nstr, 8)
    else:
        if (nstr[1] != '.') & (len(nstr) != 7):
            print("format problem in WW Number %s" % nstr)
        j = int(nstr.replace('.', ''), 8)
        if Debug:
            print("ww number %s = %6oo" % (nstr, j))
        return j


# A number-conversion routine that's more careful and adheres to the non-intuitive
# combination of Decimal and Octal and Fixed-Point and Float
#  See M-2539-2, page XI-3
#  If it starts with '0.' or '1.' its octal.  + or - are not allowed
#      There must be 5 digits to the right of the decimal point
#  If it starts with + or - it's decimal
#     +0 and -0 are different, as usual.
#  if it starts with a digit, it's a positive decimal number
#  If it starts with + or - and contains a decimal point, it's a decimal fraction
#     and in that case, it may be followed by base-10 and/or base-2 exponent (yes, both)
#     e.g. +1OO. x 10-2 x 2-2
#       Note that Flexo actually had superscript numbers, and that may have been assumed...
#       [And I'm not doing it until I find an example!]
#  I'm adding a rule for no-questions-asked Octal, the usual Pythonic 0onnnn
#  and I'm adding a hack for small positive numbers -- if it's 0-7, doesn't matter if it's octal or decimal!
def ww_int_csii(nstr, line_number, relative_base=None):
    try:
        ww_small_int = int(nstr, 10)
        if ww_small_int < 8 and ww_small_int >= 0:
            return ww_small_int
        #  otherwise, fall through to all the other tests below
    except ValueError:
        pass

    # there's a case I can't figure out how to categorize: "0.0" could be either decimal
    # or Octal, but it seems to come closer to matching the Octal pattern.
    # In general, I think this routine is more conservative about number types than the real assembler,
    # but I don't know what rules they actually used.
    if re.match('0\.|1\.', nstr):  # try Whirlwind fixed-point octal conversion, e.g. n.nnnnn
        octal_str = nstr.replace('.', '')
        if re.search('^[01][0-7][0-7][0-7][0-7][0-7]$', octal_str) is None and \
            re.search('^0.0$', nstr) is None:
            print("Line %d: Expecting n.nnnnn octal number; got %s" % (line_number, nstr))
            return None
        return int(octal_str, 8)
    if re.match('0o', nstr):  # try Pythonic octal conversion
        octal_str = nstr[2:]
        if re.search('^[0-7][0-7]*$', octal_str) is None:
            print("Line %d: Expecting 0onnnnn octal number; got %s" % (line_number, nstr))
            return None
        return int(octal_str, 8)
    if re.match('^[1-9][0-9]*r$', nstr):  # Try a Whirlwind relative base-10 label, eg "65r"
        if relative_base is None:
            print("Line %d: assertion failure: relative_base is None; continue with Zero" % line_number)
            relative_base = 0
        offset = int(nstr[0:-1])  # I don't think this can fail, as we only get here unless it's all digits
        print("relative label %s: %d + %d" % (nstr, offset, relative_base))
        return offset + relative_base

    if re.match('\+|-|[1-9]|0$', nstr):  # Try Decimal conversion
        sign = 1   # default to a positive number
        if nstr[0] == '-':
            sign = -1
        dec_str = re.sub(r'-|\+', '', nstr)
        if re.search(r'^[0-9.][0-9.]*$', dec_str) is None:
            print("Line %d: Expecting +/- decimal number; got %s" % (line_number, nstr))
            return None
        if nstr.find(".") == -1:  # if the number has no decimal point, it's an integer
            ones_comp = int(dec_str, 10)
            if ones_comp >= 0o77777:
                print("Line %d: Oversized decimal number: %d" % (line_number, ones_comp))
                return None
        else:    # it must be a decimal float
            ones_comp = int(float(dec_str) * 0o100000)
            if ones_comp >= 0o77777:
                print("Line %d: Oversized decimal float: %s" % (line_number, dec_str))
                return None
        if sign == -1:
            ones_comp = ones_comp ^ 0o177777  # this should handle -0 automatically
        return ones_comp
        # add More Code for fractional decimal numbers with exponents
    print("Line %d: not sure what to do with this so-called number: '%s'" % (line_number, nstr))
    return None


def five_bit_op(inst, binary_opcode, operand_mask):
    global NextCoreAddress, CurrentRelativeBase

    # check that the operand is a label or a number
    inst.instruction_address = NextCoreAddress
    inst.relative_address_base = CurrentRelativeBase
    inst.operand_mask = OPERAND_MASK_5BIT
    inst.binary_opcode = binary_opcode << 11
    addr_inc = 1
    if Debug:
        print("operator: %s, five bit op code %06oo, mask %4oo at addr %06oo" %
              (inst.operator, inst.binary_opcode, inst.operand_mask, inst.instruction_address))
    return addr_inc


# ok, they're six-bit op codes - shift right, shift left and cycle.  But the extra bit is in WW Bit 6, so it's
# easier to treat them as seven bit, and require the extra bit in the middle to be zero.
def seven_bit_op(inst, binary_opcode, operand_mask):
    global NextCoreAddress, CurrentRelativeBase
    inst.instruction_address = NextCoreAddress
    inst.relative_address_base = CurrentRelativeBase
    inst.operand_mask = OPERAND_MASK_SHIFT  # the mask allows 32 bit shift, i.e., five bits
    inst.binary_opcode = binary_opcode << 9
    addr_inc = 1
    if Debug:
        print("operator: %s, six bit op code %03oo, mask %4oo" % (inst.operator, binary_opcode, operand_mask))
    return addr_inc


# # process a .ORG statement, setting the next address to load into core
def dot_org_op(srcline, _binary_opcode, _operand_mask):
    global NextCoreAddress, CurrentRelativeBase

    # put a try/except around this conversion
    next_add = ww_int_csii(srcline.operand, srcline.linenumber, relative_base = CurrentRelativeBase)
    if next_add is None:
        print("Line %d: can't parse number in .org" % srcline.linenumber)
        return 1
    NextCoreAddress = next_add
    CurrentRelativeBase = next_add  # <--- This is an important assumption!!
    if Debug:
        print(".ORG %04oo" % NextCoreAddress)
    return 0


# # process a .DAORG statement, setting the next *drum* address to load
# I have no idea what to do with these!
def dot_daorg_op(srcline, _binary_opcode, _operand_mask):
    global NextCoreAddress, CurrentRelativeBase

    cb.log.warn("Line %d: Drum Address psuedo-op %s %s" %
                (srcline.linenumber, srcline.operator, srcline.operand))
    return 0

# # process a .BASE statement, resetting the relative addr count to zero
# I added this pseudo-op during the first run at cs_ii conversion
# But on the next go round, I changed it to parse the "0r" label directly.
def dot_relative_base_op(srcline, _binary_opcode, _operand_mask):
    global NextCoreAddress, CurrentRelativeBase

    CurrentRelativeBase = 0
    cb.log.warn("Deprecated .BASE @%04oo" % NextCoreAddress)
    return 0


# Program Parameters are like #define statements; they don't generate code, but
# they do put values in the symbol table for later use.
# They can be "called" in the source code as a way to insert a word of whatever value was
# assigned to the pp.
#  Samples look like this:       .PP pp15=pp14+1408  ;  @line:19a
#  The program parameter label (e.g. pp15), apparently is always two letters plus some digits,
#  but not necessarily always 'pp'
# I am not so sure how to handle these guys!
def dot_program_param_op(srcline, _binary_opcode, _operand_mask):
    #
    lhs = re.sub("=.*", '', srcline.operand)
    rhs = re.sub(".*=", '', srcline.operand)

    SymTab[lhs] = srcline

    srcline.instruction_address = label_lookup_and_eval(rhs, srcline)
    #cb.log.warn("Line %d: Insert Program Parameter %s %s" %
    #            (srcline.linenumber, srcline.operator, srcline.operand))
    return 0


# This routine is called when "pp" turns up as an op code.
# In which case we're supposed to include the value of the parameter as a word
def insert_program_param_op(srcline, _binary_opcode, _operand_mask):
    cb.log.warn("Line %d: Insert Program Parameter %s %s as a word" %
                (srcline.linenumber, srcline.operator, srcline.operand))
    return 0

# the Source Code may have a DITTO operation
# don't know exactly what it does yet, except to duplicate words in memory
def ditto_op(srcline, _binary_opcode, _operand_mask):
    cb.log.warn("Line %d: DITTO operation %s %s" %
                (srcline.linenumber, srcline.operator, srcline.operand))
    return 0


def csii_op(src_line, _binary_opcode, _operand_mask):
    cb.log.warn("Line %d: CS-II operation %s %s; inserting .word 0" %
                (src_line.linenumber, src_line.operator, src_line.operand))
    global NextCoreAddress, CurrentRelativeBase
    ret = 0
    src_line.instruction_address = NextCoreAddress
    src_line.relative_address_base = CurrentRelativeBase
    src_line.operand_mask = WORD_MASK
    src_line.binary_opcode = 0
    NextCoreAddress += 1
    return ret




# # process a .SWITCH statement -- just pass the value forward to let the sim figure out what to do...
def dot_switch_op(srcline, _binary_opcode, _operand_mask):
    global SwitchTab
    global cb

    sw_class = wwinfra.WWSwitchClass()
    ret = 0
    # put a try/except around this conversion
    tokens = re.split("[ \t]", srcline.operand)
    name = tokens[0]
    if name == "FFRegAssign":  # special case syntax for assigning FF Register addresses
        tokens.append('')  # cheap trick; add a null on the end to make sure the next statement doesn't trap
        ff_reg_map, val = sw_class.parse_ff_reg_assignment(cb, name, tokens[1:])
        if ff_reg_map is None:
            cb.log.warn("can't parse %s: %s" % (name, tokens[1]))
            ret = 1
    else:
        if len(tokens) != 2:
            cb.log.warn("usage:  .SWITCH <switchname> <value>")
            return 1
        int_val = ww_int(tokens[1], srcline.linenumber)  # this will trap if it can't convert the number
        if int_val is not None:
            val = "0o%o" % int_val   # convert the number into canonical octal
        else:
            cb.log.warn(".SWITCH %s setting %s must be an octal number" % (name, tokens[1]))
            ret = 1
            val = ' '
    SwitchTab[name] = val       # we're going to save the validated string, not numeric value
    cb.log.info(".SWITCH %s set to %s" % (name, val))
    return ret


# # process a .WORD statement, to initialize the next word of storage
# coming into the routine, the number to which storage should be set is
# already in the operand field of the srcline class
def dot_word_op(src_line, _binary_opcode, _operand_mask):
    global NextCoreAddress, CurrentRelativeBase

    ret = 0
    # op-code contains the type of .word directive
    # check that the operand is a number
    #     if i.operand[0].isalpha():
    # if src_line.operand.isdigit() == False:
    #    print(("Warning: Line %d .word operand must be numeric; got %s" % (src_line.linenumber, src_line.operand)))
    #    ret = 1
    src_line.instruction_address = NextCoreAddress
    src_line.relative_address_base = CurrentRelativeBase
    src_line.operand_mask = WORD_MASK
    src_line.binary_opcode = 0
    NextCoreAddress += 1
    if Debug:
        print(".WORD %04s at addr %04oo" % (src_line.operand, src_line.instruction_address))
    return ret


# # process a .JumpTo statement, to indicate the program's start address
def dot_jumpto_op(src_line, _binary_opcode, _operand_mask):
    global WW_JumptoAddress
    # the operand could be a number or a label; resolve that later
    WW_JumptoAddress = src_line.operand
    if Debug:
        print(".JumpTo %04s" % src_line.operand)
    return 0

# # process a .dbwgt to add a debug widget to the simulated CRT display
# This directive gives an address,which could be a number or label, and an optional
# increment value, which must be a number.
def dot_dbwgt_op(src_line, _binary_opcode, _operand_mask):
    global DbWgtTab

    tokens = src_line.operand.split()
    addr = strip_space(tokens[0])
    if len(tokens) > 1:
        incr = strip_space(tokens[1])
    else:
        incr = "1"
    # the operand could be a number or a label; resolve that later
    DbWgtTab.append(DebugWidgetClass(src_line.linenumber, addr, incr))
    if Debug:
        print(".DbWgt %04s %s" % (addr, incr))
    return 0


# process a .ISA 1950 statement, to change the instruction set to
# the 1950's version with qh, qd and all the rest
def dot_change_isa_op(src_line, _binary_opcode, _operand_mask):
    global op_code, op_code_1950, op_code_1958  # the table for opcodes is a global
    if src_line.operand == "1950":
        op_code = change_isa(op_code_1950)
    elif src_line.operand == "1958":
        op_code = change_isa(op_code_1958)
    else:
        print("Error on .isa; must be 1950 or 1958, not %s" % src_line.operand)
        exit(1)
    return 0


def dot_python_exec_op(src_line, _binary_opcode, _operand_mask):
    global ExecTab, NextCoreAddress

    exec = src_line.operand
    addr = NextCoreAddress
    if addr in ExecTab:
        ExecTab[addr] = ExecTab[addr] + ' \\n ' + exec
    else:
        ExecTab[addr] = exec
    if Debug:
        print(".exec @0o%02o %s" % (addr, exec))
    return 0



# # process a filename directive
def dot_ww_filename_op(src_line, _binary_opcode, _operand_mask):
    global WW_Filename
    # the operand is a string identifying the file name read into the tape decoder
    WW_Filename = src_line.operand
    if Debug:
        print(".ww_filename %04s" % src_line.operand)
    return 0


def dot_ww_tapeid_op(src_line, _binary_opcode, _operand_mask):
    global WW_TapeID
    # the operand is a string identifying the Whirlwind Tape ID (if available)
    WW_TapeID = src_line.operand
    if Debug:
        print(".ww_tapeid %04s" % src_line.operand)
    return 0


# # parse a line after it's been Lexed.  This routine simply looks up the
# # opcode string to find the binary opcode, and also to find if it's
# # a five- or six-bit opcode, or a pseudo-op
# I'm ignoring upper/lower case in op codes
# return the number of errors
def parse_ww(srcline):
    global NextCoreAddress, CurrentRelativeBase
    # the special case at the start handles lines where there's a label but no operation
    # This happens because a line can have more than one label(!)
    # e.g.
    #   d25:
    #   0r: ca f11
    # "real" operations increment the next address; this just records it.
    # if the line has a label but no op, we need to update the Relative Address base
    if srcline.label == "z1":
        breakp("z1")
    if len(srcline.operator) == 0:
        srcline.instruction_address = NextCoreAddress
        if len(srcline.label):
            SymTab[srcline.label] = srcline  # store the label in the symtab
            CurrentRelativeBase = NextCoreAddress
            print("Line %d: Label %s: Implicit Set of Relative Base to 0o%o" %
                  (srcline.linenumber, srcline.label, CurrentRelativeBase))
        return 0

    ret = 0
    addr_inc = 0
    # continue from here with normal instruction processing
    op = srcline.operator
    if op in op_code:
        op_list = op_code[op]
        addr_inc = op_list[0](srcline, op_list[1], op_list[2])  # dispatch to the appropriate operator
    else:
        print("Unrecognized operator in line %d: %s" % (srcline.linenumber, srcline.operator))
        ret += 1

    # Adjust the Relative label (e.g. '0r:')
    # special-case the "0r" label;  that one says, where ever you are, that line is the new base
    # address for relative address offsets like "5r" or "r+5"
    # Don't put "r" in the symbol table; it's picked off later with another special case.
    if m := re.match("([0-9]+)r", srcline.label):
        offset = int(m.group(1), 10)
        new_relative_base = srcline.instruction_address - offset
        if offset == 0:
            print("Line %d: Setting '0r' Relative Base to 0o%o" % (srcline.linenumber, srcline.instruction_address))
            CurrentRelativeBase = srcline.instruction_address
        else:
            if new_relative_base != CurrentRelativeBase:
                cb.log.warn("Line %d: Label %s: Changing Relative Base from 0o%o to 0o%o" %
                        (srcline.linenumber, srcline.label, CurrentRelativeBase, new_relative_base))
                CurrentRelativeBase = new_relative_base
    else:
        # the book says that any 'comma operator', i.e. a label, resets the Relative Address
        if len(srcline.label):
            SymTab[srcline.label] = srcline
            if srcline.instruction_address is not None:
                CurrentRelativeBase = srcline.instruction_address
                print("Line %d: Label %s: Setting Relative Base to 0o%o" %
                        (srcline.linenumber, srcline.label, CurrentRelativeBase))

    if len(srcline.operand) == 0:
        print("Missing operand in line %d: %s" % (srcline.linenumber, srcline.operator))
        ret += 1

    NextCoreAddress += addr_inc

    return ret


# ;categorize the operand part of the instruction
OPERAND_NONE = 0  # it's a pseudo-op
OPERAND_JUMP = 1  # the address is a jump target
OPERAND_WR_DATA = 2  # the address writes a data word to Core
OPERAND_RD_DATA = 4  # the address writes a data word from Core
OPERAND_PARAM = 8  # the operand isn't an address at all

NO_DIRECTIVE_OP = 0
DOT_WORD_OP = 1
DOT_FLEXL_OP = 2
DOT_FLEXH_OP = 3

# dictionary table for op codes
#  indexed by op code
#  Return 
#    numeric value
#    5-bit, 6-bit or pseudo-op
#    mask

op_code_1958 = {   # # function, op-code, mask
    "si":  [five_bit_op, 0, 0, OPERAND_PARAM],
    "<unused01>": [five_bit_op, 0o1, 0, OPERAND_PARAM],
    "bi":  [five_bit_op,  0o2, 0, OPERAND_WR_DATA],
    "rd":  [five_bit_op,  0o3, 0, OPERAND_PARAM],
    "bo":  [five_bit_op,  0o4, 0, OPERAND_RD_DATA],
    "rc":  [five_bit_op,  0o5, 0, OPERAND_PARAM],
    "sd":  [five_bit_op,  0o6, 0, OPERAND_RD_DATA],
    "cf":  [five_bit_op, 0o07, 0, OPERAND_PARAM],
    "ts":  [five_bit_op, 0o10, 0, OPERAND_WR_DATA],
    "td":  [five_bit_op, 0o11, 0, OPERAND_WR_DATA],
    "ta":  [five_bit_op, 0o12, 0, OPERAND_WR_DATA],
    "ck":  [five_bit_op, 0o13, 0, OPERAND_RD_DATA],
    "ab":  [five_bit_op, 0o14, 0, OPERAND_WR_DATA],
    "ex":  [five_bit_op, 0o15, 0, OPERAND_WR_DATA | OPERAND_RD_DATA],
    "cp":  [five_bit_op, 0o16, 0, OPERAND_JUMP],
    "sp":  [five_bit_op, 0o17, 0, OPERAND_JUMP],
    "ca":  [five_bit_op, 0o20, 0, OPERAND_RD_DATA],
    "cs":  [five_bit_op, 0o21, 0, OPERAND_RD_DATA],
    "ad":  [five_bit_op, 0o22, 0, OPERAND_RD_DATA],
    "su":  [five_bit_op, 0o23, 0, OPERAND_RD_DATA],
    "cm":  [five_bit_op, 0o24, 0, OPERAND_RD_DATA],
    "sa":  [five_bit_op, 0o25, 0, OPERAND_RD_DATA],
    "ao":  [five_bit_op, 0o26, 0, OPERAND_WR_DATA | OPERAND_RD_DATA],
    "dm":  [five_bit_op, 0o27, 0, OPERAND_RD_DATA],
    "mr":  [five_bit_op, 0o30, 0, OPERAND_RD_DATA],
    "mh":  [five_bit_op, 0o31, 0, OPERAND_RD_DATA],
    "dv":  [five_bit_op, 0o32, 0, OPERAND_RD_DATA],
    "slr": [seven_bit_op,  0o154, 0, OPERAND_PARAM],
    "slh": [seven_bit_op,  0o155, 0, OPERAND_PARAM],
    "srr": [seven_bit_op,  0o160, 0, OPERAND_PARAM],
    "srh": [seven_bit_op,  0o161, 0, OPERAND_PARAM],
    "sf":  [five_bit_op, 0o35, 0, OPERAND_WR_DATA],
    "clc": [seven_bit_op,  0o170, 0, OPERAND_PARAM],
    "clh": [seven_bit_op,  0o171, 0, OPERAND_PARAM],
    "md":  [five_bit_op, 0o37, 0, OPERAND_RD_DATA],

    "ica": [csii_op, 0o37, 0, OPERAND_RD_DATA],
    "imr": [csii_op, 0o37, 0, OPERAND_RD_DATA],
    "IN":  [csii_op, 0o37, 0, OPERAND_RD_DATA],
    "isp": [csii_op, 0o37, 0, OPERAND_RD_DATA],
    "its": [csii_op, 0o37, 0, OPERAND_RD_DATA],
    "OUT": [csii_op, 0o37, 0, OPERAND_RD_DATA],

}

op_code_1950 = {   # # function, op-code, mask
    "ri":  [five_bit_op, 0, 0, OPERAND_PARAM],
    "rs":  [five_bit_op, 0o1, 0, OPERAND_PARAM],
    "rf":  [five_bit_op,  0o2, 0, OPERAND_WR_DATA],
    "rb":  [five_bit_op,  0o3, 0, OPERAND_PARAM],
    "rd":  [five_bit_op,  0o4, 0, OPERAND_RD_DATA],
    "rc":  [five_bit_op,  0o5, 0, OPERAND_PARAM],
    "qh":  [five_bit_op,  0o6, 0, OPERAND_PARAM],
    "qd":  [five_bit_op,  0o7, 0, OPERAND_PARAM],
    "ts":  [five_bit_op, 0o10, 0, OPERAND_WR_DATA],
    "td":  [five_bit_op, 0o11, 0, OPERAND_WR_DATA],
    "ta":  [five_bit_op, 0o12, 0, OPERAND_WR_DATA],
    "ck":  [five_bit_op, 0o13, 0, OPERAND_RD_DATA],
    "qf":  [five_bit_op,  0o14, 0, OPERAND_PARAM],  # guy made up the 0o14 op-code; I don't know what code they assigned
    "qe":  [five_bit_op, 0o15, 0, OPERAND_WR_DATA | OPERAND_RD_DATA],
    "cp":  [five_bit_op, 0o16, 0, OPERAND_JUMP],
    "sp":  [five_bit_op, 0o17, 0, OPERAND_JUMP],
    "ca":  [five_bit_op, 0o20, 0, OPERAND_RD_DATA],
    "cs":  [five_bit_op, 0o21, 0, OPERAND_RD_DATA],
    "ad":  [five_bit_op, 0o22, 0, OPERAND_RD_DATA],
    "su":  [five_bit_op, 0o23, 0, OPERAND_RD_DATA],
    "cm":  [five_bit_op, 0o24, 0, OPERAND_RD_DATA],
    "sa":  [five_bit_op, 0o25, 0, OPERAND_RD_DATA],
    "ao":  [five_bit_op, 0o26, 0, OPERAND_WR_DATA | OPERAND_RD_DATA],
    "<unused05>":  [five_bit_op,  0o27, 0, OPERAND_PARAM],
    "mr":  [five_bit_op, 0o30, 0, OPERAND_RD_DATA],
    "mh":  [five_bit_op, 0o31, 0, OPERAND_RD_DATA],
    "dv":  [five_bit_op, 0o32, 0, OPERAND_RD_DATA],
    "sl":  [five_bit_op,  0o33, 0, OPERAND_PARAM],
    "sr":  [five_bit_op,  0o34, 0, OPERAND_PARAM],
    "sf":  [five_bit_op, 0o35, 0, OPERAND_WR_DATA],
    "cl":  [five_bit_op,  0o36, 0, OPERAND_PARAM],
    "md":  [five_bit_op, 0o37, 0, OPERAND_RD_DATA],
    }
op_code = op_code_1958  # default instruction set

meta_op_code = {
    ".ORG": [dot_org_op, 0, 0, OPERAND_NONE],
    ".DAORG": [dot_daorg_op, 0, 0, OPERAND_NONE],
    ".BASE": [dot_relative_base_op, 0, 0, OPERAND_NONE],
    ".word": [dot_word_op, DOT_WORD_OP, 0, OPERAND_NONE],
    ".flexl": [dot_word_op, DOT_FLEXL_OP, 0, OPERAND_NONE],
    ".flexh": [dot_word_op, DOT_FLEXH_OP, 0, OPERAND_NONE],
    ".switch": [dot_switch_op, 0, 0, OPERAND_NONE],
    ".jumpto": [dot_jumpto_op, 0, 0, OPERAND_NONE],
    ".dbwgt": [dot_dbwgt_op, 0, 0, OPERAND_NONE],
    ".ww_file": [dot_ww_filename_op, 0, 0, OPERAND_NONE],
    ".ww_tapeid": [dot_ww_tapeid_op, 0, 0, OPERAND_NONE],
    ".isa": [dot_change_isa_op, 0, 0, OPERAND_NONE],  # directive to switch to the older 1950 instruction set
    ".exec": [dot_python_exec_op, 0, 0, OPERAND_NONE],
    ".PP":   [dot_program_param_op, 0, 0, OPERAND_NONE],
    "pp": [insert_program_param_op, 0, 0, OPERAND_NONE],
    "DITTO": [ditto_op, 0, 0, OPERAND_NONE],
}

# this little routine updated the op code table to be used for analyze instructions.  (So far) there are only
# two, the 1950 version from R-193 with extensions, and the 2M-0277 1958 version
#  This should be revised if there are ever more op code sets
def change_isa(oplist):
    global op_code, op_code_1950
    global ISA_1950

    if oplist == op_code_1950:
        ISA_1950 = True
    else:
        ISA_1950 = False
    op_code = {}
    op_code.update(oplist)
    op_code.update(meta_op_code)
    return op_code


# go through the instructions and figure out which line is referenced by some other line
def label_code(i):
    operand_type = op_code[i.operator][3]
    if operand_type == OPERAND_NONE:
        return
    pc = i.instruction_address
    addr = i.binary_instruction_word & i.operand_mask
    if operand_type & OPERAND_JUMP:
        CoreReferredToByJump[addr].append(pc)
    if operand_type & OPERAND_RD_DATA:
        CoreReadBy[addr].append(pc)
    if operand_type & OPERAND_WR_DATA:
        CoreWrittenBy[addr].append(pc)


# Whirlwind labels can have simple arithmetic expressions embedded, to calculate offsets from
# whatever the nearest label might be, e.g., "t1+5" for five beyond the memory address identified by t1.
# I think the offsets can be added or subtracted, but I don't think there are any other operations.
# I've read that a "programmed constant", i.e., sort of like a cross between a label and a #define
# can also be used in the expression, but haven't seen a case of this.
# In this instance, there will certainly be cases with more than one term in the expression, e.g. t1+5+8
# Numbers default to Decimal, and can also come in the 0.00000 octal format.
# Return an Int with the offset
def eval_addr_expr(expr: str, line_number):

    loop = 0
    terms = expr
    offset = 0
    while len(terms):
        loop += 1
        if loop > 20:
            print("eval_addr_expr stuck in loop, line %d: expr=%s" % (line_number, expr))
            exit(1)

        if terms[0] == '+' or terms[0] == '-':
            op = terms[0]
            terms = terms[1:]
        else:
            op = '+'
        if m := re.search("([0-9.]*)", terms):
            number_str = m.group(1)
            terms = re.sub("[0-9.]*", "", terms)
            if len(number_str):
                number = ww_int(number_str, line_number)
            else:
                number = 0
            if op == '-':
                number = -number
            offset += number

    return offset


# Labels can have simple arithmetic expressions (I think only "label +/- number +/- number")
# Here we evaluate the arithmetic
# This routine could run into "programmed parameters", kinda like ifdefs, and will evaluate these
def label_lookup_and_eval(label_with_expr: str, srcline):
    if label_with_expr == '-.9000':
        breakp('-.9000')

    # if there's an expression, split it into tokens
    expr_terms_limit = 10  # this is to catch iteration bugs
    tokens = []
    lbl = label_with_expr
    while re.search("[-+]", lbl[1:]):  # search for a +/- after the first character
        m = re.search("([-+]?[^-+].*?)[-+].*", lbl)  #  note non-greedy match
        if m is None:
            cb.log.fatal("oops; no match in label_lookup_and_eval with %s" % label_with_expr)
        token = m.group(1)
        lbl = lbl[len(token):]   # strip the token
        tokens.append(token)
        if (expr_terms_limit := expr_terms_limit - 1) == 0:
            cb.log.fatal("oops; endless loop on expr %s?" % label_with_expr)

    tokens.append(lbl)  # add whatever is left into the token list

    # CS-II has this weird label format with an offset prepended to a label value, e.g. "19r6"
    # Separate the offset and the label and turn the offset into an explicit Add, i.e., "r6+19"
    # I'll actually append the offset to the end of the list of tokens, on the assumption that
    # there ain't ever gonna be expressions with multiplication or parentheses!
    # The syntax 19r6 means r6+19.  But I can only assume pp1-19r6 means pp1-(r6 + 19) = pp1 - r6 - 19
    # That is, I assume there's no syntax for a negative offset
    new_tokens = []
    for token in tokens:
        tag = token  # remember the name, so we can remove it from the list
        if token == '+.0':
            breakp('+.0')
        first_sign = ''   # default is assumed positive
        second_sign = '+'
        if token[0] == '+' or token[0] == '-':
            first_sign = token[0]
            second_sign = token[0]
            token = token[1:]

        # This stanza converts Whirlwind CS-II labels of the form "5a5" to "a5+5", i.e., moving
        # the implicit offset from the front to an explicit add.
        # Note that there's a very near miss between WW format "5a5" and Unix convention "0o5" for octal
        # It's not quite ambiguous, since CS-II rules against the use of letters I or O as variable names
        # So there's a special-case escape for Unix numbers.  Phew!
        # If this gets a notch worse somewhere, I'll add a flag to the command line to say what
        # number conventions are in use.
        if m := re.search("^([-+]?[0-9.]+)[a-zA-Z].*", token) and not re.match("^0o[0-9]", token):
            offset = m.group(1)
            label = token[len(offset):]
            new_tokens.append(first_sign + label)
            new_tokens.append(second_sign + offset)
            print("converting %s to %s%s%s%s" % (token, first_sign, label, second_sign, offset))
        else:
            new_tokens.append(first_sign + token)
    tokens = new_tokens

    # now we can evaluate all the terms in the expression
    # This is a bit confusing, because '+' does double-duty to indicate addition
    # but also that the following digits are a decimal number
    # I _think_ the "op" test below has been superceded by the token parser I added above.
    # A leading + or - simply means the sign of the number
    result = 0
    # op = '+'
    sign = ''
    for token in tokens:
        val = 0
        if token[0] == '-' or token[0] == '+':
            # op = token[0]
            sign = token[0]
            token = token[1:]
        if re.match("[a-zA-Z]", token):
            if token == 'r':  # special case for relative addresses
                val = CurrentRelativeBase
            elif token in SymTab:
                val = SymTab[token].instruction_address
            if val is None:
                cb.log.fatal("Line %d: Unknown label %s in %s" % (srcline.linenumber, token, srcline.operand))
                val = 0
        elif re.match("[0-9.]", token):
            val = ww_int(sign + token, srcline.linenumber,
                                relative_base = srcline.relative_address_base)
        else:
            cb.log.warn("unknown symbol %s in label_lookup_and_eval with %s" % (token, label_with_expr))
        # if op == '-':
        #     result -= val
        # else:
        result += val

    # print("line %d: label_lookup_and_eval(%s) resolves to %d (0o%o)" %
    #      (srcline.linenumber, label_with_expr, result, result))
    # print(tokens)
    return result








def old_label_lookup_and_eval(label_with_expr: str, srcline):
    if re.search("^([a-z][a-z0-9]+)", label_with_expr):  # test to see if it's a label or just a number
        if re.search("[+\-]", label_with_expr):  # this must a label followed by an expression
            label = re.sub("[+\-].*", "", label_with_expr)
            expr = re.sub("^[a-z0-9]+", "", label_with_expr)
        else:  # it's just a label, no additional adornments
            label = label_with_expr
            expr = ''
    else:  # in this case, it's just a number
        label = ''
        expr = label_with_expr

    if len(expr):
        label_offset = eval_addr_expr(expr, srcline.linenumber)
    else:
        label_offset = 0

    binary_operand = None
    if label == 'r':  # special case for relative addresses
        binary_operand = CurrentRelativeBase
    elif label in SymTab:
        binary_operand = SymTab[label].instruction_address
    if binary_operand is None:
        print("unknown label %s in line %d" % (label, srcline.linenumber))
        binary_operand = 0

    return binary_operand + label_offset


# this routine looks up an operand to resolve a label or convert a number
# Return one for an error, zero for no error.
def resolve_labels_gen_instr(srcline) -> int:
    if srcline.binary_opcode is None:
        # this used to be an error, but cs_ii introduced labels on a line by themselves
        # print("no op code: %s" % srcline.operator)
        return 0

    if True:   #  srcline.operand[0].isalpha():
        operand = srcline.operand
        binary_operand = label_lookup_and_eval(operand, srcline)
        if binary_operand is None:
            # I'm setting it to zero to prevent a trap later, but returning an error now
            srcline.binary_instruction_word = 0
            return 1
        if Debug:
            print("label %s resolved to %04oo" % (operand, binary_operand))
    # else:
    #     binary_operand = ww_int(srcline.operand, srcline.linenumber,
    #                             relative_base = srcline.relative_address_base)
    #     if Debug:
    #         print("numeric %04oo" % binary_operand)

    if binary_operand is None:
        print("no operand found when resolving label %s in line %d" % (srcline.operand, srcline.linenumber))
        return 1
    binary_operand &= srcline.operand_mask
    srcline.binary_instruction_word = binary_operand | srcline.binary_opcode
    if Debug:
        print("  binary_instruction_word %06oo" % srcline.binary_instruction_word)
    CoreMem[srcline.instruction_address] = srcline.binary_instruction_word
    CommentTab[srcline.instruction_address] = srcline.comment
    return 0


# march through the list of debug widgets and convert the args to binary
# Return 0 for no-error, 1 for error so the next layer up can just add up
# the error count
def resolve_dbwgt(dbwgt):
    ret = 0
    for w in dbwgt:
        w.addr_binary = resolve_one_label(w.addr_str, "Debug Widget")
        w.incr_binary = ww_int(w.incr_str, w.linenumber)
        if w.incr_binary is None:
            ret += 1
    return ret


# There's a special case to resolve the label for the JumpTo directive
def resolve_one_label(label, label_type):
    if label is None:
        return None

    ret = label
    if label[0].isalpha():  # resolve the start address, if any.
        if label in SymTab:
            ret = "0o%04o" % SymTab[label].instruction_address
            if Debug:
                print("%s %s resolved to 0o%04o" % (label_type, label, ret))
        else:
            print("missing label for %s address %s" % (label_type, label))
            exit(1)

    return ww_int(ret, 0)


class LexedLine:
    def __init__(self, _linenumber, _label, _operator, _operand, _comment, _directive):
        self.linenumber = _linenumber
        self.label = _label
        self.operator = _operator
        self.operand = _operand
        self.comment = _comment
        self.binary_opcode = None
        self.binary_instruction_word = None
        self.operand_mask = None
        self.instruction_address = None
        self.relative_address_base = None
        self.directive = _directive

    def formatit(self):
        print("%3d, %s : %s %s ; %s" %
              (self.linenumber,
               self.label,
               self.operator,
               self.operand,
               self.comment))

    def _list_to_comment(self, name, llist, reversesymtab):
        if len(llist) == 0:
            return ''
        ret = ''
        for i in llist:
            if reversesymtab[i] is not None:
                ret += reversesymtab[i] + ' '
            else:
                ret += "a%04o " % i
        return "%s %s" % (name, ret)

    # return a label to attach to the line and/or a comment showing xrefs
    def _auto_label(self):
        if self.binary_instruction_word is None:
            return '', ''
        addr = self.instruction_address
        line_label = ''
        if self.label is None:
            if len(CoreReadBy[addr]) != 0:
                line_label = "r%04o: " % addr
            if len(CoreWrittenBy[addr]) != 0:
                line_label = "w%04o: " % addr
            if len(CoreReferredToByJump[addr]) != 0:
                line_label = "i%04o: " % addr
        list1 = self._list_to_comment("JumpedToBy", CoreReferredToByJump[addr], ReverseSymTab)
        list2 = self._list_to_comment("WrittenBy", CoreWrittenBy[addr], ReverseSymTab)
        list3 = self._list_to_comment("ReadBy", CoreReadBy[addr], ReverseSymTab)
        auto_xref = "%s%s%s" % (list1, list2, list3)
        if auto_xref != '':
            auto_xref = "@@" + auto_xref
        return line_label, auto_xref

    # line#  Address Word  Label: operator  operand ; Comment
    def listing(self, cb):
        fc = wwinfra.FlexoClass(None)

        # special-case the lines which are blank or have nothing but comments
        if (len(self.label) == 0) & (len(self.operand) == 0) & (len(self.operator) == 0):
            if len(self.comment) == 0:
                return ''
            return "                        ; %s" % self.comment

        if self.instruction_address is not None:
            decimal = ''
            if cb.decimal_addresses:
                decimal = '.' + cb.int_str(self.instruction_address)
            addr = "@%04o%s:" % (self.instruction_address, decimal)
        else:
            addr = "      "
            if cb.decimal_addresses:
                addr += "     "

        if self.binary_instruction_word is not None:
            wrd = "%06o" % self.binary_instruction_word
        else:
            wrd = "      "

        auto_label, auto_comment = self._auto_label()

        _label = self.label
        if (len(_label) == 0) & (len(auto_label) != 0):
            _label = auto_label

        if len(_label):
            label_separator = ':'
        else:
            label_separator = ' '

        # the following happens only on the pass where the .w, .fl, .fh are found in, and removed from, the source deck
        if self.directive != 0:
            if self.directive == DOT_WORD_OP:
                self.operator = ".word"
                self.operand = wrd
                self.comment = ""
            elif self.directive == DOT_FLEXL_OP:
                self.operator = ".flexl"
                self.operand = wrd
                self.comment = "Flexo Code '%s'" % \
                               fc.code_to_letter(self.binary_instruction_word & 0o77, show_unprintable=True)
            elif self.directive == DOT_FLEXH_OP:
                self.operator = ".flexh"
                self.operand = wrd
                self.comment = "Flexo Code '%s'" % \
                               fc.code_to_letter((self.binary_instruction_word >> 10) & 0o77, show_unprintable=True)
            else:
                print("finish Listing, line 484")
                quit(1)

        return "%s%s  %8s%s %-4s %-8s  ; %s %s" % \
               (addr, wrd, _label, label_separator, self.operator, self.operand, self.comment, auto_comment)


def write_listing(cb, sourceprogram, output_file):
    if output_file is None:
        fout = sys.stdout.fileno()
    else:
        fout = open(output_file, 'wt')
        print("Listing output to file %s" % output_file)
    for srcline in sourceprogram:
        fout.write(srcline.listing(cb) + '\n')
    fout.close()


# Output the Core Image
def write_core(coremem, ww_filename, ww_tapeid, ww_jumpto, output_file, isa_1950):
    global SwitchTab, CommentTab, SymTab, DbWgtTab, ExecTab

    if output_file is None:
        fout = sys.stdout.fileno()
    else:
        fout = open(output_file, 'wt')
        print("Corefile output to file %s" % output_file)
    fout.write("\n; *** Core Image ***\n")
    if isa_1950:  # default in the sim is the 1958 instruction set; this directive changes it to 1950
        fout.write("%%ISA: %s\n" % "1950")
    fout.write("%%File: %s\n" % ww_filename)
    fout.write("%%TapeID: %s\n" % ww_tapeid)
    if ww_jumpto is not None:
        fout.write('%%JumpTo 0o%o\n' % ww_jumpto)
    for s in SwitchTab:  # switch tab is indexed by name, contains a validated string for the value
        fout.write("%%Switch: %s %s\n" % (s, SwitchTab[s]))
    for w in DbWgtTab:
        fout.write("%%DbWgt:  0o%03o  0o%02o\n" % (w.addr_binary, w.incr_binary))
    columns = 8
    addr = 0
    while addr < CORE_SIZE:
        i = 0
        non_null = 0
        row = ""
        while i < columns:
            if coremem[addr+i] is not None:
                row += "%07o " % coremem[addr+i]
                non_null += 1
            else:
                row += " None   "
            i += 1
        if non_null:
            fout.write('@C%04o: %s\n' % (addr, row))
        addr += columns

    for s in SymTab:
        addr = SymTab[s].instruction_address
        fout.write("@S%04o: %s\n" % (addr, s))
    for addr in ExecTab:
        fout.write("@E%04o: %s\n" % (addr, ExecTab[addr]))
    for addr in range(0, len(CommentTab)):
        if CommentTab[addr] is not None and len(CommentTab[addr]) > 0:
            fout.write("@N%04o: %s\n" % (addr, CommentTab[addr]))
    fout.close()


# # Globals
SourceProgram = []  # # a list of class structs, one per source line
SymTab = {}         # # a dictionary of symbols found in the source
CommentTab = [None] * CORE_SIZE     # # an array of comments found in the source, indexed by address
DbWgtTab = []   # an array to hold directoves to add Debug Widgets to the screen
ExecTab = {}    # dictionary of Python Exec statements, indexed by core mem address
CoreMem = [None] * CORE_SIZE  # # an image of the final core memory.
ReverseSymTab = [None] * CORE_SIZE

# arrays to keep track of who's calling whom
CoreReferredToByJump = [[] for _ in range(CORE_SIZE)]
CoreReadBy = [[] for _ in range(CORE_SIZE)]
CoreWrittenBy = [[] for _ in range(CORE_SIZE)]

NextCoreAddress = 0  # # an int that keeps track of where to put the next instruction
# WW Subroutines use "relative" addresses, that is, labels which are relative to the start
# of the routine.  A label "0r" resets the base address, as (I think) does any assignment
# of a physical address, i.e., a ".org xx" in the source
CurrentRelativeBase = 0  # an int that keeps track of the offset from the last relative base

WW_Filename = None
WW_TapeID = None
WW_JumptoAddress = None  # symbolic name for the start address, if any
SwitchTab = {}
ISA_1950 = False  # flag to show which instruction set is in force
cb = wwinfra.ConstWWbitClass()


# #############  Main  #################
def main():
    global WW_Filename
    global WW_TapeID
    global WW_JumptoAddress
    global SwitchTab
    global Debug
    global Legacy_Numbers
    global op_code
    global ISA_1950
    global cb
    global CurrentRelativeBase

    OutputCoreFileExtension = '.acore'  # 'assembler core', not the same as 'tape core'
    OutputListingFileExtension = '.lst'
    # This flag causes the lexer to assume that numeric operands are octal, and convert them
    # to 0onnn format
    Legacy_Numbers = False

    parser = argparse.ArgumentParser(description='Assemble a Whirlwind Program.')
    parser.add_argument("inputfile", help="file name of ww asm source file")
    parser.add_argument("--Debug", '-d', help="Print lotsa debug info", action="store_true")
    parser.add_argument("--Legacy_Numbers", help="guy-legacy - Assume numeric strings are Octal", action="store_true")
    parser.add_argument("-D", "--DecimalAddresses", help="Display traec information in decimal (default is octal)",
                        action="store_true")
    parser.add_argument("--ISA_1950", help="Use the 1950 version of the instruction set",
                        action="store_true")
    parser.add_argument('--outputfilebase', '-o', type=str, help='base name for output file')
    args = parser.parse_args()
    print(parser.prog, ' ', args)

    cb.log = wwinfra.LogClass(sys.argv[0], quiet=False)
    cb.decimal_addresses = args.DecimalAddresses  # if set, trace output is expressed in Decimal to suit 1950's chic

    input_file_name = args.inputfile
    output_file_base_name = re.sub("\.ww$", '', input_file_name)
    if args.outputfilebase is not None:
        output_file_base_name = args.outputfilebase
    print('File %s' % input_file_name)
    Debug = args.Debug
    Legacy_Numbers = args.Legacy_Numbers
    op_code = change_isa(op_code_1958)
    if args.ISA_1950:
        op_code = change_isa(op_code_1950)
    WW_Filename = input_file_name   # WW_filename will be overwritten if there's a directive in the source

    # # on the first pass, read in the program, do lexical analysis to find
    # labels, operators and operands.
    # Convert the source program into a list of 'input line' structures

    print("***Lexical Phase")
    line_number = 0
    error_count = 0
    SwitchTab = {}
    for line in open(input_file_name, 'r'):
        inline = line.rstrip(' \t\n\r')  # strip trailing blanks and newline
        line_number += 1

        srcline = lex_line(inline, line_number)
        SourceProgram.append(srcline)

        if Debug:
            print("Line %d: label '%s', operator '%s', operand '%s', comment '%s', directive %d" %
                  (srcline.linenumber, srcline.label, srcline.operator, srcline.operand,
                   srcline.comment, srcline.directive))

    if Debug:
        print("SourceProgram Length %d lines", (len(SourceProgram)))

    # # Scan the source again to create the symbol table
    for srcline in SourceProgram:
        if Debug:
            srcline.formatit()
        if len(srcline.label):
            if srcline.label in SymTab:
                print("duplicate label %s at Line %d" % (srcline.label, srcline.linenumber))
                error_count += 1

    print("*** Symbol Table:")
    if Debug:
        for s in SymTab:
            print("Symbol %s: line %d" % (s, SymTab[s].linenumber))
    else:
        print("  %d symbols" % len(SymTab))

    # # Scan again to parse instructions and assign addresses
    # # Parse Instructions
    print("*** Parse Instructions")
    for srcline in SourceProgram:
        error_count += parse_ww(srcline)

    if error_count != 0:  # bail out if there were errors in parsing the source
        print("Error Count = %d" % error_count)
        exit(1)

    # # Scan Again to resolve address labels and generate the final binary instruction
    print("*** Resolve Labels and Generate Instructions")
    for srcline in SourceProgram:
        if len(srcline.operator) != 0:
            error_count += resolve_labels_gen_instr(srcline)

    if error_count != 0:  # bail out if there were errors in parsing the source
        print("Error Count = %d" % error_count)
        exit(1)

    print("*** Identify Cross-References")
    for srcline in SourceProgram:
        if len(srcline.operator) != 0:
            label_code(srcline)
            if srcline.label != '':
                ReverseSymTab[srcline.instruction_address] = srcline.label

    jumpto = resolve_one_label(WW_JumptoAddress, "JumpTo")
    error_count += resolve_dbwgt(DbWgtTab)

    if error_count != 0:  # bail out if there were errors in parsing the source
        print("Error Count = %d; output files suppressed" % error_count)
        exit(1)
    else:
        # # Listing & Output
        print("*** Listing ***")
        write_listing(cb, SourceProgram, output_file_base_name + OutputListingFileExtension)

        # # Output Core Image
        print("\n*** Core Image ***")
        write_core(CoreMem, WW_Filename, WW_TapeID, jumpto,
                   output_file_base_name + OutputCoreFileExtension, ISA_1950)


main()
