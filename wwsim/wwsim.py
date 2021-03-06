#!/usr/bin/python3

# simulate the Whirlwind instruction set
# g fedorkow, Dec 30, 2017

# todo
# Jan 28, 2019 - watch for confusion of CoreMem and coremem throughout the code...

# Changes
# Jul 18, 2019
# I added a hack to print a warning but return zero and keep running if uninitialized memory is read
# moved the cpu.print statement out of each instruction and into the calling loop.  Can't remember why I
#   didn't write it that way the first time
#
# updated to Python 3 April 2020

import re
import sys
import argparse
import wwinfra
import ww_io_sim
import time

from typing import List

TTYoutput = []
Debug = False


# move these into the "constants" class
# use these vars to control how much Helpful Stuff emerges from the sim
TracePC = False    # print a line for each instruction
TraceALU = False   # print a line for add, multiply, negate, etc
TraceBranch = True  # print a line for each branch
TraceQuiet = False


# print sim state at a breakpoint
def breakp_dump_sim_state(cpu):
    print("breakpoint @PC=%s  Xi=%s, Yi=s, Vy=s" % (cpu.wwaddr_to_str(cpu.PC),
                                                    cpu.wwint_to_str(CoreMem.rd[0o201])))


# start tracing at a breakpoint
def breakp_start_trace(cpu):
    print("breakpoint @PC=%s" % (cpu.wwaddr_to_str(cpu.PC)))
    cpu.cb.TracePC = True


def breakp():
    print("** Breakpoint **")


Breakpoints = {
    #  address   action
    #    0032: breakp_dump_sim_state,
    #    0117: breakp_start_trace,
}




class CpuClass:
    def __init__(self, cb):
        global CoreMem
        # I don't know what initializes the CPU registers, but it's easier to code if I assume they're zero!
        self._BReg = 0
        self._AC = 0    # Accumulator
        self._AReg = 0    # Address Register, used for subroutine return address
        self._SAM = 0   # Two-bit carry-out register; it's only legal values appear to be 1, 0, -1
                        # SAM is set by many instructions, but used only by ca cs and cm
        self.PC = None  # Program Counter
        self.IODevice = None  # Device last selected by SI instruction
        self.IODeviceClass = None
        self.MemGroupA = 0  # I think Reset sets logical Group A to point to Physical Bank 0
        self.MemGroupB = 1  # I *think* Reset sets logical Group B to point to Physical Bank 1

        self.cb = cb

        # we need to keep track of the scope object since it needs background processing
        self.scope = ww_io_sim.DisplayScopeClass(cb)

        self.IODeviceList = [
            self.scope,
            wwinfra.FlexoClass(cb),
            ww_io_sim.tty_class(cb),
            ww_io_sim.DrumClass(cb),
            ww_io_sim.CoreClearIoClass(cb),
            ww_io_sim.PhotoElectricTapeReaderClass(cb),
            ww_io_sim.InterventionAndActivateClass(cb),
            ww_io_sim.IndicatorLightRegistersClass(cb),
            ww_io_sim.InOutCheckRegistersClass(cb),
        ]

        self.cpu_switches = None
        # Aug 27, 2018 - started to add r/w designator to each op to see if it should trap on an uninitialized var
        #  And the microsecond count to estimate performance
        #  And changed from [] mutable list to () immutable set
        self.op_decode = [
            #  function    op-name  description       r/w, usec
            (self.si_inst, "SI", "Select Input",      '',  30),
            (self.unused1_inst, "unused", "unused",   '',  0),
            (self.bi_inst, "BI", "Block Transfer In", 'w', 8000),
            (self.rd_inst, "RD", "Read",              '',  15),
            (self.bo_inst, "BO", "Block Transfer Out", 'r', 8000),  # 04
            (self.rc_inst, "RC", "Record",            '',  22),    # 05
            (self.sd_inst, "SD", "Sum Digits",        'r', 22),    # 06
            [self.cf_inst, "CF", "Change Fields"],  # 07
            [self.ts_inst, "TS", "Transfer to Storage"],  # 010,
            [self.td_inst, "TD", "Transfer Digits"],      # 011
            [self.ta_inst, "TA", "Transfer Address"],
            [self.ck_inst, "CK", "Check"],
            [self.ab_inst, "AB", "Add B Reg"],             # 014
            [self.ex_inst, "EX", "Exchange"],              # 015
            [self.cp_inst, "CP", "Conditional program"],   # 016
            [self.sp_inst, "SP", "Subprogram"],            # 017
            [self.ca_inst, "CA", "Clear and add"],         # 020
            [self.cs_inst, "CS", "Clear and subtract"],    # 021
            [self.ad_inst, "AD", "Add to AC"],             # 022
            [self.su_inst, "SU", "Subtract"],              # 23o, 19d
            [self.cm_inst, "CM", "Clear and add Magnitude"],  # 24o, 20d
            [self.sa_inst, "SA", "Special Add"],
            [self.ao_inst, "AO", "Add One"],               # 26o, 22d
            [self.dm_inst, "DM", "Difference of Magnitudes"],  # 027o
            [self.mr_inst, "MR", "Multiply & Round"],      # 030
            [self.mh_inst, "MH", "Multiply & Hold"],       # 031
            [self.dv_inst, "DV", "Divide"],                # 032
            [self.sl_inst, "SL", "Shift Left Hold/Roundoff"],
            [self.sr_inst, "SR", "Shift Right Hold/Roundoff"],  # 034
            [self.sf_inst, "SF", "Scale Factor 035o"],
            [self.cy_inst, "CL", "Cycle Left"],   # 036
            [self.md_inst, "MD", "Multiply Digits no Roundoff (AND)"],  # 037
        ]

        self.ext_op_code = {
            "SR": [["srr", "srh"], ["shift right and roundoff", "shift right and hold"]],
            "SL": [["slr", "slh"], ["shift left and roundoff", "shift left and hold"]],
            "CL": [["clc", "clh"], ["cycle left and clear", "cycle left and hold"]]
        }

    # convert an integer to a string, including negative number notation
    def wwint_to_str(self, num):
        if num is None:
            return " None "
        if num & self.cb.WWBIT0:
            neg = "(" + "-%04oo" % (~num & self.cb.WWBIT1_15) + ")"
        else:
            neg = ""
        return ("%06oo" % num) + neg

    # convert an address to a string, adding a label from the symbol table if there is one
    def wwaddr_to_str(self, num):
        if num in self.SymTab:
            label = "(" + self.SymTab[num] + ")"
        else:
            label = ""
        return ("0o%06o" % num) + label

    def print_cpu_state(self, pc, short_opcode, op_description, address):
        s1 = " pc:%s:  %s %s" % (self.wwaddr_to_str(pc), short_opcode, self.wwaddr_to_str(address))
        s2 = "   AC=%s, AR=%s, BR=%s, SAM=%02oo" % \
            (self.wwint_to_str(self._AC), self.wwint_to_str(self._AReg), self.wwint_to_str(self._BReg), self._SAM)
        s3 = "   nextPC=%s, Core@%s=%s" % \
             (self.wwaddr_to_str(self.PC), self.wwaddr_to_str(address),
              self.wwint_to_str(CoreMem.rd(address, fix_none=False)))
        if self.cb.TracePC:
            print(s1, s2, s3, " ; ", op_description)

    def run_cycle(self):
        global CoreMem
        global Breakpoints
        instruction = CoreMem.rd(self.PC, fix_none=False)
        if instruction is None:
            print("\nrun_cycle: Instruction is 'None' at %05oo" % self.PC)
            return self.cb.READ_BEFORE_WRITE_ALARM
        opcode = (instruction >> 11) & 0o37
        address = instruction & self.cb.WW_ADDR_MASK
        if Debug:
            print("run_cycle: ProgramCounter %05oo, opcode %03oo, address %06oo" %
                  (self.PC, opcode, address))
        current_pc = self.PC
        self.PC += 1  # default is just the next instruction -- if it's a branch, we'll reset the PC later
        oplist = self.op_decode[opcode]
        ret = (oplist[0](current_pc, address, oplist[1], oplist[2]))
        self.print_cpu_state(current_pc, oplist[1], oplist[2], address)

        if current_pc in Breakpoints:
            Breakpoints[current_pc](cpu)
        return ret

    # generic WW add, used by all instructions involving add or subtract
    def ww_add(self, a, b, sam_in, sa=False):
        """ Add ones-complement WW numbers
        :param a: 16-bit ones-complement inputs
        :param b: 16-bit ones-complement inputs
        :param sam_in: overflow from a previous SA special add; this number is a python twos-comp
          and may have the value +1, 0 or -1
        :param sa: boolean, true for Special Add
        :return: ones-complement sum, new SAM, Alarm Status
        """
        if (a is None) | (b is None):
            print("'None' Operand, a=", a, " b=", b)
            return 0, 0, self.cb.READ_BEFORE_WRITE_ALARM

        # you can't get overflow adding two numbers of different sign
        could_overflow_pos = ((a & self.cb.WWBIT0) == 0) & ((b & self.cb.WWBIT0) == 0)  # if both sign bits are off
        could_overflow_neg = ((a & self.cb.WWBIT0) != 0) & ((b & self.cb.WWBIT0) != 0)  # if both sign bits are on

        ww_sum = a + b + sam_in

        if ww_sum >= self.cb.WW_MODULO:  # end-around carry;
            ww_sum = (ww_sum + 1) % self.cb.WW_MODULO  # WW Modulo is Python Bit 16, i.e., the 17th bit

        sam_out = 0  # the default is "no overflow" and "no alarm"
        alarm = self.cb.NO_ALARM

        if sa:
            if could_overflow_pos & ((ww_sum & self.cb.WWBIT0) != 0):
                sam_out = 1
                ww_sum &= ~self.cb.WWBIT0  # clear the sign bit; the result is considered Positive
            if could_overflow_neg & ((ww_sum & self.cb.WWBIT0) == 0):
                sam_out = -1
                ww_sum |= self.cb.WWBIT0  # set the sign bit
            # the following just makes sure the answer fits the word...  I don't think this ever does anything
            ww_sum &= self.cb.WWBIT0_15

        # check for positive or negative overflow.  Since we're adding two 15-bit numbers, it can't overflow
        # by more than one bit (even with the carry-in, I think:-))
        else:
            if could_overflow_pos & ((ww_sum & self.cb.WWBIT0) != 0):
                alarm = self.cb.OVERFLOW_ALARM
            if could_overflow_neg & ((ww_sum & self.cb.WWBIT0) == 0):
                alarm = self.cb.OVERFLOW_ALARM

        if self.cb.TraceALU or (alarm != self.cb.NO_ALARM and not self.cb.TraceQuiet):
            print("ww_add: WWVals: a=%s, b=%s, sum=%s, sam_out=%o, alarm=%o" %
                  (self.wwint_to_str(a), self.wwint_to_str(b), self.wwint_to_str(ww_sum), sam_out, alarm))
        return ww_sum, sam_out, alarm

    # basic negation function for ones-complement
    def ww_negate(self, a):
        """ ones complement negation """
        neg_a = a ^ self.cb.WWBIT0_15
        if self.cb.TraceALU:
            print("ww_negate: a=%o  neg_a=%o" % (a, neg_a))
        return neg_a

    def convert_to_py_sign_mag(self, a):
        # convert ones-complement numbers to sign and magnitude
        if a & self.cb.WWBIT0:   # sign bit == 1 means Negative
            py_a = (self.cb.WWBIT0_15 ^ a)   # this takes ones-comp of the magnitude and clears the sign bit
            sign_a = -1
        else:
            py_a = a & self.cb.WWBIT1_15
            sign_a = 1
        return py_a, sign_a

    # basic multiplication for ones-complement
    # Assuming the Python Int is 30 bits or longer...
    def ww_multiply(self, a, b):
        # convert ones-complement numbers to sign and magnitude
        py_a, sign_a = self.convert_to_py_sign_mag(a)
        py_b, sign_b = self.convert_to_py_sign_mag(b)

        py_product = py_a * py_b
        py_sign = sign_a * sign_b

        # convert to ones-complement
        if py_sign < 0:
            product = py_product ^ self.cb.pyBIT29_0  # convert to ones-complement
            ww_sign = self.cb.WWBIT0
            sign_str = '-'
        else:
            product = py_product
            ww_sign = 0
            sign_str = '+'

        # The 30-bit result is taken apart into two 16-bit registers.  Reg_A is the most-significant
        # part with the sign bit, Reg_B is the least significant, with WW Bit 15 unused and zero (I think)
        reg_b = (product << 1 & self.cb.WWBIT0_15)
        reg_a = ((product >> 15) & self.cb.WWBIT0_15) | ww_sign

        if self.cb.TraceALU:
            print("ww_multiply: tc_a=%o, tc_b=%o, tc_product=%s%o" % (py_a, py_b, sign_str, product))
            print("ww_multiply: a=%s, b=%s, reg_a=%s, reg_b=%s" %
                  (self.wwint_to_str(a), self.wwint_to_str(b), self.wwint_to_str(reg_a), self.wwint_to_str(reg_b)))

        return reg_a, reg_b, self.cb.NO_ALARM

    def ww_divide(self, n, d):
        """ Divide ones-complement WW numbers
        The test case, in Octal -> 0.1/0.4 = 0.2, i.e, one eighth divided by one half equals one quarter
        :param n: 16-bit ones-complement numerator
        :param d: 16-bit ones-complement divisor
        :return: ac, br, Alarm Status
        """
        if (n is None) | (d is None):
            print("Divide: 'None' Operand, n=", n, " d=", d)
            return 0, 0, READ_BEFORE_WRITE_ALARM

        # if sign bits are different, the result will be negative
        result_negative = (n & self.cb.WWBIT0) ^ (d & self.cb.WWBIT0)

        if n & self.cb.WWBIT0:
            n = self.ww_negate(n)
        if d & self.cb.WWBIT0:
            d = self.ww_negate(d)
        if n > d:
            return 0, 0, self.cb.DIVIDE_ALARM

        py_n = n * self.cb.WW_MODULO
        py_q = py_n // d

        br = py_q & self.cb.WWBIT0_15
        ac = 0

        if result_negative:
            ac = ac ^ self.cb.WWBIT0_15
            # note that BR is always positive; so it never needs to be negated

        alarm = 0

        if self.cb.TraceALU:
            print("ww_div: WWVals: n=%s, d=%s, quot=%s.%s, alarm=%o" %
                  (self.wwint_to_str(n), self.wwint_to_str(d),
                   self.wwint_to_str(ac), self.wwint_to_str(br), alarm))
        return ac, br, alarm

    # from "Whirlwind_Training_Program_Material.pdf", M_1624-1, dated November 28, 1952
    # File Whirlwind_Training_Program_Material.pdf  page ~8
    def si_inst(self, pc, address, _opcode, _op_description):  # select I/O Device
        if (address == 0) | (address == 1):
            print("Halt Instruction!  (Code=%o) at pc=0%o" % (address, pc))
            return self.cb.HALT_ALARM

        # SI 010(o) seems to clear the Flip Flop Register Set
        # not sure yet how to tell where they are all the time...
        if address == 0o10:
            print("Clear FF Registers (currently unimplemented)")
            return self.cb.UNKNOWN_IO_DEVICE_ALARM

        self.IODeviceClass = None    # forget whatever the last device was
        # scan the table of devices to see if any device matches; if so, run the si initialization for the device
        for dev in self.IODeviceList:
            cl = dev.is_this_for_me(address)
            if cl is not None:
                # we shouldn't match more than one IO address; if we get a match here , there
                # must be an incorrect table entry
                if self.IODeviceClass is not None:
                    print("SI: overlapping IO address 0o%o" % address)
                    return self.cb.UNKNOWN_IO_DEVICE_ALARM
                self.IODevice = address
                self.IODeviceClass = cl
        if self.IODeviceClass is None:
            print("SI: unknown IO address 0o%o" % address)
            return self.cb.UNKNOWN_IO_DEVICE_ALARM
        ret = self.IODeviceClass.si(address, self._AC)
        return ret

    # caution!  the RC instruction increments the PC by one for a normal operation,
    # but increments it by two if the device is busy
    # expect to see something like this:
    #       si  0402;  select  input;
    # L057: rc  0000;  record;  ## print #171740o
    #       sp  L062;  sub - program;  branch  L0062, continue program
    #       sp  L057;  sub - program;  failure - branch back to retry the RC
    # In this simulation, I haven't found a case to trigger a retry, so that code
    # will remain unexercised.
    def rc_inst(self, _pc, address, _opcode, _op_description):
        if self.IODeviceClass is None:
            print("unknown I/O device %oo" % self.IODevice)
            return self.cb.UNKNOWN_IO_DEVICE_ALARM

        alarm, symbol = self.IODeviceClass.rc(CoreMem.rd(address), self._AC)

        if self.cb.TraceQuiet is False:
            print("RC: Record to Device %s: Dev=0%oo, Output Word=0%06oo, (%s) Sub-Address %05oo" %
                  (self.IODeviceClass.name, self.IODevice, self._AC, symbol, address))
        return alarm

    # I/O Read instruction - fetch the contents of IOR into the accumulator
    # The function of this instruction depends entirely on the previous SI.  Read the book. (2M-0277)
    def rd_inst(self, _pc, address, _opcode, _op_description):
        (ret, acc) = self.IODeviceClass.rd(CoreMem.rd(address), self._AC)
        self._AC = acc
        return ret

    def bi_inst(self, _pc, address, _opcode, _op_description):
        if self.IODeviceClass is None:
            print("unknown I/O device %oo" % self.IODevice)
            return self.cb.UNKNOWN_IO_DEVICE_ALARM

        ret = self.IODeviceClass.bi(address, self._AC, CoreMem)
        self._AC = self._AC + address
        self._AReg = address
        return ret

    def bo_inst(self, _pc, address, _opcode, _op_description):
        if self.IODeviceClass is None:
            print("unknown I/O device %oo" % self.IODevice)
            return self.cb.UNKNOWN_IO_DEVICE_ALARM

        ret = self.IODeviceClass.bo(address, self._AC, CoreMem)
        self._AC = self._AC + address
        self._AReg = address
        return ret

    # ts x transfer to storage  #8 01000 86 microsec
    # Transfer contents of AO to register %0 The original contents
    # of x is destroyed.
    def ts_inst(self, _pc, address, _opcode, _op_description):
        CoreMem.wr(address, self._AC)
        return self.cb.NO_ALARM

    # td x transfer digits #9 01001 86 microsec
    # transfer last 11 digits of AC to last 11 digit positions of
    # register x. The original contents of the last 11 digit positions
    # of register x is destroyed.
    def td_inst(self, _pc, address, _opcode, _op_description):
        mask = self.cb.WW_ADDR_MASK
        m = CoreMem.rd(address, fix_none=False)  # I can't believe a td could do useful work on uninitialized storage
        if m is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        CoreMem.wr(address, m & (self.cb.WWBIT0_15 & ~mask) | (mask & self._AC))
        if self.cb.TraceALU:
            print("td_inst  AC=%oo, oldCore=%oo, newCore=%oo" % (self._AC, m, CoreMem.rd(address)))
        return self.cb.NO_ALARM

    # ta X transfer address  01010  29 microsec
    # Transfer last 11 digits of AR to last 11 digit positions of register x.
    # The original contents of the last 11 digit positions of register x are
    # destroyed. The ta operation is normally executed after an sp or cp
    # instruction in connection with sub-programing; less frequently after ao,
    # sf or other operations.
    def ta_inst(self, _pc, address, _opcode, _op_description):
        mask = self.cb.WW_ADDR_MASK
        m = CoreMem.rd(address, fix_none=False)  # I can't believe a ta could do useful work on uninitialized storage
        CoreMem.wr(address, m & (self.cb.WWBIT0_15 & ~mask) | (mask & self._AReg))
        if self.cb.TraceALU:
            print("ta_inst  AR=%oo, oldCore=%oo, newCore=%oo" % (self._AReg, m, CoreMem.rd(address)))
        return self.cb.NO_ALARM

    # execute branch instruction; this is the generic branch execution after any conditionals
    # have been met;  called by SP and CP instructions
    def ww_branch(self, pc, address, _opcode, _op_description):
        if address >= self.cb.CORE_SIZE:
            print("branch: looks like a bad branch pointer to %oo at pc=%oo" % address, pc)
            exit()
        if not self.cb.TraceQuiet:
            if address < self.PC:
                bdir = "backwards"
            else:
                bdir = "forwards"
            if self.cb.TraceBranch:
                print("branch %s from pc=%s to %s" %
                      (bdir, self.wwaddr_to_str(self.PC - 1), self.wwaddr_to_str(address)))

        # save the current PC+1 as a return address
        self._AReg = self.PC    # the PC was incremented in the calling routine (I think)
        self.PC = address
        return self.cb.NO_ALARM

    # cp x    conditiona1 program #14d  16o   01110   30 miorosec
    # If the number in AC is negative, proceed as in sp. If number in AC
    # 1s positive proceed to next instruction, but clear the AR

    # 2M-0277 says something different about AR in case of a positive result
    # "...and place in the last 11
    # digit positions of the AR the address of this next instruction."

    def cp_inst(self, pc, address, opcode, op_description):
        if self._AC & self.cb.WWBIT0:  # if AC is negative
            self.ww_branch(pc, address, opcode, op_description)
        else:
            self._AReg = self.PC  # AR is used as subroutine return address
        return self.cb.NO_ALARM

    # sp x    subprogram     #15d  17o      01111   30 microseo
    # Take next instruction from register x. If the sp instruction was
    # at address y, store y + 1 in last 11 digit positions of AR.  All of the
    # original contents 0 AR is lost.
    def sp_inst(self, pc, address, opcode, op_description):
        self.ww_branch(pc, address, opcode, op_description)
        return self.cb.NO_ALARM

    # ck X   check   01011  o13  #11d   22 microsec
    # Operates in two modes depending upon position of console switch (at T.C.)
    # labelled "Pogram Check Alarm on Special Mode." The NORMAL MODE is
    # selected if the switch is off or down. Normal Mode compares contents of
    # AC with contents of register x. If contents of AC are identical to contents
    # of register x, proceed to next instruction; otherwise, stop the computer
    # and give a "check register alarm" (Note: +0 is not identical to
    # -0.) SPECIAL MODE ia chosen if switch is on. Special Mode operates in
    # same way as above if the numbers being checked agree. If there is disagreement,
    # no check alarm will occur but the program counter (PC) will be
    # indexed by one, causing the next instruction to be skipped.
    def ck_inst(self, _pc, address, _opcode, _op_description):
        ret = self.cb.NO_ALARM
        m = CoreMem.rd(address)
        if m is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        if m != self._AC:
            if self.cpu_switches.read_switch("CheckAlarmSpecial") == 0:
                ret = self.cb.CHECK_ALARM
            else:
                # if there's a check and the Program Check Alarm switch is set to Special, then
                # instead of doing a trap, we double-increment the PC, i.e., skip the non-trap
                # instruction and do the one following.
                self.PC += 1
                if not self.cb.TraceQuiet:
                    print("Check Special Instruction going to addr=0o%o" % self.PC)
        return ret

    # ca x clear and add #16  10000 48 microsec ca
    # Clear AC and BR, then obtain oontents of SAM (+1, 0, or -1) times 2-15
    # and add contents of register x, storing result in AC. The oontents of
    # register x appears in AR. SAM is c1eared. Overflow may occur, giving an
    # arithmetic check a1arm
    def ca_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        (wwsum, self._SAM, alarm) = self.ww_add(0, operand, self._SAM)

        self._AC = wwsum
        self._AReg = operand
        self._BReg = 0
        self._SAM = 0
        return alarm

    # Operation  Function         Number  Binary   Time
    # cs x       Clear and subtract #021o  #17d   10001    48 microsec
    # Clear AC and BR, then obtain contents of SAM (+1, 0, or -l)
    # times 2**-15 and subtract contents of register x, storing result in
    # AC.  The contents of register x appears in AR.  SAM is cleared.
    # Overflow may occur, giving an arithmetic check alarm.
    def cs_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        (ww_sum, self._SAM, alarm) = self.ww_add(0, self.ww_negate(operand), self._SAM)

        self._AC = ww_sum
        self._AReg = operand
        self._BReg = 0
        self._SAM = 0
        return alarm

    # ad x   add      #022o  #18d   10010  48 micros8c
    # Add the contents of register x to contents of AC, storing result
    # in AC. The contents of register x appears in AR. SAM is cleared
    # Overflow may occur, giving an arithmetic check alarm.
    def ad_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        (ww_sum, self._SAM, alarm) = self.ww_add(self._AC, operand, 0)

        self._AC = ww_sum
        self._AReg = operand
        self._SAM = 0
        return alarm

    # sa :x special add 10101 1.24 21 26 microaec
    # Add contents of register x to contents of AC, storing fractional result
    # in AC and retaining in SAM any overflow (including sign} for use with
    # next ca, cs or cm instruction. Between sa and the next cs, ca or cm
    # instruction for which the sa is a preparation, the use of any instruction
    # which clears SAM will result in the loss of the overflow with no
    # other effect on the normal function of the intervening operation. The
    # following operations clear SAM without using its contents: sd, su, sa,
    # ao, dm, mr, mh, dv, sl, sr and sf.  ca, Cs or cm clear SAM after
    # using its contents. If the overflow resulting from the sa is to be disregarded,
    # care must be taken to destroy it before the next ca, cs or cm
    # instruction. The contents of register x appear in AR. SAM is c!eared before,
    # but not after, the addition is performed.
    def sa_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        (wwsum, self._SAM, alarm) = self.ww_add(self._AC, operand, 0, sa=True)

        self._AC = wwsum
        self._AReg = operand

        return self.cb.NO_ALARM

    # ao x add one #22 (26o)  10110 86 microsec
    #  Add the number 1 t1mes 2**-15 to contents of register x, storing
    # the result in AC and in register x. The original oontents of register x
    # appears in AR. SAM is cleared. Overflow may ooour, giving an arithmetic
    # oheck alarm.
    def ao_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address, fix_none=False)  # how could ao could do useful work on uninitialized storage
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        (wwsum, self._SAM, alarm) = self.ww_add(1, operand, 0)

        self._AC = wwsum
        CoreMem.wr(address, wwsum)  # this seems to be the only case where the answer is written back to core?
        self._AReg = operand
        self._SAM = 0

        return alarm

    # su x   subtract  #023o     #19d   10011   48   mioroseo
    # Subtract contents of register x from contents of AC, storing
    # result in AC.  The contents of register x appears in AR.  SAM is
    # cleared. Overflow may ooour, giving an arithmetic oheck alarm.
    def su_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        (wwsum, self._SAM, alarm) = self.ww_add(self._AC, self.ww_negate(operand), 0)

        self._AC = wwsum
        self._AReg = operand
        self._SAM = 0

        return alarm

    # ex x exchange    01101  o15  d13    29 usec
    # Exchange contents of AC with contents of register x. (Original contents
    # of AC in register x; original contents of register x in AC and AR.) Ex 0
    # will clear AC without clearing BR.
    def ex_inst(self, _pc, address, _opcode, _op_description):

        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        CoreMem.wr(address, self._AC)

        self._AC = operand
        self._AReg = operand

        alarm = self.cb.NO_ALARM
        if (address == 0) & (self._AC != 0):
            print("EX instruction @0o%o: the instruction book implies @0 should be zero, but it's 0o%o" %
                  (pc - 1, self._AC))
        return alarm

    # dm x  Difference of Magnitudes  #027o   #23d  22 microsec
    # Subtract the magnitude of contents of register x from the magnitude of
    # contents of AC, leaving the result in AC.  The magnitude of contents of
    # register x appears in AR.  SAM is cleared.  BR will contain the initial
    # contents of the AC.  If |C(AC) = |C(x)|, the result is -0
    #
    # guy says: I think this instruction was added later in the process...  it's
    # in the 1958 manual, and M-1624, but not R-196 1951.
    def dm_inst(self, _pc, address, _opcode, _op_description):
        # to find difference of magnitude, make the first arg positive, the second
        # negative, and add them
        # I'm assuming this ignores SAM carry-in
        ac = self._AC
        if ac & self.cb.WWBIT0:
            ac = self.ww_negate(ac)
        x = CoreMem.rd(address)
        if x is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        if (x & self.cb.WWBIT0) == 0:  # if x is positive, make it negative
            x = self.ww_negate(x)

        (wwsum, self._SAM, alarm) = self.ww_add(ac, x, 0)

        self._BReg = self._AC
        self._AC = wwsum
        self._AReg = self.ww_negate(x)  # we just made 'x' Negative above, this makes it positive
        self._SAM = 0

#        self.print_cpu_state(pc, opcode, op_description, address)
        return alarm

    # cm x    clear and add magnitude #20d   #024o  10100   48 microsec
    # Clear AC and BR, then obtain contents of SIM (+1, 0, -1)
    # times 2-15 and add magnitude of contents of register x, storing
    # result in AC. The magnitude of the contents of register x appears
    # in AR.   SAM is cleared. Overflow may occur, giving an arithmetic
    # check alarm.
    def cm_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        if operand & self.cb.WWBIT0:  # if the sign bit says its negative
            operand = self.ww_negate(operand)   # then take the ones-complement to make it positive
        (wwsum, self._SAM, alarm) = self.ww_add(0, operand, self._SAM)

        self._AC = wwsum
        self._AReg = operand
        self._BReg = 0
        self._SAM = 0
        return alarm

    # mr x multiply and roundoff #24d   030o 11000 65 microsec
    # Multiply contents of AC by contents of register x. Roundoff
    # result to 15 significant binary digits and store it in AC. Clear BR.
    # The magnitude of contents of register x appears in AR. SAM is cleared.
    def mr_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        (a, b, alarm) = self.ww_multiply(self._AC, operand)
        if (alarm == self.cb.NO_ALARM) & (b & 0o100000):
            (a, sam, alarm) = self.ww_add(a, 1, 0)  # do the roundoff

        self._AC = a
        # the instructions say that AR should contain the Magnitude of Register X,
        #  so I assume if it's negative, we make it positive first.
        if (operand & self.cb.WWBIT0) == 0:  # i.e., if positive
            self._AReg = operand
        else:
            self._AReg = self.ww_negate(operand)
        self._BReg = 0  # roundoff
        self._SAM = 0

        return alarm

    # mh X multiply and hold 11001 o31  25d 34-41 microsec
    # Multiply contents of AC by contents of register x. Retain the full product
    # in AC and in the first 15 digit positions of BR, the last digit
    # position of BR being cleared. The magnitude of contents of register x
    # appears in AR. SAM is cleared. The sign of AC is determined by sign of
    # product. Result in (AC + BR) is a double register product. The time is
    # determined the same as for MR.
    def mh_inst(self, _pc, address, _opcode, _op_description):

        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        (a, b, alarm) = self.ww_multiply(self._AC, operand)

        self._AC = a
        if (operand & self.cb.WWBIT0) == 0:  # i.e., if positive
            self._AReg = operand
        else:
            self._AReg = self.ww_negate(operand)
        self._BReg = b
        self._SAM = 0
        return alarm

    # dv X divide o11010   71 microsec
    # Divide contents of AC by contents of register x, leaving 16 binary digits
    # of the quotient in BR and +/-O in AC according to the sign of the quotient.
    # The instruction slr 15 following the dv operation will roundoff the quotient
    # to 15 binary digits and store it in AC. Let u and v be the numbers
    # in AC and register x, respectively, when the instruction dv x is performed.
    # If |u| < |v|, the correct quotient is obtained and no overflow can
    # arise. If |u| > |v| , the quotient exceeds unity and a divide-error
    # alarm will result. If u = v != 0, the dv instruction leaves 16 "ones" in
    # BR; roundoff in a subsequent slr 15 will cause overflow and give an arithmetic
    # overflow check alarm. If u = v = 0, a zero quotient of the appropriate
    # sign ia obtained. The magnitude of contents of register x appears
    # in AR. SAM is cleared.
    def dv_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        if operand is None:
            return self.cb.READ_BEFORE_WRITE_ALARM
        (a, b, alarm) = self.ww_divide(self._AC, operand)

        self._AC = a
        if (operand & self.cb.WWBIT0) == 0:  # i.e., if positive
            self._AReg = operand
        else:
            self._AReg = self.ww_negate(operand)
        self._BReg = b
        self._SAM = 0
        return alarm

    # md x   multiply digits no roundoff  #31 o37  22 microsec  [bitwise AND for pete's sake!]
    #  The product of the ith digit of the AC multiplied by the ith digit of
    # register x becomes stored in the ith digit of the AC.  The final value
    # of the ith digit of the AC is 1 if the initial value of the ith digits
    # of the AC and register x are both 1; otherwise, the final value of the
    # ith digit of the AC is 0.  AR contains the complement of the final con-
    # tents of the AC
    #
    #  This instruction seems to have been a late addition; 037 used to be 'qp'
    #  It seems to simply be a logical AND of @core & AC
    def md_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        a = self._AC & operand

        self._AC = a
        self._AReg = ~a & self.cb.WWBIT0_15
        return self.cb.NO_ALARM

    # sd X sum digits   00110   22 micrsec
    # The sum of the original contents of digit i of AC and original contents
    # of digit i of register x becomes stored in digit i of AC. The final
    # value of digit i of AC is O if the values of digit i of AC and of register
    # x are alike; the final value of digit i of AC is 1 if the values of
    # digit i of AC and of register x are different.
    def sd_inst(self, _pc, address, _opcode, _op_description):
        operand = CoreMem.rd(address)
        a = self._AC ^ operand  # xor of Register X and AC

        self._AC = a
        self._SAM = 0

        if self.cb.TraceALU:
            print("sd_inst  AC=%oo, Core=%oo" % (self._AC, CoreMem.rd(address)))
#        self.print_cpu_state(pc, opcode, op_description, address)
        return self.cb.NO_ALARM

    # srr n    shift right and roundoff #28 #34o   41 microsec
    #    Shift contents of AC and BR (except sign digit) to the right n
    # places. The integer n is treated modulo 32; digits shifted right out
    # of BR 15 are lost. (Shifting right n places is equivalent to multiplying
    # by 2**-n .) Roundoff the result to 15 binary digits and, store it in AC. Clear
    # BR. Negative numbers are complemented before and after the shift, hence
    # ones appear in the digit places made vacant by the shift of a negative number.
    # Digit 6 (the 2**9=512 digit of the address) of the instruction srr n must be
    # a zero to distinguish srr n from srh n described below. The instruction
    # srr a simply causes roundoff and clears BR. SAM is cleared. Roundoff
    # (in a srr 0) may cause overflow, with a consequent arithemetic check alarm.

    # srh n     shift right and hold #28 #34o     41 microsec
    # Shift contents of AC and BR (except sign digit) to the right n
    # places. The integer n is treated modulo 32; digits shifted right out of
    # BR 15 are lost. (Shifting right n places is equivalent to multiplying by
    # 2**-n) Do not roundoff the result nor clear BR. Negative numbers are
    # complemented before and after the shift, hence ones appear in the digit places
    # made vacant by the shift of a negative number. Digit 6 (the 2**9=512 digit
    # of the address) of the instruction srh n must be a one to distinguish srh n
    # from srr n described above. SAM is cleared.

    # [guy says] note that the B register is always considered 'positive'...  i.e.
    # all operations involving B first do a step of converting A to positive, then do the operation,
    # then convert A back to negative if needed.
    def ww_shift(self, a, b, n, shift_dir, hold):
        # shift on negative numbers works by complementing negative input, shifting and then re-complementing
        negative = (a & self.cb.WWBIT0)  # sign bit == 1 means Negative
        if negative:  # sign bit == 1 means Negative, so we turn it positive
            a = self.ww_negate(a)

        # having eliminated the sign bit, combine a and b into a single 32-bit native python number, then shift
        shift_val = a << 16 | b
        n &= 0o37   # shift value is "modulo 32".  I'm assuming "shift zero" is a no-op

        # do the actual shift, zero-filling the empty bits
        if shift_dir == self.cb.SHIFT_RIGHT:
            shift_val >>= n
        else:
            shift_val <<= n

        # Not Hold is Roundoff; that means checking the most significant bit of the new B register, and adding
        #  one to a if it's set, then clearing B.
        if hold is False:  # i.e., if Roundoff
            if self.cb.pyBIT15 & shift_val:  # python bit 15 == most significant bit of B Register
                shift_val += 1 << 16   # increase a by one
            shift_val &= ~self.cb.pyBIT15_0   # roundoff means "clear BR", which is the right half of the 32-bit word

        # The 32-bit result is taken apart into two 16-bit registers.  A Reg is the most-significant
        # part with the sign bit, B Reg is the least significant
        reg_b = shift_val & self.cb.WWBIT0_15

        # shift the top half into A, and toss whatever would have been in the sign bit, as that bit is considered Lost
        reg_a = (shift_val >> 16) & self.cb.WWBIT1_15

        # figure whether we have an alarm...  According th 2M-0277 pg 99, shift only produces an alarm in
        # the case of a "shift and roundoff"
        alarm = self.cb.NO_ALARM
        if reg_a & self.cb.WWBIT0 & (hold is False):   # the result is supposed to stay positive
            alarm = self.cb.OVERFLOW_ALARM             # -- if it switched signs, that's Overflow

        if negative:
            reg_a = ~reg_a & self.cb.WWBIT0_15
            # leave the B Register "positive"

        dir_str = {self.cb.SHIFT_RIGHT: "Right", self.cb.SHIFT_LEFT: "Left"}
        hold_str = {0: "Round", 1: " Hold"}
        if self.cb.TraceALU:
            print("ww_shift: neg=%d, %s, n=%d %s, a=%o, b=%o,  ouptut: shift_val=%oo, reg_a=%s, reg_b=%s" %
                  (negative, hold_str[hold], n, dir_str[shift_dir], a, b, shift_val, self.wwint_to_str(reg_a),
                   self.wwint_to_str(reg_b)))

        return reg_a, reg_b, alarm

    # this op code does the two Shift Right instructions
    def sr_inst(self, _pc, address, _opcode, _op_description):
        operand = address & 0o37  # the rule book says Mod 32
        hold = False
        if self.cb.WWBIT6 & address:
            hold = True
        (a, b, alarm) = self.ww_shift(a=self._AC, b=self._BReg, n=operand, shift_dir=self.cb.SHIFT_RIGHT, hold=hold)

        self._AC = a
        self._BReg = b
        self._SAM = 0

#        self.print_cpu_state(pc, opcode, op_description, address)
        return alarm

    # slr n shift left and roundoff  033-0   15+.8n microsec
    # (page 21, 2m-0277)
    # Shift frational contents of AC (except sign digit) and BR to the left n
    # places. The positive integer n is treated modulo 32; digits shifted
    # left out of AC 1 are lost. (Shifting left n places is equivalent to multiplying
    # by 2**n, with the result reduced modulo l.) Roundoff the result to
    # 15 binary digits and store it in AC. Clear BR. Negative numbers are complemented
    # before the shift and after the roundoff; hence, ones appear in
    # the digit places made vacant by the shift of a negative number. Digit 6
    # (the 2**9 = 512 digit of the address) of the instruction slr n must be a zero
    # to distinguish slr n from slh n described below. The instruction slr 0
    # simply causes roundoff and clears BR. SAM is cleared. Roundoff may
    # cause overflow with a consequent arithmetic check alarm if
    # <see doc>. The excution time varies according to the size of n.

    # slh n shift left and hold 033-1  15 + .8n microsec
    # Shift contents of AC (except sign digit) and BR to the left n places.
    # The positive integer n is treated modulo 32; digits shifted left out of
    # AC 1 are lost. (Shifting left n places is equivalent to multiplying by
    # 2**n, with the result reduced modulo 1.) Leave final product in AC and BR.
    # Do not roundoff or clear BR. Negative numbers are complemented in AC before
    # and after the shift; hence, ones appear in the digit places made
    # vacant by the shift of a negative number. Digit 6 (the 2**9 = 512 digit of
    # the address) of the instruction slh n must be a one to distinguish slh n
    # from slr n described above. SAM is cleared. The execution time depends
    # upon the size of the n.

    def sl_inst(self, _pc, address, _opcode, _op_description):
        operand = address & 0o37  # the rule book says Mod 32
        hold = False
        if self.cb.WWBIT6 & address:
            hold = True
        (a, b, alarm) = self.ww_shift(a=self._AC, b=self._BReg, n=operand, shift_dir=self.cb.SHIFT_LEFT, hold=hold)

        # hard to tell what' supposed to happen, but if it's like a multiply, then the sign shouldn't change
        # if negA:  # ken suggested fixing the sign, but that may break bjack
        #    a |= self.cb.WWBIT0  # turn on sign bit
        # else:
        #    a &= self.cb.WWBIT1_15  # turn off sign bit
        self._AC = a
        self._BReg = b
        self._SAM = 0
        return alarm

    #  [description from 2M-0277]
    # clc n         cycle left and clear (BR)  llll0-0 1.70 15 + .8n usec
    # Shift the full contents of A {including sign digit) and BR to the left n
    # places. The psitive integer n is treated modulo 32; digits shifted left
    # out of AC O are carried around into BR 15 so that no digits are lost. No
    # roundoff. Clear BR.  With the c1c operation there is no complementing of
    # AC either before or after the shift; the actual nurical digits in AC and
    # BR are cycled to the left. The digit finally shifted into the sign digit
    # position determines whether the result is to be considered a positive or
    # negtive quantity. Digit 6 (the 2**9 = 512 digit of the address) of the
    # instruction clc n must be a zero to distinguish clh n from clc n described
    # below. The instruction clc 0 simply clears BR without affecting AC. The
    # excution time depends on the size of the integer n.

    # this op code does the two Cycle Left instructions, Cycle Left Hold and Cycle Left Clear
    # Cycle Left and Clear moves bits from B into A, and clears B
    # Cycle Left and Hold rotates bits; bits that fall off the top of A rotate around to B
    def cy_inst(self, _pc, address, _opcode, _op_description):
        n = address & 0o37  # the rule book says Mod 32
        hold = False
        if self.cb.WWBIT6 & address:
            hold = True

        # ignore the sign bit, combine a and b into a single 32-bit native python number, then shift
        a = self._AC
        b = self._BReg
        shift_val = (a & self.cb.WWBIT0_15) << 16 | (b & self.cb.WWBIT0_15)

        cycle = shift_val >> (32-n)
        shift_val <<= n
        shift_val |= cycle   # combine in the overflow from the top part of the word

        reg_b = shift_val & self.cb.WWBIT0_15
        reg_a = (shift_val >> 16) & self.cb.WWBIT0_15

        # Not Hold means Clear, i.e., clear the B Reg
        if hold is False:
            reg_b = 0

            if self.cb.TraceALU:
                print("ww_left_cycle: in: n=%oo, a=%oo, b=%oo, out: a=%oo, b=%oo" % (n, a, b, reg_a, reg_b))

        self._AC = reg_a
        self._BReg = reg_b
        return self.cb.NO_ALARM

    # [From M-0277]
    # 1.1.3 (3) Primary Storage
    # Primary storage consists of 6144 registers of magnetic core memory (MCM) with
    # an access time of 7 mcroseconds, and 32 registers of test storage. There are three
    # shower-stalls a magnetic core memory, two of which contain 17 planes of 1024 cores
    # each. The third and latest shower-stall contains 17 planes of 4096 cores each.
    # The 17 planes represent the 16 binary digits of WWI register and the one digit used
    # for checking purposes.  Since WWI is designed to operate with a full complement of
    # 2048 registers of storage, only 2048 of the 6144 availble registers may be used
    # at a time.  Thus, for manipulation ease core storage is divided into six equal parts
    # of 1024 registers, with the proviso that two parts (fields) be used at one time to
    # provide the reqired 2048 registers necessary for full computer operation. The
    # six equal parts or "fields" are numbered 0 through 5 and may be chosen by the use
    # of the WWI instruction "change f1elds," cf. A control system exists which considers
    # register adresses to be in one of two groups: Group A includes register adresses
    # 0 - 1023 inclusive, and Group B includes register adresses 1024 - 2047 inclusive.
    # Any combination of fields can be used with the exception that the same field cannot
    # occupy Group A and Group B locations simultaneously. The 32 toggle-switch registers
    # of test storage and the five flip-flop storage registers, which may be interchanged
    # with any of the 32 toggle-switch storage registers, occupy registers 0 - 31 inclusive,
    # of the field memory used in Group A, which are thus normally unavailable for programming.

    # Change Field - Memory Bank Manager - from 2M-0277
    # cf pqr change fields     O0l11      0d7      15 microsec
    # The address section does not refer to a register of storage in this
    # instruction, but supplies information to the computer requesting a change
    # in fields Group A and/or B. When the field to be changed contains the
    # program, it is necessary for the cf instruction to perform like an sp
    # instruction. Digit 7 of the cf address section causes the contents of
    # the accumulator to be read to the program counter (PC) prior to the field
    # change; thus, program continuity can be preserved during field changes.
    # The A-Register will contain the original PC address plus one upon
    # completion of the cf instruction. The digit allocation for the cf word is
    # as follows:
    #
    # digits O - 4: O0ll1 cf order.
    # digit 5: spare
    # digit 6: examine feature - causes contents of core
    #   memory Group A control and Group B control
    #   registers to be read into the Accumulator.
    # digit 7: sp enable - reads content of AC to PC to
    #   establish starting point of program in the
    #   new field.
    # digit 8: change Group A field enable. (If, when the
    #   examine feature of digit 6 is requested,
    #   there is a "1" in digit 8, the content of
    #   Group A control will be changed before read-out
    #   to the A-Register takes place.)
    # digit 9: change Group B field enable. (If, when the
    #   examine feature of digit 6 is requested,
    #   there is a "1" in digit 9, the content of
    #   Group B control will be changed before read-out
    #   to the A-Register takes place.)

    # digits 10 - 12: contain field designation for Group A
    #   (registers l - 1777).
    # digits 13 - 15: contain field designation for Group B
    #   (registers 2000 - 3777).
    def cf_inst(self, pc, address, _opcode, _op_description):
        pqr = address  # the mode bits are labeled as pqr in the doc set...
        ret1 = self.cb.NO_ALARM

        if (pqr & self.cb.WWBIT7) & (pqr & self.cb.WWBIT6):
            print("cf_inst reads PC and MemGroup both into AC??")
            ret1 = self.cb.UNIMPLEMENTED_ALARM

        if pqr & self.cb.WWBIT9:
            old = CoreMem.MemGroupB
            CoreMem.MemGroupB = pqr & 0o07
            print("CF @%o: Change MemGroup B from %o to %o" % (pc, old, CoreMem.MemGroupB))

        if pqr & self.cb.WWBIT8:
            old = CoreMem.MemGroupA
            CoreMem.MemGroupA = (pqr >> 3) & 0o07
            print("CF @%o: Change MemGroup A from %o to %o" % (pc, old, CoreMem.MemGroupA))

        if pqr & self.cb.WWBIT7:  # this seems to swap PC+1 and AC;   I think PC is already incremented at this point...
            tmp = self.PC
            self.PC = self._AC  # implicit branch on bank change
            self._AC = tmp
            self._AReg = tmp
            print("CF @%o: Branch on bank change to %o" % (pc, self.PC))

        if pqr & self.cb.WWBIT6:  # read back bank selects to AC
            readout = CoreMem.MemGroupB | (CoreMem.MemGroupA << 3)
            self._AC = readout
            print("CF @%o: Read Back Group Registers A|B = %02o" % (pc, self._AC))
        return ret1

    # There's only one completely unused op-code; that one ends up here
    def unused1_inst(self, _pc, _address, _opcode, _op_description):
        return self.cb.UNIMPLEMENTED_ALARM

    def ab_inst(self, pc, _address, opcode, _op_description):
        print("unimplemented Add B Register instruction near PC=%o, opcode=%s" % (pc, opcode))
        return self.cb.UNIMPLEMENTED_ALARM

    def sf_inst(self, pc, _address, opcode, _op_description):
        print("unimplemented Scale Factor Instruction near PC=%o, opcode=%s" % (pc, opcode))
        return self.cb.UNIMPLEMENTED_ALARM


# #Print Core Image
def dump_core(coremem):
    print("\n*** Core Dump ***")
    columns = 8
    addr = 0
    while addr < len(coremem):
        a = 0
        non_null = 0
        row = ""
        while (a < columns) & (addr+a < len(CoreMem)):
            if coremem[addr+a] is not None:
                row += "%06o " % coremem[addr+a]
                non_null += 1
            else:
                row += "  --   "
            a += 1
        if non_null:
            print("%04o: %s" % (addr, row))
        addr += columns



#
# ############# Main #############
def main():
    global CoreMem   # should have put this in the CPU Class...
    parser = argparse.ArgumentParser(description='Run a Whirlwind Simulation.')
    parser.add_argument("corefile", help="file name of simulation core file")
    parser.add_argument("-t", "--TracePC", help="Trace PC for each instruction", action="store_true")
    parser.add_argument("-a", "--TraceALU", help="Trace ALU for each instruction", action="store_true")
    parser.add_argument("-j", "--JumpTo", type=str, help="Sim Start Address in octal")
    parser.add_argument("-q", "--Quiet", help="Suppress run-time message", action="store_true")
    parser.add_argument("-c", "--CycleLimit", help="Specify how long the sim may run", type=int)
    parser.add_argument("--PETRAfile", type=str,
                        help="File name for photoelectric papertape reader A input file")
    parser.add_argument("--PETRBfile", type=str,
                        help="File name for photoelectric papertape reader B input file")
    parser.add_argument("--NoAlarmStop", help="Don't stop on alarms", action="store_true")
    parser.add_argument("-n", "--NoCloseOnStop", help="Don't close the display on halt", action="store_true")
    parser.add_argument("--NoZeroOneTSR",
                        help="Don't automatically return 0 and 1 for locations 0 and 1", action="store_true")
    parser.add_argument("--CrtFadeDelay",
                        help="Configure Phosphor fade delay (default=0)", type=int)

    args = parser.parse_args()

    # instantiate the class full of constants
    cb = wwinfra.ConstWWbitClass()
    cpu = CpuClass(cb)
    cpu.cpu_switches = wwinfra.WWSwitchClass()
    CoreMem = wwinfra.CorememClass(cb)
    cb.log = wwinfra.LogClass(sys.argv[0], quiet=args.Quiet)

    # flexo = wwinfra.flexo_class()
    # tty = tty_class()

    cycle_limit = 400000  # default limit for number of sim cycles to run
    crt_fade_delay = 500

    print("corefile: %s" % args.corefile)
    if args.TracePC:
        cb.TracePC = True
    if args.TraceALU:
        cb.TraceALU = True
    if args.Quiet:
        cb.TraceQuiet = True
        print("TraceQuiet turned on")
    if args.NoZeroOneTSR:
        cb.NoZeroOneTSR = True
    else:
        print("Automatically return 0 and 1 from locations 0 and 1")
    if args.CycleLimit:
        cycle_limit = args.CycleLimit
        print("CycleLimit set to %d" % cycle_limit)
    if args.CrtFadeDelay:
        cb.crt_fade_delay_param = args.CrtFadeDelay
        print("CRT Fade Delay set to %d" % cb.crt_fade_delay_param)

    # WW programs may read paper tape.  If the simulator is invoked specifically with a
    # name for the file containing paper tape bytes, use it.  If not, try taking the name
    # of the sim file, stripping the usual .acore and adding .petrA
    if args.PETRAfile is not None:
        cb.PETRAfilename = args.PETRAfile
    else:
        cb.PETRAfilename = re.sub("\\..core$", "", args.corefile) + ".petrA"
    if args.PETRBfile is not None:
        cb.PETRBfilename = args.PETRBfile
    else:
        cb.PETRBfilename = re.sub("\\..core$", "", args.corefile) + ".petrB"

    (cpu.SymTab, JumpTo, WWfile, WWtapeID) = CoreMem.read_core(args.corefile, cpu.cpu_switches, cb)

    print("Switch CheckAlarmSpecial=%o" % cpu.cpu_switches.read_switch("CheckAlarmSpecial"))
    # set the CPU start address
    if JumpTo is None:
        cpu.PC = 0o40
    else:
        cpu.PC = JumpTo
    if args.JumpTo:
        cpu.PC = int(args.JumpTo, 8)
    print("start at 0o%o" % cpu.PC)

    # simulate each cycle one by one
    i = 0   # I don't see why I need to zero this, but if I don't, PyCharm objects to the cycle limit test below
    for i in range(1, cycle_limit):
        alarm = cpu.run_cycle()
        if cpu.scope.crt is not None:
            if i % 500 == 0:
                cpu.scope.crt.ww_scope_update()
        if alarm != cb.NO_ALARM:
            print("Alarm %d - %s at PC=0o%o" % (alarm, cb.AlarmMessage[alarm], cpu.PC - 1))
            # the normal case is to stop on an alarm; if the command line flag says not to, we'll try to keep going
            if not args.NoAlarmStop:
                break

    if i == (cycle_limit - 1):
        print("\nCycle Count Exceeded")

    print("Total cycles = %d, last PC=0o%o" % (i, cpu.PC))

    for d in cpu.IODeviceList:
        if d.name == "Flexowriter":
            s = d.get_saved_output()
            if len(s):
                print("\nFlexowriter Said:")
                for c in s:
                    sys.stdout.write(c)

        if d.name == "Teletype":
            s = d.get_saved_output()
            if len(s):
                print("\nTeletype Said:")
                for c in s:
                    sys.stdout.write(c)

        if d.name == "DisplayScope":
            if d.crt is not None:
                if args.NoCloseOnStop:
                    time.sleep(60)  # leave a minute to see what was on the display in case of a trap
                d.crt.close_display()


main()
