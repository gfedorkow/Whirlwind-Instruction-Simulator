import os
import sys
import re
import argparse
import wwinfra
import wwasmparser

# LAS Clarify what "address" means below in the comments.

AsmOperandType = Enum ("AsmOperandType", ["None",       # it's a pseudo-op
                                          "Jump",       # the address is a jump target
                                          "WrData",     # the address writes a data word to Core
                                          "RdData",     # the address writes a data word from Core
                                          "RdWrData",   # the address writes and reads a data word to/from Core
                                          "Param"])     # the operand isn't an address at all

AsmDirectiveOp = Enum ("AsmDirectiveOp", ["None", "DotWord", "DotFLexl", "DotFlexh"])

class OpCodeInfo:
    def __init__ (self, opcode: int, mask: int, type: AsmOperandType):
        self.opcode opcode
        self.mask = mask
        self.type = type

class FiveBitOpCodeInfo (OpCodeInfo):
        def __init__ (self, opcode: int, type: AsmOperandType):
            mask = 0o03777
            super().__init__ (opcode, mask, type)

class SevenBitOpCodeInfo (OpCodeInfo):
        def __init__ (self, opcode: int, type: AsmOperandType):
            mask = 0o01777
            super().__init__ (opcode, mask, type)

class CsiiOpCodeInfo (OpCodeInfo):
        def __init__ (self, opcode: int, type: AsmOperandType):
            mask = 0
            super().__init__ (opcode, mask, type)

#
# These tables map an opname to an opcode and related info.
# The format of the tables is 
#    handler-function, op-code, mask, operand-type
#
op_code_1958 = { # 
                "si":  FiveBitOpCodeInfo  (0o000, AsmOperandType.Param),
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

op_code_1950 = { #
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
# Regarding .pp, pp: We should just support .pp as it's our way of
# denoting an assembly-time variable. But we don't need to duplicate the "="
# syntax so I'll propose standard comma notation, e.g.
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

meta_op_code = { # The "dot" in each of these is parsed as an operator and so does not appear in the table
               "org": OpCodeInfo (dot_org_op,              0,                       0, AsmOperandType.None),
             "daorg": OpCodeInfo (dot_daorg_op,            0,                       0, AsmOperandType.None),  # Drum Address Origin
              "base": OpCodeInfo (dot_relative_base_op,    0,                       0, AsmOperandType.None),  # Deprecated
              "word": OpCodeInfo (dot_word_op,             AsmDirectiveOp.DotWord,  0, AsmOperandType.None),
             "flexl": OpCodeInfo (dot_word_op,             AsmDirectiveOp.DotFlexl, 0, AsmOperandType.None),
             "flexh": OpCodeInfo (dot_word_op,             AsmDirectiveOp.DotFlexh, 0, AsmOperandType.None),
            "switch": OpCodeInfo (dot_switch_op,           0,                       0, AsmOperandType.None),
            "jumpto": OpCodeInfo (dot_jumpto_op,           0,                       0, AsmOperandType.None),
             "dbwgt": OpCodeInfo (dot_dbwgt_op,            0,                       0, AsmOperandType.None),
           "ww_file": OpCodeInfo (dot_ww_filename_op,      0,                       0, AsmOperandType.None),
         "ww_tapeid": OpCodeInfo (dot_ww_tapeid_op,        0,                       0, AsmOperandType.None),
               "isa": OpCodeInfo (dot_change_isa_op,       0,                       0, AsmOperandType.None),  # Directive to switch to the older 1950 instruction set
              "exec": OpCodeInfo (dot_python_exec_op,      0,                       0, AsmOperandType.None),
             "print": OpCodeInfo (dot_python_exec_op,      0,                       0, AsmOperandType.None),
               ".pp": OpCodeInfo (dot_preset_param_op,     0,                       0, AsmOperandType.None),  # See comment above
                "pp": OpCodeInfo (insert_program_param_op, 0,                       0, AsmOperandType.None),  # See comment above
             "ditto": OpCodeInfo (ditto_op,                0,                       0, AsmOperandType.None)   # We'll parse .ditto for this
                }

def five_bit_op (p: AsmProgram, *args): return p.five_bit_op (*args)
def seven_bit_op (p: AsmProgram, *args): return p.seven_bit_op (*args)
def csii_op (p: AsmProgram, *args): return p.csii_op (*args)
def dot_org_op (p: AsmProgram, *args): return p.dot_org_op (*args)
def dot_daorg_op (p: AsmProgram, *args): return p.dot_daorg_op (*args)
def dot_relative_base_op (p: AsmProgram, *args): return p.dot_relative_base_op (*args)
def dot_word_op (p: AsmProgram, *args): return p.dot_word_op (*args)
def dot_switch_op (p: AsmProgram, *args): return p.dot_switch_op (*args)
def dot_jumpto_op (p: AsmProgram, *args): return p.dot_jumpto_op (*args)
def dot_dbwgt_op (p: AsmProgram, *args): return p.dot_dbwgt_op (*args)
def dot_ww_filename_op (p: AsmProgram, *args): return p.dot_ww_filename_op (*args)
def dot_ww_tapeid_op (p: AsmProgram, *args): return p.dot_ww_tapeid_op (*args)
def dot_change_isa_op (p: AsmProgram, *args): return p.dot_change_isa_op (*args)
def dot_python_exec_op (p: AsmProgram, *args): return p.dot_python_exec_op (*args)
def dot_preset_param_op (p: AsmProgram, *args): return p.dot_preset_param_op (*args)
def insert_program_param_op (p: AsmProgram, *args): return p.insert_program_param_op (*args)
def ditto_op (p: AsmProgram, *args): return p.ditto_op (*args)

class AsmInst:
    def __init__ (self, parsedLine: ParsedLine, prog: AsmProgram):
        self.cb = wwinfra.theConstWWbitClass
        self.parsedLine = parsedLine
        self.prog = prog
        # self.opcode: int = None       # Subclass def
        # self.pseudoOp: str = None     # Subclass def
        # def passOneOp (self):         # Subclass def
        # def passTwoOp (self):         # Subclass def
        self.instruction: int = None    # 16 bits, may be a ww instruction or data
        self.operandMask: int  = None
        self.address: int = prog.nextCoreAddress
        self.relativeAddressBase: int = None

class AsmWwOpInst (AsmInst):
    def __init__ (self, *args)
        super().__init__ (*args)
        opcodeInfo = self.prog.curOpcodeTab[parsedLine.opname]
        self.opcode: opcodeInfo.opcode
        self.operandMask = opcodeInfo.mask
        self.operandType: AsmOperandType = opcodeInfo.type
    def passOneOp (self):
        pass
    def passTwoOp (self):
        val: AsmValue = self.parsedLine.operand.evalMain (prog.envLookup, self.parsedLine)

        # A value stored in an instruction may be an addresse, or a positive
        # integer n in the range 0 <= n <= 511 mod 32. Thus we disallow
        # negative numbers, -0, or fractions. We could tag each opcode with
        # its operand type, but we'll do that only if necessary.

        if val.type == AsmExprValueType.Integer:
            if val.value < 0:
                error()
            else:
                self.instruction = self.opcode | val.value & self.operandMask
        else:
            error()

class AsmPseudoOpInst (AsmInst):
    def __init__ (self, *args)
        super().__init__ (*args)
        self.opname: str = None

class AsmDotOrgInst (AsmPseudoOpInst):
    def __init__ (self, *args)
        super().__init__ (*args)
    def passOneOp (self):

        # Need to eval this in pass one, since it determines following address
        # alloc. Normally .org is just literals, but any symbols used here
        # must have been defined earlier in the program.

        nextAddr: AsmValue = self.parsedLine.operand.evalMain (prog.envLookup, self.parsedLine)
        if nextAddr.type == AsmExprValueType.Integer:
            prog.nextCoreAddress = nextAddr
            prog.currentRelativeBase = nextAddr   # <--- This is an important assumption!! [Guy]
        else:
            error()
    def passTwoOp (self):
        pass

class AsmDotWordInst (AsmPseudoOpInst):
    def __init__ (self, *args)
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        val: AsmValue = self.parsedLine.operand.evalMain (self.prog.envLookup, self.parsedLine)
        if val.type == AsmExprValueType.Integer:
            # If positive, treat effectively as unsigned for the 16-bit range
            if val.value >= 0:
                if value.value < 2 << self.prog.wordSize:
                    self.instruction = val.value
                else:
                    error()
            else:
                # Value negative -- store one's complement
                self.instruction = (-val.value) ^ self.prog.wordMask
        elif val.type == AsmExprValueType.NegativeZero:
            # Negative zero is its own type
            self.instruction = self.prog.wordMask + 1
        elif val.type == AsmExprValueType.Fraction:
            # Fractions need to stay in signed 16-bit one's complement range
            if val.value >= -self.prog.wordMask and val.value <= self.prog.workMask:
                self.instruction = val.value
            else:
                error()
            else:
                # Value negative -- store one's complement
                self.instruction = (-val.value) ^ self.prog.wordMask

            
        else:
            error()

class AsmDotJumpToInst (AsmPseudoOpInst):
    def __init__ (self, *args)
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        value: int = self.parsedLine.operand.evalMain (prog.envLookup, self.parsedLine)
        self.instruction = value        # Address to which to jump

class DebugWidgetClass:
    def __init__(self, linenumber, addr_str, incr_str, format_str):
        self.linenumber = linenumber
        self.addr_str = addr_str
        self.incr_str = incr_str
        self.addr_binary = None
        self.incr_binary = None
        self.format_str = format_str

class AsmDotDbwgtInst (AsmPseudoOpInst):
    def __init__ (self, *args)
        super().__init__ (*args)
    def passOneOp (self):
        pass
    def passTwoOp (self):
        # We can have a max of three args for the debug widget:
        #   [Address [Incr [Format]]]
        # Address can be any address expression
        # Incr is an integer
        # Format is a %-style format string
        o = self.parsedLine.operand
        address = 0
        incr = 0
        format = ""
        if type (o) is not list:
            address = o.evalMain (prog.presetTab, self.parsedLine)
        else:
            if len (o) == 0:
                error()
            if len (o) >= 1:
                address = o[0].evalMain (prog.presetTab, self.parsedLine)
            if len (o) >= 2:
                incr = o[1].evalMain (prog.presetTab, self.parsedLine)
            if len (o) == 3:
                format = o[2].evalMain (prog.presetTab, self.parsedLine)
            else:
                error()
        self.prog.dbwgtTab.append (DebugWidgetClass (parsedLine.lineNo, address, incr, format))

class AsmProgram:
    def __init__ (self, inStream):
        self.cb = wwinfra.theConstWWbitClass
        self.wordSize = 16
        self.addressMask = 0o3777               # ??? When is it correct to use these masks?
        self.wordMask = 0o177777
        self.coreSize = 2048
        self.operandMask5bit = 0o03777
        self.operandMask6bit = 0o01777
        self.operandMaskShift = 0o777  # shifts can go from 0 to 31, i.e., five bits, but the field has room for 9 bits

        # [Guy says:] I think the CSII assembler defaults to starting to load
        # instructions at 0o40, the first word of writable core.  Of course a
        # .org can change that before loading the first word of the program.
        self.nextCoreAddress: int = 0o40     # Where to put the next instruction.
        
        self.currentRelativeBase: int = 0o40 # Base of NNr style address refs.
        self.inputFile: str = ""             # Input file name, as given on the cmd line.
        self.wwFilename: str = ""
        self.wwTapeId: str = ""
        self.wwJumpToAddress: int = None     # Initial program addr
        self.switchTab = None                # Needed?
        self.legacyNumbers: bool = False
        self.opCodeTable: list = []
        self.isa1950: bool = False
        self.annotateIoArg: bool = False

        self.insts: [AsmInst] = []

        # More than one label can map to an inst, ie since we can have labels
        # on opcode-free lines, including pseudo-ops.  Keep track sequentially,
        # with a cur-label-set reset by a real instruction. Address of label is
        # tied to inst. labelTab was called SymTab in the old assembler.
        self.labelTab = {}                            # Label: str -> AsmInst       A Label is a Variable but not all Variables must be labels.
        self.presetTab = {}                           # Variable: str -> int        Defined via .pp
        
        self.commentTab = [str]*self.coreSize         # An array of comments found in the source, indexed by address
        self.dbwgtTab = []                            # An array [list?] to hold directives to add Debug Widgets to the screen
        self.execTab = {}                             # Dictionary of Python Exec statements, indexed by core mem address
        self.coreMem = [int]*self.coreSize            # An image of the final core memory.
        self.reverseLabelTab = [str]*self.coreSize    # Address: int -> Label: str

        # Arrays to keep track of who's calling whom
        self.coreReferredToByJump = [[] for _ in range(self.coreSize)]      # Used to gen listing
        self.coreReadBy = [[] for _ in range(self.coreSize)]                # For xref
        self.coreWrittenBy = [[] for _ in range(self.coreSize)]             # For xref

        self.inStream = inStream

        pass

    # Given an int detect sign and range and generate a 16-bit one's complement
    # representation
    def IntToSignedWwInt (self. x: int) -> int:
        if val.value >= -self.prog.wordMask and val.value <= self.prog.workMask:
            if val.value < 0:
                r = self.prog.wordMask + val.value
            else:
                r = x
            return r
        else:
            error()

    # Given an int check for positive 16-bit unsigned range and generate an
    # unsigned 16-bit value (identity function)
    def IntToUnsignedWwInt (self. x: int) -> int:
        if val.value >= 0 and val.value <= 2 << self.prog.wordSize:
            return x
        else:
            error()

    # Something we can pass to AsmExpr.eval()
    #
    # May want bells or whistles at some point to distinguish an address from
    # other data.
    #
    def envLookup (var: str) -> AsmExprValue:
        if var in self.labelTab:
            return AsmExprValue (AsmExprValueType.Integer, self.labelTab[var].address)
        elif var in self.presetTab:
            return AsmExprValue (AsmExprValueType.Integer, self.presetTab[var])

    def passOne (self):
        
        # Resolve as much as possible in the first pass, such as ww opcodes,
        # certain pseudo-ops like .org which change assembly state, allocate
        # addresses, assign symbols in label table and preset table.
        #
        # Read and parse the asm file, generate an instruction for each parsed line

        while True:
            lineStr = inStream.readline()
            if lineStr == "":
                break
            else:
                line = AsmParsedLine (lineStr, lineNo, verbose = self.verbose)
                line.parseLine()
                # All lines result in an instruction of some kind
                if line.opname in meta_op_code:
                    inst = AsmPseudoOpInst (line)
                elif line.opname in self.curOpcodeTab:
                    inst = AsmWwOpInst (line)
                else:
                    error()
                # If it has a label, record it
                if line.label != "":
                    labelTab[line.label] = inst
                inst.passOneOp()
                inst.passTwoOp()
                insts.append (inst)
        
        pass

    def passTwo (self):
        
        # Evaluate operands and resolve full instructions as needed. 

        pass
    
            
    def five_bit_op (self, inst: AsmInst, binary_opcode: int, operand_mask: int) -> int:
        inst.address = self.nextCoreAddress
        inst.relativeAddressBase = self.currentRelativeBase
        inst.operandMask = self.operandMask5bit
        inst.opcode = binary_opcode << 11
        addrIncr = 1
        return addrIncr
        
    def seven_bit_op (self, inst: AsmInst, binary_opcode: int, operand_mask: int) -> int:
        inst.address = self.nextCoreAddress
        inst.relativeAddressBase = self.currentRelativeBase
        inst.operandMask = self.operandMaskShift
        inst.opcode = binary_opcode << 9
        addrIncr = 1
        return addrIncr

    # LAS 12/8/24 Made a change in transferring this routine from the original,
    # as the original incremented NextCoreAddress directly, rather than
    # returning an increment and letting the caller do the bump, which seems to
    # have been the convention. So I "fixed" it here and return the incr, but
    # note we still just insert a .word 0.
    
    def csii_op (self, inst: AsmInst, binary_opcode: int, operand_mask: int) -> int:
        cb.log.warn (inst.parsedLine.lineNo,
                     "CS-II operation %s in %s; inserting .word 0" % (inst.parsedLine.opname, inst.parsedLine.lineStr))
        inst.address = self.nextCoreAddress
        inst.relativeAddressBase = self.currentRelativeBase
        inst.operandMask = self.wordMask
        inst.opcode = 0
        addrIncr = 1


    # LAS 12/8/24 The original calls ww_int_csii, a digit parser which should
    # not be needed under the new grammar. However I see in .ww files that .org
    # seems to accept only octal, regardless of the usual numeric parsing
    # format. Here I'm assuming standard format, so e.g. ".ORG 00040" will be
    # taken as decimal.

    def dot_org_op (self, inst: AsmInst, binary_opcode: int, operand_mask: int) -> int:
        nextAddr: AsmValue = inst.parsedLine.operand.evalMain (env, inst.parsedLine)    # env!!!!!!!!
        if nextAddr.type == AsmExprValueType.Integer:
            self.nextCoreAddress = nextAddr
            self.currentRelativeBase = nextAddr   # <--- This is an important assumption!!
            addrIncr = 0
            return addrIncr
        else:
            error()

    # [Guy:] process a .DAORG statement, setting the next *drum* address to
    # load. I have no idea what to do with these!

    def dot_daorg_op (self, inst: AsmInst, binary_opcode: int, operand_mask: int) -> int:
        cb.log.warn (inst.parsedLine.lineNo,
                     "Drum Address pseudo-op %s in %s" % (inst.parsedLine.opname, inst.parsedLine.lineStr))

    # [Guy:] process a .BASE statement, resetting the relative addr count to
    # zero I added this pseudo-op during the first run at cs_ii conversion But
    # on the next go round, I changed it to parse the "0r" label directly.

    def dot_relative_base_op (self, inst: AsmInst, binary_opcode: int, operand_mask: int) -> int:
        cb.log.warn (srcline.linenumber, "Deprecated .BASE @%04oo" % NextCoreAddress)
        self.currentRelativeBase = 0
        addrIncr = 0
        return addrIncr

    # LAS 12/8/24 I'm departing from the original in that the flex ops have
    # their own routines, rather than multiplexing .word

    def dot_word_op (self, inst: AsmInst, binary_opcode: int, operand_mask: int) -> int:
        inst.address = self.nextCoreAddress
        inst.relativeAddressBase = self.currentRelativeBase
        inst.operandMask = self.wordMask
        inst.opcode = 0
        addrIncr = 1
        
