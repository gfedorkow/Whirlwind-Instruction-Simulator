import os
import sys
import re
import math
import traceback
import argparse
import wwinfra
from enum import Enum
from wwasmparser import AsmExprValue, AsmExprValueType, AsmExprEnv, AsmExpr, AsmExprType, AsmParsedLine
from wwflex import FlasciiToFlex

AsmOperandType = Enum ("AsmOperandType", ["None",       # it's a pseudo-op
                                          "Jump",       # the address is a jump target
                                          "WrData",     # the instruction writes to address 
                                          "RdData",     # the instruction reads from address 
                                          "RdWrData",   # the instruction reads and writes from/to address
                                          "Param"])     # the operand isn't an address at all

class OpCodeInfo:
    def __init__ (self, opcode: int, type: AsmOperandType):
        self.opcode = opcode
        self.opcodeWitdth: int = None   # subclass def
        self.type = type
        self.className = AsmWwOpInst
        
class FiveBitOpCodeInfo (OpCodeInfo):
    def __init__ (self, opcode: int, type: AsmOperandType):
        super().__init__ (opcode, type)
        self.opcodeWidth = 5

class SiOpCodeInfo (FiveBitOpCodeInfo):
    def __init__ (self, opcode: int, type: AsmOperandType):
        super().__init__ (opcode, type)
        self.className = AsmWwSiOpInst

class SevenBitOpCodeInfo (OpCodeInfo):
    def __init__ (self, opcode: int, type: AsmOperandType):
        super().__init__ (opcode, type)
        self.opcodeWidth = 7
        
class CsiiOpCodeInfo (OpCodeInfo):
    def __init__ (self, opcode: int, type: AsmOperandType):
        super().__init__ (opcode, type)

class OpCodeTables:
    def __init__ (self):
        #
        # These tables map an opname to an opcode and related info.
        #
        self.op_code_1958 = { # 
                "si":  SiOpCodeInfo       (0o000, AsmOperandType.Param),
        "<unused01>":  FiveBitOpCodeInfo  (0o001, AsmOperandType.Param),
                "bi":  FiveBitOpCodeInfo  (0o002, AsmOperandType.WrData),
                "rd":  FiveBitOpCodeInfo  (0o003, AsmOperandType.Param),
                "bo":  FiveBitOpCodeInfo  (0o004, AsmOperandType.RdData),
                "rc":  FiveBitOpCodeInfo  (0o005, AsmOperandType.Param),
                "sd":  FiveBitOpCodeInfo  (0o006, AsmOperandType.RdData),
                "cf":  FiveBitOpCodeInfo  (0o007, AsmOperandType.Param),
                "ts":  FiveBitOpCodeInfo  (0o010, AsmOperandType.WrData),
                "td":  FiveBitOpCodeInfo  (0o011, AsmOperandType.WrData),
                "ta":  FiveBitOpCodeInfo  (0o012, AsmOperandType.WrData),
                "ck":  FiveBitOpCodeInfo  (0o013, AsmOperandType.RdData),
                "ab":  FiveBitOpCodeInfo  (0o014, AsmOperandType.WrData),
                "ex":  FiveBitOpCodeInfo  (0o015, AsmOperandType.RdWrData),
                "cp":  FiveBitOpCodeInfo  (0o016, AsmOperandType.Jump),
                "sp":  FiveBitOpCodeInfo  (0o017, AsmOperandType.Jump),
                "ca":  FiveBitOpCodeInfo  (0o020, AsmOperandType.RdData),
                "cs":  FiveBitOpCodeInfo  (0o021, AsmOperandType.RdData),
                "ad":  FiveBitOpCodeInfo  (0o022, AsmOperandType.RdData),
                "su":  FiveBitOpCodeInfo  (0o023, AsmOperandType.RdData),
                "cm":  FiveBitOpCodeInfo  (0o024, AsmOperandType.RdData),
                "sa":  FiveBitOpCodeInfo  (0o025, AsmOperandType.RdData),
                "ao":  FiveBitOpCodeInfo  (0o026, AsmOperandType.RdWrData),
                "dm":  FiveBitOpCodeInfo  (0o027, AsmOperandType.RdData),
                "mr":  FiveBitOpCodeInfo  (0o030, AsmOperandType.RdData),
                "mh":  FiveBitOpCodeInfo  (0o031, AsmOperandType.RdData),
                "dv":  FiveBitOpCodeInfo  (0o032, AsmOperandType.RdData),
               "slr":  SevenBitOpCodeInfo (0o154, AsmOperandType.Param),
               "slh":  SevenBitOpCodeInfo (0o155, AsmOperandType.Param),
               "srr":  SevenBitOpCodeInfo (0o160, AsmOperandType.Param),
               "srh":  SevenBitOpCodeInfo (0o161, AsmOperandType.Param),
                "sf":  FiveBitOpCodeInfo  (0o035, AsmOperandType.WrData),
               "clc":  SevenBitOpCodeInfo (0o170, AsmOperandType.Param),
               "clh":  SevenBitOpCodeInfo (0o171, AsmOperandType.Param),
                "md":  FiveBitOpCodeInfo  (0o037, AsmOperandType.RdData),
               "ica":  CsiiOpCodeInfo     (0o037, AsmOperandType.RdData),
               "imr":  CsiiOpCodeInfo     (0o037, AsmOperandType.RdData),
                "IN":  CsiiOpCodeInfo     (0o037, AsmOperandType.RdData),
               "isp":  CsiiOpCodeInfo     (0o037, AsmOperandType.RdData),
               "its":  CsiiOpCodeInfo     (0o037, AsmOperandType.RdData),
               "OUT":  CsiiOpCodeInfo     (0o037, AsmOperandType.RdData)
            }

        self.op_code_1950 = { #
                "ri":  FiveBitOpCodeInfo (0o00, AsmOperandType.Param),
                "rs":  FiveBitOpCodeInfo (0o01, AsmOperandType.Param),
                "rf":  FiveBitOpCodeInfo (0o02, AsmOperandType.WrData),
                "rb":  FiveBitOpCodeInfo (0o03, AsmOperandType.Param),
                "rd":  FiveBitOpCodeInfo (0o04, AsmOperandType.RdData),
                "rc":  FiveBitOpCodeInfo (0o05, AsmOperandType.Param),
                "qh":  FiveBitOpCodeInfo (0o06, AsmOperandType.Param),
                "qd":  FiveBitOpCodeInfo (0o07, AsmOperandType.Param),
                "ts":  FiveBitOpCodeInfo (0o10, AsmOperandType.WrData),
                "td":  FiveBitOpCodeInfo (0o11, AsmOperandType.WrData),
                "ta":  FiveBitOpCodeInfo (0o12, AsmOperandType.WrData),
                "ck":  FiveBitOpCodeInfo (0o13, AsmOperandType.RdData),
                "qf":  FiveBitOpCodeInfo (0o14, AsmOperandType.Param),  # guy made up the 0o14 op-code; I don't know what code they assigned
                "qe":  FiveBitOpCodeInfo (0o15, AsmOperandType.RdWrData),
                "cp":  FiveBitOpCodeInfo (0o16, AsmOperandType.Jump),
                "sp":  FiveBitOpCodeInfo (0o17, AsmOperandType.Jump),
                "ca":  FiveBitOpCodeInfo (0o20, AsmOperandType.RdData),
                "cs":  FiveBitOpCodeInfo (0o21, AsmOperandType.RdData),
                "ad":  FiveBitOpCodeInfo (0o22, AsmOperandType.RdData),
                "su":  FiveBitOpCodeInfo (0o23, AsmOperandType.RdData),
                "cm":  FiveBitOpCodeInfo (0o24, AsmOperandType.RdData),
                "sa":  FiveBitOpCodeInfo (0o25, AsmOperandType.RdData),
                "ao":  FiveBitOpCodeInfo (0o26, AsmOperandType.RdWrData),
        "<unused05>":  FiveBitOpCodeInfo (0o27, AsmOperandType.Param),
                "mr":  FiveBitOpCodeInfo (0o30, AsmOperandType.RdData),
                "mh":  FiveBitOpCodeInfo (0o31, AsmOperandType.RdData),
                "dv":  FiveBitOpCodeInfo (0o32, AsmOperandType.RdData),
                "sl":  FiveBitOpCodeInfo (0o33, AsmOperandType.Param),
                "sr":  FiveBitOpCodeInfo (0o34, AsmOperandType.Param),
                "sf":  FiveBitOpCodeInfo (0o35, AsmOperandType.WrData),
                "cl":  FiveBitOpCodeInfo (0o36, AsmOperandType.Param),
                "md":  FiveBitOpCodeInfo (0o37, AsmOperandType.RdData)
            }

        # LAS 12/5/24
        #
        # Regarding .pp, We should support it as our way of denoting an assembly-time
        # variable. But we don't need to duplicate the "=" syntax so I'll propose
        # standard comma notation, e.g.
        #
        #                       .pp MAX_POS_COORD, 0o076040
        #
        # The model in csii did not use an explicit pseudo-op, but a naming convention
        # where you could say e.g.:
        #
        #                       pp1=420
        #                       sp ppl
        #       which is eqv to:
        #                       sp 420
        #
        # We don't need to implement this unless we want to process code verbatim.
        # 
        # Regarding ditto: we can implement ditto as in csii but we'll call it ".ditto"
        # to remain true to the rest of the syntax. However again it's not clear
        # whether this needs to be supported as-is.  Also there are simpler ways to add
        # block allocation to the current assembler, e.g.:
        #
        #                       .words 42, 0o5757
        #
        # could allocate 42 words filled with 0o5757.

        # Map the pseudo-op code to the class handling it.
        # The "dot" in each of these is parsed as an operator and so does not appear in the table

        self.meta_op_code = {
          "org": AsmDotOrgInst,
        "daorg": AsmDotDaOrgInst,       # Drum Address Origin -- generates warning, don't know what to do yet
         "base": AsmDotBaseInst,        # Deprecated -- will generate warning
         "word": AsmDotWordInst,
        "words": AsmDotWordsInst,
        "float": AsmDotFloatInst,
        "flexl": AsmDotFlexlhInst,
        "flexh": AsmDotFlexlhInst,
       "switch": AsmDotSwitchInst,
       "jumpto": AsmDotJumpToInst,
        "dbwgt": AsmDotDbwgtInst,
      "ww_file": AsmDotWwFilenameInst,
    "ww_tapeid": AsmDotWwTapeIdInst,
          "isa": AsmDotIsaInst,         # Directive to switch to the older 1950 instruction set
         "exec": AsmDotExecInst,
        "print": AsmDotPrintInst,
           "pp": AsmDotPpInst,
      "include": AsmDotIncludeInst      # Include the text of another ww file
            }

class AsmXrefEntry:
    def __init__ (self):
        self.readByStr = ""
        self.writtenByStr = ""
        self.jumpedToByStr = ""
        self.AtAddrStr = ""
        self.annotateIoStr = ""     # Not really an xref items but looks like a good place for it
    def listingString (self):
        r = self.annotateIoStr
        if self.writtenByStr == "" and self.readByStr == "" and self.jumpedToByStr == "":
            r += ""
        else:
            r += "@@"
            if self.writtenByStr != "":
                r += "WrittenBy " + self.writtenByStr
            if self.readByStr != "":
                r += "ReadBy " + self.readByStr
            if self.jumpedToByStr != "":
                r += "JumpedToBy " + self.jumpedToByStr
        return r

class AsmInst:
    def __init__ (self, parsedLine: AsmParsedLine, prog):   # Should be prog: AsmProgram -- python is stupid
        self.cb = wwinfra.theConstWWbitClass
        self.parsedLine = parsedLine
        self.prog = prog
        self.xrefs = AsmXrefEntry()
        # self.opcode: int = None       # Subclass def
        # self.pseudoOp: str = None     # Subclass def
        # def passOneOp (self):         # Subclass def
        # def passTwoOp (self):         # Subclass def
        self.instruction: int = 0       # 16 bits, may be a ww instruction or data
        self.address: int = self.prog.nextCoreAddress   # All instructions even pseudo-ops get an address
        self.prog.coreToInst[self.address] = self
        self.relativeAddressBase: int = 0
        # If it has a label, record it
        if self.parsedLine.label != "":
            self.prog.labelTab.insert (parsedLine.label, self)
        # If it has a comment, record it
        if self.parsedLine.comment != "":
            self.prog.commentTab[self.address] = self.parsedLine.comment
    #
    # Given an int detect sign and range and generate a 16-bit one's complement
    # representation.
    #
    # Note if x is positive, and we wish to represent -x, then
    #
    #   representation[-x] == 2^n - 1 - x (mod 2^n), where n is the bit length.
    #
    # Thus we use maxUnsignedWord which here is 2^16 - 1 and do the subtract of the
    # negation, or just maxUnsignedWord + x. Since we're checking range there will
    # be no overflow and thus no need to compute mod 2^n. This is all in the
    # spirit of keeping this calc in a more number-theoretic form at this
    # level, and not relying on bit-twiddling.
    #
    def intToSignedWwInt (self, x: int) -> int:
        if x >= -self.prog.maxSignedWordMag and x <= self.prog.maxSignedWordMag:
            if x < 0:
                r = self.prog.maxUnsignedWord + x  # One's-complement representation
            else:
                r = x
            return r
        else:
            self.error ("Signed integer conversion of %d is out of 16-bit one's-complement range" % x)
    #
    # Given an int check for positive 16-bit unsigned range and generate an
    # unsigned 16-bit value (identity function)
    #
    def intToUnsignedWwInt (self, x: int) -> int:
        if x >= 0 and x <= self.prog.maxUnsignedWord:
            return x
        else:
            self.error ("Unsigned integer conversion of %d (= 0o%o) is out of 16-bit unsigned range" % (x, x))
    #
    # Convert host int x to one's complement given the total bit size (i.e., including sign) nbits
    #
    def intToSignedOnesCompInt (self, x: int, nbits: int) -> int:
        maxmag = 2**(nbits-1)
        if x >= -maxmag and x <= maxmag:
            if x < 0:
                r = 2**nbits - 1 + x  # One's-complement representation
            else:
                r = x
            return r
        else:
            # self.error ("Signed integer conversion of %d is out of %d-bit one's-complement range" % (x, nbits))
            # LAS This error is too obscure so we'll punt up a level
            return None

    def error (self, msg: str):
        sys.stdout.flush()
        """
        traceback.print_stack()
        sys.stdout.flush()
        sys.stderr.flush()
        """
        self.cb.log.error (self.parsedLine.lineNo, "%s:\n%s" % (msg, self.parsedLine.lineStr))
        pass
    def fatalError (self, msg: str):
        sys.stdout.flush()
        """
        traceback.print_stack()
        sys.stdout.flush()
        sys.stderr.flush()
        """
        self.cb.log.fatal ("line: %d, %s:\n%s" % (self.parsedLine.lineNo, msg, self.parsedLine.lineStr))
        pass
    def operandTypeError (self, val: AsmExprValue):
        # Grab the undefined error as it's too noisy, e.g., always comes with unbound var.
        if val.type != AsmExprValueType.Undefined:
            self.error ("Incorrect operand type %s" % val.asString())
    def addrRangeError (self, addr: int):
        self.error ("Address 0o%o out of range" % addr)
    # Return a string for the prefix address, perhaps with decimal addresses and perhaps with content
    def fmtPrefixAddrStr (self, address: int,
                          contents: int = None) -> str:
        da = self.cb.decimal_addresses
        daStr = ".%04d" % address if da else ""
        if contents is not None:
            return ("@%04o" + daStr + ":%06o") % (address, contents)
        else:
            return (" "*5 + " "*len (daStr) + " "*7)
    def opnamePrefix (self):
        return ""
    # Look for semicolons and justify
    # LAS 4/3/25 This and listingString() have a lot of hacks and should be replaced by a proper FSM scanner
    def formatComment (self, comment: str, inst: str) -> (str, int):
        nSemis = 0
        cw = self.prog.commentWidth
        if cw == 0:
            r = comment
        else:
            cc = self.prog.labelTab.maxLabelLen + self.prog.commentColumn
            initCc = self.prog.commentColumn - 1
            l = len(comment)
            s = ""
            r = ""
            for i in range (0, l):
                if comment[i] == ';':
                    s = s.rstrip (" ")
                    if nSemis == 0 and inst == "":
                        n = initCc - len (s)
                    else:
                        n = cw - len (s)
                    nSemis += 1
                    if n < 0:
                        n = 1
                    r += s + " "*n + ";"
                    s = ""
                elif i == l - 1:
                    s += comment[i]
                    r += s
                else:
                    s += comment[i]
        return (r, nSemis)
    def listingString (self,
                       quoteStrings: bool = True,
                       minimalListing: bool = False,
                       omitUnrefedLabels: bool = False,
                       omitAutoComment: bool = False) -> str:
        p = self.parsedLine
        sp = " "
        if p.dotIfExpr is not None:
            dotIf = ".if " + p.dotIfExpr.listingString() + sp
        else:
            dotIf = ""
        prefixAddr = self.prefixAddrStr() if not minimalListing else ""
        autoComment = self.xrefs.listingString() if not minimalListing and not omitAutoComment else ""
        maxLabelLen = self.prog.labelTab.maxLabelLen
        commentWidth = self.prog.commentWidth
        if omitUnrefedLabels and p.label not in self.prog.labelRef:
            plabel = ""
        else:
            plabel = p.label
        sp1 = sp*(maxLabelLen - len (plabel) - len (dotIf))
        label = "%s%s" % (sp1, plabel) + (":" if plabel != "" else sp)
        inst = self.opnamePrefix() + p.opname + (sp + p.operand.listingString (quoteStrings = quoteStrings)) if p.operand is not None else ""
        (comment, nSemis) = self.formatComment (p.comment, inst)
        s1 = prefixAddr + sp + dotIf + label + sp 
        s2 = s1 + inst
        commentColumn = len (s1) + self.prog.commentColumn
        sp2 = sp*(commentColumn - len (s2)) if p.label != "" or p.opname != "" else ""
        s3 = (sp2 + ";" + comment + " " + autoComment) if comment + autoComment != "" else ""
        return (s2 + s3).rstrip (" ")

class AsmWwOpInst (AsmInst):
    def __init__ (self, *args):
        super().__init__ (*args)
        opcodeInfo = self.prog.curOpcodeTab[self.parsedLine.opname]
        self.opcode = opcodeInfo.opcode << (self.prog.wordWidth - opcodeInfo.opcodeWidth)
        self.operandType: AsmOperandType = opcodeInfo.type
        self.operandVal: AsnExprValue = None    # Value stashed here after evaluation by AsmExpr.eval()
    def prefixAddrStr (self) -> str:      # A ww op always displays address and contents in the prefix address
        return self.fmtPrefixAddrStr (self.address, contents = self.instruction)
    def passOneOp (self):
        self.prog.nextCoreAddress += 1
    def passTwoOp (self):
        self.operandVal = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        val = self.operandVal
        #
        # A value stored in an instruction may be an address, or a positive
        # integer n in the range 0 <= n <= 511 mod 32. Thus we disallow
        # negative numbers, -0, or fractions, and we check we're in address
        # range.  We could tag each opcode with its operand type, but we'll do
        # that only if necessary.
        #
        if val.type == AsmExprValueType.Integer:
            if val.value < 0 or val.value >= self.prog.coreSize:
                self.addrRangeError (val.value)
            else:
                self.instruction = self.opcode | val.value      # mask not needed because we've checked range
                self.prog.coreMem[self.address] = self.instruction
                self.addXref (val.value)
        else:
            self.operandTypeError (val)
    def addXref (self, operand: int):
        if self.operandType in [AsmOperandType.RdData, AsmOperandType.WrData,
                                AsmOperandType.RdWrData, AsmOperandType.Jump]:
            address = operand
            otherInst = self.prog.coreToInst[address]
            if otherInst is not None:   # Could be None due to errors
                otherLabelOrAddr = (otherInst.parsedLine.label if otherInst.parsedLine.label != "" else "a%04o" % otherInst.address) + " "
                thisLabelOrAddr = (self.parsedLine.label if self.parsedLine.label != "" else "a%04o" % self.address) + " "
                self.xrefs.AtAddrStr += otherLabelOrAddr + " "
                match self.operandType:
                    case AsmOperandType.RdData:
                        otherInst.xrefs.readByStr += thisLabelOrAddr
                    case AsmOperandType.WrData:
                        otherInst.xrefs.writtenByStr += thisLabelOrAddr
                    case AsmOperandType.RdWrData:
                        otherInst.xrefs.readByStr += thisLabelOrAddr
                        otherInst.xrefs.writtenByStr += thisLabelOrAddr
                    case AsmOperandType.Jump:
                        otherInst.xrefs.jumpedToByStr += thisLabelOrAddr
                    case AsmOperandType.Param:
                        pass
                    
class AsmWwSiOpInst (AsmWwOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passTwoOp (self):
        super().passTwoOp()
        val = self.operandVal
        if val.type == AsmExprValueType.Integer:
            d: str = "; Auto-Annotate I/O: %s" % self.cb.Decode_IO (val.value)
            if d not in self.parsedLine.comment:
                self.xrefs.annotateIoStr = d
        else:
            self.operandTypeError (val)

class AsmPseudoOpInst (AsmInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def prefixAddrStr (self) -> str:      # A pseudo-op by default displays only the address in the prefix addr string
        return self.fmtPrefixAddrStr (self.address)
    def opnamePrefix (self):
        return "."
    def wwWord (self, val: AsmExprValue) -> int:
        inst = 0
        if val.type == AsmExprValueType.Integer:

            # This integer handling illustrates why we really could use more
            # data types, esp. an Address type, so that we can clearly deal
            # with range and sign. Here we check sign only to call the standard
            # converters, which also check sign.
            
            if val.value >= 0:
                # If positive, treat effectively as unsigned for the 16-bit range
                inst = self.intToUnsignedWwInt (val.value)
            else:
                # Value negative -- store one's complement
                inst = self.intToSignedWwInt (val.value)
        elif val.type == AsmExprValueType.NegativeZero:
            # Negative zero is its own type
            inst = self.prog.maxUnsignedWord
        elif val.type == AsmExprValueType.Fraction:
            # Fractions need to stay in signed 16-bit one's complement range
            inst = self.intToSignedWwInt (int (round (val.value * 2**(self.prog.wordWidth - 1))))
        else:
            self.operandTypeError (val)
        return inst

class AsmNullInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        pass

class AsmUnknownInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
        self.error ("Unknown op name %s" % self.parsedLine.opname)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        pass

# AsmDotIfInst is the blandest of instructions. Note it doesn't even run
# super() in init, just inits the pieces it needs. Technically I suppose it
# should subclass from a bare base class. It is only emitted on a false
# .if. Like a neutrino, it exists only as a pass-through to the instruction
# source line so elided by the false .if, to extract an appropriate listing
# string.

class AsmDotIfInst (AsmInst):
    def __init__ (self, instParsedLine: AsmParsedLine, *args):
        self.instParsedLine: AsmParsedLine = instParsedLine
        self.cb = wwinfra.theConstWWbitClass
    def prefixAddrStr (self) -> str:
        return self.fmtPrefixAddrStr (0)
    def listingString (self, **kwargs) -> str:
        return ";" + self.prefixAddrStr() + self.instParsedLine.lineStr
    def passOneOp (self):
        pass
    def passTwoOp (self):
        pass
 
class AsmDotOrgInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):

        # Need to eval this in pass one, since it determines following address
        # alloc. Normally .org is just literals, but any symbols used here
        # must have been defined earlier in the program.

        nextAddr: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if nextAddr.type == AsmExprValueType.Integer:
            if nextAddr.value >= 0 and nextAddr.value < self.prog.coreSize:
                self.prog.nextCoreAddress = nextAddr.value
                self.prog.currentRelativeBase = nextAddr   # <--- This is an important assumption!! [Guy]
            else:
                self.addrRangeError (nextAddr.value)
        else:
            self.operandTypeError (nextAddr)
    def passTwoOp (self):
        pass

# [Guy:] process a .DAORG statement, setting the next *drum* address to load. I
# have no idea what to do with these!

class AsmDotDaOrgInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        self.prog.cb.log.warn (self.parsedLine.lineNo,
                               "Drum Address pseudo-op %s in %s" % (self.parsedLine.opname, self.parsedLine.lineStr))
    def passTwoOp (self):
        pass

# [Guy:] process a .BASE statement, resetting the relative addr count to zero. I
# added this pseudo-op during the first run at cs_ii conversion But on the next
# go round, I changed it to parse the "0r" label directly.

class AsmDotBaseInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        # Like .org, need to eval this in pass one, since it determines following address alloc.
        self.prog.currentRelativeBase = 0
        self.prog.cb.log.warn (self.parsedLine.lineNo, "Deprecated .BASE @%04oo" % self.prog.nextCoreAddress)
    def passTwoOp (self):
        pass

class AsmDotWordInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def prefixAddrStr (self) -> str:      # Override - display contents too
        return self.fmtPrefixAddrStr (self.address, contents = self.instruction)
    def passOneOp (self):
        self.prog.nextCoreAddress += 1
    def passTwoOp (self):
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        self.instruction = self.wwWord (val)
        self.prog.coreMem[self.address] = self.instruction

class AsmDotWordsInst (AsmDotWordInst):
    def __init__ (self, *args):
        super().__init__ (*args)
        self.block = {}
        self.fillInst = 0
    def listingString (self,
                       minimalListing: bool = False,
                       **kwargs) -> str:
        s = super().listingString (minimalListing = minimalListing, **kwargs)
        if minimalListing:
            return s
        for i in range (1, len (self.block)):
            s += "\n" + self.fmtPrefixAddrStr (self.address + i, contents = self.block[i])
        return s
    def passOneOp (self):
        # Need to eval in pass one since this determines next addr. So all vars
        # must have been defined previoiusly in the file.
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if val.type != AsmExprValueType.List:
            valList = [val, AsmExprValue (AsmExprValueType.Integer, 0)]
        else:
            valList = val.value
        if len (valList) == 2:
            lenVal = valList[0]
            if lenVal.type == AsmExprValueType.Integer:
                fillLen = lenVal.value
                fillVal = valList[1]
                self.fillInst = self.wwWord (fillVal)
                for i in range (0, fillLen):
                    self.block[i] = self.fillInst
                self.prog.nextCoreAddress += fillLen
            else:
                self.operandTypeError (lenVal)
        else:
            self.error ("Incorrect number of operands")
    def passTwoOp (self):
        self.instruction = self.fillInst
        for i in range (0, len (self.block)):
            self.prog.coreMem[self.address+i] = self.block[i]

class AsmDotFloatInst (AsmDotWordsInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        self.prog.nextCoreAddress += 2
    def passTwoOp (self):
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if val.type == AsmExprValueType.List:
            if len (val.value) == 2:
                val1: AsmExprValue = val.value[0]
                val2: AsmExprValue = val.value[1]
                if val1.type == AsmExprValueType.Fraction:
                    decMant = val.value[0].value  
                elif val1.type == AsmExprValueType.Integer:
                    decMant = val.value[0].value
                else:
                    self.operandTypeError (val1)
                if val2.type == AsmExprValueType.Integer:
                    decExp = val.value[1].value
                    v: float = decMant*10**decExp
                    exp: int = 0 if v == 0 else math.ceil (math.log (abs(v), 2)) # Signed, mag 6 bit range, host rep
                    fracMant: float = v/2**exp
                    if fracMant >= 1.0:
                        exp += 1
                        fracMant: float = v/2**exp
                    mant = int (round (fracMant * 2**24)) # Mag is full 24-bit resolution, host rep
                    wwExp = self.intToSignedOnesCompInt (exp, 7)
                    if wwExp is None:
                        self.error ("Float out of range")
                        wwExp = 0
                    wwMant = self.intToSignedOnesCompInt (mant, 25)
                    if wwMant is None:
                        self.error ("Float out of range")
                        wwMant = 0
                    wwMantHiMask = 0o177777000
                    wwMantHi = (wwMant & wwMantHiMask) >> 9
                    wwMantLo = wwMant & ~wwMantHiMask
                    wwHiWord = wwMantHi
                    wwLoWord =  (wwExp << 9) | wwMantLo
                    self.instruction = wwHiWord
                    self.block[0] = wwHiWord
                    self.block[1] = wwLoWord
                else:
                    self.operandTypeError (val2)
            else:
                self.error (".float takes two operands")
        else:
            self.operandTypeError (val)
        self.prog.coreMem[self.address] = self.block[0]
        self.prog.coreMem[self.address+1] = self.block[1]

# .flexl and .flexh each store a word (as in .word) representing a character as
# translated to the Flexowriter character code, for each character in the
# string given as the first operand. If a second operand, an integer, is
# supplied, it is added as a terminator. .flexl stores in the low part of the
# word and .flexh in the high part.

class AsmDotFlexlhInst (AsmDotWordsInst):
    def __init__ (self, *args):
        super().__init__ (*args)
        self.block = {}
        self.fillInst = 0
    def listingString (self,
                       minimalListing: bool = False,
                       **kwargs) -> str:
        s = super().listingString (minimalListing = minimalListing, **kwargs)
        return s
    def passOneOp (self):
        # Need to eval in pass one since this determines next addr. So all vars
        # must have been defined previoiusly in the file.
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if val.type == AsmExprValueType.List:
            valList = val.value
        else:
            valList = [val]
        if len (valList) in [1, 2]:
            strVal = valList[0]
            if strVal.type == AsmExprValueType.String:
                if len (valList) == 2:
                    termVal = valList[1]
                else:
                    termVal = None
                if termVal is None or termVal.type == AsmExprValueType.Integer:
                    flexCodes = FlasciiToFlex (strVal.value).getFlex()
                    i = 0
                    for flexCode in flexCodes:
                        if self.parsedLine.opname == "flexl":
                            pass
                        elif self.parsedLine.opname == "flexh":
                            flexCode <<= 10            # if it's "high", shift the six-bit code to WW bits 0..5
                        else:
                            self.error ("Internal error: incorrect flex operation")
                        # The conversion here is more or less a formality but might
                        # catch bugs that produce out-of-range values
                        self.block[i] = self.intToUnsignedWwInt (flexCode)
                        i += 1
                    if termVal is not None:
                        self.block[len (flexCodes)] = self.intToSignedWwInt (termVal.value)
                    self.prog.nextCoreAddress += len (self.block)
                else:
                    self.operandTypeError (termVal)
            else:
                self.operandTypeError (strVal)
        else:
            self.error ("Incorrect number of operands")
    def passTwoOp (self):
        if 0 in self.block:        # We need at least this one entry
            self.instruction = self.block[0]
            for i in range (0, len (self.block)):
                self.prog.coreMem[self.address+i] = self.block[i]

class AsmDotJumpToInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if val.type == AsmExprValueType.Integer:
            if val.value >= 0 and val.value < self.prog.coreSize:
                self.instruction = val.value                # Address to which to jump
                self.prog.wwJumpToAddress = val.value       # Also set the program-level starting jump address
            else:
                self.addrRangeError (val.value)
        else:
            self.operandTypeError (val)

class DebugWidgetClass:
    def __init__(self, lineNo: int, addr: int, paramName: str, incr: int, format: str):
        self.lineNo = lineNo
        self.addr = addr            # A widget uses either a numerical address or a param name. Addr if paramName is empty
        self.paramName = paramName
        self.incr = incr
        self.format = format

class AsmDotDbwgtInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        # We can have a max of three args for the debug widget:
        #   [Address [, Incr [, Format]]]
        # Address can be any address expression
        # Incr is an integer
        # Format is a %-style format string
        env = self.prog.env
        val: AsmExprValue = self.parsedLine.operand.evalMain (env, self.parsedLine)
        if val.type != AsmExprValueType.List:
            o = [val]
        else:
            o = val.value
        addr = 0
        paramName = ""
        incr = 1
        format = "%o"
        if len (o) == 0:
            self.error ("Internal error: .dbwgt zero-length operand list")
        if len (o) >= 1:
            if o[0].type == AsmExprValueType.Integer:
                addr = o[0].value
            elif o[0].type == AsmExprValueType.String:
                paramName = o[0].value
            else:
                self.operandTypeError (o[0])
        if len (o) >= 2:
            if o[1].type == AsmExprValueType.Integer:
                incr = o[1].value
            else:
                self.operandTypeError (o[1])
        if len (o) == 3:
            if o[2].type == AsmExprValueType.String:
                format = o[2].value
            else:
                self.operandTypeError (o[2])
        self.prog.dbwgtTab.append (DebugWidgetClass (self.parsedLine.lineNo, addr, paramName, incr, format))

class AsmDotExecInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def listingString (self,
                       quoteStrings: bool = True,
                       minimalListing: bool = False,
                       **kwargs) -> str:
        p = self.parsedLine
        prefixAddr = self.prefixAddrStr() if not minimalListing else ""
        autoComment = self.xrefs.listingString
        return super().listingString (quoteStrings = False,
                                      minimalListing = minimalListing,
                                      **kwargs)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        execCmdVal = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if execCmdVal.type != AsmExprValueType.String:
            self.operandTypeError (execCmdVal)
        else:
            execCmd = "exec: " + execCmdVal.value
            if self.address in self.prog.execTab:
                self.prog.execTab[self.address] += " \\n " + execCmd
            else:
                self.prog.execTab[self.address] = execCmd

class AsmDotPrintInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):

        # LAS 12/14/24 Taking a shortcut here for now, as I don't want to modify
        # the sim at this point if I can avoid it. We could and probably should
        # parse the format string and produce a data structure specifically for
        # .print in the sim. But for now we'll just produce the usual string
        # and let the .exec processor handle it. However it should be a goal to
        # make .print be on its own and further isolate .exec, which eventually
        # should be replaced.
        #
        # However we'll make another change in that we'll resolve all the
        # addresses here, and emit a string with numeric addresses. This avoids
        # having the sim needing to lookup a symbol. Such lookup is a
        # performance drag and also goes against modularity, where we'd like
        # symbol lookup to be needed only for debugging. See also .dbwgt for
        # more discussion.

        execCmd = "print: "
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if val.type != AsmExprValueType.List:
            operands = [val]
        else:
            operands = val.value
        fmtVal = operands[0]
        if fmtVal.type != AsmExprValueType.String:
            self.operandTypeError (fmtVal)
        else:
            execCmd += "\"" + fmtVal.value + "\""
            operandsLen = len (operands)
            for i in range (1, operandsLen):
                val = operands[i]
                # Each value after the fmt string must be an integer and valid address
                if val.type == AsmExprValueType.Integer:
                    if val.value < 0 or val.value > self.prog.coreSize:
                        self.addrRangeError (val.value)
                    else:
                        execCmd += ", 0o%06o" % val.value
                else:
                    self.operandTypeError (val)
            if self.address in self.prog.execTab:
                self.prog.execTab[self.address] += " \n " + execCmd
            else:
                self.prog.execTab[self.address] = execCmd

class AsmDotPpInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        operands = self.parsedLine.operand
        if operands.exprType == AsmExprType.BinaryComma:
            varExpr = operands.leftSubExpr
            valExpr = operands.rightSubExpr
            if varExpr.exprType == AsmExprType.Variable:
                val: AsmExprValue = valExpr.evalMain (self.prog.env, self.parsedLine)
                if val.type in [AsmExprValueType.Integer, AsmExprValueType.Fraction, AsmExprValueType.NegativeZero]:
                    if varExpr.exprData in self.prog.presetTab:
                        self.error ("Preset variable %s already defined" % varExpr.exprData)
                    else:
                        self.prog.presetTab[varExpr.exprData] = val
                else:
                    aelf.operandTypeError (val)
            else:
                self.error ("Binding target (first operand) of a preset must be a variable")
        else:
            self.error (".pp requires comma operator")
    def passTwoOp (self):
        pass

class AsmDotIncludeInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def listingString (self, minimalListing: bool = False, **kwargs) -> str:
        if self.prog.reformat:
            return super().listingString (minimalListing = minimalListing, **kwargs)
        else:
            p = self.parsedLine
            prefixAddr = self.prefixAddrStr() if not minimalListing else ""
            maxLabelLen = self.prog.labelTab.maxLabelLen
            sp = " "
            spaces = " "*maxLabelLen
            return prefixAddr + spaces + "   ; " + self.opnamePrefix() + p.opname + " " + p.operand.listingString()
    def passOneOp (self):
        if not self.prog.reformat:
            # Must be evaluated in pass one, so the operand needs to be a literal
            val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
            if val.type == AsmExprValueType.String:
                inFilename = val.value
                try:
                    inStream = open (inFilename, "r")
                    self.prog.pushStream (inStream, inFilename)
                except FileNotFoundError:
                    self.fatalError ("file %s not found" % inFilename)
                except IOError:
                    self.fatalError ("I/O Error opening file %s" % inFilename)
            else:
                self.operandTypeError (val)
    def passTwoOp (self):
        pass

# An Inst just so we can mark the end of an included file. Works ok, but feels
# a little greasy, maybe even slimy.

class AsmEndDotIncludeInst (AsmDotIncludeInst):     # Specifically to support .include
    def __init__ (self, inFilename: str, prog):
        self.inFilename = inFilename
        self.parsedLine = AsmParsedLine ("", 0)
        self.parsedLine.opname = "include"
        self.parsedLine.operand = AsmExpr (AsmExprType.LiteralString, self.inFilename)
        super().__init__ (self.parsedLine, prog)
    def opnamePrefix (self) -> str:
        return "end ."
    def passOneOp (self):
        pass
    def passTwoOp (self):
        pass

class AsmDotWwFilenameInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if val.type == AsmExprValueType.String:
            self.prog.wwFilename = val.value
        else:
            self.operandTypeError (val)

class AsmDotWwTapeIdInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if val.type == AsmExprValueType.String:
            self.prog.wwTapeId = val.value
        else:
            aelf.operandTypeError (val)

class AsmDotIsaInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        # Needs to be evaluated in pass one. Literal digits only are allowed
        digitsExpr: AsmExpr = self.parsedLine.operand
        if digitsExpr.exprType == AsmExprType.LiteralDigits:
            val: AsmExprValue = digitsExpr.evalMain (self.prog.env, self.parsedLine)
            if val.type == AsmExprValueType.Integer:
                d = {1950: self.prog.opCodeTables.op_code_1950, 1958: self.prog.opCodeTables.op_code_1958}
                if val.value in d:
                    self.prog.curOpcodeTab = d[val.value]
                elif val.value < 1950 and val.value > 1940:
                    self.error ("What do you think this is, ENIAC?")
                elif val.value < 1900 and val.value > 1800:
                    self.error ("Sorry, Babbage is no longer with us")
                elif val.value <= 1500:
                    self.error ("Setting instruction set to the Antikythera Mechanism")
                elif val.value > 2024:
                    self.error ("Setting instruction set to MIT WhirlWave Quantum Computer")
                else:
                    self.error ("Hope you and your time machine find your way home")
            else:
                self.operandTypeError (val)
        else:
            self.error ("Only literal integers allowed in .isa")
    def passTwoOp (self):
        pass

# LAS 12/16/24 ww code will need to be converted to use comma-separated
# operands, rather than space-separated.
#
# Again I'm stoppping short of a full-pipeline revamp of this since I don't
# want to modify the sim if I can help it. Below though we have everything in
# parsed format, and we'll change it back to text for the sim to parse again.
#
# The previous version special-cased FFRegAssign, but that's really not needed
# since we'll stop processing if it's a one-arg op anyway. However we do thus
# give up a little checking for form we could do.

class AsmDotSwitchInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        operands = self.parsedLine.operand
        if operands.exprType == AsmExprType.BinaryComma:
            varExpr = operands.leftSubExpr
            valExpr = operands.rightSubExpr
            # First operand is a name we take unevaluated
            if varExpr.exprType == AsmExprType.Variable:
                name = varExpr.exprData
                settingsVal: AsmExprValue = valExpr.evalMain (self.prog.env, self.parsedLine)
                # Can be one setting or a list
                if settingsVal.type != AsmExprValueType.List:
                    settingsValList = [settingsVal]
                else:
                    settingsValList = settingsVal.value
                argStr = ""
                sep = ""
                for i in range (0, len (settingsValList)):
                    val = settingsValList[i]
                    if val.type == AsmExprValueType.Integer:
                        if val.value >= 0:
                            argStr += sep + " 0o%06o" % val.value
                            sep = ","
                        else:
                            self.error ("Value can not be negative")
                    else:
                        self.operandTypeError (val)
                self.prog.switchTab[name] = argStr
            else:
                self.error ("Switch name must be a variable")
        else:
            self.error (".switch syntax error")


class AsmProgramEnv (AsmExprEnv):
    def __init__ (self, prog): # prog: AsmProgram
        self.prog = prog
    # Override the default lookup
    def lookup (self, var: str) -> AsmExprValue:
        return self.prog.envLookup (var)

# LAS 12/21/24 Defined this class to substitute for a regular dict, in order to
# keep track of max label length. Hardly seems worth it.

class AsmLabelTab:
    def __init__ (self, prog):       # prog: AsmProgram
        self.prog = prog
        self.labelToInst: dict = {}  # Label: Variable: str -> AsmInst      A Label is a Variable but not all Variables must be labels.
        self.maxLabelLen = 0
    def insert (self, label: str, inst: AsmInst):
        if label in self.labelToInst:
            self.prog.error ("Label %s already defined" % label)
        else:
            self.labelToInst[label] = inst
            self.maxLabelLen = max (self.maxLabelLen, len (label))
    def lookup (self, label: str):
        if label in self.labelToInst:
            return self.labelToInst[label]
        else:
            return None
    def labels (self) -> [str]:
        return list (self.labelToInst)

class AsmProgram:
    def __init__ (self,
                  inFilename, inStream,
                  coreOutFilename, listingOutFilename,
                  verbose, debug, minimalListing, isa1950,
                  reformat, omitUnrefedLabels, commentColumn, commentWidth, omitAutoComment):
        #
        # The "fundamental constants" of the machine. Masks, which can hide
        # bugs, are not used. Ranges of fields are checked.
        #
        self.wordWidth = 16
        self.maxUnsignedWord = 2**self.wordWidth - 1
        self.maxSignedWordMag = 2**(self.wordWidth - 1) - 1 # One's-complement machine
        self.addressWidth = 11
        self.coreSize = 2**self.addressWidth
        #
        # The opcode tables do hold another fundamental constant, the opcode
        # width. Since this can vary that knowledge is in the OpcodeInfo
        # classes.
        #
        self.opCodeTables = OpCodeTables()
        self.isa1950 = isa1950
        if self.isa1950:
            self.curOpcodeTab: dict = self.opCodeTables.op_code_1950
        else:
            self.curOpcodeTab: dict = self.opCodeTables.op_code_1958
        self.metaOpcode = self.opCodeTables.meta_op_code

        self.cb = wwinfra.theConstWWbitClass
        self.flexoClass = wwinfra.FlexoClass (self.cb, log = wwinfra.LogFactory().getLog())   # want a non-asm log at the low-level

        # [Guy says:] I think the CSII assembler defaults to starting to load
        # instructions at 0o40, the first word of writable core.  Of course a
        # .org can change that before loading the first word of the program.
        self.nextCoreAddress: int = 0o40     # Where to put the next instruction.
        
        self.currentRelativeBase: int = 0o40 # Base of NNr style address refs.
        self.wwTapeId: str = ""
        self.wwJumpToAddress: int = None     # Initial program addr
        self.minimalListing = minimalListing
        self.reformat = reformat
        self.omitUnrefedLabels = omitUnrefedLabels
        self.commentColumn = commentColumn if commentColumn is not None else 25
        self.commentWidth = commentWidth if commentWidth is not None else 0
        self.omitAutoComment = omitAutoComment
        self.opCodeTable: list = []
        self.isa1950: bool = False

        self.insts: [AsmInst] = []

        # These two tables constitute the evaluation environment for
        # AsmExpr.eval(), via AsmProgram.envLookup(), which feeds AsmProgramEnv
        self.labelTab = AsmLabelTab (self)            # Label: Variable: str -> AsmInst
        self.presetTab = {}                           # Variable: str -> AsmExprValue        Defined via .pp

        self.env = AsmProgramEnv (self)               # The evaluation environment itself

        self.commentTab = [""]*self.coreSize          # An array of comments found in the source, indexed by address
        self.dbwgtTab = []                            # An array [list?] to hold directives to add Debug Widgets to the screen
        self.execTab = {}                             # Dictionary of Python Exec statements, indexed by core mem address
        self.switchTab = {}
        
        self.coreMem = [None]*self.coreSize           # An image of the final core memory. Maps int -> int. Type ([int]*self.coreSize)[int]

        self.parsedLine: AsmParsedLine = None

        self.coreToInst = [None]*self.coreSize        # An array mapping an address to an AsmInst -- for xref. Type ([AsmInst]*self.coreSize)[Address: int]
        self.labelRef = {}                            # Map Label: str -> True. Just need to know label has been ref'd

        self.inFilename = inFilename
        self.wwFilename = self.inFilename             # wwFilename will be overwritten if there's a directive in the source
        self.inStream = inStream
        self.coreOutFilename = coreOutFilename
        self.listingOutFilename = listingOutFilename

        self.inFilenameStack: [str] = []
        self.inStreamStack: [] = []

        # LAS 12/27/24 As of now these options are detected on the cmd line but
        # there are no statements using them in the code
        self.verbose = verbose
        self.debug = debug

    def error (self, msg: str):
        sys.stdout.flush()
        self.cb.log.error (self.parsedLine.lineNo, "%s in %s" % (msg, self.parsedLine.lineStr))

    def copyWwFileToBak (self) -> bool:
        bakFile = self.inFilename + ".bak"
        sout = open (bakFile, "wt")
        sin = open (self.inFilename, "r")
        while True:
            l = sin.readline()
            if l == "":
                break
            else:
                sout.write (l)
        sin.close()
        sout.close()
        return True
        
    #
    # Used in AsmProgramEnv
    #
    # May want bells or whistles at some point to distinguish an address from
    # other data.
    #
    def envLookup (self, var: str) -> AsmExprValue:
        inst = self.labelTab.lookup (var)
        if inst is not None:
            self.labelRef[var] = True
            return AsmExprValue (AsmExprValueType.Integer, inst.address)
        elif var in self.presetTab:
            return self.presetTab[var]
        else:
            return None

    # Support for .include

    def pushStream (self, inStream, inFilename):
        self.inStreamStack.append (self.inStream)
        self.inFilenameStack.append (self.inFilename)
        self.inStream = inStream
        self.inFilename = inFilename

    def popStream (self) -> bool:
        if self.inStreamStack == []:
            return False
        else:
            self.inStream.close()
            self.inStream = self.inStreamStack.pop()
            self.inFilename = self.inFilenameStack.pop()
            return True

    def evalDotIf (self) -> bool:
        if self.parsedLine.dotIfExpr is not None:
            val = self.parsedLine.dotIfExpr.evalMain (self.env, self.parsedLine)
            if val.type == AsmExprValueType.Integer:
                return val.value != 0
            else:
                self.error (".if arg must be an integer")
                return True
        else:
            return None     # Indicates no .if was specified

    def passOne (self):
        #
        # Resolve as much as possible in the first pass, such as ww opcodes and
        # certain pseudo-ops like .org which change assembly state. Allocate
        # addresses, assign symbols in label table and preset table.
        #
        # Read and parse the asm file, generate an instruction (instance of
        # AsmInst) for each parsed line.
        #
        lineNo = 0
        while True:
            lineStr = self.inStream.readline()
            lineNo += 1
            if lineStr == "":
                curInfile = self.inFilename
                if self.popStream():
                    inst = AsmEndDotIncludeInst (curInfile, self)
                    self.insts.append (inst)
                    continue
                else:
                    self.inStream.close()
                    break
            else:
                line = AsmParsedLine (lineStr, lineNo, verbose = self.verbose)
                line.parseLine()
                self.parsedLine = line      # Current line available for error messages
                # All lines result in an instruction class instance of some kind
                dotIf = self.evalDotIf()
                if dotIf is not None and not dotIf:
                    # A false .if means don't include the instruction, so make a DotIfInst pass-through for the listing
                    inst = AsmDotIfInst (line, self)
                else:
                    opname = line.opname.lower()
                    if opname in self.metaOpcode:
                        inst = self.metaOpcode[opname] (line, self)
                    elif opname in self.curOpcodeTab:
                        inst = self.curOpcodeTab[opname].className (line, self)
                    elif opname == "":
                        inst = AsmNullInst (line, self)
                    else:
                        inst = AsmUnknownInst (line, self)
                inst.passOneOp()
                self.insts.append (inst)
        pass

    def passTwo (self):
        # Evaluate operands and resolve full instructions as needed.
        for inst in self.insts:
            inst.passTwoOp()

    def writeCore (self):
        print ("Corefile output to file %s" % self.coreOutFilename)
        fout = open (self.coreOutFilename, 'wt')
        fout.write("\n; *** Core Image ***\n")
        if self.curOpcodeTab == self.opCodeTables.op_code_1950:  # default in the sim is the 1958 instruction set; this directive changes it to 1950
            fout.write("%%ISA: %s\n" % "1950")
        fout.write("%%File: %s\n" % self.wwFilename)
        fout.write("%%TapeID: %s\n" % self.wwTapeId)
        if self.wwJumpToAddress is not None:
            fout.write('%%JumpTo 0o%o\n' % self.wwJumpToAddress)
        for s in self.switchTab:  # switch tab is indexed by name, contains a validated string for the value
            fout.write("%%Switch: %s %s\n" % (s, self.switchTab[s]))
        for w in self.dbwgtTab:
            addrStr = w.paramName if w.paramName != "" else "0o%03o" % w.addr
            fout.write("%%DbWgt:  %s  0o%02o %s\n" % (addrStr, w.incr, w.format))
        columns = 8
        addr = 0
        while addr < self.coreSize:
            i = 0
            non_null = 0
            row = ""
            while i < columns:
                if self.coreMem[addr+i] is not None:
                    row += "%07o " % self.coreMem[addr+i]
                    non_null += 1
                else:
                    row += " None   "
                i += 1
            if non_null:
                fout.write('@C%04o: %s\n' % (addr, row))
            addr += columns
        for s in self.labelTab.labels():
            addr = self.labelTab.lookup(s).address
            fout.write("@S%04o: %s\n" % (addr, s))
        for s in self.presetTab:
            value = self.presetTab[s].value
            fout.write("@S%04o: %s\n" % (value, s))
        for addr in self.execTab:
            fout.write("@E%04o: %s\n" % (addr, self.execTab[addr]))
        for addr in range(0, len(self.commentTab)):
            if self.commentTab[addr] is not None and len(self.commentTab[addr]) > 0:
                fout.write("@N%04o: %s\n" % (addr, self.commentTab[addr]))
        fout.close()

    def writeListing (self):
        listingOutStream = open (self.listingOutFilename, 'wt')
        print ("Listing output to file %s" % self.listingOutFilename)
        for inst in self.insts:
            listingOutStream.write (inst.listingString (minimalListing = self.minimalListing,
                                                        omitUnrefedLabels = self.omitUnrefedLabels,
                                                        omitAutoComment = self.omitAutoComment) + "\n")
        listingOutStream.close()

    def assemble (self):
        self.passOne()
        self.passTwo()
        errorCount = self.cb.log.error_count
        if errorCount != 0:  # Don't write files if picked up errors
            print ("Error Count = %d; output files suppressed" % errorCount)
        else:
            if self.reformat:
                status: bool = self.copyWwFileToBak()
                if status:
                    self.listingOutFilename = self.inFilename
                    self.writeListing()
                else:
                    error()
            else:
                self.writeCore()
                self.writeListing()

def main():
    parser = wwinfra.StdArgs().getParser ("Assemble a Whirlwind Program.")
    parser.add_argument("inputfile", help="file name of ww asm source file")
    parser.add_argument('--outputfilebase', '-o', type=str, help='base name for output file')
    parser.add_argument("--Verbose", '-v',  help="print progress messages", action="store_true")
    parser.add_argument("--Debug", '-d', help="Print lotsa debug info", action="store_true")
    parser.add_argument("--MinimalListing", help="Do not include prefix address and auto-comments in listing", action="store_true")
    parser.add_argument("-D", "--DecimalAddresses", help="Display listing addresses in decimal as well as octal", action="store_true")
    parser.add_argument("--ISA_1950", help="Use the 1950 version of the instruction set", action="store_true")
    parser.add_argument("--Reformat", help="Prettify the source .ww file and move the original to .ww.bak", action="store_true")
    parser.add_argument("--OmitUnrefedLabels", help="Don't put unreferenced labels in the listing", action="store_true")
    # Suggested for comment columns is "--CommentColumn 25 --CommentWidth 50"
    parser.add_argument("--CommentColumn", type=int, help="Column after labels for comments in listing. Default 25")
    parser.add_argument("--CommentWidth", type=int, help="Space to allocate to each comment field in listing. If not specified or zero, no field detection")
    parser.add_argument("--OmitAutoComment", help="Omit the auto-comment xref in listing", action="store_true")
    # We decided to keep this always-on
    # parser.add_argument("--Annotate_IO_Names", help="Auto-add comments to identify SI device names", action="store_true")
    
    # No longer supported, in favor of editing the code. Thus bare digits are always decimal.
    # Parser.add_argument("--Legacy_Numbers", help="guy-legacy - Assume numeric strings are Octal", action="store_true")

    args = parser.parse_args()
    cb = wwinfra.ConstWWbitClass (args = args)
    wwinfra.theConstWWbitClass = cb
    cb.decimal_addresses = args.DecimalAddresses  # if set, trace output is expressed in Decimal to suit 1950's chic
    cb.log = wwinfra.LogFactory().getLog (isAsmLog = True)
    debug = args.Debug
    verbose = args.Verbose
    minimalListing = args.MinimalListing
    isa1950 = args.ISA_1950
    reformat = args.Reformat
    if reformat:
        minimalListing = True
    omitUnrefedLabels = args.OmitUnrefedLabels
    commentColumn = args.CommentColumn
    commentWidth = args.CommentWidth
    omitAutoComment = args.OmitAutoComment
    inFilename = args.inputfile
    outFileBaseName = re.sub("\\.ww$", '', inFilename)
    if args.outputfilebase is not None:
        outFileBaseName = args.outputfilebase
    # cb.CoreFileName = os.path.basename (outFileBaseName)  # There does not seem to be a reason store this in cb in the assembler
    coreOutFilename = outFileBaseName + ".acore"
    listingOutFilename = outFileBaseName + ".lst"
    inStream = open (inFilename, "r")
    prog = AsmProgram (
        inFilename, inStream,
        coreOutFilename, listingOutFilename,
        verbose, debug, minimalListing, isa1950,
        reformat, omitUnrefedLabels, commentColumn, commentWidth, omitAutoComment)
    prog.assemble()

main()
