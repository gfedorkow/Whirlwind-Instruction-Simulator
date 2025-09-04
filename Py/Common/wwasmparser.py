
import os
import sys
import traceback
import wwinfra
from enum import Enum

# The parser is used by more than one module and so needs to make sure it uses
# the asm log.

class AsmLogFactory:
    def getLog (self) -> wwinfra.AsmLogClass:
        return wwinfra.LogFactory().getLog (isAsmLog = True)

class AsmParseSyntaxError (Exception):
    pass

class AsmExprEvalError (Exception):
    pass

AsmTokenType = Enum ("AsmTokenType", ["Operator", "Comment", "AutoComment",
                                      "DigitString", "Identifier", "DotPrint", "DotExec",
                                      "String", "EndOfString", "Null"])

class AsmToken:
    def __init__(self, tokenType: AsmTokenType, tokenStr: str):
        self.tokenType = tokenType
        self.tokenStr = tokenStr
    def print (self):
        print ("AsmToken ", self.tokenType, self.tokenStr)

class AsmTokenizer:
    endOfString = "<end-of-string>"
    def __init__ (self, str):
        self.pos = 0
        self.state = 0
        self.str = str
        self.slen = len (str)
        self.buffer = ""
        self.tokenBuf: AsmToken = None
        self.cb = wwinfra.theConstWWbitClass
        self.log = AsmLogFactory().getLog()
    def isWhitespace (self, c) -> bool:
        return c in [' ', '\n', '\r', '\t']
    def caratString (self, str, pos) -> str:
        s = " " * pos
        return ":\n" + str.rstrip ("\r\n") + "\n" + s + "^\n"
    def isSingleCharOper (self, c) -> bool:
        return c in ['+', '-', '@', ':', '.', ';', ',', '*', '/', '|', '&', '(', ')']
    def isDigit (self, c) -> bool:
        return ord (c) >= ord ('0') and ord (c) <= ord ('9')
    def isExtAlphaChar (self, c) -> bool:
        c = c.lower()
        return ord (c) >= ord ('a') and ord (c) <= ord ('z') or c == '_'
    def isExtAlphaNumChar (self, c) -> bool:
        return self.isExtAlphaChar (c) or self.isDigit (c)
    def push (self, c):
        self.buffer += c
    def pop (self):
        buf = self.buffer
        self.buffer = ""
        return buf
    def illegalChar (self, c, pos, str, state):
        # traceback.print_stack()
        raise AsmParseSyntaxError ("Tokenizer state %d: Illegal char \'%c\'" % (state, c))
    def getTokens (self):   # Debug fcn
        token = AsmToken (AsmTokenType.Null, "")
        tokens = []
        while token.tokenType != AsmTokenType.EndOfString:
            token = self.getToken()
            tokens.append (token)
        return tokens
    def printTokens (self, tokens): # Debug fcn
        for token in tokens:
            print (token.tokenType, token.tokenStr)
    # public
    def getToken (self) -> AsmToken:
        if self.tokenBuf is not None:
            token = self.tokenBuf
            self.tokenBuf = None
            return token
        else:
            token1 = self.getRawToken()
            if token1.tokenType == AsmTokenType.Operator and token1.tokenStr == '.':
                token2 = self.getRawToken()
                if token2.tokenType == AsmTokenType.Identifier and token2.tokenStr in ["exec"]:  # ["print", "exec]"
                    tokType = AsmTokenType.DotPrint if token2.tokenStr == "print" else AsmTokenType.DotExec
                    restOfString = self.str[self.pos:self.slen].rstrip ("\r\n")
                    self.tokenBuf = AsmToken (AsmTokenType.EndOfString, "")
                    return AsmToken (tokType, restOfString)
                else:
                    self.tokenBuf = token2
                    return token1
            else:
                return token1
    def getRawToken (self) -> AsmToken:
        while self.pos <= self.slen:
            if self.pos < self.slen:
                c = self.str[self.pos]
            else:
                c = self.endOfString
            match self.state:
                case 0:
                    if c == self.endOfString:
                        self.state = 0
                        return AsmToken (AsmTokenType.EndOfString, "")
                    if self.isWhitespace (c):
                        self.state = 0
                        self.pos += 1
                    elif c == ';':
                        self.state = 5
                        self.pos += 1                        
                    elif c == '@':
                        self.state = 1
                        self.pos += 1
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        self.pos += 1
                        return AsmToken (AsmTokenType.Operator, c)
                    elif c == '0':
                        self.state = 8
                        self.pos += 1
                        self.push (c)
                    elif self.isDigit (c):
                        self.state = 3
                        self.pos += 1
                        self.push (c)
                    elif c == '"':
                        self.state = 9
                        self.pos += 1
                    elif self.isExtAlphaChar (c):
                        self.state = 4
                        self.pos += 1
                        self.push (c)
                    else:
                        self.illegalChar (c, self.pos, self.str, self.state)
                case 1:
                    if c == '@':
                        self.state = 2
                        self.pos += 1
                    else:
                        self.state = 0
                        return AsmToken (AsmTokenType.Operator, "@")
                case 2:
                    if c == self.endOfString:
                        self.state = 0
                        return AsmToken (AsmTokenType.AutoComment, self.pop())
                    else:
                        self.state = 2
                        self.pos += 1
                        self.push (c)
                case 3:
                    if c == self.endOfString:
                        self.state = 0
                        return AsmToken (AsmTokenType.DigitString, self.pop())
                    if self.isDigit (c):
                        self.state = 3
                        self.pos += 1
                        self.push (c)
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        return AsmToken (AsmTokenType.DigitString, self.pop())
                    elif self.isWhitespace (c):
                        self.state = 0
                        self.pos += 1
                        return AsmToken (AsmTokenType.DigitString, self.pop())
                    elif self.isExtAlphaChar (c):
                        self.state = 4
                        self.pos += 1
                        self.push (c)
                    else:
                        self.illegalChar (c, self.pos, self.str, self.state)
                case 4:
                    if c == self.endOfString:
                        self.state = 0
                        return AsmToken (AsmTokenType.Identifier, self.pop())
                    elif self.isExtAlphaNumChar (c):
                        self.state = 4
                        self.pos += 1
                        self.push (c)
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        return AsmToken (AsmTokenType.Identifier, self.pop())
                    elif self.isWhitespace (c):
                        self.state = 0
                        self.pos += 1
                        return AsmToken (AsmTokenType.Identifier, self.pop())
                    else:
                        self.illegalChar (c, self.pos, self.str, self.state)
                case 5:
                    if c == '@':
                        self.state = 6
                        self.pos += 1
                    elif c == self.endOfString:
                        self.state = 0
                        return AsmToken (AsmTokenType.Comment, self.pop())
                    else:
                        self.state = 5
                        self.pos += 1
                        self.push (c)
                case 6:
                    if c == '@':
                        self.state = 7
                        self.pos += 1
                        return AsmToken (AsmTokenType.Comment, self.pop())
                    else:
                        self.push ('@')     # We want the previous atsign
                        self.state = 5
                case 7:
                    if c == self.endOfString:
                        self.state = 0
                        return AsmToken (AsmTokenType.AutoComment, self.pop())
                    else:
                        self.state = 7
                        self.pos += 1
                        self.push (c)
                case 8:
                    if c == 'o':
                        self.state = 3
                        self.pos += 1
                        self.pop()
                        return AsmToken (AsmTokenType.Operator, "0o")
                    elif c == self.endOfString:
                        self.state = 0
                        self.pop()
                        return AsmToken (AsmTokenType.DigitString, "0")
                    elif self.isDigit (c):
                        self.state = 3
                        self.pos += 1
                        self.push (c)
                    elif self.isWhitespace (c):
                        self.state = 0
                        self.pos += 1
                        self.pop()
                        return AsmToken (AsmTokenType.DigitString, "0")
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        self.pop()
                        return AsmToken (AsmTokenType.DigitString, "0")
                    elif self.isExtAlphaNumChar (c):
                        self.state = 4
                    else:
                        self.illegalChar (c, self.pos, self.str, self.state)
                case 9:
                    if c == '"':
                        self.state = 0
                        self.pos += 1
                        return AsmToken (AsmTokenType.String, self.pop())
                    elif c == "\\":
                        self.state = 10
                        self.pos += 1
                    else:
                        self.state = 9
                        self.pos += 1
                        self.push (c)
                # Here we process common escapes \n etc. and note they are
                # converted back to escapes in AsmExpr.listingstring(). 
                case 10:
                    if c == "b":
                        self.state = 9
                        self.pos += 1
                        self.push ("\b")
                    elif c == "t":
                        self.state = 9
                        self.pos += 1
                        self.push ("\t")
                    elif c == "n":
                        self.state = 9
                        self.pos += 1
                        self.push ("\n")
                    else:
                        self.state = 9
                        self.push ("\\")
        return AsmToken()


AsmExprType = Enum ("AsmExprType", ["BinaryPlus", "BinaryMinus",
                                    "UnaryPlus", "UnaryMinus", "UnaryZeroOh",
                                    "BinaryMult", "BinaryDiv",
                                    "BinaryDot", "BinaryComma",
                                    "BinaryBitAnd", "BinaryBitOr",
                                    "Variable", "LiteralString", "LiteralDigits",
                                    "ParenWrapper", "Null"])

# LAS 11/14/24 We have three numerical value types, each constrained to a bit
# length of 16: integer, negative-zero, and fraction. We have one string type,
# used only as a literal, for pseudo-ops like .print. We have the List type for
# gathering up expressions via the comma operator. The value of a List type is
# a list of AsmExprValues. Such a list will be produced when there are multiple
# operands, e.g ".dbwgt xyz, 0o10".
#
# Assembly-time arithmetic operations treat the binary point differently in the
# integer and fraction cases.  Right now such arithmetic is only supported on
# integers. A fraction, negative zero, or string appearing in one of those
# operations results in an error.  Fractions, negative zero, and strings can be
# literals only. There doesn't seem to be a reason right now to support
# arithmetic on fractions at the assembly-lang level, and negative zero is only
# relevant on one's-complement machines.  Assembly-language integers are
# represented by the integer type of the host language. Negative zero does not
# appear as a distinct value in any modern languages. For storing in ww memory,
# values are converted to one's complement. Addresses should not need
# conversion (i.e., conversion in this domain is the identity fcn) as they
# can't go negative (should be an error to get a negative number for final
# storage as an address), and are not large enough to need more bits than a
# non-negative one's-complement ww number.
#
# Numeric values in AsmExprValue are always signed integers. Fractions are
# computed by converting the digit string to a signed floating point number,
# multiplying that by 2^15 and rounding to the nearest int.
#
# Signed integer values in the host language are converted to 16-bit
# one's-complement signed integers. Positive integers in the host language
# greater than 2^15 - 1 will be stored as unsigned 16 bit values. This then
# easily supports 0o, for example.
#
# Unbound variables in eval return the Undefined value.

AsmExprValueType = Enum ("AsmExprValueType", ["Integer", "NegativeZero", "Fraction",
                                              "String", "List", "Undefined"])

# Needed by debugger, as we need to differentiate between a plain value and an address.

AsmExprValueSubType = Enum ("AsmExprValueSubType", ["Address", "Undefined"])

class AsmExprValue:
    def __init__ (self, exprValueType: AsmExprValueType, value,
                  subType = AsmExprValueSubType.Address):
        self.type = exprValueType
        self.subType = subType
        self.value = value  # int or float or str or list
    def asString (self) -> str:
        if self.type == AsmExprValueType.List:
            return str (self.type) + " " + str ([v.asString() for v in self.value])
        else:
            return str (self.type) + " " + str (self.value)

# We use a generic function here so that an eval may be done from contexts
# outside the parser module, without requirng the parser module to import all
# sorts of extra stuff. This maintains modularity and also helps avoid circular
# refs, which python really seems to hate. So e.g., in wwasm.py tables are
# built for labels and other vars and we just pass those to the AsmExprEnv
# subclass that support the lookup fcn.

class AsmExprEnv:
    def __init__ (self):
        pass
    # Overridden by subclasses
    def lookup (self, var: str) -> AsmExprValue:
        # If we're just testing the parser we'll return 42 for everything
        return AsmExprValue (AsmExprValueType.Integer, 42)

class AsmExpr:
    def __init__ (self, exprType: AsmExprType, exprData: str):
        self.cb = wwinfra.theConstWWbitClass
        self.exprType = exprType
        self.exprData = exprData            # variable, literal, or oper name
        self.leftSubExpr: AsmExpr = None
        self.rightSubExpr: AsmExpr = None
        self.suppressEvalError: bool = False # Feels likea hack, but adding an error value type is worse. Needed by --Reformat
    def print (self, indent = 3):           # Debug fcn
        t = self.exprType
        if t in [AsmExprType.BinaryPlus, AsmExprType.BinaryMinus,
                 AsmExprType.BinaryMult, AsmExprType.BinaryDiv, AsmExprType.BinaryDot,
                 AsmExprType.BinaryBitAnd, AsmExprType.BinaryBitOr,
                 AsmExprType.BinaryComma]:
            print (" " * indent + t.name)
            if self.leftSubExpr is not None:
                self.leftSubExpr.print (indent = indent + 3)
            else:
                print (" " * indent + "None")   # Should only get here if there is a bug
            if self.rightSubExpr is not None:
                self.rightSubExpr.print (indent = indent + 3)
            else:
                print (" " * indent + "None")   # Should only get here if there is a bug
        elif t in [AsmExprType.UnaryPlus, AsmExprType.UnaryMinus, AsmExprType.UnaryZeroOh, AsmExprType.ParenWrapper]:
            print (" " * indent + t.name)
            self.leftSubExpr.print (indent = indent + 3)
        elif t in [AsmExprType.Variable, AsmExprType.LiteralString, AsmExprType.LiteralDigits, AsmExprType.Null]:
            print (" " * indent + t.name, self.exprData)
    def listingString (self, quoteStrings: bool = True):
        if self.exprType in [AsmExprType.BinaryPlus, AsmExprType.BinaryMinus,
                             AsmExprType.BinaryMult, AsmExprType.BinaryDiv, AsmExprType.BinaryBitAnd,
                             AsmExprType.BinaryBitOr]:
            return self.leftSubExpr.listingString() + " " + self.exprData + " " + self.rightSubExpr.listingString()
        elif self.exprType in [AsmExprType.BinaryDot, AsmExprType.BinaryComma]:
            opStr = "." if self.exprType == AsmExprType.BinaryDot else ", "
            return self.leftSubExpr.listingString() + opStr + self.rightSubExpr.listingString()
        elif self.exprType in [AsmExprType.UnaryPlus, AsmExprType.UnaryMinus, AsmExprType.UnaryZeroOh]:
            return self.exprData + self.leftSubExpr.listingString()
        elif self.exprType in [AsmExprType.LiteralString]:
            s = self.strToSrcFormat (self.exprData)
            return "\"" + s + "\"" if quoteStrings else s
        elif self.exprType == AsmExprType.ParenWrapper:
            return "(" + self.leftSubExpr.listingString() + ")"
        else:
            return self.exprData
    # Convert newlines back to escapes, etc.
    def strToSrcFormat (self, s: str) -> str:
        return s.replace("\n", "\\n").replace("\b", "\\b").replace("\t", "\\t")
    def getIdStr (self):    # Just for test/debug print
        return "AsmExpr-" + str (id (self))
    def evalError (self, msg: str):
        raise AsmExprEvalError (msg)
    def DecimalDigitStringToInt (self, s: str) -> int:
        return int (s)
    def OctalDigitStringToInt (self, s: str) -> int:
        r = 0
        for i in range (len(s)):
            c = s[i]
            d = ord(c) - ord('0')
            if d < 0 or d > 7:
                self.evalError ("Digit string must be octal")
            else:
                r = 8*r + d
        return r
    #
    # Entry point for eval, with error-catching wrapper.
    #
    # Hokey python, Batman! We want to declare parsedLine below as
    # AsmParsedLine, but it looks like an explicit fwd decl is needed. The
    # solution for now is just don't declare it!
    #
    def evalMain (self, env: AsmExprEnv, parsedLine) -> AsmExprValue:
        try:
            return self.eval (env)
        except AsmExprEvalError as e:
            sys.stdout.flush()
            # traceback.print_stack()
            p = parsedLine
            if not self.suppressEvalError:
                p.log.error (p.lineNo, "%s:\n%s" % (e, p.lineStr))
            """
            p.log.error (p.lineNo,
                         "Char pos %d: %s%s" %
                         (p.tokenizer.pos, e, p.tokenizer.caratString (p.lineStr, p.tokenizer.pos - 1)))
            """
            return AsmExprValue (AsmExprValueType.Undefined, "")
    def eval (self, env: AsmExprEnv) -> AsmExprValue:
        if self.exprType in [AsmExprType.BinaryPlus,
                             AsmExprType.BinaryMinus,
                             AsmExprType.BinaryMult,
                             AsmExprType.BinaryDiv,
                             AsmExprType.BinaryBitAnd,
                             AsmExprType.BinaryBitOr]:
            x = self.leftSubExpr.eval (env)
            onlyIntMsg = "Only integers are allowed in arithmetic operations"
            if (x.type != AsmExprValueType.Integer):
                self.evalError (onlyIntMsg)
            else:
                y = self.rightSubExpr.eval (env)
                if (y.type != AsmExprValueType.Integer):
                    self.evalError (onlyIntMsg)
                else:
                    fcn = {
                        AsmExprType.BinaryPlus:   lambda x, y: x + y,
                        AsmExprType.BinaryMinus:  lambda x, y: x - y,
                        AsmExprType.BinaryMult:   lambda x, y: x * y,
                        AsmExprType.BinaryDiv:    lambda x, y: x // y,
                        AsmExprType.BinaryBitAnd: lambda x, y: x & y,
                        AsmExprType.BinaryBitOr:  lambda x, y: x | y
                        }[self.exprType]
                    return AsmExprValue (AsmExprValueType.Integer, fcn (x.value, y.value))
        elif self.exprType == AsmExprType.BinaryDot and \
             self.leftSubExpr.exprType in [AsmExprType.UnaryPlus, AsmExprType.UnaryMinus] and \
             self.leftSubExpr.leftSubExpr.exprType == AsmExprType.LiteralDigits and \
             self.leftSubExpr.leftSubExpr.exprData in ["0", "1"] and \
             self.DecimalDigitStringToInt (self.rightSubExpr.exprData) is not None:
            # It's a literal decimal fraction
            s = "%s%s.%s" % (
                "+" if self.leftSubExpr.exprType == AsmExprType.UnaryPlus else "-",
                self.leftSubExpr.leftSubExpr.exprData,
                self.rightSubExpr.exprData)
            v = float (s)
            if v >= 1.0:
                self.evalError ("Too many digits specified in fraction")
            return AsmExprValue (AsmExprValueType.Fraction, v)
        elif self.exprType == AsmExprType.BinaryDot:
            # It's a literal octal number, of the form (0|1).xxxxx
            # Essentially, assure xxxxx is 5 octal digits, cut out the dot, and convert unsigned
            l = self
            if l.leftSubExpr.exprType == AsmExprType.LiteralDigits and \
               l.rightSubExpr.exprType == AsmExprType.LiteralDigits and \
               l.leftSubExpr.exprData in ["0", "1"] and \
               len (l.rightSubExpr.exprData) == 5:
                v = self.OctalDigitStringToInt (l.leftSubExpr.exprData + l.rightSubExpr.exprData)
                return AsmExprValue (AsmExprValueType.Integer, v)
            else:
                self.evalError ("Improperly formatted octal number")
        elif self.exprType in [AsmExprType.UnaryPlus, AsmExprType.UnaryMinus]:
            # Handle ordinary unary op, with specialization of -0
            x = self.leftSubExpr.eval (env)
            if self.exprType == AsmExprType.UnaryMinus and x.type == AsmExprValueType.Integer and x.value == 0:
                # -0 case
                return AsmExprValue (AsmExprValueType.NegativeZero, 0)
            else:
                return AsmExprValue (AsmExprValueType.Integer, (-1 if self.exprType == AsmExprType.UnaryMinus else 1) * x.value)
        elif self.exprType == AsmExprType.UnaryZeroOh:
            # Handle 0o
            l = self
            if l.leftSubExpr.exprType == AsmExprType.LiteralDigits:
                v = self.OctalDigitStringToInt (l.leftSubExpr.exprData)
                return AsmExprValue (AsmExprValueType.Integer, v)
            else:
                self.evalError ("Improperly formatted octal number")
        elif self.exprType == AsmExprType.LiteralDigits:
            # Bare digits are taken as a decimal integer
            l = self
            v = self.DecimalDigitStringToInt (l.exprData)
            return AsmExprValue (AsmExprValueType.Integer, v)
        elif self.exprType == AsmExprType.LiteralString:
            # Literal string
            l = self
            return AsmExprValue (AsmExprValueType.String, l.exprData)
        elif self.exprType == AsmExprType.Variable:
            # Variable
            r = env.lookup (self.exprData)
            if r is not None:
                return r
            else:
                self.evalError ("Unbound variable %s" % self.exprData)
        elif self.exprType == AsmExprType.BinaryComma:
            x = self.leftSubExpr.eval (env)
            y = self.rightSubExpr.eval (env)
            if y.type == AsmExprValueType.List:
                if y.value is not None:
                    y.value.insert (0, x)
                    return AsmExprValue (AsmExprValueType.List, y.value)
                else:
                    return AsmExprValue (AsmExprValueType.List, [x])
            else:
                return AsmExprValue (AsmExprValueType.List, [x, y])
        elif self.exprType == AsmExprType.ParenWrapper:
            return self.leftSubExpr.eval (env)
        elif self.exprType == AsmExprType.Null:
            return AsmExprValue (AsmExprValueType.Undefined, "")
        else:
            self.evalError ("Unknown Asm Expression Type")

class AsmParsedLine:
    def __init__ (self, str, lineNo: int, verbose = False):
        self.cb = wwinfra.theConstWWbitClass
        self.log = AsmLogFactory().getLog()
        self.verbose = verbose  # Passed in potentially on the test (main) command line; key on this for debug output
        self.lineStr = str.rstrip ("\r\n")
        self.lineNo = lineNo
        self.tokenizer = AsmTokenizer (str)
        self.tokenBuf = []
        self.dotIfExpr: AsmExpr = None
        self.prefixAddr = {}
        self.label = ""
        self.opname = ""
        self.operand: AsmExpr = None
        self.comment = ""
        self.autoComment = ""
    def gtok (self) -> AsmToken:
        if self.tokenBuf != []:
            r = self.tokenBuf.pop()
        else:
            r = self.tokenizer.getToken()
        return r
    def ptok (self, tok):
        self.tokenBuf.append (tok)
    def error (self, msg: str):
        # sys.stdout.flush()
        # sys.stderr.flush()
        # traceback.print_stack()
        raise AsmParseSyntaxError (msg)
    def print (self):   # Debug fcn
        s = " "*3
        print ("\nAsmParsedLine:\n",
               s + "line=", self.lineStr, "\n",
               s + "dotIf=", self.dotIfExpr, "\n",
               s + "prefixAddr=", self.prefixAddr, "\n",
               s + "label=", self.label, "\n",
               s + "opname=", self.opname, "\n",
               s + "operand=", "AsmExpr-" + str (id (self.operand)) if self.operand is not None else "None", "\n",
               s + "comment=", self.comment, "\n",
               s + "auto-comment=", self.autoComment)
        if self.operand is not None:
            print ("Operand AsmExpr-" + str (id (self.operand)) + ":")
            self.operand.print()
        if self.dotIfExpr is not None:
            print (".if AsmExpr-" + str (id (self.dotIfExpr)) + ":")
            self.dotIfExpr.print()
    # public
    def parseLine (self) -> bool:
        try:
            self.parsePrefixAddr()
            self.parseDotIf()
            self.parseLabel()
            self.parseInst()
            self.parseComment()
            self.parseAutoComment()
            return True
        except AsmParseSyntaxError as e:
            sys.stdout.flush()
            self.log.error (self.lineNo,
                            "%s at char pos %d%s" % (e, self.tokenizer.pos, self.tokenizer.caratString (self.lineStr, self.tokenizer.pos - 1)))
            return False
    # Called from DbgDebugger for command-line processing
    def parseDbgLine (self) -> bool:
        try:
            self.parseDbgInst()
            return True
        except AsmParseSyntaxError as e:
            sys.stdout.flush()
            self.log.error (self.lineNo,
                            "%s at char pos %d%s" % (e, self.tokenizer.pos, self.tokenizer.caratString (self.lineStr, self.tokenizer.pos - 1)))
            return False
    def parsePrefixAddr (self) -> bool:
        errMsg = "Syntax error in prefix address"
        tok = self.gtok()
        if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == "@":
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.DigitString:
                self.prefixAddr[0] = tok.tokenStr
                tok = self.gtok()
                if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ".":
                    tok = self.gtok()
                    if tok.tokenType == AsmTokenType.DigitString:
                        self.prefixAddr[1] = tok.tokenStr
                        tok = self.gtok()
                        if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ":":
                            tok = self.gtok()
                            if tok.tokenType == AsmTokenType.DigitString:
                                self.prefixAddr[2] = tok.tokenStr
                                return True
                            else:
                                self.error (errMsg)
                        else:
                            self.error (errMsg)
                    else:
                        self.error (errMsg)
                else:
                    if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ":":
                        tok = self.gtok()
                        if tok.tokenType == AsmTokenType.DigitString:
                            self.prefixAddr[2] = tok.tokenStr
                            return True
                        else:
                            self.error (errMsg)
                    else:
                        self.error (errMsg)
            else:
                self.error (errMsg)
        else:
            self.ptok (tok)
            return False
    def parseLabel (self) -> bool:
        tok1 = self.gtok()
        if tok1.tokenType == AsmTokenType.Identifier:
            tok2 = self.gtok()
            if tok2.tokenType == AsmTokenType.Operator and tok2.tokenStr == ":":
                self.label = tok1.tokenStr
                return True
            else:
                self.ptok (tok2)
                self.ptok (tok1)
                return False
        else:
            self.ptok (tok1)
            return False;
    def parseDotIf (self) -> bool:
        tok1 = self.gtok()
        if tok1.tokenType == AsmTokenType.Operator and  tok1.tokenStr == ".":
            tok2 = self.gtok()
            if tok2.tokenType == AsmTokenType.Identifier and tok2.tokenStr == "if":
                #
                # "Ideal" model is to parse a full expr, but we need to be
                # simple in this part of the source line, so we'll just parse
                # an atom. Note, though, it should work to write an arbitrarily
                # complex expr in parens, if so desired.
                #
                e = self.parseAtom()
                self.dotIfExpr = e
                return True
            else:
                self.ptok (tok2)
                self.ptok (tok1)
                return False
        else:
            self.ptok (tok1)
            return False
    def parseInst (self) -> bool:
        tok1 = self.gtok()
        if tok1.tokenType == AsmTokenType.Identifier:
            e = self.parseExpr()
            self.operand = e
            self.opname = tok1.tokenStr
            return True
        elif tok1.tokenType == AsmTokenType.Operator and  tok1.tokenStr == ".":
            tok2 = self.gtok()
            if tok2.tokenType == AsmTokenType.Identifier:
                e = self.parseExpr()
                self.operand = e
                self.opname = tok2.tokenStr
                return True
            else:
                self.error ("Opname expected")
        elif tok1.tokenType == AsmTokenType.DotPrint or tok1.tokenType == AsmTokenType.DotExec:
            self.opname = "print" if  tok1.tokenType == AsmTokenType.DotPrint else "exec"
            self.operand = AsmExpr (AsmExprType.LiteralString, tok1.tokenStr)
            return True
        else:
            self.ptok (tok1)
            return False
    def parseDbgInst (self) -> bool:
        tok1 = self.gtok()
        if tok1.tokenType == AsmTokenType.Identifier:
            tok2 = self.gtok()
            if tok2.tokenType == AsmTokenType.EndOfString:
                e = AsmExpr (AsmExprType.Null, "")
            else:
                self.ptok (tok2)
                e = self.parseExpr()
            self.operand = e
            self.opname = tok1.tokenStr
            return True
        else:
            self.ptok (tok1)
            return False
    def parseExpr (self) -> AsmExpr:
        return self.parseCommaOper()
    def parseComment (self) -> bool:
        tok = self.gtok()
        if tok.tokenType == AsmTokenType.Comment:
            self.comment = tok.tokenStr.rstrip ("\r\n \t")
            return True
        else:
            self.ptok (tok)
            return False
    def parseAutoComment (self) -> bool:
        tok = self.gtok()
        if tok.tokenType == AsmTokenType.AutoComment:
            self.autoComment = tok.tokenStr
            return True
        else:
            self.ptok (tok)
            return False
    def parseUnaryOper (self) -> AsmExpr:
        tok = self.gtok()
        if tok.tokenType == AsmTokenType.Operator:
            if tok.tokenStr in ["+", "-", "0o"]:
                negate = tok.tokenStr == "-"
                # This is really groovy python syntax...
                exprType = {"-":AsmExprType.UnaryMinus,"+":AsmExprType.UnaryPlus,"0o":AsmExprType.UnaryZeroOh}[tok.tokenStr]
                e1 = AsmExpr (exprType, tok.tokenStr)
            else:
                self.ptok (tok)
                return self.parseAtom()
            e2 = self.parseUnaryOper()
            if e2 is not None:
                e1.leftSubExpr = e2
                return e1
            else:
                self.error ("Unary operator syntax error")
        else:
            self.ptok (tok)
            return self.parseAtom()
        
    # LAS 12/7/24 The binary op parsers (parseCommaOper through ParseDotOper)
    # are essentialy clones, and I haven't found a good way yet to refactor
    # them.

    # With that said, the comma operator is the only one that's not quite a
    # clone, since it's right-associative, and everything else is
    # left-associative.
    def parseCommaOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseBitOrOper()
        if e1 is not None:
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ",":
                e2 = self.parseCommaOper()
                if e2 is not None:
                    e = AsmExpr (AsmExprType.BinaryComma, tok.tokenStr)
                    e.leftSubExpr = e1
                    e.rightSubExpr = e2
                    return e
                else:
                    return e1
            else:
                self.ptok (tok)
                return e1
        else:
            self.error ("Comma operator syntax error")
    def parseBitOrOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseBitAndOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["|"]:
                e = AsmExpr (AsmExprType.BinaryBitOr, tok.tokenStr)
                if leftExpr is not None:
                    e.leftSubExpr = leftExpr
                else:
                    e.leftSubExpr = e1
                e2 = self.parseBitOrOper (leftExpr = e)
                return e2
            else:
                self.ptok (tok)
                if leftExpr is not None:
                    return leftExpr
                else:
                    return e1
        else:
            self.error ("Bitwise-or operator syntax error")
    def parseBitAndOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseAdditiveOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["&"]:
                e = AsmExpr (AsmExprType.BinaryBitAnd, tok.tokenStr)
                if leftExpr is not None:
                    e.leftSubExpr = leftExpr
                else:
                    e.leftSubExpr = e1
                e2 = self.parseBitAndOper (leftExpr = e)
                return e2
            else:
                self.ptok (tok)
                if leftExpr is not None:
                    return leftExpr
                else:
                    return e1
        else:
            self.error ("Bitwise-and operator syntax error")
    def parseAdditiveOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseMultiplicativeOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["+", "-"]:
                e = AsmExpr (AsmExprType.BinaryPlus if tok.tokenStr == '+' else AsmExprType.BinaryMinus, tok.tokenStr)
                if leftExpr is not None:
                    e.leftSubExpr = leftExpr
                else:
                    e.leftSubExpr = e1
                e2 = self.parseAdditiveOper (leftExpr = e)
                return e2
            else:
                self.ptok (tok)
                if leftExpr is not None:
                    return leftExpr
                else:
                    return e1
        else:
            self.error ("Additive operator syntax error")
    def parseMultiplicativeOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseDotOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["*", "/"]:
                d = {"*": AsmExprType.BinaryMult, "/": AsmExprType.BinaryDiv}
                e = AsmExpr (d[tok.tokenStr], tok.tokenStr)
                if leftExpr is not None:
                    e.leftSubExpr = leftExpr
                else:
                    e.leftSubExpr = e1
                e2 = self.parseMultiplicativeOper (leftExpr = e)
                return e2
            else:
                self.ptok (tok)
                if leftExpr is not None:
                    return leftExpr
                else:
                    return e1
        else:
            self.error ("Multiplicative operator syntax error")
    def parseDotOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseUnaryOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["."]:
                e = AsmExpr (AsmExprType.BinaryDot, tok.tokenStr)
                if leftExpr is not None:
                    e.leftSubExpr = leftExpr
                else:
                    e.leftSubExpr = e1
                e2 = self.parseDotOper (leftExpr = e)
                return e2
            else:
                self.ptok (tok)
                if leftExpr is not None:
                    return leftExpr
                else:
                    return e1
        else:
            self.error ("Dot operator syntax error")
    def parseAtom (self) -> AsmExpr:
        tok = self.gtok()
        tokTypeDict = {
            AsmTokenType.DigitString: AsmExprType.LiteralDigits,
            AsmTokenType.Identifier: AsmExprType.Variable,
            AsmTokenType.String: AsmExprType.LiteralString
            }
        if tok.tokenType in tokTypeDict:
            return AsmExpr (tokTypeDict[tok.tokenType], tok.tokenStr)
        elif tok.tokenType == AsmTokenType.Operator and tok.tokenStr == "(":
            # Open the trap door to the wormhole to another dimension...
            e = self.parseExpr()
            if e is not None:
                tok = self.gtok()
                if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ")":
                    r = AsmExpr (AsmExprType.ParenWrapper, "")  # An eval pass-through; used only for listing
                    r.leftSubExpr = e
                    return r
                else:
                    self.error ("Unbalanced parentheses")
            else:
                self.error ("Nested expression syntax error")
        else:
            self.ptok (tok)
            return None

class AsmParseTest:
    def __init__ (self, cmdArgs):
        self.cmdArgs = cmdArgs
        self.outStream = self.openOutStream()
        self.verbose = self.cmdArgs.Verbose
        self.cb = wwinfra.theConstWWbitClass
        self.log = AsmLogFactory().getLog()
        self.parsedLines = []
        self.lineToSection = {}
        self.lineToLabel = {}
        self.addrRefsToReferringLine = {}
        self.curSection = ""
    def openOutStream (self):
        return
        """
        inFileName = self.cmdArgs.inFileName
        outFileName = self.cmdArgs.OutFile if self.cmdArgs.OutFile is not None else self.getOutFileName (inFileName)
        if outFileName == "-":
            return sys.stdout
        else:
            return open (outFileName, "w")
        """
    def getOutFileName (self, inFileName):
        for i in range (len(inFileName)):
            j = len (inFileName) - 1 - i
            c = inFileName[j]
            if c == '.':
                return inFileName[0:j] + ".ww"
        return inFileName + ".ww"
    def flush (self):
        sys.stdout.flush()
        sys.stderr.flush()
    def parseLines (self):
        verbose = self.cmdArgs.Verbose
        lineNo = 1
        s = open (self.cmdArgs.inFileName, "r")
        while True:
            line = s.readline()
            if line == "":
                break
            else:
                l = AsmParsedLine (line, lineNo, verbose = self.verbose)
                l.parseLine()
                if verbose:
                    l.print()
                    self.flush()
                self.parsedLines.append (l)
                lineNo += 1
                if l.dotIfExpr is not None:
                    env = AsmExprEnv()
                    if verbose:
                        print ("Eval .if:")
                        print (" "*2 + l.dotIfExpr.getIdStr())
                    v = l.dotIfExpr.evalMain (env, l)
                    if v is not None:
                        if verbose:
                            print (" "*4 + v.asString())
                            print ("")
                if l.operand is not None:
                    env = AsmExprEnv()
                    if verbose:
                        print ("Eval operand:")
                        print (" "*2 + l.operand.getIdStr())
                    v = l.operand.evalMain (env, l)
                    if v is not None:
                        if verbose:
                            print (" "*4 + v.asString())
                            print ("")
                    if verbose:
                        self.flush()

# The main program is used for test and debug. Prints produced via the
# AsmParseTest class write logs which are then compared the test scripts, so
# caution should be taken when changing the format. The verbose option is
# detected by all code herein and prints stuff just for debugging. The outfile
# code is there in case we want file output sometime.

def main():
    parser = wwinfra.StdArgs().getParser (".")
    parser.add_argument ("inFileName", help="")
    # parser.add_argument ("-o", "--OutFile", help="File to write (default basename(inputFileName).ww)", type=str)
    parser.add_argument ("-v", "--Verbose", help="Print parse tree and eval result", action="store_true")
    cmdArgs = parser.parse_args()
    cb = wwinfra.ConstWWbitClass (args = cmdArgs)
    wwinfra.theConstWWbitClass = cb
    # cb.log = wwinfra.LogFactory().getLog (isAsmLog = True)    # LAS
    t = AsmParseTest (cmdArgs)
    t.parseLines()
 
if __name__ == "__main__":
    main()
