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

# Dec 7, 2023 - fixed a bug that was ignoring labels on lines with no operator or operand

import os
import sys
# sys.path.append('K:\\guy\\History-of-Computing\\Whirlwind\\Py\\Common')
import re
import argparse
import wwinfra

breakpoint_trigger = False
def breakp(log):
    global breakpoint_trigger

    if breakpoint_trigger:
        print("hit breakpoint %s" % log)
        return True
    if log == "Trigger":
        breakpoint_trigger = True
    return False

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
    def __init__(self, linenumber, addr_str, incr_str, format_str):
        self.linenumber = linenumber
        self.addr_str = addr_str
        self.incr_str = incr_str
        self.addr_binary = None
        self.incr_binary = None
        self.format_str = format_str


def strip_space(s1):
    s2 = re.sub("^[ \t]*", '', s1)
    s3 = re.sub("[ \t]*$", '', s2)
    return s3

def split_comment(in_str):
  paren_depth = 0
  in_quotes = False
  in_comment = False
  out_operands = ''
  out_comment = ''
  i = 0

  for c in in_str:
    i += 1
    if c == '(':
      paren_depth += 1
    if c == ')':
      paren_depth -= 1
    if c == '"':
      in_quotes = ~in_quotes

    if re.match("@@",in_str[i:] ) and (in_quotes == False) and (paren_depth == 0):
      break

    if (c == ';')  and (in_quotes == False) and (paren_depth == 0) and not in_comment:
      in_comment = True
      continue

    if in_comment:
      out_comment += c
    else:
      out_operands += c

  return (strip_space(out_operands), strip_space(out_comment))



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

    """
    # old comment-stripper; delete this commented code
    # strip auto-comment
    r1 = re.sub(" *@@.*", '', line)
    if LexDebug:
        print(line_number, "remaining r1 after strip-autocomment:", r1)

    # split op and save any regular comment
    rl2 = re.split(";", r1, 1)
    r2 = r1   # provisionally, output = input if no comment
    if LexDebug:
        print(line_number, "RL2 list:", rl2)
    if len(rl2) > 1:
        comment = strip_space(rl2[1])
        r2 = strip_space(rl2[0])
    """

    (r2, comment) = split_comment(line)

    # Special Case for .exec directive
    # I'm adding directives to the assembler to:
    #    - pass a string to the simulator that should be interpreted and executed as a python statement
    #    - execute a specialized formatted print statement to dump the state of named variables
    #           (i.e., for "printf debugging"
    # e.g.    .exec print("time=%d" % cm.rd(0o05))
    # The statement can't have a label, and must not start in column zero.  But other than that, we'll bypass
    # the rest of the parser checks, as the python statement could have "anything"
    # The .exec directive will follow a 'real' WW instruction; the assumption is that it is executed after
    # the preceding instruction, before the next 'real' instruction.
    exec_match = "^[ \t][ \t]*(.exec|.print)"
    if m := re.search(exec_match, r2):
        exec_stmt = re.sub(exec_match, '', r2)
        exec_stmt = exec_stmt.lstrip().rstrip()
        op = m.group(0).lstrip().rstrip()   # was '.exec'
        operand = exec_stmt
        # as above, .lower() removed
        return LexedLine(line_number, label, op, operand, comment, directive)

    # strip the initial "@address:data" tag
    #    pattern = "(^@[0-7][0-9\.]*:[0-7][0-7]*) *([a-zA-Z][a-z[A-Z[0-7]*) *"
    addr_data_tag = "(^@[0-7][0-9.]*:[0-7][0-7]*) *"
    r3 = re.sub(addr_data_tag, '', r2)
    if LexDebug:
        print(line_number, "RS2=", r3)

    # if there's nothing but a comment on the line, strip the semicolon and return it now
    if len(r3) == 0:
        return LexedLine(line_number, label, op, operand, comment, directive)

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
            r4 = re.sub("\\.w *", '', r4)
        if r4.find(".fl ") == 0:
            directive = DOT_FLEXL_OP
            r4 = re.sub("\\.fl *", '', r4)
        if r4.find(".fh ") == 0:
            directive = DOT_FLEXH_OP
            r4 = re.sub("\\.fh *", '', r4)

    # split the operator and operand
    rl5 = re.split(" ", r4, maxsplit=1)
    op = r4
    if LexDebug:
        print(line_number, "RL5:", rl5)
    if len(rl5) > 1:
        operand = strip_space(rl5[1])
        op = strip_space(rl5[0])
        op = op.lower()
        if Legacy_Numbers:   # guy's "legacy numbers" were purely and totally octal; the asm is now more flexible.
            if operand.isnumeric():
                operand = "0o" + operand

    if len(op) > 0 and op not in op_code:
        cb.log.error(line_number, "Unknown op code: %s" % op)
        op = ''
    return LexedLine(line_number, label, op, operand, comment, directive)


def ww_int(nstr, line_number, relative_base=None):
    global Legacy_Numbers
    if Legacy_Numbers:
        return ww_int_adhoc(nstr)
    return ww_int_csii(nstr, line_number, relative_base)


# This was guy's first try at WW Number Conversion, replaced in Oct 2020 with ww_int_csii
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
        if ww_small_int < 8 and ww_small_int > -8:
            return ww_small_int
        #  otherwise, fall through to all the other tests below
    except ValueError:
        pass

    # there's a case I can't figure out how to categorize: "0.0" or "0.00" could be either decimal
    # or Octal, but it seems to come closer to matching the Octal pattern.  Obviously the answer is
    # zero in either case.
    # In general, I think this routine is more conservative about number types than the real assembler,
    # but I don't know what rules they actually used.
    if re.match('0\\.|1\\.', nstr):  # try Whirlwind fixed-point octal conversion, e.g. n.nnnnn
        octal_str = nstr.replace('.', '')
        if re.search('^[01][0-7][0-7][0-7][0-7][0-7]$', octal_str) is None and \
            re.search('^0.00*$', nstr) is None:
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

    if re.match('\\+|-|[1-9]|0$', nstr):  # Try Decimal conversion
        sign = 1   # default to a positive number
        sign_str = '+'
        if nstr[0] == '-':
            sign = -1
            sign_str = '-'
        dec_str = re.sub(r'-|\+', '', nstr)
        if re.search(r'^[0-9.][0-9.]*$', dec_str) is None:
            cb.log.error(line_number, "Expecting +/- decimal number; got %s" % (nstr))
            return None
        if nstr.find(".") == -1:  # if the number has no decimal point, it's an integer
            ones_comp = int(dec_str, 10)
            if ones_comp >= 0o77777:
                cb.log.error(line_number, "Oversized decimal number: %s%d" % (sign_str, ones_comp))
                return None
        else:    # it must be a decimal float
            ones_comp = int(float(dec_str) * 0o100000)
            if ones_comp >= 0o77777:
                cb.log.error(line_number, "Oversized decimal float: %s%s" % (sign_str, dec_str))
                return None
        if sign == -1:
            ones_comp = ones_comp ^ 0o177777  # this should handle -0 automatically
        return ones_comp
        # add More Code for fractional decimal numbers with exponents
    cb.log.error(line_number, "not sure what to do with this number: '%s'" % (nstr))
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
    next_add = ww_int_csii(srcline.operand, srcline.linenumber, relative_base=CurrentRelativeBase)
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

    cb.log.warn(srcline.linenumber, "Drum Address psuedo-op %s %s" %
                (srcline.operator, srcline.operand))
    return 0

# # process a .BASE statement, resetting the relative addr count to zero
# I added this pseudo-op during the first run at cs_ii conversion
# But on the next go round, I changed it to parse the "0r" label directly.
def dot_relative_base_op(srcline, _binary_opcode, _operand_mask):
    global NextCoreAddress, CurrentRelativeBase

    CurrentRelativeBase = 0
    cb.log.warn(srcline.linenumber, "Deprecated .BASE @%04oo" % NextCoreAddress)
    return 0


# Preset Parameters are like #define statements; they don't generate code, but
# they do put values in the symbol table for later use.
# They can be "called" in the source code as a way to insert a word of whatever value was
# assigned to the pp.
#  Samples look like this:       .PP pp15=pp14+1408  ;  @line:19a
#  The program parameter label (e.g. pp15), apparently is always two letters plus one or two digits,
#  but not necessarily always 'pp'
# I am not so sure how to handle these guys!
# See M-2539-2 Comprehensive System manual, pdf page 75 for the CS-II rules.  This assembler
# doesn't enforce any of the rules; a Preset Param is just another label in the symbol table.
# Preset Parameters are only represented as labels in the symbol table for the simulator, i.e.,
# the .pp pseudo-op is not passed through.
def dot_preset_param_op(srcline, _binary_opcode, _operand_mask):
    #
    lhs = re.sub("=.*", '', srcline.operand)
    rhs = re.sub(".*=", '', srcline.operand)

    SymTab[lhs] = srcline

    srcline.instruction_address = label_lookup_and_eval(rhs, srcline)
    return 0


# This routine is called when "pp" turns up as an op code.
# In which case we're supposed to include the value of the parameter as a word
def insert_program_param_op(srcline, _binary_opcode, _operand_mask):
    cb.log.warn(srcline.linenumber, "Insert Program Parameter %s %s as a word" %
                (srcline.operator, srcline.operand))
    return 0


# the Source Code may have a DITTO operation
# don't know exactly what it does yet, except to duplicate words in memory
def ditto_op(srcline, _binary_opcode, _operand_mask):
    cb.log.warn(srcline.linenumber, "DITTO operation %s %s" %
                (srcline.operator, srcline.operand))
    return 0


def csii_op(src_line, _binary_opcode, _operand_mask):
    cb.log.warn(src_line.linenumber, "CS-II operation %s %s; inserting .word 0" %
                (src_line.operator, src_line.operand))
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

    sw_class = wwinfra.WWSwitchClass(cb)
    ret = 0
    # put a try/except around this conversion
    tokens = re.split("[ \t]", srcline.operand)
    name = tokens[0]
    if name == "FFRegAssign":  # special case syntax for assigning FF Register addresses
        tokens.append('')  # cheap trick; add a null on the end to make sure the next statement doesn't trap
        ff_reg_map, val = sw_class.parse_ff_reg_assignment(cb, name, tokens[1:])
        if ff_reg_map is None:
            cb.log.warn(srcline.linenumber, "can't parse %s: %s" % (name, tokens[1]))
            ret = 1
    else:
        if len(tokens) != 2:
            cb.log.warn(srcline.linenumber, "usage:  .SWITCH <switchname> <value>")
            return 1
        int_val = ww_int(tokens[1], srcline.linenumber)  # this will trap if it can't convert the number
        if int_val is not None:
            val = "0o%o" % int_val   # convert the number into canonical octal
        else:
            cb.log.warn(srcline.linenumber, ".SWITCH %s setting %s must be an octal number" % (name, tokens[1]))
            ret = 1
            val = ' '
    SwitchTab[name] = val       # we're going to save the validated string, not numeric value
    cb.log.info(".SWITCH %s set to %s" % (name, val))
    return ret


# # process a .WORD statement, to initialize the next word of storage
# coming into the routine, the number to which storage should be set is
# already in the operand field of the srcline class.
# This same routine handles .flexh and .flexl for inserting words that
# correspond to Flexowriter characters.
def dot_word_op(src_line, _binary_opcode, _operand_mask):
    global NextCoreAddress, CurrentRelativeBase, cb

    ret = 0
    # op-code contains the type of .word directive

    # a flex[hl] directive can have a single quoted letter as an argument; otherwise treat the operand as a
    # regular number or label
    if re.match("\\.flexh|\\.flexl", src_line.operator) and re.match("\"|\\'.\"|\\'", src_line.operand):
            # The argument should be a valid flexo character
            fc = wwinfra.FlexoClass(cb)
            flexo_char = fc.ascii_to_flexo(src_line.operand[1])
            if flexo_char is None:
                cb.log.fatal("Line %d: can't convert ASCII character to Flexo" % src_line.linenumber)
            if re.match("\\.flexh", src_line.operator):
                flexo_char <<= 10  # if it's "high", shift the six-bit code to WW bits 0..5
            # convert the result back into a string and replace the incoming Operand with the new one
            src_line.operand = "0o%o" % flexo_char

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
    # defaults
    incr = "1"
    format_str = "%o"
    i = 1
    while i < len(tokens):
        tok = strip_space(tokens[i])
        if tok[0].isnumeric():
            incr = tok
        elif len(tok) > 2 and tok[0] == '"' and tok[-1] == '"' and '%' in tok:
            format_str = tok[1:-1]
        else:
            print("Line %d: unknown param for .dbwgt op: %s" % (src_line.linenumber, tok))
        i += 1

    # the operand could be a number or a label; resolve that later
    DbWgtTab.append(DebugWidgetClass(src_line.linenumber, addr, incr, format_str))
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

    # transform a .exec or .print command slightly to make it more readable in the .acore file
    exec_cmd = re.sub("^\\.", "", src_line.operator) + ':'
    exec_arg = src_line.operand
    exec = exec_cmd + ' ' + exec_arg
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


# Look up a label; generate an error if it's already in the symtab, otherwise
# add the object corresponding to the line with the label to the symbol table.
# Return zero for "it's all ok" and one for "not so good", so I can just add
# the return code to the overall error count.
def add_sym(label, srcline):
    global SymTab, cb

    if label in SymTab:
        cb.log.error(srcline.linenumber, "Ignoring duplicate label %s" % (srcline.label))
        return 1

    SymTab[label] = srcline
    return 0


# # Parse a line after it's been Lexed.  This routine simply looks up the
# # opcode string to find the binary opcode, and also to find if it's
# # a five- or six-bit opcode, or a pseudo-op
# I'm ignoring upper/lower case in op codes
# Return the number of errors
def parse_ww(srcline):
    global NextCoreAddress, CurrentRelativeBase
    # the special case at the start handles lines where there's a label but no operation
    # This happens because a line can have more than one label(!)
    # e.g.
    #   d25:
    #   0r: ca f11
    # "real" operations increment the next address; this just records it.
    # if the line has a label but no op, we need to update the Relative Address base

    if len(srcline.operator) == 0:
        # a label can appear on a line by itself, without an operator
        err = 0
        srcline.instruction_address = NextCoreAddress
        if len(srcline.label):
            err = add_sym(srcline.label, srcline)  #  poor form -- converting True/False to 1/0
            CurrentRelativeBase = NextCoreAddress
            if Debug: print("Line %d: Label %s: Implicit Set of Relative Base to 0o%o" %
                  (srcline.linenumber, srcline.label, CurrentRelativeBase))
        return err

    ret = 0
    addr_inc = 0
    # continue from here with normal instruction processing
    # Op Codes and Directives are case-independent
    op = srcline.operator
    if op in op_code:
        op_list = op_code[op]
        addr_inc = op_list[0](srcline, op_list[1], op_list[2])  # dispatch to the appropriate operator
    else:
        cb.log.error(srcline.linenumber, "Unrecognized operator: %s" % (srcline.operator))
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
                cb.log.warn(srcline.linenumber, "Label %s: Changing Relative Base from 0o%o to 0o%o" %
                        (srcline.label, CurrentRelativeBase, new_relative_base))
                CurrentRelativeBase = new_relative_base
    else:
        # the book says that any 'comma operator', i.e. a label, resets the Relative Address
        if len(srcline.label):
            if add_sym(srcline.label, srcline):
                ret += 1
            if srcline.instruction_address is not None:
                CurrentRelativeBase = srcline.instruction_address
                if Debug: print("Line %d: Label %s: Setting Relative Base to 0o%o" %
                        (srcline.linenumber, srcline.label, CurrentRelativeBase))

    if len(srcline.operand) == 0:
        cb.log.error(srcline.linenumber, "Missing operand: %s" % (srcline.operator))
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
    ".org": [dot_org_op, 0, 0, OPERAND_NONE],
    ".daorg": [dot_daorg_op, 0, 0, OPERAND_NONE],  # Disk Address Origen
    ".base": [dot_relative_base_op, 0, 0, OPERAND_NONE],
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
    ".print": [dot_python_exec_op, 0, 0, OPERAND_NONE],
    ".pp":   [dot_preset_param_op, 0, 0, OPERAND_NONE],
    "pp": [insert_program_param_op, 0, 0, OPERAND_NONE],
    "ditto": [ditto_op, 0, 0, OPERAND_NONE],
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
            print("eval_addr_expr probably stuck in loop, line %d: expr=%s" % (line_number, expr))
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
                if number is None:
                    # we've already printed a number-conversion error message, but stop processing here
                    print("Line %d: can't evaluate number %s in expression; returning zero offset",
                          line_number, number_str)
                    return 0
            else:
                number = 0
            if op == '-':
                number = -number
            offset += number

    return offset


# Labels can have simple arithmetic expressions (I think only "label +/- Label +/- Label")
# Dec 17, 2023; I added an OR operator "|" to combine numbers.
# Note a fundamental problem in number-syntax -- +/- specifically identifies Decimal numbers,
# so in this parser, I'm _requiring_ arithmetic operators to be separated by spaces, and +/-
# symbols that indicate Decimal numbers to be joined to their number.
# e.g. it's legal to say "1 + 2 - -0.7"
# but it's not legal to say 1+2
# This routine could run into "programmed parameters", kinda like ifdefs, and will evaluate these as well

# Dec 22, 2023 - new version of label parser, which can parse a variety of expressions as long as they
# evaluate down into constants

def label_lookup_and_eval(label_with_expr: str, srcline):
    # if there's an expression, split it into tokens
    tokens = label_with_expr.split()

    # CS-II has this weird label format with an offset prepended to a label value, e.g. "19r6"
    # Separate the offset and the label and turn the offset into an explicit Add, i.e., "r6+19"
    #   The syntax 19r6 means r6+19.  But I can only assume pp1-19r6 means pp1-(r6 + 19) = pp1 - r6 - 19
    #   That is, I assume there's no syntax for a negative offset
    # The 19r6-style labels are interpreted in ww_int();
    #  That's probably a bug; they should be considered part of the expression parser.

    # For this parser, I'm assuming that there must be an odd number of tokens, with every second one
    # being an arithmetic operator!
    if (len(tokens) % 2) != 1:
        cb.log.error(srcline.linenumber,
                     "Expression %s must contain labels separated by operators, i.e., an odd number of tokens"
                     % label_with_expr)

    valid_expr_ops = ['+', '-', '|', '*', '/']
    for i in range(0, len(tokens)):
        if (i % 2) == 1 and tokens[i] not in valid_expr_ops:
            cb.log.error(srcline.linenumber, "Invalid Expression Operator: %s" % tokens[i])
        if (i % 2) == 0 and not re.match("[0-9a-zA-Z+-]", tokens[i]):
            cb.log.error(srcline.linenumber, "%s doesn't look like a number or label" % tokens[i])

    # now we can evaluate all the terms in the expression
    # This is a bit confusing, because '+' does double-duty to indicate addition
    # but also that the following digits are a decimal number
    vals = [None] * len(tokens)

    # first loop evaluates the numbers and labels
    for i in range(0, len(tokens), 2):
        token = tokens[i]
        val = None
        if re.match("[a-zA-Z]", token):
            if token == 'r':  # special case for relative addresses
                val = CurrentRelativeBase
            elif token in SymTab:
                val = SymTab[token].instruction_address
            if val is None:
                cb.log.error(srcline.linenumber, "Unknown label %s in expression %s; using zero" %
                             (token, srcline.operand))
                val = 0
        elif re.match("[0-9+-]", token):
            # I need to pass the Sign into wwint to catch Decimal numbers...  ugh...
            val = ww_int(token, srcline.linenumber,
                                relative_base = srcline.relative_address_base)
            if val is None:
                cb.log.error(srcline.linenumber, "Can't convert number %s in expression; returning zero" %
                      token)
                val = 0
        else:
            cb.log.error(srcline.linenumber, "Unknown symbol %s in label_lookup_and_eval with %s" %
                         (token, label_with_expr))
        if val is None:
            return 0
        vals[i] = val

    # finally, do the arithmetic
    result = vals[0]
    for i in range(1, len(tokens), 2):
        eval_op = tokens[i]
        if len(tokens) < (i + 1):   # this test should never fail...
            cb.log.error(srcline.linenumber, "Missing operand after eval_operator '%s'" % eval_op)
        if eval_op == '+':
            result += vals[i + 1]
        elif eval_op == '-':
            result -= vals[i + 1]
        elif eval_op == '|':
            result |= vals[i + 1]
        elif eval_op == '*':
            result *= vals[i + 1]
        elif eval_op == '/':
            result //= vals[i + 1]
        else:
            cb.log.error(srcline.linenumber, "Unexpected eval_operator '%s'" % eval_op)

    # print("line %d: label_lookup_and_eval(%s) resolves to %d (0o%o)" %
    #      (srcline.linenumber, label_with_expr, result, result))
    # print(tokens)
    return result


# this routine looks up an operand to resolve a label or convert a number
# Return one for an error, zero for no error.
def resolve_labels_gen_instr(srcline) -> int:
    global Annotate_IO_Arg

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

    if (srcline.operator == "si") and Annotate_IO_Arg:
        srcline.comment += "; Auto-Annotate I/O: %s" % cb.Decode_IO(binary_operand)

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


# There's a special case to resolve the label for the psuedo-op directives
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
        self.operator = _operator.lower()
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
        if w.addr_binary:
            addr = "0o%03o" % w.addr_binary
        else:
            addr = w.addr_str
        fout.write("%%DbWgt:  %s  0o%02o %s\n" % (addr, w.incr_binary, w.format_str))

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


# I think the CSII assembler defaults to starting to load instructions at 0o40, the
# first word of writable core.  Of course a .org can change that before loading the
# first word of the program.
NextCoreAddress = 0o40  # # an int that keeps track of where to put the next instruction
# WW Subroutines use "relative" addresses, that is, labels which are relative to the start
# of the routine.  A label "0r" resets the base address, as (I think) does any assignment
# of a physical address, i.e., a ".org xx" in the source
CurrentRelativeBase = 0o40  # an int that keeps track of the offset from the last relative base

WW_Filename = None
WW_TapeID = None
WW_JumptoAddress = None  # symbolic name for the start address, if any
SwitchTab = {}
ISA_1950 = False  # flag to show which instruction set is in force


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
    global Annotate_IO_Arg



    OutputCoreFileExtension = '.acore'  # 'assembler core', not the same as 'tape core'
    OutputListingFileExtension = '.lst'
    # This flag causes the lexer to assume that numeric operands are octal, and convert them
    # to 0onnn format
    Legacy_Numbers = False

    parser = wwinfra.StdArgs().getParser ("Assemble a Whirlwind Program.")
    parser.add_argument("inputfile", help="file name of ww asm source file")
    parser.add_argument("--Verbose", '-v',  help="print progress messages", action="store_true")
    parser.add_argument("--Debug", '-d', help="Print lotsa debug info", action="store_true")
    parser.add_argument("--Annotate_IO_Names", help="Auto-add comments to identify SI device names", action="store_true")
    parser.add_argument("--Legacy_Numbers", help="guy-legacy - Assume numeric strings are Octal", action="store_true")
    parser.add_argument("-D", "--DecimalAddresses", help="Display traec information in decimal (default is octal)",
                        action="store_true")
    parser.add_argument("--ISA_1950", help="Use the 1950 version of the instruction set",
                        action="store_true")
    parser.add_argument('--outputfilebase', '-o', type=str, help='base name for output file')
    args = parser.parse_args()

    cb = wwinfra.ConstWWbitClass (args = args)
    wwinfra.theConstWWbitClass = cb
    cb.decimal_addresses = args.DecimalAddresses  # if set, trace output is expressed in Decimal to suit 1950's chic

    input_file_name = args.inputfile
    output_file_base_name = re.sub("\\.ww$", '', input_file_name)
    if args.outputfilebase is not None:
        output_file_base_name = args.outputfilebase

    cb.CoreFileName = os.path.basename (output_file_base_name)
    cb.log = wwinfra.LogFactory().getLog (isAsmLog = True)
        
    Debug = args.Debug
    verbose = args.Verbose
    if verbose:
        print('File %s' % input_file_name)
    Legacy_Numbers = args.Legacy_Numbers
    op_code = change_isa(op_code_1958)
    if args.ISA_1950:
        op_code = change_isa(op_code_1950)
    WW_Filename = input_file_name   # WW_filename will be overwritten if there's a directive in the source
    Annotate_IO_Arg = args.Annotate_IO_Names

    # # on the first pass, read in the program, do lexical analysis to find
    # labels, operators and operands.
    # Convert the source program into a list of 'input line' structures

    if verbose:
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

    if Debug:
        print("*** Symbol Table:")
        for s in SymTab:
            print("Symbol %s: line %d" % (s, SymTab[s].linenumber))
    elif verbose:
        print("  %d symbols" % len(SymTab))

    # # Scan again to parse instructions and assign addresses
    # # Parse Instructions
    if verbose:
        print("*** Parse Instructions")
    for srcline in SourceProgram:
        error_count += parse_ww(srcline)

#    if error_count != 0:  # bail out if there were errors in parsing the source
#        print("Error Count = %d" % error_count)
#        exit(1)

    # # Scan Again to resolve address labels and generate the final binary instruction
    if verbose:
        print("*** Resolve Labels and Generate Instructions")
    for srcline in SourceProgram:
        if len(srcline.operator) != 0:
            error_count += resolve_labels_gen_instr(srcline)

#    if error_count != 0:  # bail out if there were errors in parsing the source
#        print("Error Count = %d" % error_count)
#        exit(1)

    if verbose:
        print("*** Identify Cross-References")
    for srcline in SourceProgram:
        if len(srcline.operator) != 0:
            label_code(srcline)
            if srcline.label != '':
                ReverseSymTab[srcline.instruction_address] = srcline.label

    jumpto = resolve_one_label(WW_JumptoAddress, "JumpTo")
    error_count += resolve_dbwgt(DbWgtTab)

    # ok, so Nov 2023 it dawned on me that it would be cleaner to print error messages
    # and count errors in the Log class, not ad-hoc one at a time.
    # So I 'should' eliminate the local error_count var by using the Log class routine
    # In the meantime, I have both :-(
    error_count += cb.log.error_count


    if error_count != 0:  # bail out if there were errors in parsing the source
        print("Error Count = %d; output files suppressed" % error_count)
        exit(1)
    else:
        # # Listing & Output
        if verbose:
            print("*** Listing ***")
        write_listing(cb, SourceProgram, output_file_base_name + OutputListingFileExtension)

        # # Output Core Image
        if verbose:
            print("\n*** Core Image ***")
        write_core(CoreMem, WW_Filename, WW_TapeID, jumpto,
                   output_file_base_name + OutputCoreFileExtension, ISA_1950)


main()
