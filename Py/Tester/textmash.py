import os
import sys
import subprocess
import argparse
import re
import shutil

class Masher:
    def __init__ (self):
        self.delim = "-*-*-*-*-*-*-*-*-*-*-123456-*-*-*-*-*-*-*-*-*-* "
        pass
    def checkDelim (self, s: str) -> bool:
        return self.delim in s
    def getFileName (self, s: str) -> str:
        return s.split (self.delim)[1].rstrip ("\n\r")
    # Check that all files to be mashed exist and are readable
    def checkInFiles (self. inFiles: [str]) -> bool:
        for inFile in inFiles:
            pass

        
    def mashFiles (self, inFiles: [str], outFile: str):
        sout = open (outFile, "wt")
        for file in inFiles:
            s = open (file, "r")
            sout.write (self.delim + file + "\n")
            while (True):
                line = s.readline()
                if len (line) == 0:
                    break
                else:
                    sout.write (line)
        pass
    def splitFiles (self, inFile: str):
        s = open (inFile, "r")
        curOutFile = None
        sout = None
        while (True):
            line = s.readline()
            if self.checkDelim (line) or len (line) == 0:
                if curOutFile is not None:
                    sout.close()
                if self.checkDelim (line):
                    curOutFile = self.getFileName (line)
                    sout = open (curOutFile, "wt")
                else:
                    break
            else:
                sout.write (line)
        pass

def main():
    files: [str] = []
    op: str = None
    outFile: str = None
    inFile: str = None
    state: int = 0
    i = 1
    while (True):
        arg = sys.argv[i]
        match state:
            case 0:
                if arg in ("-s""):
                    op = "s"
                    i += 1
                    state = 1
                elif arg in ("-m"):
                    op = "m"
                    i += 1
                    state = 2
                else:
                    break
            case 1:
                inFile = arg
                break
            case 2:
                if arg in ("-o"):
                    i += 1
                    state = 3
                else:
                    files.append (arg)
                    i += 1
                    state = 2
            case 3:
                outFile = arg
                break
        pass
    if (op is None or
        op == "m" and (outFile is None or inFile is not None) or
        op == "s" and (outFile is not None or inFile is None)):
        print ("Usage:\n"
               "  textmash -m file1 ... fileN -o outFile\n"
               "     Mashes file1 through fileN into outFile\n"
               "  textmash -s inFile\n"
               "     Splits inFile into the files specified therewithin\n")
        sys.exit (0)
    else:
        print (files, inFile, outFile)
        m = Masher()
        if op == "m":
            m.mashFiles (files, outFile)
        else:
            m.splitFiles (inFile)
    pass

main()

