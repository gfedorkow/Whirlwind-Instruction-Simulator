#!/usr/bin/python3

# guy fedorkow, Dec 9, 2019
# convert an ASCII string into equivalent Flexowriter character codes
# Output in "core" format

import sys
import argparse
import re
import wwinfra
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


def main():
    parser = argparse.ArgumentParser(description='Convert an ASCII string to Flexowriter codes.')
    parser.add_argument("ascii_string", help="string to be converted to flexowriter code")
    args = parser.parse_args()

    cb = wwinfra.ConstWWbitClass()
    flexo = wwinfra.FlexoClass(cb)
#    core = wwinfra.CorememClass(cb)

    upper_dict = make_ascii_dict(flexo, upper_case=True)
    lower_dict = make_ascii_dict(flexo, upper_case=False)
    upper_case = False

    flexo_codes:int = []
    for c in args.ascii_string:
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

    print("; ascii string '%s' converted to flexo code" % args.ascii_string)
    output_str ='@T000: '
    for f in flexo_codes:
        output_str += "%06o  " % f

    print(output_str)


if __name__ == "__main__":
    main()
