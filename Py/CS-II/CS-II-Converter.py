

# Sample input file.  Note that tabs are treated essentially as newlines

#  %File 102782316_fc126-269-330_11-25.7ch
#  fc TAPE 126-269-330 MOUSE DISPLAY ROUTINES WALSH
#  DECIMAL
#  |ENTRY FOR THE LOOK DISPLAY
#  [1;31m0.02043|[0mtap14	spg2<del>
#  |ENTRY FOR THE A<del>IM DISPLAY
#  tap14	spg1
#  |ENTRY FOR THE MOVE DISPLAY
#  tap14	spd1
#  |ENTRY FOR THE TABLE OF VALUES DISPLAY
#  tap14	sph1
#  |ENTRY TO CHANGE MOVE DISPLAY FROM DISPA<del>CHER
#  cf+0.00354	spe1	cac12	cf<del><del><del><del><del><del><del><del>+0.0|ENTRY TO TAKE A PICTURE OF THE PREVIOUS DISPLAY
#  cf+0.00354	si4	cac8	ts1e11	spe13	cac9	ts1e11	si4	sp1e11
#  |L<del>IGHT GUN INPUT ENTRY
#  tap14	spd47
#  |MOVE DISPLAY ROUTINE
#  |TEST FOR ZERO MOVES, (-)=YES <del><del><del><del><del><del><del><del><del><del><del><del><del><del><del><del><del><del><del><del><del><del><del><del>= DO INITIAL SETTINGS
#  [1;31m<del><del><del><del><del><del><del><del>d1,[0mcaz1	dm0	cpe2
#  |TEST PRESENT X POSITION TO SEE IF THE MOUSE HAS BACKED UP FURTHER THAN THE INITIAL POINT OF THE DISPLAY, (+)=NO, (-)=YES
#  [1;31md4,[0mcaz6	sup5	ad1	tss3	cpd5
#  |TEST END OF COMPLETE DISPLAY, (+)=YES, (-)=NO
#  caz9	sup9	sup5	<del><del><del><del><del><del><del><del><del><del><del>su1	cpd8
#  |TEST PRESENT X POSITION TO SEE IF IT HAS PAST THE THREE QUARTER MARK OF THE PRESENT DISPLAY, (+)=NO, (-)=<del>YES
#  cas3	sup8	cpd8
#  |SET THE COUNTER FOR THE NUMBER OF ALLOWED BACKUPS
#  cs1	tsp11


# See chapter XIV of the M-2539-2_Comprehensive_System_Manual_Dec55 for a definition of the
# CS-ii manual


import sys
# sys.path.append('K:\\guy\\History-of-Computing\\Whirlwind\\Py\\Common')
import argparse
import re
import wwinfra
from typing import List, Dict, Tuple, Sequence, Union, Any

cb = wwinfra.ConstWWbitClass(get_screen_size = False)

def breakp():
    print("breakpoint")

# sample input
# line 255f: d29,tad30
# line 255g: adc19
# line 255h: ts3d29
# line 255i: cac20+
# line 255j: spd25
# line 255k: d30,sp0
# line 256a: |SCOPE OUTPUT DISPLAY ROUTINE

class parser_state_class:
    def __init__(self):
        self.number_base = 10  # default to base 10; so says M-2539 Part 2, pg XIV-11
        self.start_at = None
        self.tape_name = None
        self.file_name = None
        self.tape_mode_settings = None
        self.wwasm_output = ''


class csii_statement_class:
    def __init__(self, statement, src_line):
        self.src_line = src_line
        self.statement = statement
        self.label = ''
        self.label2 = ''  # apparently it's possible to attach two labels to one instruction
        self.comment = ''
        self.opcode = ''
        self.operand = ''
        self.psuedo_op = None
        # it is possible to have both of these address assignments on a single instruction
        self.address_assignment = ''  # this makes a .ORG to set the current location in core
        self.drum_address_assignment = ''  # this makes a (weird kind of) .ORG to set the location on the drum


    # in the case of a Program Parameter, I'm going to make an assember directive ".PP", followed by what
    # ever param statement the programmer included.
    # The Assembler can then take apart the left hand and right hand sides of the assignment
    def catch_program_param(self, operation, line_number):
        #  print("Line %s: program param %s" % (line_number, operation))
        self.opcode = ".PP"
        self.operand = operation


    # Section VII of the CS-II manual M-2539-2, contains many more rules for parsing statements
    # e.g., labels can have two commas, relative base addresses can be fixed to specific locations with a '|' symbol
    def parse_line(self, cs_ii_pgm, line_number, csii_statement):

        # catch a special case.  "| foo bar" is a comment, but "^120|" is a statement assigning
        # the current location the value of 120.  Note that the value could be octal, i.e. "0.02402|"
        # I haven't found a description of the actual rule.
        # There actually could be two address assignments, one for where to put the thing on the drum
        # (starting with 'DA'), and one to say where to put it in Core

        if line_number == "13d":
            breakp()

        operation = ''
        # find comments, record them and dispose of them for the rest of the process
        if csii_statement[0] == '|':
            self.comment = re.sub(".*\|", '|', csii_statement)
            instruction = ''
        else:
            instruction = csii_statement

        p = "([.0-9DAa-z+-]+)\|"   # catch the address assignment statements
        while m := re.match(p, instruction):
            addr = m.group(1)
            if re.match("DA", addr):
                self.drum_address_assignment = addr[2:]  # drop the 'DA'
            else:
                self.address_assignment = addr
            ns = re.sub(p, '', instruction, count = 1)
            instruction = ns
            print("Line %s: add in a .ORG '%s' for %s" % (line_number, addr, csii_statement))

        #check for directives, e.g. OCTAL, DECIMAL, START AT
        if (p_op := self.check_for_pseudo_op(cs_ii_pgm, instruction)) is not None:
             self.psuedo_op = p_op
        else:
            #labels are at the start of the line, followed by a comma
            # it looks like its possible to attach two labels to the same instruction, e.g. 'r6,y30,ca0'
            if ',' in instruction:
                split_instruction = instruction.split(',')
                if len(split_instruction) == 2:
                    (self.label, operation) = split_instruction
                elif len(split_instruction) == 3:
                    (self.label, self.label2, operation) = split_instruction
                else:
                    cb.log.warn("Line %s: can't parse %s", line_number, instruction)
            else:
                operation = instruction

            if len(operation):
                # "Program parameters" are sort of like #defines, labels defined with fixed values
                # I think a Program Parameter name must start with 'p' and have a two-letter identifier
                # followed by the usual number.
                # This seems to imply that an op code may never start with a 'p'...
                # e.g.   pp15=pp14+1408
                if re.match("p[a-z][0-9][0-9]*=", operation):
                    self.catch_program_param(operation, line_number)
                elif len(operation) >= 2 and operation[0].isalpha() and operation[1].isalpha() and operation[0] != 'p':
                    # the two-letter or three-letter op-code is jammed against the operand with no spaces
                    oplen = 2  # default is a two-letter opcode, e.g., sp, ta, mh
                    # Except for srr, srh, slr, slh, clr, clh, plus all the Interpreted instructions
                    if operation[0:2] == "sl" or operation[0:2] == "sr" or \
                        operation[0:2] == "cl" or operation[0] == 'i':
                        oplen = 3
                    # two more special cases
                    if operation == "DITTO" or operation == "OUT":
                        oplen = len(operation)
                    if len(operation) < oplen:
                        cb.log.info("op code is too short: %s" % operation)
                    else:
                        self.opcode = operation[0:oplen]
                    self.operand = operation[oplen:]
                    if len(self.operand) == 0:
                        self.operand = "0"
                        self.comment = "default operand; " + self.comment
                else:
                    self.operand = operation
                    self.opcode = ".word"

#        print("label:%s opcode:%s operand:%s pseudo-op:%s comment:%s" %
#              (self.label, self.opcode, self.operand, self.psuedo_op, self.comment))
        if len(self.operand):
            self.operand = self.operand_fixer(cs_ii_pgm, self.operand, line_number)


    def format_wwasm(self, cs_ii_pgm, line_identifier):
        stmt = ''

        # include the original source line as a comment, as long as the source line itself isn't just a comment
        # I'm also suppressing the original source line if it's a ".PP" statement, as the converter
        # simply passes the whole statement through to the assembler.
        if len(self.src_line) and not (self.opcode == '' and self.label == '') and not (self.opcode == '.PP'):
            stmt += "\n       ;CS-II Src: %s\n" % self.src_line
        # if the source line as an address assignment (i.e. "23|", emit a .org
        # Note that it could be decimal or octal, depending on the last pseudo-op
        addr_assign = self.address_assignment
        if len(addr_assign):
            if cs_ii_pgm.number_base == 8:  # if we're in an OCTAL segment, take a side trip to convert to octal format
                try:
                    addr_assign = "0.%05o" % int(addr_assign, 8)
                except ValueError:
                    cb.log.fatal("non-octal number in an octal expression: %s" % self.address_assignment)
            stmt += "       .ORG %s\n" % addr_assign

        drum_addr_assign = self.drum_address_assignment
        if len(drum_addr_assign):
            if cs_ii_pgm.number_base == 8:  # if we're in an OCTAL segment, take a side trip to convert to octal format
                try:
                    drum_addr_assign = "0.%05o" % int(drum_addr_assign, 8)
                except ValueError:
                    cb.log.fatal("non-octal number in an octal expression: %s" % self.drum_address_assignment)
            stmt += "       .DAORG %s\n" % drum_addr_assign

        # I don't think an address assignment can happen on the same line as a directive, but if so
        # this should generate a wwasm error
        if self.psuedo_op:  # and len()
            stmt += "       %s ; %s @line:%s\n" % (self.psuedo_op, self.statement, line_identifier)
        else:
            lbl = self.label
            if len(self.label):
                lbl += ':'
            stmt += "%-6s %s %-15s ; %s @line:%s\n" % \
                   (lbl, self.opcode, self.operand, self.comment, line_identifier)
        cs_ii_pgm.wwasm_output += stmt


    def check_for_pseudo_op(self, cs_ii_pgm, stmt):
        ret = None
        if re.match("DECIMAL", stmt):
            cs_ii_pgm.number_base = 10
            ret = ''
        if re.match("OCTAL", stmt):
            cs_ii_pgm.number_base = 8
            ret = ''
        if re.match("START AT", stmt):
            cs_ii_pgm.start_at = re.sub("START AT *", '', stmt)
            ret = ".jumpto %s" % cs_ii_pgm.start_at
        return ret


    # check M-2539-2 VIII-8 for a run-down of floating, temporary and relative addressing for labels.
    # This routine standardizes the use of labels in a more-modern format.
    #   I'm also classifying numbers... if the number can be read unambiguously by wwasm, don't
    # mess with it.  But where the rules are vague, convert to a modern standard format.
    # In particular, wwasm will always see 0oNNN as octal.  Note that 0oNNN could be interpreted
    # as a label (like "0r") except that the book says "Variables are one letter except for oh and ell"
    def operand_fixer(self, cs_ii_pgm, operand_arg, line_number):
        global cb

        if line_number == "44e":
            breakp()

        print_it = False
        got_it = 0
        operand = operand_arg  # we return the operand unchanged unless it needs conversion

        # catch labels with offsets in front.  The format would be a couple decimal digits, the label letter[s]
        # and then a couple of decimal numbers to complete the label
        # I'm converting this into a standard label followed by an added offset
        # e.g. 120E11 -> E11+120
        #   ... to be resolved in the wwasm
        # That's because J Backus said Numbers start with a Number, Labels start with a Letter.
        #    It's The Right Thing to Do
        if re.match("[.0-9]+[a-z]+[0-9]*$", operand):
            nl = self.offset_label_fixer(operand)
            self.comment += ";old label: %s, new label: %s" % (operand, nl)
            operand = nl


        # categorize the remaining types of operands
        if re.match("[0-1]*\.[0-7]*$", operand):
            if print_it: print("octal fraction: %s" % operand)
            got_it += 1
        # uh-oh.  The Book says that a number of the form "+0.nnnnn" is a Decimal Fraction
        # BUT; in the exemplar, mouse.fc, +0.nnnnn is clearly octal (for use with the CF instruction
        # I think the rule might be:
        #   +.nnn or -.nnn is a decimal fraction
        #   +0.nnnnn or 0.nnnnn or 1.nnnnn would all be octal numbers
        if re.match("[\+\-][01]*\.[0-9]+$", operand):
            if print_it: print("decimal fraction: %s" % operand)
            got_it += 1
        if re.match("\+0\.[0-7][0-7][0-7][0-7][0-7]$", operand):
            new_op = operand
            if operand[0] == '+':
                new_op = operand[1:]
            operand = new_op
            print("Warning: might be octal fraction starting with +: %s" % operand)
            got_it += 1

        # As far as I can tell, number base conversion only applies to integers, i.e., no decimal point
        # This clause checks decimal and octal integers, depending on the last DECIMAL or OCTAL directive.
        if re.match("[-+0-9]*$", operand) and (cs_ii_pgm.number_base is None):
            cb.log.warn("missing number base:%s" % operand)
        if re.match("[-+0-9]*$", operand) and (cs_ii_pgm.number_base == 10):
            if print_it: print("decimal integer: %s" % operand)
            got_it += 1
        if re.match("[-+0-7]*$", operand) and (cs_ii_pgm.number_base == 8):
            # convert to Python-style octal integer
            sign = ''
            new_op = operand
            if operand[0] == '+':
                new_op = operand[1:]
            if operand[0] == '-':
                cb.log.warn("operand %s is a negative octal integer??" % operand)
                sign = '-'
                new_op = operand[1:]
            operand = "%s0o%s" % (sign, new_op)

            print("octal integer: %s" % operand)
            got_it += 1

        if operand[0].isalpha():
            if print_it: print("absolute label: %s" % operand)
            got_it += 1
        if operand[0].isnumeric() and operand[-1] == 'r':
            if print_it: print("relative label: %s" % operand)
            got_it += 1
        if re.match("\-?[0-9]+[a-z][0-9]+$", operand):  #the Minus on the front is optional
            if print_it: print("offset label: %s" % operand)
            got_it += 1
        if got_it != 1:
            print("Line %s: unknown operand: %s" % (line_number, operand))
        return(operand)


    def offset_label_fixer(self, operand):
        global cb
        ret = operand  # by default, do nothing
        m = re.match("([.0-9]+)([a-z]+.*)", operand)
        if m:
            offset = m.group(1)
            label = m.group(2)
            ret = label + ' + ' + offset
        else:
            cb.log.warn("match failed for operand=%s in offset_label_fixer", operand)
        return ret

# My Flexo converter carries both Delete (rubout) and color change codes through to the ascii
# output, converting the red/black shift to ASCII \e codes.  Both are ignored in Whirlwind language
# processors.
# This short routine removes delete characters and ascii color codes.
def strip_color_and_del(line):
    ln1 = re.sub('<del>', '', line)
    ln2 = re.sub('\x1b\[1;31m', '', ln1)
    ln3 = re.sub('\x1b\[0m', '', ln2)
    return ln3


def read_fc(cb, filename:str, cs_ii_pgm):
    line_number = 0

    cb.log.info("FileName: %s" % filename)
    try:
        fd = open(filename, "r")   # open as a file of characters
    except IOError:
        fd = None  # this prevents an uninitialized var warning in fd.read below
        cb.log.fatal("Can't open FC file %s" % filename)

    for line in fd:
        line_number += 1
        if len(line) == 0:
            break
        if line[0] == '%':
            cs_ii_pgm.file_name = line
            continue
        if re.match("[Ff][Cc] TAPE .*", line):
            cs_ii_pgm.tape_name = line
            continue
        if re.match("\([0-9][0-9]*,[0-9][0,9]*\)", line):
            cs_ii_pgm.tape_mode_settings = line
            continue
        ln = strip_color_and_del(line.rstrip())
        subline = ln.split('\t')
        sub_number = 'a'
        for statement in subline:
            # cs_ii_pgm.wwasm_output += "; line %d%s: %s\n" % (line_number, sub_number, sl)
            # parser state for this particular statement
            line_identifier = "%d%s" % (line_number, sub_number)
            # I want to see the complete input line in the output stream as a comment, but only once!
            src_line = ''
            if sub_number == 'a':
                src_line = ln
            cs_ii = csii_statement_class(statement, src_line)
            if len(statement) > 0:
                cs_ii.parse_line(cs_ii_pgm, line_identifier, statement)
            cs_ii.format_wwasm(cs_ii_pgm, line_identifier)
            sub_number = chr(ord(sub_number) + 1)  #increment the ascii letter code

    print(cs_ii_pgm.wwasm_output)


# Pythonic entry point
def main():
    global cb
    parser = argparse.ArgumentParser(description='Convert a Whirlwind FC tape to wwasm format.')
    parser.add_argument("fc_file", help="file name of tape image in .fc format")
    parser.add_argument("-o", "--OutputFile", type=str, help="Base name for output core file(s)")
    parser.add_argument("-q", "--Quiet", help="Suppress run-time message", action="store_true")

    args = parser.parse_args()

    log = wwinfra.LogClass(sys.argv[0], quiet=args.Quiet)
    cb.log = log

    if args.OutputFile:
        output_filename = args.OutputFile
    else:
        of = re.sub("\\.fc$|\\.csii$", '', args.fc_file)
        output_filename = of + '.ww'

    # "global" state for the program we're converting
    cs_ii_pgm = parser_state_class()

    read_fc(cb, args.fc_file, cs_ii_pgm)

    try:
        fd = open(output_filename, "w")   # open as a file of characters
    except IOError:
        fd = None  # this prevents an uninitialized var warning in fd.read below
        cb.log.fatal("Can't open .ww output file %s" % output_filename)
    fd.write(cs_ii_pgm.wwasm_output)
    fd.close()


if __name__ == "__main__":
    main()
