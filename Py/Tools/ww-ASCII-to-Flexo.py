#!/usr/bin/python3

# guy fedorkow, Dec 9, 2019
# convert an ASCII string into equivalent Flexowriter character codes
# Output in "core" format

import sys
import argparse
import re
import wwinfra
import struct
from typing import List, Dict, Tuple, Sequence, Union, Any
from wwflex import FlasciiToFlex, FlexToComment, FlexToFlexoWin

def format_tcodes(input_string, flexo_codes):
    output_str = "; ascii string converted to flexo code:\n; "
    for offset in range(0, len(input_string)):
        s = input_string[offset]
        output_str += s
        if  s == '\n' and offset < len(input_string):
            output_str += "; "
    output_str += "\n"

    addr = 0
    output_str += '@T000: '
    for f in flexo_codes:
        output_str += "%06o  " % f
        addr += 1
        if addr % 8 == 0:
            output_str += '\n@T%03o: ' % addr
    return output_str

def main():
    parser = wwinfra.StdArgs().getParser ("Convert an ASCII string to Flexowriter codes.")
    parser.add_argument("ascii_string", nargs='?', help="string to be converted to flexowriter code")
    parser.add_argument("-i", "--InputFile", type=str, help="ASCII File to be converted")
    parser.add_argument("-o", "--OutputFile", type=str, help="File name for Flexo Output")
    parser.add_argument("-b", "--BinaryOut", help="Output Flexo in Binary Format (default is .tcore)", action="store_true")
    parser.add_argument("-q", "--Quiet", help="Suppress run-time message", action="store_true")
    parser.add_argument("-r", "--Readable", help="Add a section to support human readbility of the translation", action="store_true")
    parser.add_argument("-w", "--FlexoWin", help="Create and print to a FlexoWin in addition to creating an output file", action="store_true")
    parser.add_argument("--OmitAutoStop", help="Omit the addition of the flex <stop> code to the end of the output file", action="store_true")
    args = parser.parse_args()

    cb = wwinfra.ConstWWbitClass(args = args)
    wwinfra.theConstWWbitClass = cb
    cb.log = wwinfra.LogFactory().getLog(quiet=args.Quiet)

    input_string = args.ascii_string

    if args.InputFile:
        fd = None
        try:
            fd = open(args.InputFile, "r") if args.InputFile != "-" else sys.stdin
        except IOError:
            cb.log.fatal("Can't open input file %s" % args.InputFile)

        input_string = fd.read()
        fd.close()
    if input_string is None:
        cb.log.fatal("No input to convert!  Try '-i <input_file>' or cmd line")

    out_fd = None
    if args.OutputFile:
        if args.BinaryOut:
            mode = "wb"
        else:
            mode = "w"
        try:
            out_fd = open(args.OutputFile, mode)
        except IOError:
            cb.log.fatal("Can't write to file %s" % args.OutputFile)

    # LAS Auto-add the <stop> char by default here; suppressed by --OmitAutoStop
    flexo_codes = FlasciiToFlex (input_string, addStopCode = not args.OmitAutoStop).getFlex()

    if args.BinaryOut:
        sys.stdout = sys.stdout.buffer
        for f in flexo_codes:
            b = struct.pack('B', f)
            if out_fd:
                out_fd.write(b)
            else:
                sys.stdout.write(b)
    else:
        output_str = format_tcodes(input_string, flexo_codes)
        if args.Readable:
            # LAS
            output_str += "\n;\n;\n" + (FlexToComment (flexo_codes).getComment())

        if out_fd:
            out_fd.write(output_str)
        else:
            print("%s" % output_str)

    # This is largely for testing, i.e., to see if a given Flascii file prints properly
    if args.FlexoWin:
        w = FlexToFlexoWin()
        for code in flexo_codes:
            w.addCode (code)
        input ("<return> to quit: ")

if __name__ == "__main__":
    main()
