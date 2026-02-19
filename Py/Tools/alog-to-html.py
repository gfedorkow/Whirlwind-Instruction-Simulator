import os
import sys
import re
import math
import traceback
import argparse
import wwinfra
from enum import Enum
from wwasmparser import AsmExprValue, AsmExprValueType, AsmExprEnv, AsmExpr, AsmExprType
from wwflex import FlasciiToFlex
from archaeolog import ArchaeoLogReader, AlogParsedLine, ArchaeoAttr

AlogElementType = int|float|str

class Top:
    def __init__ (self, alog: ArchaeoLogReader = None, htmlOut = None):
        self.alog = alog
        self.htmlOut = htmlOut
        pass
    def copyFileToStream (self, inFile: str, outStream):
        inStream = open (inFile, "r")
        outStream.write (inStream.read())
        inStream.close()
        pass
    def formatSingletonAttrValues (self, attrValues) -> str:
        r = ""
        for (attr, value) in attrValues:
            r += "%s: %s%s" % (attr, value, "&nbsp;"*5)
        return r

class Tapes (Top):
    def __init__ (self, **kwargs):
        super().__init__ (**kwargs)
        alog = self.alog
        self.tapeNameSet: set = set()
        self.tapeList = []
        for obj in alog.objects:
            type = alog.lookup (obj, "fileType")
            if type is not None and type in ("tap", "7ch", "7CH"):
                self.tapeNameSet.add (obj)
        self.tapeNameList: [] = [x for x in self.tapeNameSet]
        self.tapeNameList.sort() 
        for tapeName in self.tapeNameList:
            tapeType = alog.lookup (tapeName, "fileType")
            tape = Tape (tapeName, tapeType, **kwargs)
            self.tapeList.append (tape)
        pass
    def print (self):
        for tape in self.tapeList:
            tape.print()
        pass
    def emitHtml (self):
        s = self.htmlOut
        self.copyFileToStream ("prefix.html", s)
        s.write ("<ul id=\"myUL\">\n")
        s.write ("<li><span class=\"caret\">Beverages</span>\n")
        s.write ("<ul class=\"nested\">\n")
        for tape in self.tapeList:
            s.write ("<li>")
            tape.emitHtml()
            s.write ("</li>\n")
        s.write ("</ul>\n")
        s.write ("</li>\n")
        s.write ("</ul>\n")
        self.copyFileToStream ("suffix.html", s)
        s.close()
        pass

class Tape (Top):
    def __init__ (self, tapeName: str, tapeType: str, **kwargs):
        super().__init__ (**kwargs)
        alog = self.alog
        self.tapeName = tapeName
        self.tapeType = tapeType
        self.coreList: [Core] = []
        coreNames = [x for x in (alog.lookupAll (tapeName, "utdToCore") | alog.lookupAll (tapeName, "utdToFc"))]
        coreNames.sort()
        avgCoreSize = 0
        for coreName in coreNames:
            coreType = alog.lookup (coreName, "fileType")
            self.coreList.append (Core (coreName, coreType, **kwargs))
            coreSize = alog.lookup (coreName, ArchaeoAttr.fileSize)
            if coreSize is not None:
                avgCoreSize += coreSize
        if len (coreNames) != 0:
            avgCoreSize = avgCoreSize // len (coreNames)
        alog.addEntry (self.tapeName, "nCoreFiles", len (coreNames))
        alog.addEntry (self.tapeName, "avgCoreSize", avgCoreSize)
        pass
    def print (self):
        print (self.tapeName, self.tapeType)
        for core in self.coreList:
            core.print()
    def emitHtml (self):
        s = self.htmlOut
        e: str = self.alog.lookup (self.tapeName, ArchaeoAttr.error)
        if e is None:
            e = "None"
        attrValues = self.alog.lookupAllSingletons (self.tapeName)
        attrValuesStr = self.formatSingletonAttrValues (attrValues)
        r = str.replace
        attrValuesStr = attrValuesStr.replace ('[','').replace("],","").replace(']','').replace("'","").replace(',',':')
        nIgnored = self.alog.lookup (self.tapeName, ArchaeoAttr.utdIgnoredCoreFiles)
        if nIgnored is not None and nIgnored > 0:
            redPrefix = "<f1>"
            redSuffix = "</f1>"
        else:
            redPrefix = "<f2>"
            redSuffix = "</f2>"
        info = "%s<b>%s</b><br>%s%s%s" % (redPrefix, self.tapeName, "&nbsp;"*10, attrValuesStr, redSuffix)
        s.write ("<li><span class=\"caret\">%s</span>\n" % info)
        s.write ("<ul class=\"nested\">\n")
        for core in self.coreList:
            s.write ("<li>")
            core.emitHtml()
            s.write ("</li>\n")
        s.write ("</ul>\n")
        s.write ("</li>\n")
        pass

class Core (Top):
    def __init__ (self, coreName: str, coreType: str, **kwargs):
        super().__init__ (**kwargs)
        self.coreName: str = coreName
        self.coreType: str = coreType
        self.coreList: [Core] = []
        pass
    def print (self):
        print (self.coreName, self.coreType)
    def emitHtml (self):
        s = self.htmlOut
        attrValues = self.alog.lookupAllSingletons (self.coreName)
        attrValuesStr = self.formatSingletonAttrValues (attrValues)
        ignored = self.alog.lookup (self.coreName, ArchaeoAttr.error) == "ignored"
        if ignored:
            redPrefix = "<f1>"
            redSuffix = "</f1>"
        else:
            redPrefix = "<f2>"
            redSuffix = "</f2>"
        info = "%s%s%s %s%s" % ("&nbsp;"*10, redPrefix, self.coreName, attrValuesStr, redSuffix)
        s.write (info)
        pass

class AlogToHtml:
    def __init__ (self):
        self.verbose = False
        self.objAttrToValue: {str: set(AlogElementType)} = {}       # Concat string reps of obj and attr to form dict key
        self.objToTriple: {str: [AlogElementType]} = {}
        self.objects: set(str) = set()
        self.attrs: set = set()
        self.values: set = set()
        self.treeTops: set = set()
        self.singletonAttrs: set = set()
        self.muiltiValuedAttrs: set = set()
        self.rows: [[[AlogElementType]]] = []
        pass

    def error (self, msg: str):
        sys.stdout.flush()
        self.cb.log.error (self.parsedLine.lineNo, "%s in %s" % (msg, self.parsedLine.lineStr))

    def stringToNumber (self, s):
        r = None
        try:
            r = int (s)
            return r
        except ValueError as e:
            pass
        try:
            r = float (s)
            return r
        except ValueError as e:
            pass
        return r

    def addEntry (self, obj, attr, value):
        objStr = str (obj)
        if isinstance (attr, ArchaeoAttr):
            attrStr = attr.name
        else:
            attrStr = str (attr)
        key = objStr + attrStr
        if key not in self.objAttrToValue:
            self.objAttrToValue[key] = set()
            self.singletonAttrs.add (attrStr)
        else:
            if attrStr in self.singletonAttrs:
                self.singletonAttrs.remove (attrStr)
            self.muiltiValuedAttrs.add (attrStr)
        self.objAttrToValue[key].add (value)
        # self.objToTriple[objStr] = [obj, attr, value]
        self.objects.add (objStr)
        self.attrs.add (attr)
        self.values.add (value)

    def lookup (self, obj, attr) -> AlogElementType:
        if isinstance (attr, ArchaeoAttr):
            attrStr = attr.name
        else:
            attrStr = str (attr)
        key = str (obj) + attrStr
        if key in self.objAttrToValue:
            for value in self.objAttrToValue[key]:
                return value
        else:
            return None

    # list of attr-value pairs which are singly attached to obj
    def lookupAllSingletons (self, obj) -> [[]]:
        r = []
        for attr in self.attrs:
            valueSet = self.lookupAll (obj, attr)
            if len (valueSet) == 1:
                for value in valueSet:
                    r.append ([attr, value])
        return r
        pass

    def lookupAll (self, obj, attr) -> set:
        if isinstance (attr, ArchaeoAttr):
            attrStr = attr.name
        else:
            attrStr = str (attr)
        key = str (obj) + attrStr
        if key in self.objAttrToValue:
            return self.objAttrToValue[key]
        else:
            return set()

    def lookupObjTriples (self, obj) -> [AlogElementType]:
        pass

    def extractElements (self, line: AlogParsedLine) -> [AlogElementType]:
        # A paren wrapper and a three-valued comma operator (walk into a bar...)
        e: [AsmExpr] = [None]*3
        e[0] = line.operand.leftSubExpr.leftSubExpr
        e[1] = line.operand.leftSubExpr.rightSubExpr.leftSubExpr
        e[2] = line.operand.leftSubExpr.rightSubExpr.rightSubExpr
        r = []
        for i in range (0, 3):
            x = e[i]
            if x.exprType == AsmExprType.LiteralString:
                r.append (x.exprData)
            elif x.exprType == AsmExprType.LiteralNumber:
                r.append (self.stringToNumber (x.exprData))
            else:
                print ("LAS Bad type")
                r.append (0)
        return r

    # Transform to list format so we can hack with it in hmachine
    def emitLispTriples (self):
        alr = ArchaeoLogReader()
        lineNo = 0
        while True:
            lineStr = alr.readLine()
            lineNo += 1
            if lineStr != "":
                # line = AlogParsedLine (lineStr, lineNo, verbose = self.verbose)
                line = AlogParsedLine (lineStr, lineNo)
                line.parseLine()
                # A paren wrapper and three-valued comma operator
                obj: AsmExpr = line.operand.leftSubExpr.leftSubExpr
                attr: AsmExpr = line.operand.leftSubExpr.rightSubExpr.leftSubExpr
                value: AsmExpr = line.operand.leftSubExpr.rightSubExpr.rightSubExpr
                s = sys.stdout
                s.write ("(")
                s.write (obj.listingString())
                s.write (" ")
                s.write (attr.listingString())
                s.write (" ")
                s.write (value.listingString())
                s.write (")\n")
            else:
                break
        pass

    #
    # Part of eventual csv gen
    #
    def findObjAttrRow (self, obj, attr) -> [[AlogElementType]]:
        for row in self.rows:
            for t in row:
                if t[0] == obj and t[1] == attr:
                    return row
        return None
    def addTripleToMatchingRows (self, triple):
        obj, attr, value = triple
        matched = False
        for row in self.rows:
            for t in row:
                if (obj == t[0]):
                    row.append (triple)
                    matched = True
                    break
        if not matched:
            self.rows.append ([triple])
        pass
    def copyRow (self, row) -> []:
        newRow = row.copy()
        return newRow
    def replaceTriple (self, row, obj, attr, triple):
        for t in row:
            if t[0] == obj and t[1] == attr:
                row.remove (t)
                break
        row.append (triple)
        pass
    def buildRows (self):
        alr = ArchaeoLogReader()
        lineNo = 0
        while True:
            lineStr = alr.readLine()
            lineNo += 1
            if lineStr != "":
                # line = AlogParsedLine (lineStr, lineNo, verbose = self.verbose)
                line = AlogParsedLine (lineStr, lineNo)
                line.parseLine()
                # line.print()
                triple = self.extractElements (line)
                obj, attr, value = triple
                # print ("LAS57", triple)
                row = self.findObjAttrRow (obj, attr)
                if row is not None:
                    newRow = self.copyRow (row)
                    self.replaceTriple (newRow, obj, attr, triple)
                    # print ("LAS102", row, newRow)
                    self.rows.append (newRow)
                else:
                    self.addTripleToMatchingRows (triple)
            else:
                break
        pass

    def passOne (self):
        alr = ArchaeoLogReader()
        lineNo = 0
        while True:
            lineStr = alr.readLine()
            lineNo += 1
            if lineStr != "":
                # line = AlogParsedLine (lineStr, lineNo, verbose = self.verbose)
                line = AlogParsedLine (lineStr, lineNo)
                line.parseLine()
                # line.print()
                obj, attr, value = self.extractElements (line)
                self.addEntry (obj, attr, value)
            else:
                break
        for obj in self.objects:
            if obj not in self.values:
                self.treeTops.add (obj)
        h = open ("xxx.html", "wt")
        t = Tapes (alog = self, htmlOut = h)
        t.emitHtml()
        # LAS
        # for tape in t.tapeSet:
        #   print (tape)
        pass

def main():
    parser = wwinfra.StdArgs().getParser ("ArchaeoLog To Html.")
    args = parser.parse_args()
    
    cb = wwinfra.ConstWWbitClass (args = args)
    wwinfra.theConstWWbitClass = cb
    # cb.log = wwinfra.LogFactory().getLog (isAsmLog = True)

    x = AlogToHtml()
    x.passOne()
    # LAS
    print ("Singleton attributes:",  x.singletonAttrs)
    print ("Multi-valued attributes:", x.muiltiValuedAttrs)
    # x.emitLispTriples()
    x.buildRows()
    print ("LAS86")
    for row in x.rows:
        print (row)

main()

