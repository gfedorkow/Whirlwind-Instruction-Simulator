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


def make_ascii_dict(flexo, upper_case:bool=False):
    ascii_dict = {}
    for flex in range(1,64):
        if upper_case:
            ascii = flexo.flexocode_ucase[flex]
        else:
            ascii = flexo.flexocode_lcase[flex]
        ascii_dict[ascii] = flex
    return ascii_dict

def convert_ascii(cb, input_string):
    flexo = wwinfra.FlexoClass(cb)

    upper_dict = make_ascii_dict(flexo, upper_case=True)
    lower_dict = make_ascii_dict(flexo, upper_case=False)
    upper_case = False

    flexo_codes = []
    for c in input_string:
        if c in lower_dict and c in upper_dict:
            flexo_codes.append(lower_dict[c])
        elif c in lower_dict:
            if upper_case == True:
                flexo_codes.append(flexo.FLEXO_LOWER)
                upper_case = False
            flexo_codes.append(lower_dict[c])
        elif c in upper_dict:
            if upper_case == False:
                flexo_codes.append(flexo.FLEXO_UPPER)
                upper_case = True
            flexo_codes.append(upper_dict[c])
    return flexo_codes

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
    # global theConstWWbitClass

    # parser = argparse.ArgumentParser(description='Convert an ASCII string to Flexowriter codes.')
    parser = wwinfra.StdArgs().getParser ("Convert an ASCII string to Flexowriter codes.")
    parser.add_argument("ascii_string", nargs='?', help="string to be converted to flexowriter code")
    parser.add_argument("-i", "--InputFile", type=str, help="ASCII File to be converted")
    parser.add_argument("-o", "--OutputFile", type=str, help="File name for Flexo Output")
    parser.add_argument("-b", "--BinaryOut", help="Output Flexo in Binary Format (default is .tcore)", action="store_true")
    parser.add_argument("-q", "--Quiet", help="Suppress run-time message", action="store_true")
    args = parser.parse_args()

    cb = wwinfra.ConstWWbitClass(corefile='help-me', args = args)
    wwinfra.theConstWWbitClass = cb
    cb.log = wwinfra.LogFactory().getLog(logname='help-me', quiet=args.Quiet)
#    core = wwinfra.CorememClass(cb)

    input_string = args.ascii_string

    if args.InputFile:
        fd = None
        try:
            fd = open(args.InputFile, "r")
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

    flexo_codes = convert_ascii(cb, input_string)

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

        if out_fd:
            out_fd.write(output_str)
        else:
            print("%s" % output_str)

if __name__ == "__main__":
    main()
