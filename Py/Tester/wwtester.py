
import os
import sys
import subprocess
import argparse
import yaml
import re
import shutil
from wwinfra import ArgsTokenizer


# On cygwin-on-Windows, there's an unhappy mixture of Windows-style file paths
# and Linux-style filepaths.
# On cygwin, a rooted file on the C drive is /cygdrive/c/rest-of-path
# This routine checks for that pattern, and changes it to c:/rest-of-path.
# "os.path normalization" takes care of forward and backward slashes.
def cyg_to_win(cygpath):
    m = re.match("/cygdrive/(.)/", cygpath)
    if m:
        npath = re.sub("/cygdrive/./", m.group(1) + ":/", cygpath)
        return npath
    return cygpath

class Test:
    def __init__ (self, testName, cmdArgs):
        self.testName = testName
        # Bail if path not specified
        if "WWROOT" not in list (os.environ):
            sys.stdout.write ("WWROOT not found.")
            sys.stdout.flush()
            sys.exit (True)
        self.commonDir = cyg_to_win(os.environ["WWROOT"])
        self.testsDir = os.path.normpath (self.commonDir + "/Tests")
        self.testDir = os.path.normpath (self.testsDir + "/" + self.testName)
        self.dryRun = cmdArgs.DryRun
        self.quiet = cmdArgs.Quiet
        self.accept = cmdArgs.Accept
        self.testType = None
        self.testBaseName = ""
        self.simArgs = []
        self.asmArgs = []
        self.coreArgs = []
        self.disasmArgs = []
        self.fileFilters = []
        self.testRefsDir = os.path.normpath (self.testDir + "/TestRefs")
        self.testResultsDir = os.path.normpath (self.testDir + "/TestResults")
        self.readTestInfoFile()
        self.asmPyProg = os.path.normpath (self.commonDir + "/Py/Assembler/wwasm.py")
        self.asmLogFileName = os.path.normpath (self.testResultsDir + "/" + self.testBaseName + "." + "wwasm" + ".log")
        self.disasmPyProg = os.path.normpath (self.commonDir + "/Py/Disassembler/wwdisasm.py")
        self.disasmLogFileName = os.path.normpath (self.testResultsDir + "/" + self.testBaseName + "." + "wwdisasm" + ".log")
        self.simPyProg = os.path.normpath (self.commonDir + "/Py/Sim/wwsim.py")
        self.simLogFileName = os.path.normpath (self.testResultsDir + "/" + self.testBaseName + "." + "wwsim" + ".log")
        self.wwFile = os.path.normpath (self.testDir + "/" + self.testBaseName + ".ww")
        self.coreFileBase = os.path.normpath (self.testResultsDir + "/" + self.testBaseName)
        self.coreFile = self.coreFileBase + ".acore"
        self.coreFileAsSrc = os.path.normpath (self.testDir + "/" + self.testBaseName + ".acore")

    def parseOptions (self, str):
        if str is None:
            return []
        t = ArgsTokenizer (str)
        optionList = []
        while True:
            tok = t.getToken()
            if tok == t.endOfString:
                break
            else:
                optionList.append (tok)
        return optionList

    def confirmOkDir (self, dir):
        sys.stdout.write ("%s is not the standard test directory. Ok to delete? [y,N]: " % dir)
        sys.stdout.flush()
        r = sys.stdin.readline().lower()
        return True if r == "y\n" else False

    def setupResultsDir (self):
        testResultsDirBaseName = os.path.basename (self.testResultsDir)
        oldDir = self.testResultsDir + ".old"
        if os.path.exists (oldDir):
            if testResultsDirBaseName == "TestResults":
                shutil.rmtree (oldDir)
            else:
                if not confirmOkDir (oldDir):
                    sys.exit (True)
                else:
                    shutil.rmtree (oldDir)
        if os.path.exists (self.testResultsDir):
            os.rename (self.testResultsDir, oldDir)
        os.mkdir (self.testResultsDir)

    def readTestInfoFile (self):
        try:
            s = open (self.testDir + "/" + "TestInfo.yaml", "r")
        except FileNotFoundError as e:
            return self
        y = yaml.Loader (s)
        d = y.get_data()
        self.testType = d["testType"]
        self.testBaseName = d["baseName"]
        keys = list (d)
        if "cmd" in keys:
            self.asmArgs += (self.parseOptions (d["cmd"]))
        if "cmdOptions" in keys:
            self.asmArgs += (self.parseOptions (d["cmdOptions"]))
        if "asmOptions" in keys:
            self.asmArgs += (self.parseOptions (d["asmOptions"]))
        if "simOptions" in keys:
            self.simArgs += (self.parseOptions (d["simOptions"]))
        if "coreOptions" in keys:
            self.coreArgs += (self.parseOptions (d["coreOptions"]))
        if "disasmOptions" in keys:
            self.disasmArgs += (self.parseOptions (d["disasmOptions"]))
        if "verify" in keys:
            filterList = []
            for verifyDict in d["verify"]:
                verifyDictKeys = list (verifyDict)
                if "file" in verifyDictKeys:
                    fileDict = verifyDict["file"]
                    self.fileFilters.append (FileFilter (fileDict["name"], fileDict["filter"], self))
                else:
                    logDict = verifyDict["log"]
                    self.fileFilters.append (LogFilter (logDict["name"], logDict["filter"], self))
        return self

    def run (self):     # Subclass overrides should call super
        # x = subprocess.run(["ls", "-1"],capture_output=True).stdout
        self.setupResultsDir()
        if "-c" not in self.simArgs and "--CycleLimit" not in self.simArgs:
            self.simArgs += ["-c", "10000"]
        if "--LogDir" not in self.simArgs:
            self.simArgs += ["--LogDir", self.testResultsDir]
        if "--LogDir" not in self.asmArgs:
            self.asmArgs += ["--LogDir", self.testResultsDir]
        if "--LogDir" not in self.disasmArgs:
            self.disasmArgs += ["--LogDir", self.testResultsDir]
        self.asmCmd = ["python", self.asmPyProg, self.wwFile] + self.asmArgs + ["-o", self.coreFileBase]
        self.simCmd = ["python", self.simPyProg] + self.simArgs + [self.coreFile] + self.coreArgs
        self.disasmCmd = ["python", self.disasmPyProg] + self.disasmArgs + [self.coreFileAsSrc] + ["-o", self.coreFileBase + ".ww"]

    def cmdListToString (self, cmdList):
        s = ""
        for x in cmdList:
            if os.path.isabs (x):
                s += " .../%s" % os.path.basename (x)
            else:
                s += " %s" % x
        return s

    def runSubprocess (self, cmd, logFileName):
        if self.dryRun:
            print ("Dry run: " + self.cmdListToString (cmd))
        else:
            sys.stdout.flush()
            logFile = open (logFileName, "wb")  # Binary mode to avoid adding cr to lines
            print ("*** wwtester running command: ", self.cmdListToString (cmd))
            # This is probably not the best way to combine stdout and stderr.
            # Should try to find a better way. See net search for "python popen combine stdout stderr".
            proc = subprocess.Popen (cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for line in proc.stdout:
                if not self.quiet:
                    print (line.decode(), end="", file=sys.stdout)      # Print to stdout
                logFile.write(line)                                     # Write to file
            for line in proc.stderr:
                if not self.quiet:
                    print (line.decode(), end="", file=sys.stderr)      # Print to stderr
                logFile.write(line)                                     # Write to file
            sys.stdout.flush()
            sys.stderr.flush()
            logFile.flush()
            logFile.close()

    def report (self):
        sys.stdout.write ("*** wwtester checking test results...\n")
        for fileFilter in self.fileFilters:
            fileFilter.report()
        sys.stdout.write ("*** wwtester test complete\n")

    def acceptResults (self):
        # rm testRefs and mv testResults to testRefs
        self.testResultsDir
        self.testRefsDir
        testRefsDirBaseName = os.path.basename (self.testRefsDir)
        if os.path.exists (self.testRefsDir):
            if testRefsDirBaseName == "TestRefs":
                shutil.rmtree (self.testRefsDir)
            else:
                print ("Error: Incorrect TestRefs directory: ", self.testRefsDir)
                sys.exit (True)
        if os.path.exists (self.testResultsDir):
            os.rename (self.testResultsDir, self.testRefsDir)

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

# fileName is relative to TestRefs or TestResults dir

class FileFilter:
    def __init__ (self, fileName, filterRegexp, test: Test):
        self.fileName = fileName
        self.filterRegexp = "^.*" + filterRegexp + ".*$"
        self.test = test
        self.srcFile = os.path.normpath (self.test.testRefsDir + "/" + self.fileName)
        self.dstFile = os.path.normpath (self.test.testResultsDir + "/" + self.fileName)
    # private
    def scanForMatch (self, s) -> str:
        while (True):
            line = s.readline()
            if len (line) == 0:
                return ""
            elif re.match (self.filterRegexp, line):
                return line
    def verify (self) -> (bool, str, int, str, int):
        src = LineStream (self.srcFile)
        dst = LineStream (self.dstFile)
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
        sys.stdout.write ("Checking files %s and %s with filter regexp \"%s\"..." % (self.srcFile, self.dstFile, self.filterRegexp))
        if not self.test.dryRun:
            (verifyStatus, srcLine, srcLineNo, dstLine, dstLineNo) = self.verify()
            if verifyStatus:
                sys.stdout.write ("PASSED\n")
            else:
                sys.stdout.write ("FAILED: First diff found is:\n%dc%d\n < %s---\n > %s" %
                                  (srcLineNo,
                                   dstLineNo,
                                   srcLine if srcLine != "" else "\n",
                                   dstLine if dstLine != "" else "\n"
                                  ))
        else:
            sys.stdout.write ("Dry Run: NO RESULT\n")


# The log name is the command name used, the middle piece of a log file name
# consisting of <core-file-base>.<command-name>.log, e.g., bounce.wwsim.log.
# Filter is a regexp and denotes line of the file which should remain in the
# comparison, i.e., it works like egrep.

class LogFilter (FileFilter):
    def __init__ (self, logName, filterRegexp, test: Test):
        self.logName = logName
        fileName = test.testBaseName + "." + self.logName + ".log"
        super().__init__ (fileName, filterRegexp, test)

#
# Test Types
#
        
# Assemble a .ww and run it, without generating a flowgraph (.gv) file

class AsmSimTest (Test):
    def __init__ (self, testName, cmdArgs):
        super().__init__ (testName, cmdArgs)
    def run (self):
        super().run()
        self.runSubprocess (self.asmCmd, self.asmLogFileName)
        self.runSubprocess (self.simCmd, self.simLogFileName)
        self.report()

# Disassamble a core file.

class DisasmTest (Test):
    def __init__ (self, testName, cmdArgs):
        super().__init__ (testName, cmdArgs)
    def run (self):
        super().run()
        self.runSubprocess (self.disasmCmd, self.disasmLogFileName)
        self.report()

# Run an arbitrary command

class CommandTest (Test):
    def __init__ (self, testName, testerCmdArgs):
        super().__init__ (testName, testerCmdArgs)
    def run (self):
        super().run()
        self.runSubprocess (self.cmd, self.cmdOptions)
        self.report()

# All is a special test type -- but has a dir!

class AllTest (Test):
    def __init__ (self, testName, cmdArgs):
        super().__init__ (testName, cmdArgs)
        self.cmdArgs = cmdArgs
    def run (self):
        testNames = os.listdir (self.testsDir)
        for testName in testNames:
            if testName != "All":
                sys.stdout.write ("\n*** wwtester running test: %s\n" % (testName))
                testType = Test(testName, self.cmdArgs).readTestInfoFile().testType
                if testType is not None:
                    testClassName = testType + "Test"
                    test = globals()[testClassName](testName, self.cmdArgs)
                    test.run()
           
#
# End Test Types
#
        
def main():
    parser = argparse.ArgumentParser (description="Run Whirlwind Tests")
    parser.add_argument ("testName", help="Test name, a directry under the Tests directory. Specify \"All\" to run all tests.")
    parser.add_argument ("--TestsDir", help="Dir where to find tests. Default $PYTHONPATH/../../Tests.", type=str)
    parser.add_argument ("--DryRun", help="Print out commands to be run, but don't run them.", action="store_true")
    parser.add_argument("-q", "--Quiet", help="Suppress stdout and stderr output from program under test", action="store_true")
    parser.add_argument("--Accept", help="Copy all files in TestResults to TestRefs, replacing files therein", action="store_true")
    cmdArgs = parser.parse_args()
    # Instantiate a direct instance of Test just so we can read test info to find what subclass to instantiate
    testType = Test(cmdArgs.testName, cmdArgs).readTestInfoFile().testType
    if testType is not None:
        testClassName = testType + "Test"
        # Now make the real test subclass using the metasystem
        test = globals()[testClassName](cmdArgs.testName, cmdArgs)
        if test.accept:
            test.acceptResults()
        else:
            test.run()

if __name__ == "__main__":
    main()

