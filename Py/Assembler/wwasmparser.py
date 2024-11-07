

import os
import sys
import traceback
import wwinfra
from enum import Enum

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
        return c == ' ' or c == '\t'
    def caratString (self, str, pos) -> str:
        s = " " * pos
        return ":\n" + str + "\n" + s + "^\n"
    def isSingleCharOper (self, c) -> bool:
        return c in ['+', '-', '@', ':', '.', ';', '*', '(', ')']
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
        self.cb.log.error (0, "State %d: Illegal char %c at pos %d in %s" % (state, c, pos, str) +
                           self.caratString (str, pos))
        raise AsmParseSyntaxError
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
                    else:
                        self.illegalChar (c, self.pos, self.str, self.state)
        return AsmToken()

AsmExprType = Enum ("AsmExprType", ["BinaryPlus", "BinaryMinus",
                                    "UnaryPlus", "UnaryMinus", "UnaryZeroOh",
                                    "BinaryMult", "BinaryDot",
                                    "Variable", "Literal"])

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
                 AsmExprType.BinaryMult, AsmExprType.BinaryDot]:
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
        elif t in [AsmExprType.Variable, AsmExprType.Literal]:
            print (" " * indent + t.name, self.exprData)

class AsmParseSyntaxError (Exception):
    pass

class AsmParsedLine:
    def __init__ (self, str, lineNo):
        self.cb = wwinfra.theConstWWbitClass
        self.lineStr = str
        self.lineNo = lineNo
        self.tokenizer = AsmTokenizer (str)
        self.tokenBuf = []
        self.prefixAddr = {}
        self.label = ""
        self.opcode = ""
        self.addrExpr: AsmExpr = None
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
    def error (self):
        sys.stdout.flush()
        # traceback.print_stack()
        self.cb.log.error (self.lineNo,
                           "Asm syntax error at char pos %d%s" %
                           (self.tokenizer.pos, self.tokenizer.caratString (self.lineStr, self.tokenizer.pos - 1)))
        raise AsmParseSyntaxError
    def print (self):   # Debug fcn
        s = " "*3
        print ("\nAsmParsedLine:\n",
               s + "line=", self.lineStr, "\n",
               s + "prefixAddr=", self.prefixAddr, "\n",
               s + "label=", self.label, "\n",
               s + "opcode=", self.opcode, "\n",
               s + "expr=", "AsmExpr-" + str (id (self.addrExpr)) if self.addrExpr is not None else "None", "\n",
               s + "comment=", self.comment, "\n",
               s + "auto-comment=", self.autoComment)
        if self.addrExpr is not None:
            print ("AsmExpr-" + str (id (self.addrExpr)) + ":")
            self.addrExpr.print()
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
            return False
    def parsePrefixAddr (self) -> bool:
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
                                self.error()
                        else:
                            self.error()
                    else:
                        self.error()
                else:
                    tok = self.gtok()
                    if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ":":
                        tok = self.gtok()
                        if tok.tokenType == AsmTokenType.DigitString:
                            addrPart3 = tok.tokenStr
                            return True
                        else:
                            self.error()
                    else:
                        self.error()
            else:
                self.error()
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
            self.addrExpr = e
            self.opcode = tok1.tokenStr
            return True
        elif tok1.tokenType == AsmTokenType.Operator and  tok1.tokenStr == ".":
            tok2 = self.gtok()
            if tok2.tokenType == AsmTokenType.Identifier:
                e = self.parseExpr()
                self.addrExpr = e
                self.opcode = tok2.tokenStr
                return True
            else:
                error()
        elif tok1.tokenType == AsmTokenType.DotPrint or tok1.tokenType == AsmTokenType.DotExec:
            self.opcode = "print" if  tok1.tokenType == AsmTokenType.DotPrint else "exec"
            self.addrExpr = AsmExpr (AsmExprType.Literal, tok1.tokenStr)
            return True
        else:
            self.ptok (tok1)
            return False
    def parseExpr (self) -> AsmExpr:
        return self.parseAdditiveOper()
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
                self.error()
        else:
            self.ptok (tok)
            return self.parseAtom()
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
            self.error()
    def parseMultiplicativeOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
        e1 = self.parseDottedOper()
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
            self.error()
    def parseDottedOper (self, leftExpr: AsmExpr = None) -> AsmExpr:
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
                e2 = self.parseDottedOper (leftExpr = e)
                return e2
            else:
                self.ptok (tok)
                if leftExpr is not None:
                    return leftExpr
                else:
                    return e1
        else:
            self.error()
    def parseAtom (self) -> AsmExpr:
        tok = self.gtok()
        if tok.tokenType in [AsmTokenType.DigitString, AsmTokenType.Identifier]:
            return AsmExpr (AsmExprType.Variable if tok.tokenType == AsmTokenType.Identifier else AsmExprType.Literal,
                            tok.tokenStr)
        elif tok.tokenType == AsmTokenType.Operator and tok.tokenStr == "(":
            # Open the trap door to the wormhole to another dimension...
            e = self.parseExpr()
            if e is not None:
                tok = self.gtok()
                if tok.tokenType == AsmTokenType.Operator and tok.tokenStr == ")":
                    return e
                else:
                    self.error()
            else:
                self.error()
        else:
            self.ptok (tok)
            return None
