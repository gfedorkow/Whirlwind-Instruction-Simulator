

import os
import sys
import traceback
import wwinfra
from enum import Enum

class CwParseSyntaxError (Exception):
    pass

CwTokenType = Enum ("CwTokenType", ["Operator", "DigitString", "Identifier",
                                    "String", "EndOfString", "Null"])

class CwToken:
    def __init__ (self, tokenType: CwTokenType, tokenStr: str):
        self.tokenType = tokenType
        self.tokenStr = tokenStr
    def print (self):
        print ("CwToken ", self.tokenType, self.tokenStr)


# Deliver a seq of chars to the tokenizer, on a whole-file basis. Buffer by
# lines to keep counts for error messages.

class CwCharSeq:
    def __init__ (self, inStream):
        self.inStream = inStream
        self.lineNo = 0
        self.line = ""
        self.lineLen = -1
        self.pos = 0
        self._curChar = None
        self.next()
    # Advance the char position
    def next (self):
        if self.pos >= self.lineLen:
            self.line = self.inStream.readline()
            if self.line != "":
                self.lineLen = len (self.line)
                self.pos = 0
                self.lineNo += 1
            else:
                self._curChar = ""
                return
        r = self.line[self.pos]
        self.pos += 1
        self._curChar = r
    def curChar (self) -> str:     # returns a single-char string, or empty if eof
        return self._curChar

class CwTokenizer:
    endOfString = "<end-of-string>"
    def __init__ (self, inStream):
        self.charSeq = CwCharSeq (inStream)
        self.state = 0
        self.buffer = ""
        self.cb = wwinfra.theConstWWbitClass
    def isWhitespace (self, c) -> bool:
        return c in [' ', '\n', '\r', '\t']
    def caratString (self, str, pos) -> str:
        s = " " * pos
        return ":\n" + str.rstrip ("\r\n") + "\n" + s + "^\n"
    def isSingleCharOper (self, c) -> bool:
        return c in ['+', '-', '.', ';', ',', '*', '/', '|',
                     '&', '^', '(', ')', '{', '}' ,'[', ']',
                     '>', '<', '=', ';', '=']
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
        token = CwToken (CwTokenType.Null, "")
        tokens = []
        while token.tokenType != CwTokenType.EndOfString:
            token = self.getToken()
            tokens.append (token)
        return tokens
    def printTokens (self, tokens): # Debug fcn
        for token in tokens:
            print (token.tokenType, token.tokenStr)
    # public
    def getToken (self) -> CwToken:
        while True:
            c = self.charSeq.curChar()
            if c == "":
                c = self.endOfString
            match self.state:
                case 0:
                    if c == self.endOfString:
                        self.state = 0
                        return CwToken (CwTokenType.EndOfString, "")
                    if self.isWhitespace (c):
                        self.state = 0
                        self.charSeq.next()
                    elif c == '@':
                        self.state = 1
                        self.charSeq.next()
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        self.charSeq.next()
                        return CwToken (CwTokenType.Operator, c)
                    elif c == '0':
                        self.state = 8
                        self.charSeq.next()
                        self.push (c)
                    elif self.isDigit (c):
                        self.state = 3
                        self.charSeq.next()
                        self.push (c)
                    elif c == '"':
                        self.state = 9
                        self.charSeq.next()
                    elif self.isExtAlphaChar (c):
                        self.state = 4
                        self.charSeq.next()
                        self.push (c)
                    else:
                        self.illegalChar (c, self.pos, self.str, self.state)
                case 1:
                    if c == '@':
                        self.state = 2
                        self.charSeq.next()
                    else:
                        self.state = 0
                        return CwToken (CwTokenType.Operator, "@")
                case 2:
                    if c == self.endOfString:
                        self.state = 0
                        return CwToken (CwTokenType.AutoComment, self.pop())
                    else:
                        self.state = 2
                        self.charSeq.next()
                        self.push (c)
                case 3:
                    if c == self.endOfString:
                        self.state = 0
                        return CwToken (CwTokenType.DigitString, self.pop())
                    if self.isDigit (c):
                        self.state = 3
                        self.charSeq.next()
                        self.push (c)
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        return CwToken (CwTokenType.DigitString, self.pop())
                    elif self.isWhitespace (c):
                        self.state = 0
                        self.charSeq.next()
                        return CwToken (CwTokenType.DigitString, self.pop())
                    elif self.isExtAlphaChar (c):
                        self.state = 4
                        self.charSeq.next()
                        self.push (c)
                    else:
                        self.illegalChar (c, self.pos, self.str, self.state)
                case 4:
                    if c == self.endOfString:
                        self.state = 0
                        return CwToken (CwTokenType.Identifier, self.pop())
                    elif self.isExtAlphaNumChar (c):
                        self.state = 4
                        self.charSeq.next()
                        self.push (c)
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        return CwToken (CwTokenType.Identifier, self.pop())
                    elif self.isWhitespace (c):
                        self.state = 0
                        self.charSeq.next()
                        return CwToken (CwTokenType.Identifier, self.pop())
                    else:
                        self.illegalChar (c, self.pos, self.str, self.state)
                case 5:                                                             # got here from state 0 ; asm comment
                    if c == '@':
                        self.state = 6
                        self.charSeq.next()
                    elif c == self.endOfString:
                        self.state = 0
                        return CwToken (CwTokenType.Comment, self.pop())
                    else:
                        self.state = 5
                        self.charSeq.next()
                        self.push (c)
                case 6:
                    if c == '@':
                        self.state = 7
                        self.charSeq.next()
                        return CwToken (CwTokenType.Comment, self.pop())
                    else:
                        self.push ('@')     # We want the previous atsign
                        self.state = 5
                case 7:
                    if c == self.endOfString:
                        self.state = 0
                        return CwToken (CwTokenType.AutoComment, self.pop())
                    else:
                        self.state = 7
                        self.charSeq.next()
                        self.push (c)
                case 8:
                    if c == 'o':
                        self.state = 3
                        self.charSeq.next()
                        self.pop()
                        return CwToken (CwTokenType.Operator, "0o")
                    if c == 'x':
                        self.state = 3
                        self.charSeq.next()
                        self.pop()
                        return CwToken (CwTokenType.Operator, "0x")
                    elif c == self.endOfString:
                        self.state = 0
                        self.pop()
                        return CwToken (CwTokenType.DigitString, "0")
                    elif self.isDigit (c):
                        self.state = 3
                        self.charSeq.next()
                        self.push (c)
                    elif self.isWhitespace (c):
                        self.state = 0
                        self.charSeq.next()
                        self.pop()
                        return CwToken (CwTokenType.DigitString, "0")
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        self.pop()
                        return CwToken (CwTokenType.DigitString, "0")
                    elif self.isExtAlphaNumChar (c):
                        self.state = 4
                    else:
                        self.illegalChar (c, self.pos, self.str, self.state)
                case 9:
                    if c == '"':
                        self.state = 0
                        self.charSeq.next()
                        return CwToken (CwTokenType.String, self.pop())
                    else:
                        self.state = 9
                        self.charSeq.next()
                        self.push (c)
                        return CwToken()

CwExprType = Enum ("CwExprType", ["BinaryPlus", "BinaryMinus",
                                  "UnaryPlus", "UnaryMinus", "UnaryZeroOh",
                                  "UnaryZeroX", "BinaryMult", "BinaryDiv",
                                  "BinaryDot", "BinaryComma", "BinaryAssign",
                                  "BinaryBitAnd", "BinaryBitOr",
                                  "Identifier", "LiteralString", "LiteralDigits",
                                  "Integer", "Real", "PostfixOper"])

class CwExpr:
    def __init__ (self, exprType: CwExprType, exprData: str):
        self.cb = wwinfra.theConstWWbitClass
        self.exprType = exprType
        self.exprData = exprData            # identifier, literal, or oper name
        self.leftSubExpr: CwExpr = None
        self.rightSubExpr: CwExpr = None
    def print (self, indent):
        t = self.exprType
        if t in [CwExprType.BinaryPlus, CwExprType.BinaryMinus,
                 CwExprType.BinaryMult, CwExprType.BinaryDiv, CwExprType.BinaryDot,
                 CwExprType.BinaryBitAnd, CwExprType.BinaryBitOr,
                 CwExprType.BinaryComma, CwExprType.BinaryAssign, CwExprType.PostfixOper]:
            print (" " * indent + t.name)
            if self.leftSubExpr is not None:
                self.leftSubExpr.print (indent + 3)
            else:
                print (" " * indent + "None")   # Should only get here if there is a bug
            if self.rightSubExpr is not None:
                self.rightSubExpr.print (indent + 3)
            else:
                print (" " * indent + "None")   # Should only get here if there is a bug
        elif t in [CwExprType.UnaryPlus, CwExprType.UnaryMinus, CwExprType.UnaryZeroOh]:
            print (" " * indent + t.name)
            self.leftSubExpr.print (indent + 3)
        elif t in [CwExprType.Identifier, CwExprType.LiteralString, CwExprType.LiteralDigits]:
            print (" " * indent + t.name, self.exprData)
    def getIdStr (self):    # Just for test/debug print
        return "CwExpr-" + str (id (self))
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

# Current decl suuport is only <type-name> <var> ;

class CwDecl:
        def __init__ (self,
                      typeName: CwExpr,         # Must be identifier
                      var: CwExpr):             # Identifier only right now
            self.typeName = typeName
            self.var = var
        def print (self, indent):
            print (" "*indent + "Decl: " + self.typeName.exprData + " " + self.var.exprData)

class CwStmt:
    def __init__ (self, body):  # body is either CwExpr or CwCompoundStmt
        self.body = body
    def print (self, indent):
        error()     # Subclass responsibility

class CwCompoundStmt (CwStmt):
    def __init__ (self,
                  decls: [CwDecl],
                  stmts: [CwExpr]):
        self.decls = decls
        self.stmts = stmts
    def print (self, indent):
        print (" "*indent + "CompoundStmt")
        i = indent + 3
        for decl in self.decls:
            decl.print (i)
        for stmt in self.stmts:
            stmt.print (i)

class CwExprStmt (CwStmt):
    def __init__ (self, expr: CwExpr):
        self.expr = expr
    def print (self, indent):
        self.expr.print (indent)
        
class CwIfStmt (CwStmt):
    def __init__ (self, pred: CwExpr, thenClause: CwStmt, elseClause: CwStmt):
        self.pred = pred
        self.thenClause = thenClause
        self.elseClause = elseClause
    def print (self, indent):
        print (" "*indent + "IfStmt")
        i = indent + 3
        self.pred.print (i)
        self.thenClause.print (i)
        self.elseClause.print (i)

class CwFcnDef:
    def __init__ (self,
                  fcn: CwExpr,            # Only by name supported right now
                  params: CwExpr,         # Must be comma-oper expr
                  body: CwCompoundStmt):  # A compound statement
        self.fcn = fcn
        self.params = params
        self.body = body
    def print (self, indent):
        print (" "*indent + "FcnDef")
        i = indent + 3
        self.fcn.print (i)
        self.params.print (i)
        self.body.print (i)

class CwProgram:
    def __init__ (self, inStream, verbose = False):
        self.cb = wwinfra.theConstWWbitClass
        self.verbose = verbose  # Passed in potentially on the test (main) command line; key on this for debug output
        self.inStream = inStream
        self.tokenizer = CwTokenizer (self.inStream)
        self.tokenBuf = []

        # The top-level expression that forms what we're calling a program. A
        # program is defined via a single file.
        # self.expr = CwExpr = None

        self.fcnDef: CwFcnDef = None

    def gtok (self) -> CwToken:
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
        raise CwParseSyntaxError (msg)
    def print (self):   # Debug fcn
        s = " "*3
        print ("\nAsmParsedLine:\n",
               s + "line=", self.lineStr, "\n",
               s + "prefixAddr=", self.prefixAddr, "\n",
               s + "label=", self.label, "\n",
               s + "opname=", self.opname, "\n",
               s + "operand=", "CwExpr-" + str (id (self.operand)) if self.operand is not None else "None", "\n",
               s + "comment=", self.comment, "\n",
               s + "auto-comment=", self.autoComment)
        if self.operand is not None:
            print ("CwExpr-" + str (id (self.operand)) + ":")
            self.operand.print()

    # public
    
    def parseProgram (self) -> bool:
        try:
            self.fcnDef = self.parseFcnDef()
            print ("LAS2")
            self.fcnDef.print (0)
            return True
        except CwParseSyntaxError as e:
            sys.stdout.flush()
            self.cb.log.error (self.lineNo,
                               "%s at char pos %d%s" %
                               (e, self.tokenizer.pos, self.tokenizer.caratString (self.lineStr, self.tokenizer.pos - 1)))

    def parseDecl (self) -> CwDecl:
        tok = self.gtok()
        if tok.tokenType == CwTokenType.Identifier:
            typeName = CwExpr (CwExprType.Identifier, tok.tokenStr)
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Identifier:
                var = CwExpr (CwExprType.Identifier, tok.tokenStr)
                return CwDecl (typeName, var)
            else:
                self.ptok (tok)
        else:
            self.ptok (tok)
        return None
            
    def parseFcnDef (self) -> CwFcnDef:
        tok = self.gtok()
        if tok.tokenType == CwTokenType.Identifier:
            fcn = CwExpr (CwExprType.Identifier, tok.tokenStr)
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr == "(":
                params = self.parseCommaOper()
                tok = self.gtok()
                if tok.tokenType == CwTokenType.Operator and tok.tokenStr == ")":
                    body = self.parseCompoundStmt()
                    if body is not None:
                        return CwFcnDef (fcn, params, body)
                    else:
                        error()
                else:
                    error()
            else:
                error()
        else:
            error()

    def parseStmt (self)-> CwStmt:
        x = self.parseCompoundStmt()
        if x is not None:
            return x
        else:
            x = self.parseIfStmt()
            if x is not None:
                return x
            else:
                x = self.parseExpr()
                if x is not None:
                    tok = self.gtok()
                    if tok.tokenType == CwTokenType.Operator and tok.tokenStr == ";":
                        return CwExprStmt (x)
                    else:
                        error()
                else:
                    error()

    def parseIfStmt (self)-> CwIfStmt:
        tok = self.gtok()
        if tok.tokenType == CwTokenType.Identifier and tok.tokenStr == "if":
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr == "(":
                pred = self.parseExpr()
                if pred is not None:
                    tok = self.gtok()
                    if tok.tokenType == CwTokenType.Operator and tok.tokenStr == ")":
                        thenClause = self.parseStmt()
                        if thenClause is not None:
                            tok = self.gtok()
                            if tok.tokenType == CwTokenType.Identifier and tok.tokenStr == "else":
                                elseClause = self.parseStmt()
                                if elseClause is not None:
                                    return CwIfStmt (pred, thenClause, elseClause)
                                else:
                                    error()
                            else:
                                self.ptok (tok)
                                return CwIfStmt (pred, thenClause, None)
                        else:
                            error()
                    else:
                        error()
                else:
                    error()
            else:
                error()
        else:
            self.ptok (tok)
            return None

    def parseCompoundStmt (self) -> CwCompoundStmt:
        tok = self.gtok()
        if tok.tokenType == CwTokenType.Operator and tok.tokenStr == "{":
            decls = []
            while True:
                decl = self.parseDecl()
                if decl is not None:
                    decls.append (decl)
                else:
                    break
            body = []
            while True:
                e = self.parseStmt()
                if e is not None:
                    body.append (e)
                    tok = self.gtok()
                    if tok.tokenType == CwTokenType.Operator and tok.tokenStr == "}":
                        return CwCompoundStmt (decls, body)
                    else:
                        self.ptok (tok)
                else:
                    error()
        else:
            self.ptok (tok)
            return None

    def parseDecl (self) -> CwDecl:
        tok1 = self.gtok()
        if tok1.tokenType == CwTokenType.Identifier:
            tok2 = self.gtok()
            if tok2.tokenType == CwTokenType.Identifier:
                tok3 = self.gtok()
                if tok3.tokenType == CwTokenType.Operator and tok3.tokenStr == ";":
                    return CwDecl (CwExpr (CwExprType.Identifier, tok1.tokenStr),
                                   CwExpr (CwExprType.Identifier, tok2.tokenStr))
                else:
                    error()
            else:
                self.ptok (tok2)
                self.ptok (tok1)
                return None
        else:
            self.ptok (tok1)
            return None

    def parseExpr (self) -> CwExpr:
        return self.parseCommaOper()
    
    def parseUnaryOper (self) -> CwExpr:
        tok = self.gtok()
        if tok.tokenType == CwTokenType.Operator:
            if tok.tokenStr in ["+", "-", "0o"]:
                negate = tok.tokenStr == "-"
                # This is really groovy python syntax...
                exprType = {"-":CwExprType.UnaryMinus,"+":CwExprType.UnaryPlus,"0o":CwExprType.UnaryZeroOh}[tok.tokenStr]
                e1 = CwExpr (exprType, tok.tokenStr)
            else:
                self.ptok (tok)
                return self.parsePostfixOper()
            e2 = self.parseUnaryOper()
            if e2 is not None:
                e1.leftSubExpr = e2
                return e1
            else:
                self.error ("Unary operator sytnax error")
        else:
            self.ptok (tok)
            return self.parsePostfixOper()

    # Note comma operator and assign operator are right-associative, and
    # everything else is left-associative.
       
    def parseCommaOper (self, leftExpr: CwExpr = None) -> CwExpr:
        # e1 = self.parseAdditiveOper()
        e1 = self.parseAssignOper()
        if e1 is not None:
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr == ",":
                e2 = self.parseCommaOper()
                if e2 is not None:
                    e = CwExpr (CwExprType.BinaryComma, tok.tokenStr)
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

    def parseAssignOper (self, leftExpr: CwExpr = None) -> CwExpr:
        e1 = self.parseAdditiveOper()
        if e1 is not None:
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr == "=":
                e2 = self.parseAssignOper()
                if e2 is not None:
                    e = CwExpr (CwExprType.BinaryAssign, tok.tokenStr)
                    e.leftSubExpr = e1
                    e.rightSubExpr = e2
                    return e
                else:
                    return e1
            else:
                self.ptok (tok)
                return e1
        else:
            self.error ("Assignment operator syntax error")

    def parseAdditiveOper (self, leftExpr: CwExpr = None) -> CwExpr:
        e1 = self.parseMultiplicativeOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr in ["+", "-"]:
                e = CwExpr (CwExprType.BinaryPlus if tok.tokenStr == '+' else CwExprType.BinaryMinus, tok.tokenStr)
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
            
    def parseMultiplicativeOper (self, leftExpr: CwExpr = None) -> CwExpr:
        e1 = self.parseBitAndOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr in ["*", "/"]:
                d = {"*": CwExprType.BinaryMult, "/": CwExprType.BinaryDiv}
                e = CwExpr (d[tok.tokenStr], tok.tokenStr)
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
            
    def parseBitAndOper (self, leftExpr: CwExpr = None) -> CwExpr:
        e1 = self.parseBitOrOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr in ["&"]:
                e = CwExpr (CwExprType.BinaryBitAnd, tok.tokenStr)
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
    def parseBitOrOper (self, leftExpr: CwExpr = None) -> CwExpr:
        e1 = self.parseDotOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr in ["|"]:
                e = CwExpr (CwExprType.BinaryBitOr, tok.tokenStr)
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
            
    def parseDotOper (self, leftExpr: CwExpr = None) -> CwExpr:
        e1 = self.parseUnaryOper()
        if e1 is not None:
            if leftExpr is not None:
                leftExpr.rightSubExpr = e1
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr in ["."]:
                e = CwExpr (CwExprType.BinaryDot, tok.tokenStr)
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
            
    def parseAtom (self) -> CwExpr:
        tok = self.gtok()
        tokTypeDict = {
            CwTokenType.DigitString: CwExprType.LiteralDigits,
            CwTokenType.Identifier: CwExprType.Identifier,
            CwTokenType.String: CwExprType.LiteralString
            }
        if tok.tokenType in tokTypeDict:
            return CwExpr (tokTypeDict[tok.tokenType], tok.tokenStr)
        elif tok.tokenType == CwTokenType.Operator and tok.tokenStr == "(":
            # Open the trap door to the wormhole to another dimension...
            e = self.parseExpr()
            if e is not None:
                tok = self.gtok()
                if tok.tokenType == CwTokenType.Operator and tok.tokenStr == ")":
                    return e
                else:
                    self.error ("Unbalanced parentheses")
            else:
                self.error ("Nested expression syntax error")
        else:
            self.ptok (tok)
            return None
        
    def parsePostfixOper (self, leftExpr: CwExpr = None) -> CwExpr:
        e1 = self.parseAtom()       # Want to parse more exprs here so we can get computed functions
        if e1 is not None:
            tok = self.gtok()
            if tok.tokenType == CwTokenType.Operator and tok.tokenStr == "(":
                e2 = self.parseCommaOper()
                if e2 is not None:
                    tok = self.gtok()
                    if tok.tokenType == CwTokenType.Operator and tok.tokenStr == ")":
                        e = CwExpr (CwExprType.PostfixOper, "")
                        e.leftSubExpr = e1
                        e.rightSubExpr = e2
                        return e
                    else:
                        self.ptok (tok)
                        return e1
            else:
                self.ptok (tok)
                return e1
        else:
            self.error ("Postfix operator syntax error")

class CwParseTest:
    def __init__ (self, cmdArgs):
        self.cmdArgs = cmdArgs
        self.verbose = self.cmdArgs.Verbose
        self.cb = wwinfra.theConstWWbitClass
        self.inStream = open (self.cmdArgs.inFileName, "r")
        self.prog = CwProgram (self.inStream)
    def flush (self):
        sys.stdout.flush()
        sys.stderr.flush()
    def runTest (self):
        self.prog.parseProgram()
        print (self.prog.fcnDef)

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
    cb.log = wwinfra.LogFactory().getLog (isAsmLog = True)
    t = CwParseTest (cmdArgs)
    t.runTest()
 
if __name__ == "__main__":
    main()
