




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
    def __init__(self, run_length=0, offset=0, probe_len=0):
        self.run_length = run_length
        self.offset = offset
        self.probe_len = probe_len
    def __repr__(self):
        return "run_len=%d, at offset=%d, %3.2f%%" % \
            (self.run_length, self.offset, 100.0 * self.run_length/self.probe_len)


def print_match(probe, archive, probe_match_start, archive_match_start, match_length):
    print("\nMatch: probe start=%d, archive_start=%d, length=%d" % (probe_match_start, archive_match_start, match_length))
    prt = "archive start=%03d: " % archive_match_start
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
            prt += " %03o" % cell
        else:
            prt += " NaN"

    prt += '\n  probe start=%03d: ' % probe_match_start
    end = probe_match_start + match_length + 10
    if end > len(probe):
        end = len(probe)
    for s in range(0, probe_offset_from_archive):
        prt += "    "
    for s in range(0, end):
        p = probe[s]
        if p is not None:
            prt += " %03o" % p
    print(prt)


def scan_archive(sc, scan_start, probe, archive):
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
            if p: p &= 0o174
            if a: a &= 0o174
        if a is not None and p == a:
            if run == 0:
                probe_match_start = probe_offset
                archive_match_start = scan_start + probe_offset
            run += 1
        else:
            if run > sc.run_threshold:
                matches.append(MatchStat(run, scan_start, len(probe)))
                if sc.chatty:
                    print_match(probe, archive, probe_match_start, archive_match_start, run)
            run = 0

    if run > sc.run_threshold:
        matches.append(MatchStat(run, scan_start, len(probe)))

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
        if offset < 0:
            probe_start = -offset
            scan_start = 0
        #if offset + probe_len > archive_len:
        #    probe_end = probe_start + probe_len - archive_len

        m = scan_archive(sc, scan_start, probe[probe_start:probe_end], archive)
        if len(m):
            if sc.chatty:
                print("match at offset=%d, probe_end=%d" % (offset, probe_end))
            matches += m
            c += 1
            if c > 100:
                exit(1)
    return matches


def coremem_to_list(cb, cm, break_at_none_cell=False):
    mem_list = []
    first_addr = None
    last_addr = 0
    for addr in range(0, cb.CORE_SIZE):
        cell = cm.rd(addr, fix_none=False)
        if first_addr is None:  # skip initial 'none' cells, then remember the first non-none address
            if cell is None:
                continue
            else:
                first_addr = addr
        mem_list.append(cell)
        if cell is not None:
            last_addr = addr
    # print("last_addr=%d, memlist=" % last_addr, mem_list[0:(last_addr - first_addr) + 1])
    if first_addr is None:
        return []
    return mem_list[0:(last_addr - first_addr) + 1]


def main():
    parser = argparse.ArgumentParser(description='Analyze a Whirlwind Paper Tape.')
    parser.add_argument("ArchiveFileName", type=str, help="file name of tape image file to search")
    parser.add_argument("--Quiet", '-q', help="Print less debug info on tape blocks", action="store_true")
    parser.add_argument("--WordCompare", '-w', help="Compare the whole word, not just op-codes", action="store_true")
    parser.add_argument('--ProbeFileName', '-p', type=str, help='file name containing search pattern')
    parser.add_argument("--RunThreshold", "-t", help="set threshold bytes for identifying a match (default=10)", type=int)

    args = parser.parse_args()
    # args

    sc = SettingsClass(quiet=args.Quiet, match_complete_word=args.WordCompare)

    if args.RunThreshold is not None:
        sc.run_threshold = args.RunThreshold

    # read probe core
    # read archive core
    #probe = [3, 4, 5, 6, 7]
    #archive = [0, 1, 2, 3, 4, 5, 5, 6, 7, 8, 9, 1, 2, 3, 4, 5, 6]
    #archive  = [3, 4, 5, 6, 7]
    #probe = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    probe = [0o14174, 000, 0o130007, 0o130003, 0o150006, 0o40024, 0o50002]

    sc.archive_filename = args.ArchiveFileName
    sc.probe_filename = args.ProbeFileName
    args.LogDir = None
    cb = wwinfra.ConstWWbitClass (corefile="no_corefile_name", args = args)
    wwinfra.theConstWWbitClass = cb
    cb.log = wwinfra.LogFactory().getLog (quiet=args.Quiet)
    cb.NoZeroOneTSR = True  # don't add the automatic zero and one to locations zero and one
    cb.use_x_win = False

    # read the Archive file
    if sc.chatty: ("Reading Archive file...")
    cm = wwinfra.CorememClass(cb, use_default_tsr=False)
    cpu = wwinfra.CpuClass(cb, cm)
    cb.cpu = cpu
    cpu.cpu_switches = wwinfra.WWSwitchClass(cb)
    (cpu.SymTab, cpu.SymToAddrTab, JumpTo, WWfile, WWtapeID, dbwgt_list) = \
        wwinfra.read_core_file(cm, sc.archive_filename, cpu, cb)
    archive = coremem_to_list(cb, cm)

    if len(archive) == 0:
        if sc.chatty: print("empty file: ", sc.archive_filename)
        exit(1)

    # read the Probe file
    if sc.chatty: print("Reading Probe file...")
    cm = wwinfra.CorememClass(cb, use_default_tsr=False)
    cpu = wwinfra.CpuClass(cb, cm)
    cb.cpu = cpu
    cpu.cpu_switches = wwinfra.WWSwitchClass(cb)
    (cpu.SymTab, cpu.SymToAddrTab, JumpTo, WWfile, WWtapeID, dbwgt_list) = \
        wwinfra.read_core_file(cm, sc.probe_filename, cpu, cb)
    probe = coremem_to_list(cb, cm)

    if not sc.chatty:
        print("%-70s" % sc.archive_filename)

    # correlate images
    matches = index_scan(sc, probe, archive)
    matches = sorted(matches, key=lambda m: m.run_length, reverse=True )

    total_matches = len(matches)
    matches_to_print = 50
    i = 0
    prt = ("\nTotal of %d matches" % (total_matches))
    if total_matches > matches_to_print:
        prt += "; first %d are:" % matches_to_print
    if sc.chatty: print(prt)
    for m in matches:
        print("\nMatch: %s file %s" % (m.__repr__(), sc.archive_filename))
        i += 1
        if i >= matches_to_print:
            break
    # report results


main()