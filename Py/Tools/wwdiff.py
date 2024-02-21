# #!/usr/bin/python3

# Compare two Whirlwind "core" files to show the bit differences in each memory location
# g fedorkow, May 3, 2020

import sys
import argparse
import wwinfra

#class CpuClass:    # Stub
#     def __init__(self, cb):
#        self.cb = cb
#        self.cpu_switches = None


# sigh, I'll put this stub here, so I can call Read Core without more special cases.
class CpuClass:
    def __init__(self, cb):
        self.cb = cb
        # putting this stuff here seems pretty darn hacky
        self.cpu_switches = None
        self.SymTab = {}
        self.CommentTab = [None] * 2048
        self.cm = None
        self.ExecTab = {}


# Functionality extended in Jan 2024 to include not just seeing the diffs, but creating a
# merge of them, overwriting the first core with diffs from the second.
# This is used to merge base and patch tapes into a single runnable image.
# Core A is used as the base; Core B is merged into the base.
def merge_core(core_a, core_b, cb):
    line_a = ''
    merges = 0
    overwrites = 0
    col_diffs = 0
    column = 0
    for address in range(0, cb.CORE_SIZE):
        if column == 0:
            line_a = '@C%05o: ' % address

        wrd_a = core_a.rd(address, fix_none=False)
        wrd_b = core_b.rd(address, fix_none=False)
        if (wrd_a is None) and (wrd_b is not None):
            core_a.wr(address, wrd_b)
            line_a += "m %-9s" % (wwinfra.octal_or_none(wrd_b) + ' ')
            merges += 1
            col_diffs += 1
        elif (wrd_a is not None) and (wrd_b is not None) and (wrd_a != wrd_b):
            core_a.wr(address, wrd_b)
            line_a += "o %-9s" % (wwinfra.octal_or_none(wrd_b) + ' ')
            overwrites += 1
            col_diffs += 1

        else:
            line_a += '     --    '
        column += 1
        if column == 8 or address == (cb.CORE_SIZE - 1):
            if col_diffs != 0:
                print("%s" % line_a)
            col_diffs = 0
            column = 0

    metadata_diffs = 0
    # most of the metadata is just string-compare...
    for s in ("ww_tapeid", "filename_from_core"):
        core_a.metadata[s] += " + " + core_b.metadata[s]
        print(" meta %s: %s" % (s, core_a.metadata[s]))

    core_a.metadata["strings"] += core_b.metadata["strings"]
    # ...but jump-to is an integer
    if core_a.metadata["jumpto"] != core_b.metadata["jumpto"]:
        print("< meta %s: %s" % (s, core_a.metadata["jumpto"]))
        print("> meta %s: %s" % (s, core_b.metadata["jumpto"]))
        metadata_diffs += 1
        # metadata_goto = jumpto_addr

    cb.log.info("Core Merges = %d(d), Core Overwrites = %d(d), Metadata Diffs = %d(d)" %
                (merges, overwrites, metadata_diffs))


def diff_core(core_a, core_b, cb):
    line_a = ''
    line_b = ''
    diffs = 0
    col_diffs = 0
    column = 0
    for address in range(0, cb.CORE_SIZE):
        if column == 0:
            line_a = '@C%05o: ' % address
            line_b = '@C%05o: ' % address

        wrd_a = core_a.rd(address, fix_none=False)
        wrd_b = core_b.rd(address, fix_none=False)
        if wrd_a != wrd_b:
            line_a += "%-9s" % (wwinfra.octal_or_none(wrd_a) + ' ')
            line_b += "%-9s" % (wwinfra.octal_or_none(wrd_b) + ' ')
            col_diffs += 1
        else:
            line_a += '   --    '
            line_b += '   --    '
        column += 1
        if column == 8 or address == (cb.CORE_SIZE - 1):
            if col_diffs != 0:
                print("< %s" % line_a)
                print("> %s" % line_b)
                print('')
            diffs += col_diffs
            col_diffs = 0
            column = 0

    metadata_diffs = 0
    # most of the metadata is just string-compare...
    for s in ("ww_tapeid", "hash", "strings", "stats", "filename_from_core"):
        if core_a.metadata[s] != core_b.metadata[s]:
            print("< meta %s: %s" % (s, core_a.metadata[s]))
            print("> meta %s: %s" % (s, core_b.metadata[s]))
            metadata_diffs += 1

    # ...but jump-to is an integer
    if core_a.metadata["jumpto"] != core_b.metadata["jumpto"]:
        print("< meta %s: %s" % (s, core_a.metadata["jumpto"]))
        print("> meta %s: %s" % (s, core_b.metadata["jumpto"]))
        metadata_diffs += 1
        # metadata_goto = jumpto_addr


    #  print("diff at addr 0o%o: a=%s, b=%s" % (address, wwinfra.octal_or_none(wrd_a), wwinfra.octal_or_none(wrd_b)))
#            diffs += 1
    cb.log.info("Core Diffs = %d(d), Metadata Diffs = %d(d)" % (diffs, metadata_diffs))

# Pythonic entry point
def main():
    parser = argparse.ArgumentParser(description='Compare a Whirlwind tape image.')
    parser.add_argument("inputfiles", nargs='*', help=".core file(s)")
    # parser.add_argument("diff_file_b", help="second .core file")
    parser.add_argument("-o", "--outputfile", help="Merged file output", type=str)
    parser.add_argument("-q", "--Quiet", help="Suppress run-time message", action="store_true")
    parser.add_argument("-m", "--Merge", help="Merge files into File A", action="store_true")
    parser.add_argument("-5", "--Debug556", help="WW 556 block debug info", action="store_true")

    args = parser.parse_args()

    cb = wwinfra.ConstWWbitClass()
    cpu = CpuClass(cb)
    cb.cpu = cpu
    cpu.cpu_switches = wwinfra.WWSwitchClass(cb)
    log = wwinfra.LogClass(sys.argv[0], quiet=args.Quiet, debug556=args.Debug556)
    cb.log = log

    if args.Merge and args.outputfile is None:
        cb.log.fatal("%s requires an output file (-o) for Merge mode" % sys.argv[0])

    if len(args.inputfiles) < 2:
        cb.log.fatal("%s needs more than one file arg" % sys.argv[0])
    if len(args.inputfiles) > 2 and (not args.Merge):
        cb.log.fatal("%s can only diff two files" % sys.argv[0])

    coremem_a = wwinfra.CorememClass(cb)
    coremem_b = wwinfra.CorememClass(cb)

    # ugh, this network of semi-global data structures is getting out of hand...
    # I hadn't anticipated more than one CoreMem when writing the code...
    cb.cpu.cm = coremem_a
    coremem_a.read_core(args.inputfiles[0], cpu, cb)

    passnum = 1  # count from One (not zero)
    while passnum < len(args.inputfiles):
        cb.log.info("input file pair: %s = <,   %s = >" % (args.inputfiles[0], args.inputfiles[passnum]))
        cb.cpu.cm = coremem_b
        coremem_b.read_core(args.inputfiles[passnum], cpu, cb)

        if args.Merge:
            merge_core(coremem_a, coremem_b, cb)  # "ww_tapeid", "hash", "strings", "stats", "filename_from_core"
            wwinfra.write_core(cb, [coremem_a._coremem[0] + coremem_a._coremem[1]], 0, False,
                               coremem_a.metadata["filename_from_core"], coremem_a.metadata["ww_tapeid"],
                               coremem_a.metadata["jumpto"], args.outputfile, coremem_a.metadata["strings"])
        else:
            diff_core(coremem_a, coremem_b, cb)
        passnum += 1


if __name__ == "__main__":
    main()

