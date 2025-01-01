import os
import sys
import re
import traceback
import argparse
import wwinfra
from enum import Enum
from wwasmparser import AsmExprValue, AsmExprValueType, AsmExprEnv, AsmExpr, AsmExprType, AsmParsedLine

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
           "pp": AsmDotPpInst
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
    def error (self, msg: str):
        sys.stdout.flush()
        """
        traceback.print_stack()
        sys.stdout.flush()
        sys.stderr.flush()
        """
        self.cb.log.error (self.parsedLine.lineNo, "%s:\n%s" % (msg, self.parsedLine.lineStr))
        pass
    def operandTypeError (self, val: AsmExprValue):
        self.error ("Incorrect operand type %s" % val.asString())
    def addrRangeError (self, addr: int):
        self.error ("Address 0o%o out of range" % addr)
    # Return a string for the prefix address, perhaps with decimal addresses and perhaps with content
    def fmtPrefixAddrStr (self, address: int, contents: int = None) -> str:
        da = self.cb.decimal_addresses
        daStr = ".%04d" % address if da else ""
        if contents is not None:
            return ("@%04o" + daStr + ":%06o") % (address, contents)
        else:
            return (" "*5 + " "*len (daStr) + " "*7)
    def opnamePrefix (self):
        return ""
    def listingString (self, quoteStrings: bool = True, minimalListing: bool = False) -> str:
        p = self.parsedLine
        prefixAddr = self.prefixAddrStr() if not minimalListing else ""
        autoComment = self.xrefs.listingString() if not minimalListing else ""
        maxLabelLen = self.prog.labelTab.maxLabelLen
        sp = " "
        sp1 = sp*(maxLabelLen - len (p.label))
        label = "%s%s" % (sp1, p.label) + (":" if p.label != "" else sp)
        inst = self.opnamePrefix() + p.opname + (sp + p.operand.listingString (quoteStrings = quoteStrings)) if p.operand is not None else ""
        comment = p.comment
        s1 = prefixAddr + sp + label + sp 
        s2 = s1 + inst
        sp2 = sp*(50 - len (s2)) if p.label != "" or p.opname != "" else ""
        s3 = (sp2 + "; " + comment + " " + autoComment) if comment + autoComment != "" else ""
        return s2 + s3

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
        if self.prog.annotateIoNames:
            val = self.operandVal
            if val.type == AsmExprValueType.Integer:
                d: str = self.cb.Decode_IO (val.value)
                self.xrefs.annotateIoStr = "; Auto-Annotate I/O: %s" % d
            else:
                self.operandTypeError (val)

class AsmPseudoOpInst (AsmInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def prefixAddrStr (self) -> str:      # A pseudo-op by default displays only the address in the prefix addr string
        return self.fmtPrefixAddrStr (self.address)
    def opnamePrefix (self):
        return "."

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

# LAS 12/8/24 Issue: The original calls ww_int_csii, a digit parser which
# should not be needed under the new grammar. However I see in .ww files that
# .org seems to accept only octal, regardless of the usual numeric parsing
# format. Here I'm assuming standard format, so e.g. ".ORG 00040" will be taken
# as decimal.

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
        if val.type == AsmExprValueType.Integer:

            # This integer handling illustrates why we really could use more
            # data types, esp. an Address type, so that we can clearly deal
            # with range and sign. Here we check sign only to call the standard
            # converters, which also check sign.
            
            if val.value >= 0:
                # If positive, treat effectively as unsigned for the 16-bit range
                self.instruction = self.intToUnsignedWwInt (val.value)
            else:
                # Value negative -- store one's complement
                self.instruction = self.intToSignedWwInt (val.value)
        elif val.type == AsmExprValueType.NegativeZero:
            # Negative zero is its own type
            self.instruction = self.prog.maxUnsignedWord
        elif val.type == AsmExprValueType.Fraction:
            # Fractions need to stay in signed 16-bit one's complement range
            self.instruction = self.intToSignedWwInt (val.value)
        else:
            self.operandTypeError (val)
        self.prog.coreMem[self.address] = self.instruction

# .flexl and .flexh each store a word (as in .word), representing a character
# as translated to the Flexowriter character code. .flexl stores in the low
# part of the word and .flexh in the high part.
#
# LAS 12/16/24 I opted here for a tighter model for the .flex ops, where we
# only accept a single literal character, rather than beyond that interpreting
# the operand as a normal symbol or number, as in the prior version. In an
# email exchange Guy approved of this change.

class AsmDotFlexlhInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def prefixAddrStr (self) -> str:      # Override - display contents too
        return self.fmtPrefixAddrStr (self.address, contents = self.instruction)
    def passOneOp (self):
        self.prog.nextCoreAddress += 1
    def passTwoOp (self):
        val: AsmExprValue = self.parsedLine.operand.evalMain (self.prog.env, self.parsedLine)
        if val.type == AsmExprValueType.String:
            if len (val.value) == 1:
                flexoChar: int = self.prog.flexoClass.ascii_to_flexo (val.value)
                if self.parsedLine.opname == "flexl":
                    pass
                elif self.parsedLine.opname == "flexh":
                    flexoChar <<= 10            # if it's "high", shift the six-bit code to WW bits 0..5
                else:
                    self.error ("Internal error: incorrect flexo operation")
                # Plop the translated value in as in .word.
                # The conversion here is more of less a formality but might
                # catch bugs that produce out-of-range values
                self.instruction = self.intToUnsignedWwInt (flexoChar)
                self.prog.coreMem[self.address] = self.instruction                
            else:
                self.error (".flex operations only accept a single-character literal string")
        else:
            self.operandTypeError (val)

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
    def listingString (self, minimalListing: bool = False) -> str:
        return super().listingString (quoteStrings = False, minimalListing = minimalListing)
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
                self.prog.execTab[self.address] += " \\n " + execCmd
            else:
                self.prog.execTab[self.address] = execCmd

class AsmDotPpInst (AsmPseudoOpInst):
    def __init__ (self, *args):
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        operands = self.parsedLine.operand
        if operands.exprType == AsmExprType.BinaryComma:
            varExpr = operands.leftSubExpr
            valExpr = operands.rightSubExpr
            if varExpr.exprType == AsmExprType.Variable:
                val: AsmExprValue = valExpr.evalMain (self.prog.env, self.parsedLine)
                if val.type in [AsmExprValueType.Integer, AsmExprValueType.Fraction, AsmExprValueType.NegativeZero]:
                    self.prog.presetTab[varExpr.exprData] = val
                else:
                    aelf.operandTypeError (val)
            else:
                self.error ("Binding target (first operand) of a preset must be a variable")
        else:
            self.error (".pp requires comma operator")

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
    def __init__ (self):
        self.labelToInst: dict = {}  # Label: Variable: str -> AsmInst      A Label is a Variable but not all Variables must be labels.
        self.maxLabelLen = 0
    def insert (self, label: str, inst: AsmInst):
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
                  verbose, debug, minimalListing, annotateIoNames, isa1950):
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
        self.flexoClass = wwinfra.FlexoClass (None)

        # [Guy says:] I think the CSII assembler defaults to starting to load
        # instructions at 0o40, the first word of writable core.  Of course a
        # .org can change that before loading the first word of the program.
        self.nextCoreAddress: int = 0o40     # Where to put the next instruction.
        
        self.currentRelativeBase: int = 0o40 # Base of NNr style address refs.
        self.inputFile: str = ""             # Input file name, as given on the cmd line.
        self.wwFilename: str = ""
        self.wwTapeId: str = ""
        self.wwJumpToAddress: int = None     # Initial program addr
        self.minimalListing = minimalListing
        self.legacyNumbers: bool = False
        self.opCodeTable: list = []
        self.isa1950: bool = False
        self.annotateIoNames: bool = annotateIoNames

        self.insts: [AsmInst] = []

        # These two tables constitute the evaluation environment for
        # AsmExpr.eval(), via AsmProgram.envLookup(), which feeds AsmProgramEnv
        self.labelTab = AsmLabelTab()                 # Label: Variable: str -> AsmInst
        self.presetTab = {}                           # Variable: str -> AsmExprValue        Defined via .pp

        self.env = AsmProgramEnv (self)               # The evaluation environment

        self.commentTab = [""]*self.coreSize          # An array of comments found in the source, indexed by address
        self.dbwgtTab = []                            # An array [list?] to hold directives to add Debug Widgets to the screen
        self.execTab = {}                             # Dictionary of Python Exec statements, indexed by core mem address
        self.switchTab = {}
        
        self.coreMem = [None]*self.coreSize           # An image of the final core memory.

        self.coreToInst = [None]*self.coreSize        # An array mapping an address to an AsmInst -- for xref

        self.wwFilename = inFilename                  # wwFilename will be overwritten if there's a directive in the source
        self.inStream = inStream
        self.coreOutFilename = coreOutFilename
        self.listingOutFilename = listingOutFilename

        # LAS 12/27/24 As of now these options are detected on the cmd line but
        # there are no statements using them in the code
        self.verbose = verbose
        self.debug = debug

    def error (msg: str):
        sys.stdout.flush()
        self.cb.log.error (self.parsedLine.lineNo, "%s in %s" % (msg, self.parsedLine.lineStr))
    #
    # Used in AsmProgramEnv
    #
    # May want bells or whistles at some point to distinguish an address from
    # other data.
    #
    def envLookup (self, var: str) -> AsmExprValue:
        inst = self.labelTab.lookup (var)
        if inst is not None:
            return AsmExprValue (AsmExprValueType.Integer, inst.address)
        elif var in self.presetTab:
            return self.presetTab[var]
        else:
            return None

    def passOne (self):
        #
        # Resolve as much as possible in the first pass, such as ww opcodes,
        # certain pseudo-ops like .org which change assembly state, allocate
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
                break
            else:
                line = AsmParsedLine (lineStr, lineNo, verbose = self.verbose)
                line.parseLine()
                # All lines result in an instruction class instance of some kind
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
            listingOutStream.write (inst.listingString (minimalListing = self.minimalListing) + "\n")
        listingOutStream.close()

    def assemble (self):
        self.passOne()
        self.passTwo()
        errorCount = self.cb.log.error_count
        if errorCount != 0:  # Don't write files if picked up errors
            print ("Error Count = %d; output files suppressed" % errorCount)
        else:
            self.writeCore()
            self.writeListing()

def main():
    parser = wwinfra.StdArgs().getParser ("Assemble a Whirlwind Program.")
    parser.add_argument("inputfile", help="file name of ww asm source file")
    parser.add_argument("--Verbose", '-v',  help="print progress messages", action="store_true")
    parser.add_argument("--Debug", '-d', help="Print lotsa debug info", action="store_true")
    parser.add_argument("--MinimalListing", help="Do not include prefix address and auto-comments in listing", action="store_true")
    parser.add_argument("--Annotate_IO_Names", help="Auto-add comments to identify SI device names", action="store_true")
    parser.add_argument("--Legacy_Numbers", help="guy-legacy - Assume numeric strings are Octal", action="store_true")
    parser.add_argument("-D", "--DecimalAddresses", help="Display traec information in decimal (default is octal)",
                        action="store_true")
    parser.add_argument("--ISA_1950", help="Use the 1950 version of the instruction set",
                        action="store_true")
    parser.add_argument('--outputfilebase', '-o', type=str, help='base name for output file')
    args = parser.parse_args()
    cb = wwinfra.ConstWWbitClass (args = args)
    wwinfra.theConstWWbitClass = cb
    cb.decimal_addresses = args.DecimalAddresses  # if set, trace output is expressed in Decimal to suit 1950's chic
    cb.log = wwinfra.LogFactory().getLog (isAsmLog = True)
    debug = args.Debug
    verbose = args.Verbose
    minimalListing = args.MinimalListing
    legacyNumbers = args.Legacy_Numbers
    annotateIoNames = args.Annotate_IO_Names
    isa1950 = args.ISA_1950
    inFilename = args.inputfile
    outFileBaseName = re.sub("\\.ww$", '', inFilename)
    if args.outputfilebase is not None:
        outFileBaseName = args.outputfilebase
    # cb.CoreFileName = os.path.basename (outFileBaseName)  # There does not seem to be a reason store this in cb in the assembler
    coreOutFilename = outFileBaseName + ".ncore"
    listingOutFilename = outFileBaseName + ".nlst"
    inStream = open (inFilename, "r")
    prog = AsmProgram (
        inFilename, inStream,
        coreOutFilename, listingOutFilename,
        verbose, debug, minimalListing, annotateIoNames, isa1950)
    prog.assemble()

main()
