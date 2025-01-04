

import os
import sys
import traceback
import wwinfra
from enum import Enum
import argparse

AsmTokenType = Enum ("AsmTokenType", ["Operator", "Comment", "AutoComment",
                                      "DigitString", "Identifier", "DotPrint", "DotExec",
                                      "RecordSep", # A distinct record separator -- tab is the only one so far
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
        return c in [' ', '\n', '\r']
    def caratString (self, str, pos) -> str:
        s = " " * pos
        return ":\n" + str + "\n" + s + "^\n"
    def isSingleCharOper (self, c) -> bool:
        return c in ['+', '-', '@', ':', '.', ';', '*', '(', ')', '/', '|']
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
        self.cb.log.error (0, "State %d: Illegal char \'%c\' at pos %d in %s" % (state, c, pos, str) +
                           self.caratString (str, pos))
        traceback.print_stack()
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
    def getCommentToken (self) -> AsmToken:
        while self.pos <= self.slen:
            if self.pos < self.slen:
                c = self.str[self.pos]
                if c == '\t':
                    return AsmToken (AsmTokenType.Comment, self.pop())
                else:
                    self.push (c)
                    self.pos += 1
            else:
                return AsmToken (AsmTokenType.Comment, self.pop())
    # public            
    def getToken (self) -> AsmToken:
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
                    if c == '\t':
                        self.state = 0
                        self.pos += 1
                        return AsmToken (AsmTokenType.RecordSep, "")
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
                    elif self.isSingleCharOper (c) or c == '\t':
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
                    elif self.isSingleCharOper (c) or c == '\t':
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
                    elif self.isSingleCharOper (c) or c == '\t':
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
                                    "BinaryMult", "BinaryDot", "BinaryDiv",
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
                 AsmExprType.BinaryMult, AsmExprType.BinaryDot, AsmExprType.BinaryDiv]:
            sys.stderr.write (" " * indent + t.name)
            if self.leftSubExpr is not None:
                self.leftSubExpr.print (indent = indent + 3)
            else:
                sys.stderr.write (" " * indent + "None")   # Should only get here if there is a bug
            if self.rightSubExpr is not None:
                self.rightSubExpr.print (indent = indent + 3)
            else:
                sys.stderr.write (" " * indent + "None")   # Should only get here if there is a bug
        elif t in [AsmExprType.UnaryPlus, AsmExprType.UnaryMinus, AsmExprType.UnaryZeroOh]:
            sys.stderr.write (" " * indent + t.name)
            self.leftSubExpr.print (indent = indent + 3)
        elif t in [AsmExprType.Variable, AsmExprType.Literal]:
            sys.stderr.write (" " * indent + t.name + " " + self.exprData + "\n")

class AsmParseSyntaxError (Exception):
    pass

class AsmParsedLine:
    def __init__ (self, str, lineNo):
        self.cb = wwinfra.theConstWWbitClass
        self.lineStr = str.rstrip ("\r\n")
        self.lineNo = lineNo
        self.tokenizer = AsmTokenizer (str)
        self.tokenBuf = []
        self.prefixComment = ""
        self.sectionOffset = 0
        self.opcode = ""
        self.addrExpr: AsmExpr = None
        self.postfixComment = ""
    def gtok (self, getComment = False) -> AsmToken:
        if self.tokenBuf != []:
            r = self.tokenBuf.pop()
        else:
            if not getComment:
                r = self.tokenizer.getToken()
            else:
                r = self.tokenizer.getCommentToken()
        return r
    def ptok (self, tok):
        self.tokenBuf.append (tok)
    def error (self):
        sys.stdout.flush()
        traceback.print_stack()
        self.cb.log.error (self.lineNo,
                           "Asm syntax error at char pos %d%s" %
                           (self.tokenizer.pos, self.tokenizer.caratString (self.lineStr, self.tokenizer.pos - 1)))
        raise AsmParseSyntaxError
    def print (self):   # Debug fcn
        s = " "*3
        sys.stderr.write ("\nAsmParsedLine:\n" +
                          s + "line=" + self.lineStr + "\n" +
                          s + "prefixComment= " + self.prefixComment + "\n" +
                          s + "sectionOffset= " + str (self.sectionOffset) + "\n" +
                          s + "opcode= " + self.opcode + "\n" +
                          s + "expr= " + "AsmExpr-" + (str (id (self.addrExpr)) if self.addrExpr is not None else "None") + "\n" +
                          s + "postfixComment= " + self.postfixComment + "\n")
        if self.addrExpr is not None:
            sys.stderr.write ("AsmExpr-" + str (id (self.addrExpr)) + ":" + "\n")
            self.addrExpr.print()
            sys.stderr.write ("\n")
        if False: # Activate as needed
            if self.opcode != "" and self.addrExpr.exprType == AsmExprType.Literal:
                sys.stderr.write ("Literal address ref: " + self.opcode + " " + self.addrExpr.exprData + "\n")
    # public
    def parseLine (self) -> bool:
        try:
            self.parsePrefixComment()
            if self.parseSectionOffset():
                self.parseRecordSep()
                self.parseInst()
                self.parseRecordSep()
                self.parsePostfixComment()
                return True
            else:
                return False
        except AsmParseSyntaxError as e:
            return False
    def parseRecordSep (self) -> bool:
        tok = self.gtok()
        if tok.tokenType == AsmTokenType.RecordSep:
            return True
        else:
            return False
    def parsePrefixComment (self) -> bool:
        tok = self.tokenizer.getCommentToken() # Must be of type AsmTokenType.Commentp
        self.prefixComment = tok.tokenStr.rstrip ("\r\n")
        return True;
    def parsePostfixComment (self) -> bool:
        tok = self.tokenizer.getCommentToken() # Must be of type AsmTokenType.Comment
        self.postfixComment = tok.tokenStr.rstrip ("\r\n")
        return True;
    def parseSectionOffset (self) -> bool:
        tok = self.gtok()
        if tok.tokenType != AsmTokenType.DigitString:
            self.ptok (tok)
            self.sectionOffset = 0
            return True
        else:
            self.sectionOffset = int (tok.tokenStr)
            return True
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
    def parseUnaryOper (self) -> AsmExpr:
        tok = self.gtok()
        if tok.tokenType == AsmTokenType.Operator:
            if tok.tokenStr == "-":     # Lookahead for the idiom "(-)"
                tok1 = self.gtok()
                if tok1.tokenType == AsmTokenType.Operator and tok1.tokenStr == ")":
                    self.ptok (tok1)
                    return AsmExpr (AsmExprType.Literal, "0")
                else:
                    self.ptok (tok1)
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
            if tok.tokenType == AsmTokenType.Operator and tok.tokenStr in ["*", "/"]:
                e = AsmExpr (AsmExprType.BinaryMult if tok.tokenStr == "*" else AsmExprType.BinaryDiv, "")
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

class AsmProgram:
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
        inFileName = self.cmdArgs.inFileName
        outFileName = self.cmdArgs.OutFile if self.cmdArgs.OutFile is not None else self.getOutFileName (inFileName)
        if outFileName == "-":
            return sys.stdout
        else:
            return open (outFileName, "w")
    def getOutFileName (self, inFileName):
        for i in range (len(inFileName)):
            j = len (inFileName) - 1 - i
            c = inFileName[j]
            if c == '.':
                return inFileName[0:j] + ".ww"
        return inFileName + ".ww"
    def absLabel (self, section: str, relOrAbsLabel: str) -> str:
        if relOrAbsLabel[len(relOrAbsLabel)-1] == 'r':
            return relOrAbsLabel.rstrip ("r") + section
        else:
            return relOrAbsLabel
    def getExprValue (self, expr: AsmExpr) -> str:
        if expr.exprType in [AsmExprType.Variable, AsmExprType.Literal]:
            return expr.exprData
        elif expr.exprType == AsmExprType.BinaryDot:
            return "%s.%s" % (expr.leftSubExpr.exprData, expr.rightSubExpr.exprData)
    def resolveOpcode (self, opcode: str) -> str:
        dict = {"sl": "slr", "sr": "srr", "p": ".word"}
        if opcode in dict:
            return dict[opcode]
        else:
            return opcode
    def parseLines (self):
        lineNo = 1
        s = open (self.cmdArgs.inFileName, "r")
        while True:
            line = s.readline()
            if line == "":
                break
            else:
                l = AsmParsedLine (line, lineNo)
                l.parseLine()
                if self.verbose:
                    l.print()
                self.parsedLines.append (l)
                lineNo += 1
    def genTables (self):
        parsedLine: AsmParsedLine = None
        for parsedLine in self.parsedLines:
            if self.curSection is not None:
                self.lineToSection[parsedLine] = self.curSection
            if parsedLine.opcode == "section":
                self.curSection = parsedLine.addrExpr.exprData
            elif parsedLine.opcode != "":
                parsedLine.opcode = self.resolveOpcode (parsedLine.opcode)
                label = "%d%s" % (parsedLine.sectionOffset, self.curSection)
                self.lineToLabel[parsedLine] = label
                addrRefExpr = parsedLine.addrExpr
                if addrRefExpr.exprType in [AsmExprType.Variable, AsmExprType.Literal]:
                    if addrRefExpr.exprType == AsmExprType.Variable:
                        refLabel = self.absLabel (self.curSection, addrRefExpr.exprData)
                        addrRefExpr.exprData = refLabel
                        self.addrRefsToReferringLine[refLabel] = parsedLine
                pass
            else:
                pass
    def genAsmCode (self):
        s = self.outStream
        for parsedLine in self.parsedLines:
            if parsedLine.opcode == "section":
                s.write ("%s:\n" % parsedLine.addrExpr.exprData)
            elif parsedLine.opcode != "":
                opcode = parsedLine.opcode
                commentSpaces = " "*((20 - (len (parsedLine.addrExpr.exprData) + len (opcode))))
                comment = parsedLine.postfixComment
                commentFmt = "%s; %s" % (commentSpaces, comment) if comment != "" else ""
                label = self.lineToLabel[parsedLine]
                if label in self.addrRefsToReferringLine:
                    s.write ("%s:%s %s %s%s\n" % (label,
                                                " "*((10 - (len(label) + 1)) - 1),
                                                opcode,
                                                self.getExprValue (parsedLine.addrExpr),
                                                commentFmt))
                else:
                    s.write ("%s%s %s%s\n" % (" "*10,
                                            opcode,
                                            self.getExprValue (parsedLine.addrExpr),
                                            commentFmt))
            elif parsedLine.prefixComment != "" and parsedLine.opcode == "":
                s.write ("; %s\n" % parsedLine.prefixComment)

def main():
    parser = wwinfra.StdArgs().getParser (".")
    parser.add_argument ("inFileName", help="")
    parser.add_argument ("-o", "--OutFile", help="File to write (default basename(inputFileName).ww)", type=str)
    parser.add_argument ("-v", "--Verbose", help="Generate extra debug output", action="store_true")
    cmdArgs = parser.parse_args()
    cb = wwinfra.ConstWWbitClass (args = cmdArgs)
    wwinfra.theConstWWbitClass = cb
    cb.log = wwinfra.LogFactory().getLog (isAsmLog = True)
    p = AsmProgram (cmdArgs)
    p.parseLines()
    p.genTables()
    p.genAsmCode()
 
if __name__ == "__main__":
    main()
        
