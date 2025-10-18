#!/usr/bin/python3.6
# Whirlwind Trace Log analysis
# read an execution trace log and some other meta data, use it
# to generate a flow graph for the code.
# Guy Fedorkow, Dec 2019

# see https://en.wikipedia.org/wiki/Cyclomatic_complexity

# from __future__ import print_function

# ToDo, Jan 18, 2021
# add labels and comments to nodes discovered by static analysis
# count the number of core locations loaded at the start of the program

import re
import argparse
import sys
import os
import statistics as stat
from wwinfra import CorememClass
from wwcpu import CpuClass

CORESIZE: int = 2048
NBANKS: int = 6

Debug = False

def breakp():
    return

# defines for how much stuff to put in each block in the flow graph.
FLOW_BLOCK_TERSE = 1         # just the identifiers
FLOW_BLOCK_START_FINISH = 0  # include first and last instruction for each block
FLOW_BLOCK_ALL_CODE = 2      # include all the instructions and comments in each block


# not used
# from https://stackoverflow.com/questions/45926230/how-to-calculate-1st-and-3rd-quartiles
def quartile(data):
    data.sort()
    half_list = int(len(data)//2)
    upper_quartile = stat.median(data[-half_list])
    lower_quartile = stat.median(data[:half_list])
    print("Lower Quartile: "+str(lower_quartile))
    print("Upper Quartile: "+str(upper_quartile))
    print("Interquartile Range: "+str(upper_quartile-lower_quartile))


class TraceLogClass:
    def __init__(self, pc: int, label: str, opcode: str, operand: int, acc: int, comment: str,
                 log_beginning=False, log_end=False):
        self.pc = pc
        self.label = label     # this would be whatever label the assembler put in the .acore file
        self.opcode = opcode
        self.operand = operand
        self.acc = acc
        self.comment = comment
        self.log_beginning = log_beginning  # tack a marker on the front and the tail of the log
        self.log_end = log_end

        self.itsabranch = (opcode == 'SP') or (opcode == 'CP') or (opcode == 'CK')

class CoreMemoryMetaData:
    def __init__(self, cb):
        self.NBANKS = NBANKS
        self.cb = cb
        self._cmm = []
        for _i in range(self.NBANKS):
            self._cmm.append([None] * (self.cb.CORE_SIZE // 2))
        self.MemGroupA = 0  # I think Reset sets logical Group A to point to Physical Bank 0
        self.MemGroupB = 1  # I *think* Reset sets logical Group B to point to Physical Bank 1

    def rd(self, addr):
        if addr & self.cb.WWBIT5:  # High half of the address space, Group B
            ret = self._cmm[self.MemGroupB][addr & self.cb.WWBIT6_15]
        else:
            ret = self._cmm[self.MemGroupA][addr & self.cb.WWBIT6_15]
        return ret

    def wr(self, addr, node):
        if addr & self.cb.WWBIT5:  # High half of the address space, Group B
            self._cmm[self.MemGroupB][addr & self.cb.WWBIT6_15] = node
        else:
            self._cmm[self.MemGroupA][addr & self.cb.WWBIT6_15] = node

    # hmm, how do you do a loop over all core when it's segmented...
    def len(self):
        # print("CoreMemoryMetaData.len() Needs Work!")
        return (self.cb.CORE_SIZE // 2)

    def make_core_node(self, pc: int, label: str, opcode: str, operand: int, comment: str):
        if self.rd(pc) is None:
            self.wr(pc, CoreNodeClass(pc, label, opcode, operand, comment))
        else:  # these fields aren't filled in if the node is first encountered as a possible branch target
            if self.rd(pc).label == '':
                self.rd(pc).label = label
            if self.rd(pc).comment == '':
                self.rd(pc).label = comment

            if self.rd(pc).use_count is None:   # this can't happen any more; I experimented with None as initial use_count
                print("Use Count should never be None")
                exit(-1)


class CoreNodeClass:
    def __init__(self, pc: int, label: str, opcode: str, operand: int, comment: str):

        self.pc = pc
        self.opcode = opcode
        self.label = label
        self.operand = operand
        self.comment = comment

#          #  Start with use-count 'None'.  If the node is used, count the number of times, starting with One
#          #  I'm reserving the value Zero for instructions which are found through static analysis but
#          # never executed
#          self.use_count = None
        self.use_count = 0
        self.branched_to_by = {}
        self.branches_to = {}
        self.branch_not_taken = False
        self.first_word = False
        self.last_word = False
        self.block_id = None


def add_branch_addr_to_core(core, pc, value, cm, cpu, branches_to=False, branched_to_by=False):
    if branches_to ^ branched_to_by is False:
        print("add_branch_addr_to_core should be To or From, not both or neither!")
        exit(1)
    # make sure the node to which we are branching exists
    if core.rd(pc) is None:
        instruction = cm.rd(pc)
        # move these two lines into the CPU class and get the SLH/SLR stuff right, plus label and comment
        opcode = cpu.op_decode[(instruction >> 11) & 0o37][1]
        operand = instruction & cpu.cb.WW_ADDR_MASK
        core.wr(pc, CoreNodeClass(pc, '', opcode, operand, ''))
    if branches_to:
        if value not in core.rd(pc).branches_to:
            core.rd(pc).branches_to[value] = 1  # keep a count, starting at one
        else:
            core.rd(pc).branches_to[value] += 1  # increment the count for each use
    if branched_to_by:
        if value not in core.rd(pc).branched_to_by:
            core.rd(pc).branched_to_by[value] = 1  # keep a count, starting at one
        else:
            core.rd(pc).branched_to_by[value] += 1  # increment the count for each use


class BlockClass:  # this class holds a summarized block of code, with links to where it goes next
    def __init__(self, cb, seq, start_addr, label, comment, opcode, operand):
        self.cb = cb
        self.id = 'b%d' % seq
        self.label = 'b%d:%s' % (seq, label)
        self.start_addr = start_addr
        self.end_addr = 0    # fill this in later with the last instruction in the block
        self.start_comment = comment
        self.end_comment = ''
        self.end_instruction = ''
        self.decimal_addresses = cb.decimal_addresses
        self.start_instruction = self.add_instruction_notation(cb.cpu, start_addr, opcode, operand)

        self.branches_to = {}
        self.instruction_trace = ''
        self.first_block = False
        self.last_block = False
        self.contains_io = False
        self.contains_cf = False
        self.subroutine_return_address = None   # if this looks like a subroutine, point to the block with the return
        self.subroutine_return_block_id = None   # if this looks like a subroutine, point to the block with the return
        self.external_references_block_id = []


    def add_instruction_notation(self, cpu, pc, opcode, operand):
        label = cpu.wwaddr_to_str(pc, label_only_flag=True)
        return "@%s:%s %s" % (label, opcode, self.cb.int_str(operand))

#        if self.decimal_addresses:
#            return "@%03d:%s %04d" % (pc, opcode, operand)
#        else:
#            return "@%03o:%s %05o" % (pc, opcode, operand)


BlockSeq = 1   # blocks need unique names, so for now we use a sequence number

# core_node points to the metadata for one core entry
def make_block(cb, pc, core_node, last_block=False):
    global BlockSeq

    label = core_node.label
    comment = core_node.comment
    opcode = core_node.opcode
    operand = core_node.operand
    first_block = core_node.first_word

    block = BlockClass(cb, BlockSeq, pc, label, comment, opcode, operand)
    block.first_block = first_block
    block.last_block = last_block
    if opcode == 'TA':
        block.subroutine_return_address = operand
        core_node.subroutine_return = True

    BlockSeq += 1
    return block


# Scale colors
def scale_colors(blocklist):
    edge_branch_counts = []
    for b in blocklist:
        for link in b.branches_to:
            edge_branch_counts.append(b.branches_to[link])
    edge_branch_counts.sort()
    n_edges = len(edge_branch_counts)
    cbin_thresholds = []   # color bins
    cbins = ((0.00, "Black"), (0.50, "Blue"), (0.95, "Red"))
    if len(edge_branch_counts):
        for cbin in cbins:
            cbin_thresholds.append((edge_branch_counts[int(n_edges * cbin[0])], cbin[1]))
    else:
        cbin_thresholds = (0, cbins[0][1])  # this is the case when the trace is so short there are no branches.
    return cbin_thresholds


def pick_edge_color(cbin_thresholds, edge_branch_count) -> str:
    color = None
    for cbin in cbin_thresholds:
        if edge_branch_count >= cbin[0]:
            color = cbin[1]
    return color


# read the input trace file, parse it down to individual entries
# each trace log entry = [pc, label, op code, operand, AC]
# Note that we're attaching 'fake' log entries at the start and end
# That does mark the ends, but it also makes it safe for looking at the next or previous
# entry for any 'real' log, without having to check for overflow each time
def readlog(filename):

    if Debug:
        print("\n ** Read Trace Log")
    tracelog = [TraceLogClass(0, '', '', 0, 0, '', log_beginning=True)]
    fd = None
    try:
        fd = open(filename, "r")
        if Debug:
            print("Using file %s for Trace Log" % filename)
    except IOError:
        print("Can't open Trace Log file %s" % filename)
        exit(1)

    line_number = 1

    # each line should be:
    #   pc:0o000567:  MH 0o000017(label) AC=000207o, AR=000473o, BR=072422o, SAM=00o    nextPC=0o000570, \
    #                                                                    Core@0o000017=000473o  ;  Multiply & Hold
    # we want pc, op-code, operand and AC
    pattern = " pc:0o([0-7]*).*:  *([A-Z]*)  *0o([0-7]*).*AC=([0-7]*).*; *(.*)"  # obvious, no?  ugh...
#    pattern = " pc:0o(0-7]*) ([A-Z]*) 0o([0-7]*).*"

    for line in fd:
        line = line.rstrip(' \t\n\r')  # strip trailing blanks and newline
        line_number += 1
        if len(line) == 0:  # skip blank lines
            continue
        if not line.startswith(' pc:'):
            continue
#        if Debug:
#            print("Line %d: %s" % (line_number, line))

        pc = None
        opcode = None
        operand = None
        acc = None
        comment = None
        m = re.search(pattern, line)
        if m:
            if Debug:
                print(f"match: 0:'{m.group(0)}', 1:'{m.group(1)}' 2:'{m.group(2)}' 3:'{m.group(3)}' \
                 4:'{m.group(4)}'  5:'{m.group(5)}'")
            pc = m.group(1)
            opcode = m.group(2)
            operand = m.group(3)
            acc = m.group(4)
            comment = m.group(5)
        tracelog.append(TraceLogClass(int(pc, 8), ("pc0o%s" % pc), opcode, int(operand, 8), int(acc, 8), comment))

    fd.close()
    tracelog.append(TraceLogClass(0, '', '', 0, 0, '', log_end=True))

    return tracelog


# read the sequence of log entries and mark block-start and block-end in a core image
# Recall that the first and last entries are placeholders, so it's always safe to look one ahead or
# one behind.
def trace_to_core(tracelog, core_meta_data, cm, cpu):

    if Debug:
        print("\n ** Construct Core Map")
    for i in range(1, len(tracelog)-1):
        pc = tracelog[i].pc
        core_meta_data.make_core_node(pc, tracelog[i].label, tracelog[i].opcode,
                                      tracelog[i].operand, tracelog[i].comment)
        if i == 1:   # special case -- the first instruction is obviously the start of a block
            core_meta_data.rd(pc).first_word = True
        if i == len(tracelog) - 2:   # special case for end of the trace
            core_meta_data.rd(pc).last_word = True

        # make_core_node will only change the opcode if the use-count is zero, so if the trace comes back
        # with a different opcode for this core location, then the WW program rewrites the instruction type
        if core_meta_data.rd(pc).opcode != tracelog[i].opcode:
            print("Holy Cow!! They changed an opcode at instruction 0o%o: was %s, now %s" %
                  (pc, core_meta_data.rd(pc).opcode, tracelog[i].opcode))
        if core_meta_data.rd(pc).use_count is None:
            core_meta_data.rd(pc).use_count = 1  # this should never happen
            print("Use Count Should Never be None")
            exit(-1)
        else:
            core_meta_data.rd(pc).use_count += 1
        if Debug:
            print("tracelog %d = 0o%o" % (i, tracelog[i].pc))
        # start to figure out block boundaries
        # If there's a change in the PC, it's clearly a new block, so we can mark the end of one and the start
        # of the next.

        next_pc = tracelog[i+1].pc
        if tracelog[i].itsabranch and not core_meta_data.rd(pc).last_word:  # something caused a branch
            add_branch_addr_to_core(core_meta_data, pc, next_pc, cm, cpu, branches_to=True)
            add_branch_addr_to_core(core_meta_data, next_pc, pc, cm, cpu, branched_to_by=True)


# Chase down all the Branches Not Taken.  Instructions which could be executed but are
# not are indicated with a use-count of zero.
# A branch-not-taken could go to an instruction that we've already tracked; if so, there's
# nothing to do.  But if the instruction it would have gone to hasn't been seen before, we need
# to add a block.
def static_trace(core_meta_data, start_pc, prev_pc, cm, cpu):
    trace = cpu.cb.tracelog
    cb = cpu.cb
    if trace:
        cb.log.info("Static Trace at pc=0o%02o, prev_pc=0o%02o" % (start_pc, prev_pc))
    if core_meta_data.rd(start_pc) is not None:
        if prev_pc not in core_meta_data.rd(start_pc).branched_to_by:
            core_meta_data.rd(start_pc).branched_to_by[prev_pc] = 0
        return

    instruction_list = ''
    pc = start_pc
    opcode = ""
    operand = 0
    while pc < cb.CORE_SIZE:
        instruction = cm.rd(pc)
        if instruction is None:
            cb.log.warn("static trace leads to None?")
        opcode = cpu.op_decode[(instruction >> 11) & 0o37][1]
        operand = instruction & cpu.cb.WW_ADDR_MASK

        label = cpu.wwaddr_to_str(pc, label_only_flag=True)
        comment = "n/c"   # 'no comment', i.e. there might be one in the source, but the instruction didn't
                          # execute, so it's not in the trace log.  oops.
        core_meta_data.make_core_node(pc, label, opcode, operand, comment)
        if pc == start_pc:
            core_meta_data.rd(pc).branched_to_by[prev_pc] = 0
        instruction_list += "@0o%02o:%s 0o%02o\\l" % (pc, opcode, operand)
        # test for the end of a block; could be a branch, or it could be a halt instruction
        if opcode == "CP" or opcode == "SP" or instruction == 0 or instruction == 0o1:
            break
        if opcode == "CF":  # it's hard to trace any further after a CF!
            break
        pc += 1
    if trace:
        cb.log.info("found static block starting at 0o%02o: %s" % (start_pc, instruction_list))
    if opcode == "SP":   # an unused SP can only go to one new location
        #  Caution!  Amateur recursion!
        if operand not in core_meta_data.rd(pc).branches_to:
            core_meta_data.rd(pc).branches_to[operand] = 0  # add a new zero-use branch target for unconditional branch
        static_trace(core_meta_data, operand, pc, cm, cpu)
    if opcode == "CP":
        if operand not in core_meta_data.rd(pc).branches_to:
            core_meta_data.rd(pc).branches_to[operand] = 0  # add a new zero-use branch target
        static_trace(core_meta_data, operand, pc, cm, cpu)
        if (pc + 1) not in core_meta_data.rd(pc).branches_to:
            core_meta_data.rd(pc).branches_to[pc + 1] = 0  # add a new zero-use branch target
        static_trace(core_meta_data, pc+1, pc, cm, cpu)



# scan a sequential block of instructions to see if any of them might do an I/O op or contain a Change Field
# start_addr is the address of the first instruction in the block; end_addr is the address
# of the last instruction.
def block_contains_io_cf(cb, core_meta_data, start_addr: int, end_addr: int):
    pc = start_addr
    contains_io = False
    contains_cf = False

    while pc < (end_addr +1):
        opcode = core_meta_data.rd(pc).opcode
        if cb.cpu.isa_1950 == False:
            if opcode.lower() in ('si', 'bo', 'bi', 'rc', 'rd'):
                contains_io = True
            if opcode.lower() == 'cf':
                contains_cf = True
        else:
            cb.log.warn("block_contains_io can't decode 1950 instruction set")
        pc += 1
    return contains_io, contains_cf


# march through the core image and turn it into a list of code blocks.
# we assume that a block:
#   - starts where some instruction branches to it
#   - ends where there's a non-sequential change of control
# no word may be in more than one block
# words that aren't in blocks either aren't executed in this run, or aren't instructions at all
def define_blocks(cb, core_meta_data, cm, cpu):
    blocklist = []
    errors = 0
    current_block = None

    if Debug:
        print("\n ** Construct Block List")

    # keep track of 'branches not taken' by static analysis
    # i.e., a CP instruction can take the branch or not.  If the trace case only hits one
    # direction, we won't see the other direction at all on the graph, so we'll add it by static tracing
    for pc in range(0, CORESIZE):
        if core_meta_data.rd(pc) is not None:
            if core_meta_data.rd(pc).opcode == 'CP' : # or core_meta_data[pc].last_word:  # this case could apply to CK too, I think, but I haven't seen one...
                if (pc + 1) not in core_meta_data.rd(pc).branches_to:  # this is the case where the CP never falls through
                    core_meta_data.rd(pc).branches_to[pc + 1] = 0  # add to the dictionary of branches_to
                    static_trace(core_meta_data, pc + 1, pc, cm, cpu)
            if core_meta_data.rd(pc).opcode == 'CP':
               if core_meta_data.rd(pc).operand not in core_meta_data.rd(pc).branches_to:  # this is the case where the branch is never taken
                    core_meta_data.rd(pc).branches_to[core_meta_data.rd(pc).operand] = 0  # add to the dictionary of branches_to
                    static_trace(core_meta_data, core_meta_data.rd(pc).operand, pc, cm, cpu)

    # there's a special-case fixup here...
    # if something branches into the middle of what otherwise would be a larger block, then a
    # boundary must be installed.  That is, the instruction prior to the branch target must be
    # treated as if it was a branch itself to the following instruction.
    # Here's a corner case.  @137 must be marked end-of-block because of the jump from 116 to 0o140.
    # But the Jump to 141 from 0o325 should not cause an edge from 140 to 141
    #    @0134:104166   i0134:  cs  w0166   ; clear and subtract @@ JumpedToBy: a0122 a0125
    #    @0135:140167           mr  r0167   ; multiply and roundoff
    #    @0136:040166           ts  w0166   ; transfer to storage  
    #    @0137:100200           ca  w0200   ; clear and add
    #    @0140:074320   i0140:  sp  i0320   ; sub-program @@ JumpedToBy: a0116
    #
    #    @0141:040165   i0141:  ts  w0165   ; transfer to storage @@ JumpedToBy: a0325
    #    @0142:100164           ca  w0164   ; clear and add
    #    @0143:160001          srr  00001   ; shift right and roundoff
    for pc in range(0, CORESIZE):
        if pc != 0 and core_meta_data.rd(pc) is not None:
            branched_to_by: int = len(core_meta_data.rd(pc).branched_to_by)
            if branched_to_by and (core_meta_data.rd(pc - 1) is not None) and \
                    (core_meta_data.rd(pc - 1).opcode != 'SP') and (core_meta_data.rd(pc - 1).opcode != 'CP'):
                if pc not in core_meta_data.rd(pc - 1).branches_to:
                    core_meta_data.rd(pc - 1).branches_to[pc] = core_meta_data.rd(pc - 1).use_count

    last_word = False
    for pc in range(0, CORESIZE):
        if core_meta_data.rd(pc) is not None:
            branched_to_by: int = len(core_meta_data.rd(pc).branched_to_by)
            branches_to: int = len(core_meta_data.rd(pc).branches_to)
            if Debug:
                print("addr 0o%o: op=%s, comment='%s', branched_to_by=%d, branches_to=%d" %
                      (core_meta_data.rd(pc).pc, core_meta_data.rd(pc).opcode, core_meta_data.rd(pc).comment,
                       branched_to_by, branches_to))
            if core_meta_data.rd(pc).opcode == '':
                continue
            if core_meta_data.rd(pc).last_word:
                last_word = True
            if core_meta_data.rd(pc).first_word or branched_to_by:
                if current_block:
                    print("oops, starting a new block when we're already in one; pc = 0o%05o" % pc)
                    errors += 1
                else:
                    current_block = make_block(cb, pc, core_meta_data.rd(pc))

            if current_block:
                current_block.instruction_trace += "@%-10s: %s %-10s ;%s\\l" % \
                                                   (cpu.wwaddr_to_str(pc,no_label=True), core_meta_data.rd(pc).opcode,
                                                    cpu.wwaddr_to_str(core_meta_data.rd(pc).operand),
                                                    core_meta_data.rd(pc).comment)
                # update the core memory address to remember which block it's in
                core_meta_data.rd(pc).block_id = current_block.id
            # we end a block if it branches to something.  There's a special case -- if it's the end of a
            # trace and the block hasn't already been marked as having an end, then we flush out that last
            # bit here.
            if (core_meta_data.rd(pc).last_word and core_meta_data.rd(pc).use_count == 1) or branches_to:
                if current_block is None:
                    print("oops, ending a block when we aren't in one; pc = 0o%05o" % pc)
                    errors += 1
                    continue
                current_block.branches_to = core_meta_data.rd(pc).branches_to
                current_block.last_block = last_word
                current_block.end_addr = pc
                current_block.end_comment = core_meta_data.rd(pc).comment
                current_block.end_instruction = \
                    current_block.add_instruction_notation(cpu, pc, core_meta_data.rd(pc).opcode,
                                                           core_meta_data.rd(pc).operand)
                blocklist.append(current_block)
                current_block = None  #reset for the next block
                last_word = False
        else:  # else the pc points to an unused core location
            if current_block is not None:
                print("Unidentified end of block; pc = 0o%05o" % pc)
                blocklist.append(current_block)
                current_block = None

    # identify the first and last blocks
    # Dec 31, 2021 And mark any block that has an I/O instruction
    # Feb 17, 2023 And convert subroutine return addresses to block numbers
    for b in blocklist:
        first = ''
        last = ''
        if b.first_block:
            first = '_Start'
        if b.last_block:
            last = '_End'
        b.label = b.label + first + last
        b.contains_io, b.contains_cf = block_contains_io_cf(cb, core_meta_data, b.start_addr, b.end_addr)
        # This section converts subroutine return addresses into block names
        # This is not good, but the designated return instruction is not traced, it may not be in
        # any block, in which case we shall simply say so (for now)
        if b.subroutine_return_address:
            if core_meta_data.rd(b.subroutine_return_address) is not None:
                b.subroutine_return_block_id = core_meta_data.rd(b.subroutine_return_address).block_id
            else:
                b.subroutine_return_block_id = "none"
    return blocklist


def dump_block_list(blocklist, block_index, core):
    cpu = core.cb.cpu    # this is embarrassing...
    print('\n ** Dump block list')
    for b in blocklist:
        first = ''
        last = ''
        io = ''
        cf = ''
        subr = ''  # if this block is the (likely) entry point for a surbroutine, we announce its exit point
        if b.first_block:
            first = ' First Block'
        if b.last_block:
            last = ' Last Block'
        if b.contains_io:
            io = ' I/O'
        if b.contains_cf:
            cf = ' CF'
        if b.subroutine_return_block_id:
            subr = " subr-entry, return in %s" % b.subroutine_return_block_id
        print('\n*Block %s start_addr:%o, end %o:%s; %s %s %s%s%s' %
              (b.id, b.start_addr, b.end_addr, b.start_comment, first, last, io, cf, subr))
        addr = b.start_addr
        while (addr < core.cb.CORE_SIZE) and (core.rd(addr) is not None):
            print('     @%-10s: %s %-10s ; %s' %
                  (cpu.wwaddr_to_str(addr), core.rd(addr).opcode, cpu.wwaddr_to_str(core.rd(addr).operand),
                   core.rd(addr).comment))
            if len(core.rd(addr).branches_to) != 0:
                break
            addr += 1
        print("instruction trace:\n%s" % b.instruction_trace)
        for link in b.branches_to:
            print("  %s:s -> %s:n;" % (b.id, block_index[link]))
    print('')


# so what I want at the end is a list of blocks and arrows between them
# output should be graphviz format
#   https://graphviz.org/doc/info/
#   https://graphviz.org/doc/info/lang.html
#   https://graphviz.org/doc/info/shapes.html   etc
# digraph flowchart {
#   size="4, 4";
#   s [label=start];
#
#   s -> a;
#   a -> b;
#   a -> c;
#   c -> d;
#   d -> e [penwidth=3];
#   d -> f;
#   e -> f;
#   e -> c [weight=3] ;
#   f -> a;
#   }
#     Sample from my own dot files...
#  b132 [label="b132:z?(13w)\n@0o2600:TA 0o0615\n@0o2614:CP 0o0616\n";shape=box3d]
#  b133 [label="b133:z?(1w)\n@0o2615:SP 0o0000\n";shape=box3d]
#  b134 [label="b134:_End(1w)\n@0o3706:SI 0o0000\n";color="Green";shape=box3d]
#  b2 -> b86 [label="x1";  color="Red"];
#  b2 -> b3 [label="x0"; style=dashed color="Blue"];
#  b3 -> b4 [label="x1";  color="Red"];

def format_one_block(b, block_info_len, cpu):
    block_len = b.end_addr - b.start_addr + 1
    if block_info_len != FLOW_BLOCK_ALL_CODE:
        short = (block_info_len == FLOW_BLOCK_TERSE)
        if not short:
            start_comment = " ;" + b.start_comment
            end_comment = " ;" + b.end_comment
        else:
            start_comment = ''
            end_comment = ''
        block_start_label = "%s%s\\n" % (b.start_instruction, start_comment)
        if block_len > 1:
            block_end_label = "%s%s\\n" % (b.end_instruction, end_comment)
        else:
            block_end_label = ''
    else:
        block_start_label = b.instruction_trace
        block_end_label = ''
    style = ''
    if b.first_block or b.last_block or b.contains_io:  # highlight first and last blocks
        style = ';color="Green"'
    if b.contains_cf:  # CF fields have special (bad) meaning in flow-graphs, so that supersedes I/O designation
        style = ';color="Red"'

    # Bug - Jan 27, 2025 - guy - Labels contain comments from code, which may in turn contain double quotes
    # These quotes must be escaped to avoid freaking the Dot compiler out.
    # Somehow this approach using replace() isn't working, but I don't want to debug this Right Now!
    # [LAS 10/6/25 It looks like the other two vars below other than b.label
    #  needed the escapes too. With those additions it works.]
    b.label = b.label.replace('"', '\\"')
    block_start_label = block_start_label.replace ('"', '\\"')
    block_end_label = block_end_label.replace ('"', '\\"')
    
    graph_label = '  %s [label="%s(%dw)\\l%s:\\l%s%s"%s;fontname=courier;shape=box3d]\n' % \
                  (b.id, b.label, block_len, cpu.wwaddr_to_str (b.start_addr, label_only_flag=True), block_start_label, block_end_label, style)
    return(graph_label)


# Write the flow diagram gv file.
# The flag 'short' controls whether source code comments should be included
# in the flow graph bubbles
def output_block_list(cb, blocklist, core, title, output_file, block_info_len, cpu):
    if output_file is None:
        fout = sys.stdout
    else:
        print("flow-graph output to file %s" % output_file)
        fout = open(output_file, 'wt')
    # fout.write("\n; *** %s ***\n" % filetype)

    block_index = {}  # dictionary of block_id names indexed by start address
    for b in blocklist:  # fill in the index
        block_index[b.start_addr] = b.id

    if Debug:
        dump_block_list(blocklist, block_index, core)
    # run through the counts to figure out what color to use for edges.  Hot ones get red, not gets black
    edge_color_thresholds = scale_colors(blocklist)

    # output GraphViz dot format
    if cb.decimal_addresses:
        notation = "Decimal"
    else:
        notation = "Octal"
    title_box = title + '\\nNotation: ' + notation
    fout.write('digraph flowchart {\n')
    fout.write('  size="50, 50";\n')   # Size of Canvas: ultimately this sets the pixel size for a png output file
        # I changed the size above from 15 to 50 Mar 8, 2024 to make it act like it was printing on a bigger sheet
        # of "paper" so that when viewed as an SVG with Firefox, it wouldn't need so much magnification to be visible.
        # All the browsers I tried won't zoom beyond 500%...
    fout.write(' t0 [label="%s"; shape=folder];\n' % title_box)
    for b in blocklist:
        graph_label = format_one_block(b, block_info_len, cpu)
        fout.write(graph_label)
    fout.write('')

    edge_count = 0
    for b in blocklist:
        for link in b.branches_to:
            edge_count += 1  # this is just a statistic to print at the end
            edge_branch_count = b.branches_to[link]
            if link != 0:  # the end state is not easy to manage...  it looks like a branch to zero, but
                    # from an instruction that's not a branch
                if edge_branch_count == 0:
                    style = "style=dashed"
                else:
                    style = ''
                fout.write('  %s:s -> %s:n [label="x%d"; %s color="%s"];\n' %
                           (b.id, block_index[link], edge_branch_count, style,
                            pick_edge_color(edge_color_thresholds, edge_branch_count)))
                if b.subroutine_return_block_id:
                    fout.write('  %s:s -> %s:n [label="rts"; style="dashed" color="Orange"];\n' %
                               (b.id, b.subroutine_return_block_id))
    fout.write('  }\n')

    core_locations = 0
    for pc in range(0, CORESIZE):
        if core.rd(pc) is not None:
            core_locations += 1

    print("Flow Statistics: Nodes=%d, Edges=%d, core-locations-touched=%d" %
          (len(blocklist), edge_count, core_locations))

class FlowGraph:
    def __init__ (self, argFlowGraph, argFlowGraphOutFile, argFlowGraphOutDir, cb, isStatic: bool = False):
        self.outfile = ""
        self.outfile_basename = ""
        self.do_flowgraph = argFlowGraph
        self.flowgraph_outfile = argFlowGraphOutFile
        self.flowgraph_outdir = argFlowGraphOutDir
        self.cb = cb
        # If outfile is spec'd, it supersedes the dir if the dir is spec'd. In
        # specifying the dir standard derived naming will be used.
        if self.flowgraph_outfile is not None:
            self.do_flowgraph = True
            self.outfile = self.flowgraph_outfile
        else:
            suffix = "flow" if not isStatic else "flow.static"
            self.outfile_basename = re.sub ("\\.acore$", "", os.path.basename (self.cb.CoreFileName)) + "." + suffix + ".gv"
        if self.flowgraph_outdir is not None:
            self.do_flowgraph = True
            self.outfile = self.flowgraph_outdir + "/" + self.outfile_basename
        else:
            self.outfile = self.outfile_basename
        if self.do_flowgraph:
            cb.tracelog = self.init_log()

    # Private
    def run_flow_analysis (self, cb, tracelog, cm, cpu, title, block_info_len):
        # uh-oh.  The flow analysis keeps an image of core memory with pointers, links, etc for
        # each instruction executed (but not the ones that aren't).  But for static analysis, we also need
        # to know what's in the underlying core memory to see what it would have executed had it got there.
        #  That's all ok, just that the naming is convoluted
        # core_meta_data = [None] * CORESIZE
        core_meta_data = CoreMemoryMetaData(cb)
        trace_to_core(tracelog, core_meta_data, cm, cpu)  # summarize the trace log into a core image
        blocklist = define_blocks(cb, core_meta_data, cm, cpu)
        output_block_list(cb, blocklist, core_meta_data, title, self.outfile, block_info_len, cpu)

    # Private
    def init_log (self):
        tracelog = []
        tracelog.append (TraceLogClass(0, '', '', 0, 0, '', log_beginning=True))
        return tracelog

    # Public
    def finish_flow_graph_from_sim (self, cb, cm, cpu, title, block_info_len=FLOW_BLOCK_ALL_CODE):
        if self.do_flowgraph:
            tracelog = cb.tracelog
            tracelog.append(TraceLogClass(0, '', '', 0, 0, '', log_end=True))
            self.run_flow_analysis(cb, tracelog, cm, cpu, title, block_info_len)

    # Public
    def finish_flow_graph_from_asm (self, cb, title, block_info_len=FLOW_BLOCK_ALL_CODE):
        tracelog = cb.tracelog
        tracelog.append (TraceLogClass(0, '', '', 0, 0, '', log_end=True))
        cm = CorememClass (cb)
        cpu = CpuClass (cb, cm)
        cb.cpu = cpu
        self.run_flow_analysis(cb, tracelog, cm, cpu, title, block_info_len)

