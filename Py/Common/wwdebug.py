import os
import sys
import re
import math
import traceback
import argparse
import wwinfra
from enum import Enum
from wwasmparser import AsmExprValue, AsmExprValueType, AsmExprValueSubType, AsmExprEnv, AsmExpr, AsmExprType, AsmParsedLine

class DbgException (Exception):
    pass

class DbgEnv (AsmExprEnv):
    def __init__ (self, table, getRegFcn):
        self.table = table
        self.getRegFcn = getRegFcn
    # Override the default lookup
    def lookup (self, var: str) -> AsmExprValue:
        v: int = self.getRegFcn (var)
        if v is not None:
            # Subtype must be undefined so we don't try to use the value as an address
            return AsmExprValue (AsmExprValueType.Integer, v, subType = AsmExprValueSubType.Undefined)
        elif var in self.table:
            v = self.table[var]
            return AsmExprValue (AsmExprValueType.Integer, v)
        else:
            return AsmExprValue (AsmExprValueType.Undefined, var)

class DbgBrks:
    def __init__ (self, dbg):
        self.dbg = dbg
        self.jumpOpcodes = [0o16, 0o17] # cp, sp
        self.writeOpcodes = [0o10, 0o11, 0o12, 0o15, 0o26] # ts, td, ta, ao, ex
        self.reset()
    def reset (self):
        self.brkTab = {}
        self.idSeq = 0
        self.pcToBrkPtTab = {}
        self.addrToWrBrkTab = {}
        self.addrToRdBrkTab = {}
    def list (self):
        for brkId in self.brkTab:
            brk = self.brkTab[brkId]
            print ("% 3d %s %s" % (brk.id, "disabled" if brk.disabled else "enabled ", brk.listStr()))
    # Note no error if id does not exist. Easier to capture
    # ranges. Doesn't seem worth it to flag those over the max in the table.
    def delete (self, brkId: int):
        if brkId in self.brkTab:
            brk = self.brkTab[brkId]
            brk.delete (brkId)
            del self.brkTab[brkId]
    def deleteAll (self):
        self.reset()
    # No error here or in enable either; see above comment.
    def disable (self, brkId: int):
        if brkId in self.brkTab:
            brk = self.brkTab[brkId]
            brk.disabled = True
    def disableAll (self):
        for brkId in self.brkTab:
            brk = self.brkTab[brkId]
            brk.disabled = True
    def enable (self, brkId: int):
        if brkId in self.brkTab:
            brk = self.brkTab[brkId]
            brk.disabled = False
    def enableAll (self):
        for brkId in self.brkTab:
            brk = self.brkTab[brkId]
            brk.disabled = False
    # Checks for all kinds of breaks
    def checkBrk (self, pc): # Returns subclass of DbgBrk
        if pc in self.pcToBrkPtTab:
            r = self.pcToBrkPtTab[pc]
        else:
            (opcode, short_opcode, address, label) = self.dbg.getInstInfoFcn (pc)
            if opcode in self.writeOpcodes and address in self.addrToWrBrkTab:
                r = self.addrToWrBrkTab[address]
            else:
                r = None
        if r is not None and r.disabled:
            r = None
        return r

class DbgBrk:
    def __init__ (self, brks: DbgBrks):
        self.brks = brks
        self.id = self.brks.idSeq
        self.brks.idSeq += 1
        self.brks.brkTab[self.id] = self
        self.disabled = False
        pass
    def formatLabel (self, addr):
        dbg = self.brks.dbg
        sym = "(" + dbg.addrToSymTab[addr][0] + ")" if addr in dbg.addrToSymTab else ""
        return "0o%o%s" % (addr, sym)

class DbgBrkPt (DbgBrk):
    def __init__ (self, brks: DbgBrks, pc: int):
        if pc not in brks.pcToBrkPtTab:
            super().__init__ (brks)
            self.pc = pc
            self.brks.pcToBrkPtTab[self.pc] = self
    def prompt (self):
        return "Breakpoint:"
    def listStr (self):
        return "break point %s" % self.formatLabel (self.pc)
    def delete (self, brkId: int):
        del self.brks.pcToBrkPtTab[self.pc]

class DbgWriteWatchPt (DbgBrk):
    def __init__ (self, brks: DbgBrks, addr: int):
        super().__init__ (brks)
        self.addr = addr
        self.brks.addrToWrBrkTab[addr] = self
    def prompt (self):
        return "Write breakpoint:"
    def listStr (self):
        return "write watch %s" % self.formatLabel (self.addr)
    def delete (self, brkId: int):
        del self.brks.addrToWrBrkTab[self.addr]

class DbgReadWatchPt (DbgBrk):
    def __init__ (self, brks: DbgBrks, addr: int):
        super().__init__ (brks)
        self.addr = addr
        self.brks.addrToRdBrkTab[addr] = self
    def prompt (self):
        return "Read breakpoint:"
    def listStr (self):
        return "read  watch %s" % self.formatLabel (self.addr)
    def delete (self, brkId: int):
        del self.brks.addrToRdBrkTab[self.addr]

# This state is set by the debugger -- i.e., it's the state of the prog from the debugger's viewpoint
DbgProgState = Enum ("DbgProgState", ["Running", "Stepping", "Restarting", "Stopped"])

# This is the state from the prog's viewpoint. For the debugger we want the
# largest-grain abstraction, so we'll avoid if we can importing the cb.ALARM
# enum.

DbgProgContext = Enum ("DbgProgContext", ["Normal", "Alarmed"])

class DbgDebugger:
    def __init__ (self):
        self.jumpOpcodes = [0o16, 0o17] # cp, sp
        self.writeOpcodes = [0o10, 0o11, 0o12, 0o15, 0o26] # ts, td, ta, ao, ex
        self.formatStrs = ["fl", "fr", "fm", "fx", "i", "o", "d"]
        self.brks = DbgBrks (self)
    # If program exits then we want to return to initial dbg stopped state, but
    # breakpoints and other info should be preserved; hence any such state to
    # be preserved must be defined in init.  However we need to get new
    # versions of coremem etc. So the sim must call reset when we restart and
    # pass in the new objects.
    def reset (self,
               coreMem: wwinfra.CorememClass,
               symToAddrTab: dict,
               addrToSymTab: dict,
               fmtPrinterFcn,
               asmLineFcn,
               getRegFcn,
               getInstInfoFcn):
        self.coreMem = coreMem
        self.symToAddrTab = symToAddrTab
        self.addrToSymTab = addrToSymTab
        self.fmtPrinterFcn = fmtPrinterFcn
        self.asmLineFcn = asmLineFcn
        self.getRegFcn = getRegFcn
        self.getInstInfoFcn = getInstInfoFcn
        self.cb = wwinfra.theConstWWbitClass
        self.env = DbgEnv (self.symToAddrTab, self.getRegFcn)
        self.state = DbgProgState.Stopped
        self.tbStack = {}       # This implements a circular buffer of size tbSize
        self.tbIndex = 0
        self.tbSize = 100
    def checkAddrRange (self, v: int) -> bool:
        return v >= 0 and v <= 0o3777
    def addBkpt (self, addr: int) -> bool:
        if self.checkAddrRange (addr):
            if addr not in self.addrToBkptIdTab:
                self.bkptIdToAddrTab[self.bkptId] = addr
                self.addrToBkptIdTab[addr] = self.bkptId
                print (self.fmtBkpt (self.bkptId))
                self.bkptId += 1
            else:
                bkptId = self.addrToBkptIdTab[addr]
                print (self.fmtBkpt (bkptId))
            return True
        else:
            return False
    def getInstStr (self, addr: int) -> str:
        (opcode, short_opcode, address, label) = self.getInstInfoFcn (addr)
        return "%s 0o%o%s" % (short_opcode, address, label)
    def checkTraceback (self, pc):
        (opcode, short_opcode, address, label) = self.getInstInfoFcn (pc)
        if True: # opcode in self.jumpOpcodes:
            self.tbStack[self.tbIndex] = [pc, opcode, short_opcode, address]
            self.tbIndex = (self.tbIndex + 1) % self.tbSize
    def error (self):
        print ("Error!")
        # traceback.print_stack()
        raise DbgException ("")
        pass
    # Return True if a restart command was issued
    def repl (self, pc: int) -> bool:
        self.checkTraceback (pc)
        if self.state == DbgProgState.Running:
            brk = self.brks.checkBrk (pc)
            if brk is None:
                return False
            else:
                print (brk.prompt())
        print (self.asmLineFcn (pc))
        while True:
            s = input ("dbg %o> " % pc)
            if s == "quit":
                sys.exit (0)
            elif s == "":
                self.state = DbgProgState.Stepping
                return False
            else:
                try:
                    parsedLine = AsmParsedLine (s, 0)
                    status = parsedLine.parseDbgLine()
                    if status:
                        # parsedLine.print()
                        cmdClassName = "DbgCmd_" + parsedLine.opname
                        if cmdClassName in globals():
                            self.state = DbgProgState.Stopped
                            cmd = globals()[cmdClassName](parsedLine, self)
                            # valList = cmd.eval()
                            # for val in valList: print (val.asString())
                            cmd.execute()
                            if self.state in [DbgProgState.Running, DbgProgState.Stepping, DbgProgState.Restarting]:
                                break
                        else:
                            print ("Unknown command")
                except DbgException as e:
                    continue
        if self.state == DbgProgState.Restarting:
            self.state = DbgProgState.Running
            return True
        else:
            return False;
        pass

class DbgCmd:
    def __init__ (self, parsedLine: AsmParsedLine, dbg: DbgDebugger):
        self.parsedLine = parsedLine        # Contains opname and operands
        self.dbg = dbg
    def eval (self) -> [AsmExprValue]:
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.dbg.env, self.parsedLine)
        if val.type == AsmExprValueType.Undefined:
            valList = []
        elif val.type != AsmExprValueType.List:
            valList = [val]
        else:
            valList = val.value
        return valList
    def error (self):
        self.dbg.error()
    def helpStrs (self) -> [str]:
        return ["Help!"]
    # Run fcn on each expr in the comma-expr.
    # Signature of fcn is fcn (expr: AsmExpr, pos: int)
    # Nop if it's not a comma-expr.
    def walkCommaExpr (self, exprIn: AsmExpr, fcn):
        if exprIn.exprType == AsmExprType.BinaryComma:
            expr = exprIn
            pos = 0
            while True:
                if expr.exprType == AsmExprType.BinaryComma:
                    left = expr.leftSubExpr
                    fcn (left, pos)
                    expr = expr.rightSubExpr
                    pos += 1
                else:
                    # Assume here that a null expr is considered a "terminator"
                    # and is not of interest
                    if expr.exprType != AsmExprType.Null:
                        fcn (expr, pos)
                    return
        pass
    def formatAddr (self, expr: AsmExpr, addr: int, fmtIn: str) -> str:
        fmt = fmtIn if fmtIn in ["o", "d"] else "o"
        if expr is None:
            exprStr = ""
        else:
            exprStr = "(" + expr.listingString() + ")"
        r = ("0" + fmt + "%" + fmt + exprStr) % addr
        return r
    def formatMemContents (self, addr: int, fmt: str) -> str:
        if fmt == "i":
            return self.dbg.getInstStr (addr)
        else:
            if self.dbg.checkAddrRange (addr):
                r = self.dbg.fmtPrinterFcn ("\"%" + fmt + "\"," + ("0o%o" % addr))
            else:
                r = "<addr-out-of-range>"
        return r

# p -- print 
class DbgCmd_p (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        self.walkCommaExpr (self.parsedLine.operand, self.setFormatFcn)
        pass
    def helpStrs (self) -> [str]:
        r = [
            "p expr [, block-len] [, format]",
            "Format = o: octal, d: decimal, fr: fraction, fl: 24,6 float, fm: 30,15 float, fx: flexo-to-ascii, i: instruction.",
            "Print an address or block and its contents, or just the value if a register is specfied.",
            "Default format is octal."
            ]
        return r
    def setFormatFcn (self, expr: AsmExpr, pos: int):
        if pos != 0:
            if expr.exprType == AsmExprType.Variable:
                if expr.exprData in self.dbg.formatStrs:
                    expr.exprType = AsmExprType.LiteralString
    def execute (self):
        valList = self.eval()
        doBlk = False
        fmt = "o"
        blkLen = 0
        if len (valList) >= 1 and len (valList) <= 3:
            exprVal = valList[0]
            if exprVal.type == AsmExprValueType.Integer:
                addr = exprVal.value
                displayContents = exprVal.subType == AsmExprValueSubType.Address
            else:
                self.error()
            if len (valList) == 2:
                fmtOrBlkLenVal = valList[1]
                if fmtOrBlkLenVal.type == AsmExprValueType.String:
                    fmt = fmtOrBlkLenVal.value
                    if fmt not in self.dbg.formatStrs:
                        self.error()
                elif fmtOrBlkLenVal.type == AsmExprValueType.Integer:
                    blkLen = fmtOrBlkLenVal.value
                    doBlk = True
                else:
                    self.error()
            elif len (valList) == 3:
                blkLenVal = valList[1]
                if blkLenVal.type == AsmExprValueType.Integer:
                    blkLen = blkLenVal.value
                    doBlk = True
                else:
                    self.error()
                fmtVal = valList[2]
                if fmtVal.type == AsmExprValueType.String:
                    fmt = fmtVal.value
                    if fmt not in self.dbg.formatStrs:
                        self.error()
                else:
                    self.error()
            o = self.parsedLine.operand
            if o.exprType == AsmExprType.BinaryComma:
                expr = o.leftSubExpr
            else:
                expr = o
            if doBlk:
                baseAddr = addr
                print (self.formatAddr (self.parsedLine.operand.leftSubExpr, baseAddr, fmt) + ":")
                for i in range (0, blkLen):
                    curAddr = baseAddr + i
                    memContentsStr = self.formatMemContents (curAddr, fmt)
                    print ("  " + self.formatAddr (None, curAddr, fmt) + " = " + memContentsStr)
            else:
                if displayContents:
                    memContentsStr = self.formatMemContents (addr, fmt)
                    print (self.formatAddr (expr, addr, fmt) + " = " + memContentsStr)
                else:
                    print ("%s = %s" % (expr.listingString(), ("%" + fmt) % addr))
        else:
            self.error()

# r -- run
class DbgCmd_r (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = ["r", "Run program from current pc"]
        return r
    def execute (self):
        self.dbg.state = DbgProgState.Running
        pass

# s -- step
class DbgCmd_s (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = ["s", "Step program one instruction. Typing carriage-return does this too."]
        return r
    def execute (self):
        self.dbg.state = DbgProgState.Stepping
        pass

# rs -- restart
class DbgCmd_rs (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = ["rs", "Restart program"]
        return r
    def execute (self):
        self.dbg.state = DbgProgState.Restarting
        pass

# b -- set breakpoint
class DbgCmd_b (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = [
            "b addr1,...,addrN",
            "Define a breakpoint for each given address. Prints id and corresponding address."
            ]
        return r
    def execute (self):
        valList = self.eval()
        if len (valList) > 0:
            for val in valList:
                if val.type == AsmExprValueType.Integer:
                    addr = val.value
                    DbgBrkPt (self.dbg.brks, addr)
                else:
                    self.error()
        else:
            self.error()

# bl -- list breakpoints
class DbgCmd_bl (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = ["bl", "List breakpoints and watchpoints."]
        return r
    def execute (self):
        self.dbg.brks.list()

class DbgRangeCmd (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        self.rangeList: [[int, int]] = []
        self.all = False
    def parseRange (self, expr: AsmExpr, pos: int):
        if expr.exprType == AsmExprType.Variable:
            if expr.exprData == "all":
                self.all = True
            else:
                error()
        elif expr.exprType == AsmExprType.LiteralDigits:
            v = int (expr.exprData)
            self.rangeList.append ([v, v])
        elif expr.exprType == AsmExprType.BinaryMinus:
            if expr.leftSubExpr.exprType == AsmExprType.LiteralDigits:
                if expr.rightSubExpr.exprType == AsmExprType.LiteralDigits:
                    self.rangeList.append ([int (expr.leftSubExpr.exprData), int (expr.rightSubExpr.exprData)])
                else:
                    self.error()
            else:
                self.error()
        else:
            self.error()
    def parseRanges (self):
        self.all = False
        expr = self.parsedLine.operand
        if expr.exprType != AsmExprType.BinaryComma:
            commaExpr = AsmExpr (AsmExprType.BinaryComma, "")
            commaExpr.leftSubExpr = expr
            commaExpr.rightSubExpr = AsmExpr (AsmExprType.Null, "")
        else:
            commaExpr = expr
        self.walkCommaExpr (commaExpr, self.parseRange)
    def operate (self, id):  # id is int or True, where True means all
        self.error ("Subclass responsibility")
    def execute (self):
        self.parseRanges()
        if self.all:
            self.operate (-1)
        else:
            for r in self.rangeList:
                for i in range (r[0], r[1] + 1):
                    self.operate (i)

# bd -- delete breakpoint
class DbgCmd_bd (DbgRangeCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = [
            "bd id-range1,...,id-rangeN",
            "id-range = id-num | id-num1 - id-num2 | all",
            "Delete breakpoint or watchpoint defined by each given id, id range, or all.",
            "E.g.:",
            "bd 0-4, 7, 8-10",
            "bd all"
            ]
        return r
    def operate (self, id):
        if id == -1:
            self.dbg.brks.deleteAll()
        else:
            self.dbg.brks.delete (id)

# bdis -- disable breakpoint
class DbgCmd_bdis (DbgRangeCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = [
            "bdis id-range1,...,id-rangeN",
            "Disable breakpoint or watchpoint defined by each given id, id range, or all."
            ]
        return r
    def operate (self, id):
        if id == -1:
            self.dbg.brks.disableAll()
        else:
            self.dbg.brks.disable (id)

# ben -- enable breakpoint
class DbgCmd_ben (DbgRangeCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = [
            "bden id-range1,...,id-rangeN",
            "Enable breakpoint or watchpoint defined by each given id, id range, or all."
            ]
        return r
    def operate (self, id):
        if id == -1:
            self.dbg.brks.enableAll()
        else:
            self.dbg.brks.enable (id)

# tb -- traceback
class DbgCmd_tb (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = [
            "tb [n-insts]",
            "Traceback: history of instructions, latest at the bottom.",
            "Prints n-insts; default (and max) is %d." % self.dbg.tbSize
            ]
        return r
    def execute (self):
        valList = self.eval()
        if len (valList) == 1:
            val = valList[0]
            if val.type == AsmExprValueType.Integer:
                n = val.value
                if n < 0:
                    self.error()
                elif n > self.dbg.tbSize:
                    n = self.dbg.tbSize
            else:
                self.error()
        elif len (valList) > 1:
            self.error()
        else:
            n = self.dbg.tbSize
        stack = self.dbg.tbStack
        maxLabelLen = 0
        printInfo = []
        i = (self.dbg.tbIndex - n) % self.dbg.tbSize
        for j in range (0, n):
            if i in stack:
                e = stack[i]
                (pc, opcode, short_opcode, addr) = e
                addrLabel = ("0o%o" % addr) + (("(" + self.dbg.addrToSymTab[addr][0] + ")") if addr in self.dbg.addrToSymTab else "")
                instStr = "%s %s" % (short_opcode, addrLabel)
                label = ("0o%o" % pc) + (("(" + self.dbg.addrToSymTab[pc][0] + ")") if pc in self.dbg.addrToSymTab else "")
                labelLen = len (label)
                maxLabelLen = max (maxLabelLen, labelLen)
                printInfo.append ([instStr, pc, label, labelLen])
            i = (i + 1) % self.dbg.tbSize
        for p in printInfo:
            (instStr, pc, label, labelLen) = p
            print ("%s: %s%s" % (label, " "*(maxLabelLen - len (label)), instStr))

# wwr -- watch write
class DbgCmd_wwr (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = [
            "wwr addr1, ..., addrN",
            "Watch for memory write. When any write instruction (ts, td, ta, ao, ex)",
            "is executed which writes at one of the given addresses, break.",
            "Prints watchpoint id and corresponding address."
            ]
        return r
    def execute (self):
        valList = self.eval()
        if len (valList) > 0:
            for val in valList:
                if val.type == AsmExprValueType.Integer:
                    addr = val.value
                    DbgWriteWatchPt (self.dbg.brks, addr)
                else:
                    self.error()
        else:
            self.error()

# wr -- write mem loc
class DbgCmd_wr (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        r = [
            "wr address, value",
            "Writes value into the memory at address.",
            "Address and value must be integer expressions."
            ]
        return r
    def execute (self):
        valList = self.eval()
        if len (valList) == 2:
            addrVal = valList[0]
            if addrVal.type == AsmExprValueType.Integer:
                addr = addrVal.value
                if self.dbg.checkAddrRange (addr):
                    contentsVal = valList[1]
                    if contentsVal.type in [AsmExprValueType.Integer]:
                        val = contentsVal.value
                        self.dbg.coreMem.wr (addr, val)
                    else:
                        self.error()
                else:
                    self.error ("Address out of range")
            else:
                self.error()
        else:
            self.error()
            
# h -- help
class DbgCmd_h (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        self.helpEntries = []
        self.maxInitStrLen = 0
        self.dummyParsedLine = AsmParsedLine ("ca 0", 0)
        self.dummyParsedLine.parseDbgLine()
        pass
    def helpStrs (self) -> [str]:
        return ["h", "Print help"]
    def buildHelpEntries (self, cls) -> []:
        subs = cls.__subclasses__()
        if len (subs) == 0:
            className = cls.__name__
            cmd = globals()[className](self.dummyParsedLine, self.dbg)
            s = cmd.helpStrs()
            self.maxInitStrLen = max (self.maxInitStrLen, len (s[0]))
            self.helpEntries.append (s)
        else:
            for sub in subs:
                self.buildHelpEntries (sub)
    # Though fairly elegant IMO wrt use of class meta-info, it's a bit hokey
    # having to supply a dummy instruction to parse.
    def execute (self):
        self.buildHelpEntries (DbgCmd)
        for entry in self.helpEntries:
            print ("%s" % entry[0])
            entry.pop (0)
            for t in entry:
                print ("%s%s" % (" "*(self.maxInitStrLen//3), t))
                pass

# Right now this is just a laboratory curiosity. I'd prefer at the moment to
# have only the short commands.
#
# Define a class as a subclass of another cmd and it implements an alias to the
# superclass cmd. So it's an easy way within the class structure to add
# aliases/synonyms for commands.
            
class DbgCmd_help (DbgCmd_h):
    pass

# quit -- Exit
# This command is only in long form since it's easy to type q by accident
class DbgCmd_quit (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStrs (self) -> [str]:
        return ["quit", "Exit debugger and simulator"]
    def execute (self):
        sys.exit (0)

