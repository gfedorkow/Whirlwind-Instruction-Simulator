




"""
Whirlwind Code Correlator
Guy Fedorkow, Apr 28, 2025

This script takes a 'known sample' of code in .*core format called a 'probe', and searches
for it in another .core file called the 'archive'.

We're not looking for an absolute match...  I want to find instances that are "close" as well.
The code does a sort of convolution, sliding the probe past the archive, one word at a time.

At each point, it keeps stats for how many runs words in the probe matched words in the archive,
the run length and the offset.  At the end, we can sort by run-length to provide a score.

There's an argument that causes the match to consider only the WW op-code, i.e., the top five
bits of each word.  Most instruction operands are non-relocatable physical addresses, so once
assembled, the same library can have completely different addresses.

Note that there are almost no "illegal' op codes, so there's not much point in trying to
exclude those words.

"""

"""
https://docs.python.org/3/howto/sorting.html
class Student:
    def __init__(self, name, grade, age):
        self.name = name
        self.grade = grade
        self.age = age
    def __repr__(self):
        return repr((self.name, self.grade, self.age))

student_objects = [
    Student('john', 'A', 15),
    Student('jane', 'B', 12),
    Student('dave', 'B', 10),
]
sorted(student_objects, key=lambda student: student.age)   # sort by age
[('dave', 'B', 10), ('jane', 'B', 12), ('john', 'A', 15)]
"""


import argparse
import wwinfra
import sys

cb = wwinfra.ConstWWbitClass()

def breakp():
    print("breakp")

class SettingsClass:
    def __init__(self, run_threshold=10, quiet=True, match_complete_word=False,
                 archive_filename=None, probe_filename=None):
        self.match_complete_word = match_complete_word
        self.chatty = quiet == False
        self.run_threshold = run_threshold
        self.archive_filename = archive_filename
        self.probe_filename = probe_filename


class MatchStat:
    def __init__(self, run_length, archive_match_start, probe_offset, offset, probe_len):
        self.run_length = run_length
        self.archive_match_start = archive_match_start
        self.probe_offset = probe_offset
        self.offset = offset
        self.probe_len = probe_len
    def __repr__(self):
        return "run_len=%d, at archive offset=%d (0o%o), probe_offset=%d (0o%o), %3.2f%%" % \
            (self.run_length, self.archive_match_start, self.archive_match_start, self.probe_offset,
             self.probe_offset, 100.0 * self.run_length/self.probe_len)


def DecodeOp(w, pc, short=False):
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
    # if the word is marked as a data word, or if it's an unused op code, don't decode it as an instruction
    if (wordtype == '.word') | (cb.op_code[op][2] == cb.OPERAND_UNUSED):
        return "0o%05o:   .word 0o%06o" % (pc, w)
    operand = "0o%o" % addr  # in these instructions, it's not an address, it's a param, e.g., number of bits ot shift

    long_op = "%3s  %5s" % (cb.op_code[op][0], operand)
    comment = "%s" % cb.op_code[op][1]

#    if op_name in ["SL", "SR", "CL"]:   # there are three extended 6-bit op-codes; all use "params", not addresses
#        if w & cb.WWBIT5:  # If this bit is on, it can't be a legal shift instruction; must be a data word
#            return ".word 0o%06o" % w
#        ext_op_bit = (w >> 9) & 0o1  # the extra op bit is the "512s" bit, not the MSB of address
#        long_op = "%3s  0o%05o" % \
#                  (ext_op_code[op_name][0][ext_op_bit], addr & 0o777)
#        comment = ext_op_code[op_name][1][ext_op_bit]
#    elif op_name == "cf":
#        long_op = "%3s  %5s" % (cb.op_code[op][0], operand)
#        comment = "cf" + cf_decode(addr)
    if op_name == "si":
        comment = "select I/O: " + cb.Decode_IO(addr)

    if short:
        return op_name
    long = "0o%05o:   %s   ; %s" % (pc, long_op, comment)
    return long




def print_match(sc, probe, archive, probe_match_start, archive_match_start, match_length):
    print("\nArchive: %s; Probe: %s\n Match: probe start=%d (0o%o), archive_start=%d (0o%o), length=%d" %
          (sc.archive_filename, sc.probe_filename, probe_match_start, probe_match_start, archive_match_start,
           archive_match_start, match_length))
    prt = "archive code, starting at 0o%03o:\n" % archive_match_start
    start = archive_match_start # - 10
    probe_offset_from_archive = probe_match_start - archive_match_start
    #if start < 0:
    #    start = 0
    end = archive_match_start + match_length + 10
    if end > len(archive):
        end = len(archive)
    for offset in range(start, end):
        cell = archive[offset]
        if cell is not None:
#            prt += " 0o%03o" % cell
            prt += DecodeOp(cell, offset) + '\n'
        else:
            prt += " NaN"

#    prt += '\n  probe start=%03d: ' % probe_match_start
#    end = probe_match_start + match_length + 10
#    if end > len(probe):
#        end = len(probe)
#    for s in range(0, probe_offset_from_archive):
#        prt += "    "
#    for s in range(0, end):
#        p = probe[s]
#        if p is not None:
#            prt += " %03o" % p
    print(prt)


def scan_archive(sc, scan_start, probe, archive, probe_addr_correction):
    probe_offset = 0
    probe_match_start = 0
    archive_match_start = 0
    matches = []
    run = 0
    for probe_offset in range(0, len(probe)):
        if probe_offset + scan_start >= len(archive):
            break
        p = probe[probe_offset]
        a = archive[scan_start + probe_offset]
        if not sc.match_complete_word:
            if p: p &= 0o174000  # keep the WW Op Code; toss the address field
            if a: a &= 0o174000
        # Here's the critical line matching a word from the two files
        if a is not None and p is not None and p == a:  # don't match None, but if the values match, it's part of a run
            if run == 0:
                probe_match_start = probe_offset
                archive_match_start = scan_start + probe_offset
            if a != 0:   # only count non-zero words in the run; i.e., don't report blocks of zeros
                run += 1
        else:
            if run > sc.run_threshold:
                matches.append(MatchStat(run, archive_match_start, probe_match_start + probe_addr_correction, scan_start, len(probe)))
                if True: # sc.chatty:
                    print_match(sc, probe, archive, probe_match_start + probe_addr_correction, archive_match_start, run)
            run = 0

    # pick up a last run of matches, in case we matched right through to the end
    if run > sc.run_threshold:
        matches.append(MatchStat(run, archive_match_start, probe_offset, scan_start, len(probe)))
        if True: # sc.chatty:
            print_match(sc, probe, archive, probe_match_start + probe_addr_correction, archive_match_start, run)

    return matches


def index_scan(sc, probe, archive):
    c = 0
    matches = []
    probe_len = len(probe)
    archive_len = len(archive)

    for offset in range(-probe_len, archive_len):
        probe_start = 0
        probe_end = probe_len
        scan_start = offset
        probe_addr_correction = 0
        if offset < 0:
            probe_start = -offset
            probe_addr_correction = -offset
            scan_start = 0
        #if offset + probe_len > archive_len:
        #    probe_end = probe_start + probe_len - archive_len

        m = scan_archive(sc, scan_start, probe[probe_start:probe_end], archive, probe_addr_correction)
        if len(m):
            if sc.chatty:
                print("match at offset=%d, probe_end=%d" % (offset, probe_end))
            matches += m
            c += 1
            if c > 100:
                print("more than 100 matches")
    return matches


# def coremem_to_list(cb, cm, break_at_none_cell=False):
#     mem_list = []
#     first_addr = None
#     last_addr = 0
#     for addr in range(0, cb.CORE_SIZE):
#         cell = cm.rd(addr, fix_none=False)
#         if first_addr is None:  # skip initial 'none' cells, then remember the first non-none address
#             if cell is None:
#                 continue
#             else:
#                 first_addr = addr
#         mem_list.append(cell)
#         if cell is not None:
#             last_addr = addr
#     # print("last_addr=%d, memlist=" % last_addr, mem_list[0:(last_addr - first_addr) + 1])
#     if first_addr is None:
#         return []
#     return mem_list[0:(last_addr - first_addr) + 1]


def coremem_to_list(cb, cm, break_at_none_cell=False):
    mem_list = []
    last_addr = 0
    for addr in range(0, cb.CORE_SIZE):
        cell = cm.rd(addr, fix_none=False)
        mem_list.append(cell)
        if cell is not None:
            last_addr = addr
    # print("last_addr=%d, memlist=" % last_addr, mem_list[0:(last_addr - first_addr) + 1])
    return mem_list[0:last_addr]


def analyze_a_file(cb, sc, args, probe, filename):
    # read the Archive file
    if sc.chatty: print("Reading Archive file...")
    sc.archive_filename = filename
    cm = wwinfra.CorememClass(cb, use_default_tsr=False)
    cpu = wwinfra.CpuClass(cb, cm)
    cb.cpu = cpu
    cpu.cpu_switches = wwinfra.WWSwitchClass(cb)
    (cpu.SymTab, cpu.SymToAddrTab, JumpTo, WWfile, WWtapeID, dbwgt_list) = \
        wwinfra.read_core_file(cm, sc.archive_filename, cpu, cb)
    archive = coremem_to_list(cb, cm)

    if len(archive) == 0:
        if sc.chatty:
            print("empty file: ", sc.archive_filename)
        return

    # correlate images
    matches = index_scan(sc, probe, archive)
    matches = sorted(matches, key=lambda m: m.run_length, reverse=True )

    total_matches = len(matches)
    matches_to_print = 50
    i = 0
    prt = ("\nTotal of %d matches, sorted longest to shortest:" % (total_matches))
    if total_matches > matches_to_print:
        prt += "; first %d are:" % matches_to_print
    if sc.chatty: print(prt)
    for m in matches:
        print("Match: %s file %s" % (m.__repr__(), sc.archive_filename))
        i += 1
        if i >= matches_to_print:
            break
    # report results


def main():
    parser = argparse.ArgumentParser(description='Analyze a Whirlwind Paper Tape.')
    parser.add_argument("ArchiveFileNameList", help="file name(s) of tape image file to search", nargs="*")
    parser.add_argument("--FileList", '-f', help="File containing a list of filenames", type=str)
    parser.add_argument("--Quiet", '-q', help="Print less debug info on tape blocks", action="store_true")
    parser.add_argument("--WordCompare", '-w', help="Compare the whole word, not just op-codes", action="store_true")
    parser.add_argument('--ProbeFileName', '-p', type=str, help='file name containing search pattern')
    parser.add_argument("--RunThreshold", "-t", help="set threshold bytes for identifying a match (default=10)", type=int)

    args = parser.parse_args()
    # args

    sc = SettingsClass(quiet=args.Quiet, match_complete_word=args.WordCompare)

    if args.RunThreshold is not None:
        sc.run_threshold = args.RunThreshold

    args.LogDir = None
    cb = wwinfra.ConstWWbitClass (corefile="no_corefile_name", args = args)
    wwinfra.theConstWWbitClass = cb
    cb.log = wwinfra.LogFactory().getLog (quiet=args.Quiet)
    cb.NoZeroOneTSR = True  # don't add the automatic zero and one to locations zero and one
    cb.use_x_win = False

    # read the Probe file
    sc.probe_filename = args.ProbeFileName
    if sc.chatty: print("Reading Probe file...")
    cm = wwinfra.CorememClass(cb, use_default_tsr=False)
    cpu = wwinfra.CpuClass(cb, cm)
    cb.cpu = cpu
    cpu.cpu_switches = wwinfra.WWSwitchClass(cb)
    (cpu.SymTab, cpu.SymToAddrTab, JumpTo, WWfile, WWtapeID, dbwgt_list) = \
        wwinfra.read_core_file(cm, sc.probe_filename, cpu, cb)
    probe = coremem_to_list(cb, cm)

    if args.FileList:
        file_list = []
        try:
            with open(args.FileList, 'r') as file:
                for line in file:
                    file_list.append(line.strip())  # Removes leading/trailing whitespace, including '\n'
        except FileNotFoundError:
            print(f"Error: The file '{args.FileList}' was not found.")
    else:
        file_list = args.ArchiveFileNameList

    i = 1
    list_len = len(file_list)
    for filename in file_list:

        sys.stderr.write("%d of %d\r" % (i, list_len))
        i += 1
        analyze_a_file(cb, sc, args, probe, filename)



main()