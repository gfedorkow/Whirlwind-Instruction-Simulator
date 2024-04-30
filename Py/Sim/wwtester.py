


































import os
import sys
import subprocess
import argparse
import yaml
import re
from wwinfra import Tokenizer


class Test:
    def __init__ (self, args):
        self.simArgs = []
        self.asmArgs = []
        self.coreArgs = []
        self.srcDir = "." if args.SrcDir is None else args.SrcDir
        self.dstDir =  self.srcDir + "/" + "TestResults" if args.DstDir is None else args.DstDir
        self.dstSpecified = args.DstDir is not None
        self.testBaseName = args.testBaseName
        self.dryRun = args.DryRun
        self.logFilters = []
        self.commonDir = self.unixPathFormat (os.environ["PYTHONPATH"]) # LAS Bail if don't find this
        self.asmPyProg = self.commonDir + "/../Assembler/wwasm.py"
        self.disasmPyProg = self.commonDir + "/../Disassembler/wwdisasm.py"
        self.simPyProg = self.commonDir + "/../Sim/wwsim.py"
        self.wwFile = self.srcDir + "/" + self.testBaseName + ".ww"
        self.coreFileBase = self.dstDir + "/" + self.testBaseName
        self.coreFile = self.coreFileBase + ".acore"

    def unixPathFormat (self, x):       # Python is smart enough not to need this
        return x

    def parseOptions (self, str):
        if str is None:
            return []
        t = Tokenizer (str, delimiter = ' ')
        optionList = []
        while True:
            tok = t.getToken()
            if tok == t.endOfString:
                break
            else:
                optionList.append (tok)
        return optionList

    def readTestInfoFile (self):
        s = open (self.srcDir + "/" + "TestInfo.yaml", "r")
        # LAS check error
        y = yaml.Loader (s)
        d = y.get_data()
        keys = list (d)
        if "asmOptions" in keys:
            self.asmArgs += (self.parseOptions (d["asmOptions"]))
        if "simOptions" in keys:
            self.simArgs += (self.parseOptions (d["simOptions"]))
        if "coreOptions" in keys:
            self.coreArgs += (self.parseOptions (d["coreOptions"]))
        if "verify" in keys:
            filterList = []
            for verifyDict in d["verify"]:
                logDict = verifyDict["log"]
                self.logFilters.append (LogFilter (logDict["name"], logDict["filter"], self))

    def run (self):     # Subclass overrides should call super
        # x = subprocess.run(["ls", "-1"],capture_output=True).stdout
        self.readTestInfoFile()
        if not self.dstSpecified and not os.path.exists (self.dstDir): 
            os.mkdir (self.dstDir)
        if "-c" not in self.simArgs and "--CycleLimit" not in self.simArgs:
            self.simArgs += ["-c", "10000"]
        if "--LogDir" not in self.simArgs:
            self.simArgs += ["--LogDir", self.dstDir]
        if "--LogDir" not in self.asmArgs:
            self.asmArgs += ["--LogDir", self.dstDir]
        self.asmCmd = ["python", self.asmPyProg, self.wwFile] + self.asmArgs + ["-o", self.coreFileBase]
        self.simCmd = ["python", self.simPyProg] + self.simArgs + [self.coreFile] + self.coreArgs

    def cmdListToString (self, cmdList):
        s = ""
        for x in cmdList:
            if os.path.isabs (x):
                s += " .../%s" % os.path.basename (x)
            else:
                s += " %s" % x
        return s

    def runSubprocess (self, cmd):
        if self.dryRun:
            print ("Dry run: " + self.cmdListToString (cmd))
        else:
            print ("*** wwtester running command: ", self.cmdListToString (cmd))
            sys.stdout.flush()
            return subprocess.run (cmd)

    def report (self):
        sys.stdout.write ("*** wwtester checking test results...\n")
        for logFilter in self.logFilters:
            logFilter.report()
        sys.stdout.write ("*** wwtester test complete\n")

class LineStream:
    def __init__ (self, file):
        self.file = file
        self.stream = open (file, "r")
        self.lineNo = 0
    def readline (self):
        r = self.stream.readline()
        if r != "":
            self.lineNo += 1
        return r

# The log name is the command name used, the middle piece of a log file name
# consisting of <core-file-base>.<command-name>.log, e.g., bounce.wwsim.log.
# Filter is a regexp and denotes line of the file which should remain in the
# comparison, i.e., it works like egrep.

class LogFilter:
    def __init__ (self, logName, filterRegexp, test: Test):
        self.logName = logName
        self.filterRegexp = "^.*" + filterRegexp + ".*$"
        self.test = test
        self.srcLogFile = self.test.srcDir + "/" + self.test.testBaseName + "." + self.logName + ".log"
        self.dstLogFile = self.test.dstDir + "/" + self.test.testBaseName + "." + self.logName + ".log"
    # private
    def scanForMatch (self, s) -> str:
        while (True):
            line = s.readline()
            if len (line) == 0:
                return ""
            elif re.match (self.filterRegexp, line):
                return line
    def verify (self) -> (bool, str, int, str, int):
        src = LineStream (self.srcLogFile)
        dst = LineStream (self.dstLogFile)
        while (True):
            srcLine = self.scanForMatch (src)
            dstLine = self.scanForMatch (dst)
            if srcLine == "" and dstLine == "":
                return (True, "", 0, "", 0)
            if srcLine != "" and dstLine != "" and srcLine == dstLine:
                continue
            else:
                return (False, srcLine, src.lineNo, dstLine, dst.lineNo)
    # public
    def report (self):
        (verifyStatus, srcLine, srcLineNo, dstLine, dstLineNo) = self.verify()
        sys.stdout.write ("Checking logs %s and %s with filter regexp \"%s\"..." % (self.srcLogFile, self.dstLogFile, self.filterRegexp))
        if verifyStatus:
            sys.stdout.write ("PASSED\n")
        else:
            sys.stdout.write ("FAILED: First diff found is:\n%dc%d\n < %s---\n > %s" %
                              (srcLineNo,
                               dstLineNo,
                               srcLine,
                               dstLine))
        
# Assemble a .ww and run it, without generating a flowgraph (.gv) file

class AsmSimTest (Test):
    def __init__ (self, *args):
        super().__init__ (*args)
    def spaces (self, n):
        r = ""
        for i in range (0, n):
            r += " "
        return r
    def run (self):
        super().run()
        self.runSubprocess (self.asmCmd)
        self.runSubprocess (self.simCmd)
        self.report()

# Disassamble a core file. LAS 4/7/24: We need to establish criteria for
# success, e.g., idempotency modulo dates when reassembled, etc. For now success
# will simply mean the program ran successfully.

class DisasmTest (Test):
    def __init__ (self, *args):
        super().__init__ (*args)
    def run (self):
        super().run()
        disasmCmd = ["python", self.disasmPyProg, self.coreFile, "-o", self.coreFileBase]
        print ("LAS3", disasmCmd)
        # subprocess.run (asmCmd)

def main():
    parser = argparse.ArgumentParser (description="Run Whirlwind Tests")
    parser.add_argument ("testBaseName", help="base name of test")
    parser.add_argument ("--SrcDir", help="Dir of source ww code, reference logs, etc.", type=str)
    parser.add_argument ("--DstDir", help="Dir where to deposit logs and other files from the test run.", type=str)
    parser.add_argument ("--DryRun", help="Print out commands to be run, but don't run them.", action="store_true")
    args = parser.parse_args()
    test = AsmSimTest (args)
    test.run()
    # test = DisasmTest (args)
    # test.run()


if __name__ == "__main__":
    main()

