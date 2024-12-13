

import os
import sys
import traceback
import wwinfra
from enum import Enum

class AsmParseSyntaxError (Exception):
    pass

class AsmExprEvalError (Exception):
    pass

AsmTokenType = Enum ("AsmTokenType", ["Operator", "Comment", "AutoComment",
                                      "DigitString", "Identifier", "DotPrint", "DotExec",
                                      "EndOfString", "Null"])

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
                if token2.tokenType == AsmTokenType.Identifier and token2.tokenStr in ["print", "exec"]:
                    tokType = AsmTokenType.DotPrint if token2.tokenStr == "print" else AsmTokenType.DotExec
                    restOfString = self.str[self.pos:self.slen]
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
                        return AsmToken (AsmTokenType.AutoCommment, self.pop())
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
        return AsmToken()


AsmExprType = Enum ("AsmExprType", ["BinaryPlus", "BinaryMinus",
                                    "UnaryPlus", "UnaryMinus", "UnaryZeroOh",
                                    "BinaryMult", "BinaryDot", "BinaryComma",
                                    "BinaryBitAnd", "BinaryBitOr",
                                    "Variable", "LiteralString", "LiteralDigits"])

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
# appear as a distinct value in any modern languages. For storing in ww memory
# values are converted to one's complement. Addresses should not need
# conversion (i.e., conversion in this domain is the identity fcn) as they
# can't go negative (should be an error to get a negative number for final
# storage as an address), and are not large enough to need more bits than a
# non-negative one's-complement ww number.
#
# Numeric values in AsmExprValue are always signed integers. Fractions are
# computed by converting the digit string to a signed floating point number,
# and multiplying that by 2^15 and rounding to the nearest int.
#
# Signed integer values in the host language are converted to 16-bit
# one's-complement signed integers. Positive integers greater than 2^15 - 1
# will be stored as unsigned 16 bit values. This then easily supports 0o, for
# example.

AsmExprValueType = Enum ("AsmExprValueType", ["Integer", "NegativeZero", "Fraction", "String", "List"])

class AsmExprValue:
    def __init__ (self, exprValueType: AsmExprValueType, value):
        self.type = exprValueType
        self.value = value  # int or str or list
    def asString (self) -> str:
        if self.type == AsmExprValueType.List:
            return str (self.type) + " " + str ([v.asString() for v in self.value])
        else:
            return str (self.type) + " " + str (self.value)

# We use a generic function here so that an eval may be done from contexts
# outside the parser module, without requirng the parses module to import all
# sorts of extra stuff. This maintains modularity and also helps avoid circular
# refs, which python really seems to hate, So e.g., in wwasm.py tables are
# built for labels and other vars and we can just pass in the function that
# access those.

class AsmExprEnv:
    def __init__ (self, lookupFcn = lambda x: AsmExprValue (AsmExprValueType.Integer, 42)):
        self.lookupFcn = lookupFcn
    def lookup (self, var: str) -> AsmExprValue:
        return self.lookupFcn (var)

class AsmExpr:
    def __init__ (self, exprType: AsmExprType, exprData: str):
        self.cb = wwinfra.theConstWWbitClass
        self.exprType = exprType
        self.exprData = exprData            # variable or literal
        self.leftSubExpr: AsmExpr = None
        self.rightSubExpr: AsmExpr = None
    def print (self, indent = 3):           # Debug fcn
        t = self.exprType
        if t in [AsmExprType.BinaryPlus, AsmExprType.BinaryMinus,
                 AsmExprType.BinaryMult, AsmExprType.BinaryDot,
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
        elif t in [AsmExprType.UnaryPlus, AsmExprType.UnaryMinus, AsmExprType.UnaryZeroOh]:
            print (" " * indent + t.name)
            self.leftSubExpr.print (indent = indent + 3)
        elif t in [AsmExprType.Variable, AsmExprType.LiteralString, AsmExprType.LiteralDigits]:
            print (" " * indent + t.name, self.exprData)
    def getIdStr (self):
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
    # Hokey python! We want to declare parsedLine below as AsmParsedLine, but
    # it looks like an explicit fwd decl is needed. The solution for now is
    # just don't declare it!
    def evalMain (self, env: AsmExprEnv, parsedLine) -> AsmExprValue:
        try:
            return self.eval (env)
        except AsmExprEvalError as e:
            sys.stdout.flush()
            # traceback.print_stack()
            p = parsedLine
            p.cb.log.error (p.lineNo,
                            "Char pos %d: %s%s" %
                            (p.tokenizer.pos, e, p.tokenizer.caratString (p.lineStr, p.tokenizer.pos - 1)))
            return None
    def eval (self, env: AsmExprEnv) -> AsmExprValue:
        if self.exprType in [AsmExprType.BinaryPlus,
                             AsmExprType.BinaryMinus,
                             AsmExprType.BinaryMult,
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
            v = round (float (s) * 2**15)
            return AsmExprValue (AsmExprValueType.Fraction, v)
        elif self.exprType == AsmExprType.BinaryDot:
            #  It's a literal octal number
            l = self
            if l.leftSubExpr.exprType == AsmExprType.LiteralDigits and \
               l.rightSubExpr.exprType == AsmExprType.LiteralDigits and \
               l.leftSubExpr.exprData in ["0", "1"]:
                v = (-1 if l.leftSubExpr.exprData == "0" else 1) * self.OctalDigitStringToInt (l.rightSubExpr.exprData)
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
            return env.lookup (self.exprData)
        elif self.exprType == AsmExprType.BinaryComma:
            x = self.leftSubExpr.eval (env)
            y = self.rightSubExpr.eval (env)
            if x.type == AsmExprValueType.List:
                if x.value is not None:
                    x.value.append (y)
                    return AsmExprValue (AsmExprValueType.List, x.value)
                else:
                    return AsmExprValue (AsmExprValueType.List, [y])
            else:
                return AsmExprValue (AsmExprValueType.List, [x, y])
        else:
            self.evalError ("Unknown Asm Expression Type")

class AsmParsedLine:
    def __init__ (self, str, lineNo: int, verbose = False):
        self.cb = wwinfra.theConstWWbitClass
        self.verbose = verbose  # Passed in potentially on the test (main) command line; key on this for debug output
        self.lineStr = str
        self.lineNo = lineNo
        self.tokenizer = AsmTokenizer (str)
        self.tokenBuf = []
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
        # traceback.print_stack()
        raise AsmParseSyntaxError (msg)
    def print (self):   # Debug fcn
        s = " "*3
        print ("\nAsmParsedLine:\n",
               s + "line=", self.lineStr.rstrip ("\r\n"), "\n",
               s + "prefixAddr=", self.prefixAddr, "\n",
               s + "label=", self.label, "\n",
               s + "opname=", self.opname, "\n",
               s + "operand=", "AsmExpr-" + str (id (self.operand)) if self.operand is not None else "None", "\n",
               s + "comment=", self.comment, "\n",
               s + "auto-comment=", self.autoComment)
        if self.operand is not None:
            print ("AsmExpr-" + str (id (self.operand)) + ":")
            self.operand.print()
    # public
    def parseLine (self) -> bool:
        try:
            self.parsePrefixAddr()
            self.parseLabel()
            self.parseInst()
            self.parseComment()
            self.parseAutoComment()
            return True
        except AsmParseSyntaxError as e:
            sys.stdout.flush()
            self.cb.log.error (self.lineNo,
                               "%s at char pos %d%s" %
                               (e, self.tokenizer.pos, self.tokenizer.caratString (self.lineStr, self.tokenizer.pos - 1)))
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
                    tok = self.gtok()
                    if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ":":
                        tok = self.gtok()
                        if tok.tokenType == AsmTokenType.DigitString:
                            addrPart3 = tok.tokenStr
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
                error ("Opname expected")
        elif tok1.tokenType == AsmTokenType.DotPrint or tok1.tokenType == AsmTokenType.DotExec:
            self.opname = "print" if  tok1.tokenType == AsmTokenType.DotPrint else "exec"
            self.operand = AsmExpr (AsmExprType.LiteralString, tok1.tokenStr)
            return True
        else:
            self.ptok (tok1)
            return False
    def parseExpr (self) -> AsmExpr:
        return self.parseCommaOper()
    def parseComment (self) -> bool:
        tok = self.gtok()
        if tok.tokenType == AsmTokenType.Comment:
            self.comment = tok.tokenStr
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
                e1 = AsmExpr (exprType, "")
            else:
                self.ptok (tok)
                return self.parseAtom()
            e2 = self.parseUnaryOper()
            if e2 is not None:
                e1.leftSubExpr = e2
                return e1
            else:
                self.error ("Unary operator sytnax error")
        else:
            self.ptok (tok)
            return self.parseAtom()
        
    # LAS 12/7/24 The binary op parsers (parseCommaOper though ParseDotOper)
    # are essentialy clones, and I haven't found a good way yet to refactor
    # them.

    def parseCommaOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseAdditiveOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ",":
                e = AsmExpr (AsmExprType.BinaryComma, "")
                if leftExpr is not None:
                    e.leftSubExpr = leftExpr
                else:
                    e.leftSubExpr = e1
                e2 = self.parseCommaOper (leftExpr = e)
                return e2
            else:
                self.ptok (tok)
                if leftExpr is not None:
                    return leftExpr
                else:
                    return e1
        else:
            self.error ("Comma operator syntax error")
    def parseAdditiveOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseMultiplicativeOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["+", "-"]:
                e = AsmExpr (AsmExprType.BinaryPlus if tok.tokenStr == '+' else AsmExprType.BinaryMinus, "")
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
        e1 = self.parseBitAndOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["*"]:
                e = AsmExpr (AsmExprType.BinaryMult, "")
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
    def parseBitAndOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseBitOrOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["&"]:
                e = AsmExpr (AsmExprType.BinaryBitAnd, "")
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

    def parseBitOrOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseDotOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["|"]:
                e = AsmExpr (AsmExprType.BinaryBitOr, "")
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

            
    def parseDotOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseUnaryOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["."]:
                e = AsmExpr (AsmExprType.BinaryDot, "")
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
        if tok.tokenType in [AsmTokenType.DigitString, AsmTokenType.Identifier]:
            return AsmExpr (AsmExprType.Variable if tok.tokenType == AsmTokenType.Identifier else AsmExprType.LiteralDigits,
                            tok.tokenStr)
        elif tok.tokenType == AsmTokenType.Operator and tok.tokenStr == "(":
            # Open the trap door to the wormhole to another dimension...
            e = self.parseExpr()
            if e is not None:
                tok = self.gtok()
                if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ")":
                    return e
                else:
                    self.error ("Unbalanced parenthesis")
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
    def parseLines (self):
        lineNo = 1
        s = open (self.cmdArgs.inFileName, "r")
        while True:
            line = s.readline()
            if line == "":
                break
            else:
                l = AsmParsedLine (line, lineNo, verbose = self.verbose)
                l.parseLine()
                l.print()
                self.parsedLines.append (l)
                lineNo += 1
                if l.operand is not None:
                    env = AsmExprEnv()
                    print ("Eval:")
                    print (" "*2 + l.operand.getIdStr())
                    v = l.operand.evalMain (env, l)
                    if v is not None:
                        print (" "*4 + v.asString())
                        print ("")

# The main program is used for test and debug. Prints produced via the
# AsmParseTest class write logs which are then compared the test scripts, so
# caution should be taken when changing the format. The verbose option is
# detected by all code herein and prints stuff just for debugging. The outfile
# code is there in case we want file output sometime.

def main():
    parser = wwinfra.StdArgs().getParser (".")
    parser.add_argument ("inFileName", help="")
    # parser.add_argument ("-o", "--OutFile", help="File to write (default basename(inputFileName).ww)", type=str)
    parser.add_argument ("-v", "--Verbose", help="Generate extra debug output", action="store_true")
    cmdArgs = parser.parse_args()
    cb = wwinfra.ConstWWbitClass (args = cmdArgs)
    wwinfra.theConstWWbitClass = cb
    cb.log = wwinfra.LogFactory().getLog (isAsmLog = True)
    t = AsmParseTest (cmdArgs)
    t.parseLines()
 
if __name__ == "__main__":
    main()
