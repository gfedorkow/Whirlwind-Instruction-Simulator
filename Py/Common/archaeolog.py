





























from enum import Enum
import inspect
import os
import sys
import subprocess
import re
import shutil
import random
import argparse
import wwinfra
from wwasmparser import AsmExprValue, AsmExprValueType, AsmExprEnv, AsmExpr, AsmExprType, AsmParsedLine
from wwasmparser import AsmToken, AsmTokenizer, AsmTokenType, AsmParseSyntaxError

# The intent here is that attribute names be case-insensitive in downstream
# processing, but we'll emit them into the archaeolog files preserving case.

ArchaeoAttr = Enum ("ArchaeoAttr",
                    [
                     "utdToCore",
                     "utdToFc",
                     "disasmToWw",
                     "asmToAcore",
                     "asmToStaticFlowGv",
                     "simToDynamicFlowGv",
                     "dotToSvg",
                     "dotToJpg",
                     "jumpTo",
                     "jumpToCount",
                     "fileType",             # As denoted by file extension: tcore, ocore, etc.
                     "fileSize",
                     "error",
                     "utdIgnoredCoreFiles",
                     "tapePathName",
                     "tapeId"
                    ])

class ArchaeoLog:
    def __init__ (self):
        self.enable = "--ArchaeoLog" in sys.argv
        self.logFile = None
        if self.enable:
            progName = os.path.basename (sys.argv[0])
            self.commonDir = os.environ["PYTHONPATH"]
            logDir = self.commonDir + "/../../archaeolog"
            if not os.path.exists (logDir):
                os.mkdir (logDir)
            fileOpened = False
            limit = 10
            i = 0
            logFile = None
            while not fileOpened and i < limit:
                r = random.randrange (1, 1000000)
                logFileName = logDir + "/" + progName + "." + str (r)
                try:
                    logFile = open (logFileName, "x")
                    fileOpened = True
                except FileExistsError as e:
                    # print ("Conflict", logFileName)
                    logFile = None
                i += 1
                if i == limit:
                    print ("Random Retry Limit reached for ArchaeoLog. ArchaeoLog is broken!", logFileName)
            self.logFile = logFile
        pass
    def writeObj (self, obj):     # private
        if isinstance (obj, int) or isinstance (obj, float):
            self.logFile.write (str (obj))
        elif isinstance (obj, ArchaeoAttr):
            self.logFile.write ("\"")
            self.logFile.write (obj.name)
            self.logFile.write ("\"")
        elif isinstance (obj, str):
            # Convert certain chars to escapes
            s = obj.replace("\n", "\\n").replace("\b", "\\b").replace("\t", "\\t").replace("\"", "\\\"")
            self.logFile.write ("\"")
            self.logFile.write (s)
            self.logFile.write ("\"")
        else:
            # It's likely that whatever type we actually have will have an id
            # string which does not need escaping, but for completeness,
            # truth-and-beauty check anyway.
            #
            # This is same as last clause but keep separate for now since we
            # may need changes.
            s = str(obj).replace("\n", "\\n").replace("\b", "\\b").replace("\t", "\\t").replace("\"", "\\\"")
            self.logFile.write ("\"")
            self.logFile.write (s)
            self.logFile.write ("\"")
        pass
    def log (self, obj, attr, val):
        if self.logFile is not None:
            self.logFile.write ("(")
            self.writeObj (obj)
            self.logFile.write (",")
            self.writeObj (attr)
            self.logFile.write (",")
            self.writeObj (val)
            self.logFile.write (")\n")
            self.logFile.flush()
        pass
    def close (self):
        if self.logFile is not None:
            self.logFile.close()

class ArchaeoLogReader:
    def __init__ (self):
        self.commonDir = os.environ["PYTHONPATH"]
        self.logDir = self.commonDir + "/../../archaeolog"
        self.files: [] = os.listdir (self.logDir)
        self.nFiles = len (self.files)
        self.fileIndex = -1
        self.curStream = None
        pass
    #
    # Read archaeolog files as a series of text lines, each line of the form
    # "(x,x,x)", where x is either a quoted string or a number. An empty string
    # means end of series.
    #
    # Parsing is left to the consumer.
    #
    def readLine (self) -> str:
        lineStr = self.curStream.readline() if self.curStream is not None else ""
        if lineStr == "":
            if self.curStream is not None:
                self.curStream.close()
            self.fileIndex += 1
            if self.fileIndex < self.nFiles:
                self.curStream = open (self.logDir + "/" + self.files[self.fileIndex], "r")
                lineStr = self.curStream.readline()
        return lineStr

# Top-level parse for an ArchaeoLog triple. Right now just parse an expression,
# with it understood that the format will be a paren wrapper enclosing a
# three-element comma-oper expr.
    
class AlogParsedLine (AsmParsedLine):
    def __init__ (self, str, verbose = False):
        super().__init__ (str, 0, verbose = verbose)
        self.tokenizer = AlogTokenizer (str)        # Replace the tokenizer so we can parse floats etc.
        pass
    def print (self):
        super().print()
        pass
    def parseLine (self) -> bool:
        try:
            self.parseStmt()
            return True
        except AsmParseSyntaxError as e:
            sys.stdout.flush()
            self.log.error (self.lineNo,
                            "%s at char pos %d%s" % (e, self.tokenizer.pos, self.tokenizer.caratString (self.lineStr, self.tokenizer.pos - 1)))
        pass
    def parseStmt (self) -> bool:
        self.operand = self.parseExpr()
        pass

class AlogTokenizer (AsmTokenizer):
    def __init__ (self, str):
        super().__init__ (str)
    # Cut the number or operators down just these three
    def isSingleCharOper (self, c) -> bool:
        return c in (',', '(', ')')
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
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        self.pos += 1
                        return AsmToken (AsmTokenType.Operator, c)
                    elif c == '"':
                        self.state = 9
                        self.pos += 1
                    else:
                        self.state = 2
                        self.pos += 1
                        self.push (c)
                case 2:
                    if c == self.endOfString:
                        self.state = 0
                        return AsmToken (AsmTokenType.NumberString, self.pop())
                    elif self.isSingleCharOper (c):
                        self.state = 0
                        return AsmToken (AsmTokenType.NumberString, self.pop())
                    else:
                        self.state = 2
                        self.pos += 1
                        self.push (c)
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
                    elif c == "\"":
                        self.state = 9
                        self.pos += 1
                        self.push ("\"")
                    else:
                        self.state = 9
                        self.push ("\\")
        return AsmToken()

def main():
    parser = wwinfra.StdArgs().getParser ("ArchaeoLog Test.")
    parser.add_argument ("n", type = int)
    args = parser.parse_args()
    random.seed (a = 0)     # For testing, we want random to be deterministic
    n = args.n
    for i in range (0, n):
        al = ArchaeoLog()
        al.log ("abc", "def", 42)
        al.log ("qwert\"poiuyt", "pqr", 57.314)
        al.log (al, "xyz\nuvw", 2.718)
        al.log ("n1", "val", 2.718)
        al.log ("n2", "val", 3.14159e-6)
        al.log ("n3", "val", -3.14159e-6)
        al.logFile.write ("(\"n4\",\"val\",1..05e94e6)\n")
        al.logFile.flush()
        for j in range (0, 10):
            attr: ArchaeoAttr = ArchaeoAttr(random.randrange (1, ArchaeoAttr.__len__() + 1))
            al.log (random.randrange (0, 1000), attr.name, random.randrange (0, 1000))
        al.close()
    """
    ar = ArchaeoLogReader()
    while True:
        s = ar.readLine()
        if s == "":
            break
        else:
            print (s.rstrip ("\n"))
    """
    pass

        
if __name__ == "__main__":
    main()



