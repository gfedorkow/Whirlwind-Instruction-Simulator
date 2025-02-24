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

DbgProgState = Enum ("DbgProgState", ["Running", "Stepping", "Restarting", "Stopped"])

class DbgDebugger:
    def __init__ (self):
        self.bkptId = 0
        # The bkptid to addr mapping is bijective, and using two dicts seems the simplest way to do it.
        self.bkptIdToAddrTab = {}       # Maps bkpt id to addr
        self.addrToBkptIdTab = {}       # Maps bkpt addr to id
    # If program exits then we want to return to initial dbg stopped state, but
    # breakpoints and other info should be preserved; hence any such state to
    # be preserved must be defined in init.  However we need to get new
    # versions of coremem etc. So the sim must call reset when we restart and
    # pass in the new objects.
    def reset (self,
               coreMem: wwinfra.CorememClass,        # Currently unused
               symToAddrTab: dict,
               addrToSymTab: dict,
               fmtPrinterFcn,
               asmLineFcn,
               getRegFcn,
               getInstStrFcn):
        self.coreMem = coreMem
        self.symToAddrTab = symToAddrTab
        self.addrToSymTab = addrToSymTab
        self.fmtPrinterFcn = fmtPrinterFcn
        self.asmLineFcn = asmLineFcn
        self.getRegFcn = getRegFcn
        self.getInstStrFcn = getInstStrFcn
        self.cb = wwinfra.theConstWWbitClass
        self.env = DbgEnv (self.symToAddrTab, self.getRegFcn)
        self.state = DbgProgState.Stopped
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
    def delBkpt (self, bkptId: int):
        if bkptId in self.bkptIdToAddrTab:
            addr = self.bkptIdToAddrTab[bkptId]
            del self.bkptIdToAddrTab[bkptId]
            del self.addrToBkptIdTab[addr]
    def checkBkpt (self, addr) -> bool:
        return addr in self.addrToBkptIdTab
    def listBkpts (self):
        for bkptId in self.bkptIdToAddrTab:
            print (self.fmtBkpt (bkptId))
    def fmtBkpt (self, bkptId: int) -> str:
        addr = self.bkptIdToAddrTab[bkptId]
        sym = "(" + self.addrToSymTab[addr][0] + ")" if addr in self.addrToSymTab else ""
        return "%d 0o%o%s" % (bkptId, addr, sym)
    # Return True if a restart command was issued
    def repl (self, pc: int) -> bool:
        if not self.checkBkpt (pc) and self.state == DbgProgState.Running:
            return False
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
        self.unevaledPosSet = {}   # Where to expect the unevaled symbols, zero-based
    def postInit (self):
        self.xformLine (self.parsedLine)
    def eval (self) -> [AsmExprValue]:
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.dbg.env, self.parsedLine)
        if val.type != AsmExprValueType.List:
            valList = [val]
        else:
            valList = val.value
        return valList
    def error (self):
        print ("Error!")
        raise DbgException ("")
        pass
    def helpStr (self) -> str:
        return "Help!"
    # Some syntactical hackery transforming the parsed line to suit the
    # eval/non-eval needs of dbg. In-place.
    def xformLine (self, parsedLine: AsmParsedLine):
        self.xformExpr (parsedLine.operand, 0)
    def xformExpr (self, expr: AsmExpr, pos: int):
        if expr.exprType == AsmExprType.BinaryComma:
            if pos in self.unevaledPosSet:
                left = expr.leftSubExpr
                if left.exprType == AsmExprType.Variable:
                    expr.leftSubExpr.exprType = AsmExprType.LiteralString
                else:
                    self.error()
            self.xformExpr (expr.rightSubExpr, pos + 1)
        else:
            if pos in self.unevaledPosSet:
                if expr.exprType == AsmExprType.Variable:
                    expr.exprType = AsmExprType.LiteralString
                else:
                    self.error()
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
            return self.dbg.getInstStrFcn (addr)
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
        self.unevaledPosSet[1] = True
        self.postInit()
        pass
    def helpStr (self) -> str:
        r = (
            "p\t<expr> [, format]\twhere format = o: octal, d: decimal, fr: fraction, fl: 24,6 float, fm: 30,15 float, i: instruction\n" +
            "\t\tprint an address and its contents, or just the value if a register is specfied"
            )
        return r
    def execute (self):
        valList = self.eval()
        if len (valList) >= 1 and len (valList) <= 2:
            exprVal = valList[0]
            if exprVal.type == AsmExprValueType.Integer:
                addr = exprVal.value
                displayContents = exprVal.subType == AsmExprValueSubType.Address
                if len (valList) == 2:
                    fmtVal = valList[1]
                    if fmtVal.type != AsmExprValueType.String:
                        self.error()
                    else:
                        fmt = fmtVal.value
                else:
                    fmt = "o"
                o = self.parsedLine.operand
                if o.exprType == AsmExprType.BinaryComma:
                    expr = o.leftSubExpr
                else:
                    expr = o
                if displayContents:
                    memContentsStr = self.formatMemContents (addr, fmt)
                    print (self.formatAddr (expr, addr, fmt) + " = " + memContentsStr)
                else:
                    print ("%s = %s" % (expr.listingString(), ("%" + fmt) % addr))
            else:
                self.error()
        else:
            self.error()

# pb -- print block
class DbgCmd_pb (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        self.unevaledPosSet[2] = True
        self.postInit()
        pass
    def helpStr (self) -> str:
        r = (
            "pb\t<addr>, <nwords> [, format]\n" +
            "\t\tprint a block of <nwords> starting at <addr>"
            )
        return r
    def execute (self):
        valList = self.eval()
        if len (valList) >= 2 and len (valList) <= 3:
            exprVal = valList[0]
            if exprVal.type == AsmExprValueType.Integer:
                baseAddr = exprVal.value
                nWordsVal = valList[1]
                if nWordsVal.type == AsmExprValueType.Integer:
                    nWords = nWordsVal.value
                    if len (valList) == 3:
                        fmtVal = valList[2]
                        if fmtVal.type != AsmExprValueType.String:
                            self.error()
                        else:
                            fmt = fmtVal.value
                    else:
                        fmt = "o"
                    print (self.formatAddr (self.parsedLine.operand.leftSubExpr, baseAddr, fmt) + ":")
                    for i in range (0, nWords):
                        addr = baseAddr + i
                        memContentsStr = self.formatMemContents (addr, fmt)
                        print ("  " + self.formatAddr (None, addr, fmt) + " = " + memContentsStr)
                else:
                    self.error()
            else:
                self.error()
        else:
            self.error()
        pass

# r -- run
class DbgCmd_r (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStr (self) -> str:
        r = "r\trun program from current pc"
        return r
    def execute (self):
        self.dbg.state = DbgProgState.Running
        pass

# s -- step
class DbgCmd_s (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStr (self) -> str:
        r = "s\tstep program one instruction"
        return r
    def execute (self):
        self.dbg.state = DbgProgState.Stepping
        pass

# rs -- restart
class DbgCmd_rs (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStr (self) -> str:
        r = "rs\trestart program"
        return r
    def execute (self):
        self.dbg.state = DbgProgState.Restarting
        pass

# b -- set breakpoint
class DbgCmd_b (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStr (self) -> str:
        r = (
            "b\t<addr>1,...,<addr>N\n" +
            "\t\tdefine a breakpoint for each given address. Prints breakpoint id and corresponding address"
            )
        return r
    def execute (self):
        valList = self.eval()
        if len (valList) > 0:
            for val in valList:
                if val.type == AsmExprValueType.Integer:
                    addr = val.value
                    if self.dbg.addBkpt (addr):
                        pass
                    else:
                        self.error()
                else:
                    self.error()
        else:
            self.error()

# bd -- delete breakpoint
class DbgCmd_bd (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStr (self) -> str:
        r = (
            "bd\t<bkptid>1,...,<bkptid>N\n" +
            "\t\tdelete breakpoint defined by each given id"
            )
        return r
    def execute (self):
        valList = self.eval()
        if len (valList) > 0:
            for val in valList:
                if val.type == AsmExprValueType.Integer:
                    bkptId = val.value
                    self.dbg.delBkpt (bkptId)
                else:
                    self.error()
        else:
            self.error()

# bl -- list breakpoints
class DbgCmd_bl (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStr (self) -> str:
        r = "bl\tlist breakpoints"
        return r
    def execute (self):
        self.dbg.listBkpts()

# h -- help
class DbgCmd_h (DbgCmd):
    def __init__ (self, *args):
        super().__init__ (*args)
        pass
    def helpStr (self) -> str:
        return "h\tPrint help"
    # Though fairly elegant IMO wrt use of class meta-info, it's a bit hokey
    # having to supply a dummy instruction to parse.
    def execute (self):
        for cls in DbgCmd.__subclasses__():
            className = cls.__name__
            dummyParsedLine = AsmParsedLine ("ca 0", 0)
            dummyParsedLine.parseDbgLine()
            cmd = globals()[className](dummyParsedLine, self.dbg)
            print (cmd.helpStr())

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
    def helpStr (self) -> str:
        return "quit\tExit debugger and simulator"
    def execute (self):
        sys.exit (0)

