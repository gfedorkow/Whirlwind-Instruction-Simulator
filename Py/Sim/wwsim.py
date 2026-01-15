
# Copyright 2022 Guy C. Fedorkow
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#   The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Simulate the Whirlwind instruction set, based on Whirlwind Instruction Set Manual 2M-0277
# g fedorkow, Dec 30, 2017


# updated to Python 3 April 2020

BlinkenLightsModule = False

import sys
import os
import platform
import psutil
# sys.path.append('K:\\guy\\History-of-Computing\\Whirlwind\\Py\\Common')
# sys.path.append('C:\\Users\\lstabile\\whirlwind\\InstructionSimulator\\Py\\Common')
# import argparse # it's now in wwinfra log package
import wwinfra
import ww_io_sim
import ww_flow_graph
import radar as radar_class
import time
from datetime import datetime
import re
import museum_mode_params as mm
import csv
import control_panel
from wwdebug import DbgDebugger, DbgProgContext
import math
import traceback
import signal
from wwcpu import CpuClass

from typing import List, Dict, Tuple, Sequence, Union, Any

TTYoutput = []
Debug = False

flowgraph = None

#
# UseDebugger is set via the -d (--Debugger) cmd line arg. When true invokes
# sim in in the interactive debugger.  The Debugger object itself is made once
# in the sim loop, and retained for re-use across executions of the program.
#
UseDebugger = False
Debugger: DbgDebugger = None

# print sim state at a breakpoint
def breakp_dump_sim_state(cpu):

    if cpu.PC == 0o121 : # (cpu._AC != 0 and cpu._AC != 0o177777) and :
        print("breakpoint @PC=%s  AC=0o%o, loop_cnt=0o%o" % (cpu.wwaddr_to_str(cpu.PC), cpu._AC,
                                                    CoreMem.rd(0o144)))


# start tracing at a breakpoint
def breakp_start_trace(cpu):
    print("breakpoint @PC=%s" % (cpu.wwaddr_to_str(cpu.PC)))
    cpu.cb.TracePC = -1  # turn on trace 'forever'


def breakp(msg=""):
    print("** Breakpoint %s**" % msg)


Breakpoints = {
    #  address   action
    #    0117: breakp_start_trace,
}

#  Python 3.10.4 (tags/v3.10.4:9d38120, Mar 23 2022, 23:13:41) [MSC v.1929 64 bit (AMD64)] on win32
#  Type "help", "copyright", "credits" or "license" for more information.
#  >>> from datetime import datetime
#  >>> t = datetime.now
#  >>> t = datetime.today()
#  >>> print(t)
#  2022-09-10 22:06:57.195959
#  >>> tt = t.timetuple()
#  >>> for it in tt:
#  ...   print(it)
#  >>> print(tt)
#  time.struct_time(tm_year=2022, tm_mon=9, tm_mday=10, tm_hour=22, tm_min=6, tm_sec=57, tm_wday=5, tm_yday=253,
#  tm_isdst=-1)
#  >>> print(tt.tm_year)
#  2022
#  >>>
# In 'midnight-restart mode, I want the sim to stop when the day changes at midnight


# At the end of the simulation, we may want to dump out the state of core memory
def write_core_dump(cb, core_dump_file_name, cm):
    core_all_banks = []
    for bank in range(0, cm.NBANKS):
        core_all_banks += cm._coremem[bank]
    corelist = [core_all_banks]

    offset = 0
    byte_stream = False
    jump_to = None
    string_list = ''
    ww_tapeid = 'dump'
    ww_filename = 'dump'
    wwinfra.write_core(cb, corelist, offset, byte_stream, ww_filename, ww_tapeid,
               jump_to, core_dump_file_name, string_list)


# This mechanism triggers run-time 'debug widgets' on the WW 'crt', that is, a display of the real-time
# values of a handful of variables as the program runs.
# Arrow keys also allow the values to be incremented or decremented.
# The first run at this was wired directly to Core memory locations, i.e., state variables of the
# running object code.
# A modification in Sept 2023 allows the debug widget to also access, view and change variables in the Python
# environment, to allow, for instance, a dbwgt to tweak aircraft parameters in the simulated environment in
# the Radar module.
# Whirlwind core memory variables are identified with either the usual label or numeric core addresses.
# Variables in the python environment are preceded by a dot, followed by a Python var name, scoped to run
# in the CPU object (I think!).
def parse_and_save_screen_debug_widgets(cb, dbwgt_list):
    cb.DebugWidgetPyVars = wwinfra.DebugWidgetPyVarsClass(cb)
    for args in dbwgt_list:
        # first arg is a label or address, second optional arg is a number to use for each increment step
        # Third arg is a Format string
        cpu = cb.cpu
        dbwgt = cb.dbwgt
        label = ''
        py_wgt_label = ''
        address = 0
        increment = 1
        format_str = "0o%o"   # by default, numbers should be displayed as octal
        if args[0][0] == '.':
            address = -1
            py_wgt_label = args[0][1:]
            try:
                eval("cb.DebugWidgetPyVars." + py_wgt_label)
            except AttributeError:
                cb.log.warn("Debug Widget: Can't find Python Label 'cb.%s'" % py_wgt_label)
                py_wgt_label = ''
        elif args[0][0].isdigit():
            address = int(args[0], 8)
            if address in cpu.SymTab:
                label = cpu.SymTab[address][0]
        else:
            label = args[0]
            address = -1
            for addr in cpu.SymTab:
                if label == cpu.SymTab[addr][0]:
                    address = addr
                    break
            if address == -1:
                cb.log.warn("Debug Widget: unknown label %s" % label)
        if len(args) >= 2:   # if there's a second arg, it would be the amount of increment in octal
            try:
                increment = int(args[1], 8)
            except ValueError:
                print("can't parse Debug Widget increment arg %s in %s" % (args[1], args[0]))
        if len(args) == 3:
            format_str = args[2]
        if address >= 0 or len(py_wgt_label):
            dbwgt.add_widget(cb, address, label, py_wgt_label, increment, format_str)

#
# ############# Main #############

# This state machine is used to control the flow of execution for the simulator
# It's called by either the xwin graphical control panel or by the buttons-and-lights panel
# def moved_to_Panel_sim_state_machine(switch_name, cb):
#    sw = switch_name
#    if sw == "Stop":
#        cb.sim_state = cb.SIM_STATE_STOP
         # self.dispatch["Stop"].lamp_object.set_lamp(True)
         # self.dispatch["Start at 40"].lamp_object.set_lamp(False)
#        return
# etc...


def poll_sim_io(cpu, cb):
    ret = cb.NO_ALARM
    # if the analog scope interface is in use, there's a physical button which signals Stop 
    if cb.ana_scope:
        if cb.ana_scope.getSimStopButton():
            return cb.QUIT_ALARM

    if cpu.scope.crt is not None:
        exit_alarm = cpu.scope.crt.ww_scope_update(CoreMem, cb)
        if exit_alarm != cb.NO_ALARM:
            return exit_alarm

        wgt = cb.dbwgt
        # check the keyboard in the CRT window for a key press
        # But only if the laptop display is in use!  i.e., don't bother with this if the analog display is active
        key = ''
        if cpu.scope.crt.win:
            key = cpu.scope.crt.win.checkKey()
        if key != '':
            print("key: %s, 0x%x" % (key, ord(key[0])))
        if key == 'q' or key == 'Q':
            ret = cb.QUIT_ALARM
        if wgt and key == "Up":
            wgt.select_next_widget(direction_up = True)
        if wgt and key == "Down":
            wgt.select_next_widget(direction_up = False)
        if wgt and key == "Right":
            wgt.increment_addr_location(direction_up = True)
        if wgt and key == "Left":
            wgt.increment_addr_location(direction_up = False)
    return ret

def main_run_sim(args, cb):
    global CoreMem, CommentTab   # should have put this in the CPU Class...
    global UseDebugger, Debugger

    # LAS dup of main
    """
    if args.CrtFadeDelay:
        cb.crt_fade_delay_param = args.CrtFadeDelay
        cb.log.info("CRT Fade Delay set to %d" % cb.crt_fade_delay_param)
    """

    CoreMem = wwinfra.CorememClass(cb)
    cpu = CpuClass(cb, CoreMem)  # instantiating this class instantiates all the I/O device classes as well
    cb.cpu = cpu
    cpu.cpu_switches = wwinfra.WWSwitchClass(cb)
    cb.dbwgt = wwinfra.ScreenDebugWidgetClass(cb, CoreMem, args.AnalogScope)

    cycle_limit = 0  # default limit for number of sim cycles to run; 'zero' means 'forever'
    # crt_fade_delay = 500
    stop_sim = False

    CycleDelayTime = 0
    if args.CycleDelayTime:
        CycleDelayTime = int(args.CycleDelayTime)

    if args.CycleLimit is not None:
        cycle_limit = args.CycleLimit
        cb.log.info ("CycleLimit set to %d" % cycle_limit)

    core_dump_file_name = None
    if args.DumpCoreToFile:
        core_dump_file_name = args.DumpCoreToFile

    if args.RestoreCoreFromFile:
        (a, b, c, d, e, dbwgt) = CoreMem.read_core(args.RestoreCoreFromFile, cpu, cb)
    if args.DrumStateFile:
        cpu.drum.restore_drum_state(args.DrumStateFile)

    if args.MuseumMode:
        cb.museum_mode = mm.MuseumModeClass()
        ns = cb.museum_mode.next_state(cb, cpu, start=True)
        cycle_limit = ns.cycle_limit
        CycleDelayTime = ns.instruction_cycle_delay
        cb.crt_fade_delay_param = ns.crt_fade_delay

    (cpu.SymTab, cpu.SymToAddrTab, JumpTo, WWfile, WWtapeID, dbwgt_list) = \
        CoreMem.read_core(cb.CoreFileName, cpu, cb)
    cpu.set_isa(CoreMem.metadata["isa"])
    if cpu.isa_1950 == False and args.Radar:
        cb.log.fatal("Radar device can only be used with 1950 ISA")

    flowgraph = None
    if args.FlowGraph:
        flowgraph = ww_flow_graph.FlowGraph (args.FlowGraph, args.FlowGraphOutFile, args.FlowGraphOutDir, cb)

    if args.Radar:
                                        # heading is given as degrees from North, counting up clockwise
                                        # name   start x/y   heading  mph  auto-click-time Target-or-Interceptor

        # This target list is optimized to increase spacing of aircraft at the start of the sim to make
        # use of the light-gun easier
        # target_list = [radar_class.AircraftClass('T1',  50.0, -100.0, 340.0, 200.0, 3, 'T'),  # was 3 revolutions
        #                radar_class.AircraftClass('I1',  90.0, -20.0, 350.0, 250.0, 7, 'I'), # was 6 revolutions
        #                radar_class.AircraftClass('T2', -20.0, -80.0,  20.0, 200.0, 0, ''),  # add in a stray aircraft
        #                ]
        target_list = [radar_class.AircraftClass('T1',  40.0, -100.0, 350.0, 200.0, 3, 'T'),  # was 3 revolutions
                       radar_class.AircraftClass('I1', 100.0,  -20.0, 350.0, 250.0, 7, 'I'), # was 6 revolutions
                       radar_class.AircraftClass('T2', -70.0, -100.0,  17.7, 200.0, 0, ''),  # add in a stray aircraft
                       # radar_class.AircraftClass('T3', -110.0, -70.0,  33.0, 200.0, 0, ''),  # add in a stray aircraft
                       ]
        radar = radar_class.RadarClass(target_list, cb, cpu, args.AutoClick)
        # register a callback for anything that accesses Register 0o27 (that's the Light Gun)
        CoreMem.add_tsr_callback(cb, 0o27, radar.mouse_check_callback)
        cb.radar = radar   # put a link to the radar class in cb, so we can use it to decide what kind of axis to draw
    else:
        radar = None

    if len(dbwgt_list):  # configure any Debug Widgets.  Do this before execution, but after all the
                         # infra setup in case we need any optional python classes
        parse_and_save_screen_debug_widgets(cb, dbwgt_list)

    cb.log.info("Switch CheckAlarmSpecial=%o" % cpu.cpu_switches.read_switch("CheckAlarmSpecial"))
    CoreMem.reset_ff(cpu)   # Reset any Flip Flop Registers specified in the Core file
    # set the CPU start address
    if JumpTo is None:
        cpu.PC = 0o40
    else:
        cpu.PC = JumpTo
    if args.JumpTo:
        cpu.PC = int(args.JumpTo, 8)
    print("start at 0o%o" % cpu.PC)

    #if project_exec_init is not None:
    #    project_exec_init(args.AutoClick)

    start_time = time.time()        # use this to compute the total run time for the sim
    checkpoint_time = start_time    # use this to calculate instructions-per-second every X-zillion instructions
    #  Here (soon!) Commences The Main Loop (ok, maybe not quite here, but soon...)
    # simulate each cycle one by one
    sim_cycle = 0
    if cb.panel and not args.QuickStart:
        cb.sim_state = cb.SIM_STATE_STOP
    else:
        cb.sim_state = cb.SIM_STATE_RUN
        cb.first_instruction_after_start = True

    alarm_state = cb.NO_ALARM
    if cb.panel:
        cb.panel.update_panel(cb, 0, init_PC=cpu.PC, alarm_state=alarm_state)  # I don't think we can miss a mouse clicks on this call

    # this was here to debug a panel/no-panel inconsistency
    # print("Dump Switch Values:")
    # cpu.cpu_switches.dump_switches()

    if cb.record_core_info:
        CoreMem.corememinfo = wwinfra.CoreMemInfo (CoreMem)

    # LAS
    if UseDebugger:
        # Refactoring and hoisting up at least the cpu class is something we should
        # do. Here I'm straining to avoid it by passing in myriad functions to the
        # debugger.
        # LAS 10/14/25 That refactoring is done so cleaning this up is on the list.
        if Debugger is None:
            Debugger = DbgDebugger()
        Debugger.reset (CoreMem,
                        cpu.SymToAddrTab,
                        cpu.SymTab,
                        cpu.wwprint_to_str,
                        cpu.get_dbg_line,
                        cpu.opname_to_opcode,
                        cpu.get_reg,
                        cpu.get_inst_info,
                        cpu.update_panel_for_dbg)

    # the main sim loop is enclosed in a try/except so we can clean up from a keyboard interrupt
    # Mostly this doesn't matter...  but the analog GPIO and SPI libraries need to be closed
    # to avoid an error message on subsequent calls
    try:
        if UseDebugger:
            # Handle keyboard interrupts specially during sim, by detecting at
            # a sync point that the interrupt count cpu.kbd_int is non-zero,
            # and doing an alarm breakpoint in the debugger. In this manner we
            # get to interrupt a ww prog in a consistent state.
            def kbd_int_handler (signum, frame):
                cpu.kbd_int += 1
                if cpu.kbd_int > 2:
                    # If user hit ^C more than twice then the sim (not the ww
                    # prog) is probably in a loop so enable the interrupt and
                    # exception
                    signal.signal (signal.SIGINT, signal.default_int_handler)
                    raise KeyboardInterrupt
            signal.signal (signal.SIGINT, kbd_int_handler)
        while True:
            # LAS
            if UseDebugger:
                cpu.kbd_int = 0
                # Detect restart cmd from dbg and set alarm state to quit, so
                # will return to main() and call main_run_sim() again, which
                # should reset everything
                dbgProgContext: DbgProgContext = None
                if alarm_state == cb.NO_ALARM:
                    dbgProgContext = DbgProgContext.Normal
                else:
                    dbgProgContext = DbgProgContext.Alarmed
                restart = Debugger.repl (cpu.PC, dbgProgContext)
                if restart:
                    alarm_state = cb.QUIT_ALARM
                    break
            
            # if the simulation is stopped, we should poll the panel and wait for a start of some wort
            #  The panel_update will set the cpu_state if start or stop buttons are pressed, and will update
            #  the PC to the starting address if needed.
            # When the simulation is not stopped, we do this check below ever n-hundred cycles to keep the
            #  panel overhead in check.
            if cb.sim_state == cb.SIM_STATE_STOP and cb.panel:
                if cb.panel.update_panel(cb, 0, alarm_state=alarm_state) == False:  # just idle here, watching for mouse clicks on the panel
                    alarm_state = cb.QUIT_ALARM
                    break  # bail out of the While True loop if display update says to stop due to Red-X hit
                time.sleep(0.1)
                continue

            #
            if cpu.stop_on_address is not None and cb.first_instruction_after_start == False:
                if cpu.PC == cpu.stop_on_address:
                    cb.log.warn("Stop on PC Preset switches activated")
                    cb.sim_state = cb.SIM_STATE_STOP
                    continue

            # ################### The Simulation Starts Here ###################
            alarm_state = cpu.run_cycle()
            # ################### The Rest is Just Overhead  ###################
            cb.first_instruction_after_start = False # clear this flag to re-enable control panel stop-on-address
            # poll various I/O circumstances, and update the xwin screen
            # Do this less frequently in AnaScope mode, as it slows the Rasp Pi performance,
            # even to check the xwin stuff
            # Set the update interval to a prime number in an attempt to prevent a program
            # loop from synchronizing with the panel update
            update_rate = 511
            if cb.analog_display:
                update_rate = 5003
            if (sim_cycle % update_rate == 0) or args.SynchronousVideo or CycleDelayTime:
                exit_alarm = cb.NO_ALARM
                if cb.panel:
                    if cb.panel.update_panel(cb, 0, alarm_state=alarm_state) == False:  # watch for mouse clicks on the panel
                        exit_alarm = cb.QUIT_ALARM
                    if cb.sim_state == cb.SIM_STATE_READIN:
                        alarm_state = cb.READIN_ALARM
                        break

                exit_alarm |= poll_sim_io(cpu, cb)
                if exit_alarm != cb.NO_ALARM:
                    alarm_state = exit_alarm

            if CycleDelayTime:
                time.sleep(CycleDelayTime/1000)  # Sleep() takes time in fractional seconds

            if args.Radar and (sim_cycle % 30 == 0):
                # the radar should return something every 20 msec, about every thousand instructions.
                # This is **like totally forever**, and I'm not taking it any more!
                # So I'll snoop the radar mailbox.  When the code picks up a new value, it sets the mailbox
                # to -1.  So I'll check *much* more often, but not put something into the mailbox until
                # the last code has been consumed.
                last_code = CoreMem.rd(0o34)
                if last_code == 0o177777:
                    (rcode, reading_name, new_rotation) = radar.get_next_radar()
                    CoreMem.wr(0o34, rcode)
                    if new_rotation:
                        print("\n")
                    if rcode != 0 and (rcode & 0o40000 == 0):
                        if not cb.TraceQuiet or not (" Geo_" in reading_name):
                            print("%s: radar-code=0o%o" % (reading_name, rcode))
                    if radar.exit_alarm != cb.NO_ALARM:
                        alarm_state = radar.exit_alarm

            # if we're doing "single step", then after each instruction, set the state back to Stop
            if cb.sim_state == cb.SIM_STATE_SINGLE_STEP:
                cb.sim_state = cb.SIM_STATE_STOP

            # Different things happen if there's an alarm; if Control Panel. we just switch to sim_stop; if it's cmd-line, exit
            if alarm_state != cb.NO_ALARM:
                cpu.print_alarm_msg (alarm_state)
                # LAS
                if UseDebugger:
                    continue
                if cb.panel:
                    if alarm_state == cb.QUIT_ALARM:   # they said Quit, we'll quit.
                        break
                    if not args.NoAlarmStop:  # here's the state where we hit an alarm, but it's not QUIT
                        cb.sim_state = cb.SIM_STATE_STOP
#                if cb.panel and cb.panel.update_panel(cb, 0, alarm_state=alarm_state) == False:  # watch for mouse clicks on the panel
#                    break
                else:
                    # the normal case with cmd-line wwsim is to stop on an alarm; if the command line flag says not to, we'll try to keep going
                    # Yeah, ok, but don't try to keep going if the alarm is the one where the user clicks the Red X. Sheesh...
                    if not args.NoAlarmStop or \
                            alarm_state == cb.QUIT_ALARM  or alarm_state == cb.HALT_ALARM or alarm_state == cb.READIN_ALARM:
                        break
            sim_cycle += 1
            checkpoint_cycle_interval = 2000000
            if (sim_cycle % checkpoint_cycle_interval) == 0 or alarm_state == cb.QUIT_ALARM:
                now = time.time()       # returns float time in microseconds from the epoch
                interval = now - checkpoint_time  # figure how long since the last checkpoint
                checkpoint_time = now
                cycle_time = interval * 1000000 / checkpoint_cycle_interval
                print("cycle %2.1fM; %4.1f usec/instruction, mem=%dMB" %
                      (sim_cycle / (1000000.0), cycle_time, psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2))
            if cycle_limit and sim_cycle == cycle_limit:
                if not cb.museum_mode:  # this is the normal case, not configured for Museum Mode forever-cycles
                    cb.log.warn("Cycle Count Exceeded")
                    alarm_state = cb.QUIT_ALARM
                    break
                else:  # else continue the simulation with the next set of parameters
                    ns = cb.museum_mode.next_state(cb, cpu)
                    sim_cycle = 0
                    cycle_limit = ns.cycle_limit
                    CycleDelayTime = ns.instruction_cycle_delay
                    cb.crt_fade_delay_param = ns.crt_fade_delay

            if UseDebugger:
                # LAS
                if cpu.kbd_int != 0:
                    alarm_state = cb.KBD_INT_ALARM
                    cpu.print_alarm_msg (alarm_state)

            pass   # Here Ends The Main Loop

    except KeyboardInterrupt:
        print("Keyboard Interrupt: Cleanup and exit")
        alarm_state = cb.QUIT_ALARM

    end_time = time.time()
    wall_clock_time = end_time - start_time  # time in units of floating point seconds
    if wall_clock_time > 2.0 and sim_cycle > 10:  # don't do the timing calculation if the run was really short
        if not cb.TraceQuiet:
            cb.log.raw("Total cycles = %d, last PC=0o%o, wall_clock_time=%d sec, avg time per cycle = %4.1f usec\n" %
                       (sim_cycle, cpu.PC, wall_clock_time, 1000000.0 * float(wall_clock_time) / float(sim_cycle)))
        if args.Radar:
            print("    elapsed radar time = %4.1f minutes (%4.1f revolutions)" %
                  (radar.elapsed_time / 60.0, radar.antenna_revolutions))
    if cb.tracelog:
        title = "%s\\nWWfile: %s" % (cb.CoreFileName, CoreMem.metadata['filename_from_core'])
        flowgraph.finish_flow_graph_from_sim (cb, CoreMem, cpu, title)

    if core_dump_file_name is not None:
        write_core_dump(cb, core_dump_file_name, CoreMem)

    # LAS 10/5/25 Removed log output from these

    for d in cpu.IODeviceList:
        if d.name == "Flexowriter":
            s = d.get_saved_output()
            if len(s):
                # logstr = ""
                print("\nFlexowriter Said:")
                for c in s:
                    sys.stdout.write(c)
                    # logstr += c
                sys.stdout.write("\n")
                # LAS
                """
                cb.log.info ("Begin Flexout:\n" + logstr)
                cb.log.info ("End Flexout")
                """

        if d.name == "Teletype":
            s = d.get_saved_output()
            if len(s):
                # logstr = ""
                print("\nTeletype Said:")
                for c in s:
                    sys.stdout.write(c)
                    # logstr += c
                # LAS
                """
                cb.log.info ("Begin Ttyout:\n" + logstr)
                cb.log.info ("End Ttyout")
                """

        if d.name == "DisplayScope":
            if d.crt is not None:
                if args.NoCloseOnStop:
                    d.crt.get_mouse_blocking()  # wait to see what was on the display in case of a trap
                d.crt.close_display()

        if d.name == "Drum":  # d points to a DrumClass object
            if args.DrumStateFile:
                d.save_drum_state(args.DrumStateFile)

    return (alarm_state, sim_cycle)   # tell the caller why we stopped!

def main():
    global BlinkenLightsModule
    global UseDebugger
    parser = wwinfra.StdArgs().getParser ("Run a Whirlwind Simulation.")
    parser.add_argument("corefile", help="file name of simulation core file")
    parser.add_argument("-t", "--TracePC", help="Trace PC for each instruction", action="store_true")
    parser.add_argument("-a", "--TraceALU", help="Trace ALU for each instruction", action="store_true")
    parser.add_argument("-f", "--FlowGraph", help="Collect data to make a flow graph. Default output file <corefile-base-name>.flow.gv", action="store_true")
    parser.add_argument("-fo", "--FlowGraphOutFile", help="Specify flow graph output file. Implies -f", type=str)
    parser.add_argument("-fd", "--FlowGraphOutDir", help="Specify flow graph output directory. Implies -f", type=str)
    parser.add_argument("-j", "--JumpTo", type=str, help="Sim Start Address in octal")
    parser.add_argument("-q", "--Quiet", help="Suppress run-time messages (nop -- here just for compat)", action="store_true")
    parser.add_argument("-v", "--Verbose", help="Produce run-time messages", action="store_true")
    parser.add_argument("--NoWarnings", help="Suppress Warning messages", action="store_true")
    parser.add_argument("-D", "--DecimalAddresses", help="Display trace information in decimal (default is octal)",
                        action="store_true")
    parser.add_argument("-c", "--CycleLimit", help="Specify how many instructions to run (zero->'forever')", type=int)
    parser.add_argument("--CycleDelayTime", help="Specify how many msec delay to insert after each instruction", type=int)
    parser.add_argument("-r", "--Radar", help="Incorporate Radar Data Source", action="store_true")
    parser.add_argument("--AutoClick", help="Execute pre-programmed mouse clicks during simulation", action="store_true")
    parser.add_argument("--AnalogScope", help="Display graphical output on an analog CRT", action="store_true")
    parser.add_argument("--xWinSize", help="specify the size of an xWinCrt pseudo-scope display in pixels", type=int)
    parser.add_argument("--FlexoWin", help="Display Flexowriter output in its own window", action="store_true")
    parser.add_argument("--NoXWin", help="Don't open any x-windows", action="store_true")
    parser.add_argument("--NoToggleSwitchWarning", help="Suppress warning if WW code writes a read-only toggle switch",
                        action="store_true")
    parser.add_argument("--LongTraceFormat", help="print all the cpu registers in TracePC",
                        action="store_true")
    parser.add_argument("--TraceCoreLocation", help="Trace references to Core Memory Location <n> octal", type=str)
    parser.add_argument("--PETRAfile", type=str,
                        help="File name for photoelectric paper tape reader A input file")
    parser.add_argument("--PETRBfile", type=str,
                        help="File name for photoelectric paper tape reader B input file")
    parser.add_argument("--NoAlarmStop", help="Don't stop on alarms", action="store_true")
    parser.add_argument("--QuickStart", help="Don't wait for the Restart button on the control panel; just go!", action="store_true")
    parser.add_argument("-n", "--NoCloseOnStop", help="Don't close the display on halt", action="store_true")
    parser.add_argument("-p", "--Panel",
                        help="Pop up a Whirlwind Manual Intervention Panel window", action="store_true")
    parser.add_argument("-b", "--BlinkenLights",
                        help="Activate a physical Whirlwind Manual Intervention Panel", action="store_true")
    parser.add_argument("-m", "--MicroWhirlwind",
                        help="Activate the MicroWhirlwind Model", action="store_true")
    parser.add_argument("--NoZeroOneTSR",
                        help="Don't automatically return 0 and 1 for locations 0 and 1", action="store_true")
    parser.add_argument("--SynchronousVideo",
                        help="Display pixels immediately; Disable video caching buffer ", action="store_true")
    parser.add_argument("--CrtFadeDelay",
                        help="Configure Phosphor fade delay (default=0)", type=int)
    parser.add_argument("--DumpCoreToFile",
                        help="Dump the contents of core into the named file at end of run", type=str)
    parser.add_argument("--RestoreCoreFromFile",
                        help="Restore contents of memory from a core dump file", type=str)
    parser.add_argument("--DrumStateFile",
                        help="File to store Persistent state for WW Drum", type=str)
    parser.add_argument("--MuseumMode",
                        help="Cycle through states endlessly for museum display", action="store_true")
    parser.add_argument("-d", "--Debugger",
                        help="Start simulation under the debugger", action="store_true")
    parser.add_argument("--ZeroizeCore",
                        help="Return zero for uninitialized core memory", action="store_true")
    parser.add_argument("-map", "--MemoryMap",
                        help="Produce a memory map (.map) file of the access types during this run", action="store_true")

    args = parser.parse_args()

    UseDebugger = args.Debugger

    quiet = not args.Verbose 
    
    # instantiate the class full of constants
    cb = wwinfra.ConstWWbitClass (corefile=args.corefile, get_screen_size = True, args = args)
    wwinfra.theConstWWbitClass = cb
    cb.log = wwinfra.LogFactory().getLog (quiet=quiet, no_warn=args.NoWarnings)

    # Many args are just slightly transformed and stored in the Universal Bit Bucket 'cb'

    if args.AutoClick:
        cb.argAutoClick = True

    if args.ZeroizeCore:
        cb.ZeroizeCore = True

    if args.BlinkenLights and BlinkenLightsModule == False:
        cb.log.warn("No BlinkenLights Hardware available")

    if args.Panel or args.BlinkenLights or args.MicroWhirlwind:
        cb.panel = control_panel.PanelClass(cb, args.Panel, args.BlinkenLights, args.MicroWhirlwind)

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

    # This command line arg switches graphical output to an analog oscilloscope display
    if args.AnalogScope:
        cb.analog_display = True

    if args.FlexoWin:
        cb.flexo_win = True
        
    if args.NoXWin:
        cb.use_x_win = False
    if args.xWinSize:
        cb.xWin_size_arg = args.xWinSize

    if args.CrtFadeDelay:
        cb.crt_fade_delay_param = args.CrtFadeDelay
        cb.log.info("CRT Fade Delay set to %d" % cb.crt_fade_delay_param)

    cb.TraceQuiet = quiet

    if args.NoZeroOneTSR:
        cb.NoZeroOneTSR = True
    else:
        cb.log.info("Automatically return 0 and 1 from locations 0 and 1")

    if args.TracePC:
        cb.TracePC = -1
    cb.LongTraceFormat = args.LongTraceFormat
    if args.TraceALU:
        cb.TraceALU = True
    if args.TraceCoreLocation:
        cb.TraceCoreLocation = int(args.TraceCoreLocation, 8)
#    if args.FlowGraph:
#        cb.tracelog = ww_flow_graph.FlowGraph.init_log_from_sim()
    cb.decimal_addresses = args.DecimalAddresses  # if set, trace output is expressed in Decimal to suit 1950's chic
    cb.no_toggle_switch_warn = args.NoToggleSwitchWarning
    cb.record_core_info = args.MemoryMap

    # I added colored text to the trace log using ANSI escape sequences.  This works by default with
    # Cygwin xterm, but for DOS Command Shell there's a special command to enable ANSI parsing.
    # The command doesn't seem to exist in xterm, but running it doesn't break anything (yet).
    # LAS 9/5/25 Keyed this on Windows since otherwise we get an unwanted
    # command-not-found error from the shell.
    if "Windows" in platform.platform():
        os.system ("color")

    # This loop runs the main part of the simulator.
    # It's a loop so that it can be restarted from the control panel, if that's in use.
    # When the Control Panel is Not in use, the sim halts with any return of an Alarm.
    # When the control panel _is_ in use, the sim only halts when there's an explicit Quit, e.g.
    # a click of the red box.
    while True:
        (alarm_state, sim_cycle) = main_run_sim(args, cb)
        if (alarm_state == cb.QUIT_ALARM) or (cb.panel is None and alarm_state != cb.NO_ALARM):
            if not cb.TraceQuiet:
                print("Ran %d cycles; Used mem=%dMB" % (sim_cycle, psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2))
            if not UseDebugger:
                break
    if CoreMem.corememinfo is not None:
        CoreMem.corememinfo.writeMapFile()
    
    # sys.exit(alarm_state != cb.NO_ALARM)
    sys.exit(0)         # return zero for an ordinary exit


if __name__ == "__main__":
    main()
