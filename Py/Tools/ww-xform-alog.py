import os
import sys
import re
import math
import traceback
import argparse
import wwinfra
from enum import Enum
from collections import deque
from wwasmparser import AsmExprValue, AsmExprValueType, AsmExprEnv, AsmExpr, AsmExprType
from wwflex import FlasciiToFlex
from archaeolog import ArchaeoLogReader, AlogParsedLine, ArchaeoAttr

AlogElementType = int|float|str

# HtmlTop and descendants represent the semantics of tapes and cores

class HtmlTop:
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

class HtmlTapes (HtmlTop):
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
            tape = HtmlTape (tapeName, tapeType, **kwargs)
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

class HtmlTape (HtmlTop):
    def __init__ (self, tapeName: str, tapeType: str, **kwargs):
        super().__init__ (**kwargs)
        alog = self.alog
        self.tapeName = tapeName
        self.tapeType = tapeType
        self.coreList: [HtmlCore] = []
        coreNames = [x for x in (alog.lookupAll (tapeName, "utdToCore") | alog.lookupAll (tapeName, "utdToFc"))]
        coreNames.sort()
        avgCoreSize = 0
        for coreName in coreNames:
            coreType = alog.lookup (coreName, "fileType")
            self.coreList.append (HtmlCore (coreName, coreType, **kwargs))
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

class HtmlCore (HtmlTop):
    def __init__ (self, coreName: str, coreType: str, **kwargs):
        super().__init__ (**kwargs)
        self.coreName: str = coreName
        self.coreType: str = coreType
        self.coreList: [HtmlCore] = []
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

class AlogToSomething:
    def __init__ (self):
        self.verbose = False
        self.objects: set(str) = set()
        self.attrs: set = set()
        self.values: set = set()
        self.treeTops: set = set()
        self.readLog()
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
        self.objects.add (objStr)
        self.attrs.add (attr)
        self.values.add (value)
    def readLog (self):
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
        pass

class AlogToLispTriples (AlogToSomething):
    def __init__ (self):
        pass
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

class AlogToHtml (AlogToSomething):
    def __init__ (self):
        self.objAttrToValue: {str: set(AlogElementType)} = {}       # Concat string reps of obj and attr to form dict key
        super().__init__()
        h = open ("xxx.html", "wt")
        t = HtmlTapes (alog = self, htmlOut = h)
        t.emitHtml()
        pass

    def addEntry (self, obj, attr, value):
        super().addEntry (obj, attr, value)
        objStr = str (obj)
        if isinstance (attr, ArchaeoAttr):
            attrStr = attr.name
        else:
            attrStr = str (attr)
        key = objStr + attrStr
        if key not in self.objAttrToValue:
            self.objAttrToValue[key] = set()
        self.objAttrToValue[key].add (value)

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

class AlogToCsv (AlogToSomething):
    def __init__ (self):
        self.objAttrToTriples: {str: [[AlogElementType]]} = {}      # key is concat string reps of obj and attr
        self.objToTriples: {str: [[AlogElementType]]} = {}          # key is obj
        
        self.paths: set = set()
        self.treeTopObjToPathToValue: {AlogElementType: [{(): AlogElementType}]} = {} # List of dicts

        super().__init__()

        self.buildRows()

        pass

    def addEntry (self, obj, attr, value):
        super().addEntry (obj, attr, value)
        objStr = str (obj)
        if isinstance (attr, ArchaeoAttr):
            attrStr = attr.name
        else:
            attrStr = str (attr)
        key = objStr + attrStr
        if key not in self.objAttrToTriples:
            self.objAttrToTriples[key] = []
        self.objAttrToTriples[key].append ([obj, attr, value])
        if obj not in self.objToTriples:
            self.objToTriples[key] = []
        self.objToTriples[key].append ([obj, attr, value])
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

    # Should be renamed -- only called with a treetop
    def walkValueTree (self, obj: AlogElementType):
        objToMultiIndex = {}        # map obj to [index, length] pair
        curPathToValue = None
        self.treeTopObjToPathToValue[obj] = []
        multiAttr = "_isMulti"  # ***********
        def walkIndexSetup (obj):
            nonlocal objToMultiIndex
            if obj in self.objToTriples:
                triples = self.objToTriples[obj]
                for triple in triples:
                    obj, attr, value = triple
                    if str (value) + multiAttr in self.objAttrToTriples:
                        objToMultiIndex[value] = [0, len (self.objToTriples[value]) - 1]
                    walkIndexSetup (value)
            pass
        def multiIndexSize () -> int:
            r: int = 1
            for obj in objToMultiIndex:
                index, len = objToMultiIndex[obj]
                r *= len
            return r
        def incrMultiIndex ():
            nonlocal objToMultiIndex
            carry = 1
            for obj in objToMultiIndex:
                index, len = objToMultiIndex[obj]
                if index + carry == len:
                    index = 0
                    carry = 1
                else:
                    index += carry
                    carry = 0
                objToMultiIndex[obj] = [index, len]
        def walk (obj, path: ()):
            self.paths.add (path)
            curPathToValue[path] = obj
            if obj in self.objToTriples:
                triples = self.objToTriples[obj]
                for triple in triples:
                    obj, attr, value = triple
                    if str (value) + multiAttr not in self.objAttrToTriples:
                        walk (value, path + (attr,))
                for triple in triples:
                    obj, attr, value = triple
                    if str (value) + multiAttr in self.objAttrToTriples:
                        mObj, mAttr, mValue = triple
                        triples = self.objToTriples[value]
                        if value in objToMultiIndex:
                            index, len = objToMultiIndex[value]
                            triple = triples[index]
                            obj, attr, value = triple
                            if attr != multiAttr:
                                walk (value, path + (attr,))
        
        walkIndexSetup (obj)
        for i in range (0, multiIndexSize()):
            curPathToValue = {}
            walk (obj, (()))
            self.treeTopObjToPathToValue[obj].append (curPathToValue)
            incrMultiIndex()

        pass

    def buildRows (self):
        suffix = 0
        objAttrStrs = [key for key in self.objAttrToTriples]
        for objAttrStr in objAttrStrs:
            triples = self.objAttrToTriples[objAttrStr]
            if len (triples) > 1:
                obj = triples[0][0]
                attr = triples[0][1]
                newObj = "obj-" + str (suffix)
                suffix += 1
                newAttr = attr + "-" + str (suffix)
                suffix += 1
                del self.objAttrToTriples[objAttrStr]
                self.objAttrToTriples[str (obj) + newAttr] = [[obj, newAttr, newObj]]
                self.objAttrToTriples[newObj + attr] = []
                for triple in triples:
                    self.objAttrToTriples[newObj + attr].append ([newObj, attr, triple[2]])
                multiAttr = "_isMulti"
                self.objAttrToTriples[newObj + multiAttr] = [[newObj, multiAttr, "True"]]
                pass

        self.objToTriples = {}
        for objAttrStr in self.objAttrToTriples:
            for triple in self.objAttrToTriples[objAttrStr]:
                obj, attr, value = triple
                if obj not in self.objToTriples:
                    self.objToTriples[obj] = []
                self.objToTriples[obj].append (triple)

        for obj in self.treeTops:
             self.walkValueTree (obj)

        pathsAsList = [path for path in self.paths]
        pathsAsList.sort (key = lambda p: p)
        canonicalPaths = pathsAsList
        print ("LAS57")
        sys.stdout.write ("\t")
        for canonicalPath in canonicalPaths:
            if len (canonicalPath) != 0:
                sys.stdout.write (str (canonicalPath[len (canonicalPath) - 1]) + "\t")
        sys.stdout.write ("\n")
        
        print ("LAS58")
        for obj in self.treeTops:
            for d in self.treeTopObjToPathToValue[obj]:
                for canonicalPath in canonicalPaths:
                    if canonicalPath in d:
                        value = str (d[canonicalPath])
                    else:
                        value = "<undefined>"
                    # sys.stdout.write (str (canonicalPath) + ": " + value + " ")
                    sys.stdout.write (value + "\t")
                sys.stdout.write ("\n")
            
        pass

    
def main():
    parser = wwinfra.StdArgs().getParser ("Transform ArchaeoLog to various representations.")
    args = parser.parse_args()
    
    cb = wwinfra.ConstWWbitClass (args = args)
    wwinfra.theConstWWbitClass = cb
    # cb.log = wwinfra.LogFactory().getLog (isAsmLog = True)

    x = AlogToHtml()

    # x.emitLispTriples()

    x = AlogToCsv()

main()

