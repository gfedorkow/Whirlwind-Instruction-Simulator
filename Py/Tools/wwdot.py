
import os
import sys
import subprocess
import shutil
import datetime
import time
import math

# Replacement for graphviz's dot command. All dot args should be accepted.
#
# dot can hang on large or strange graphs, so we wrap it in a timer and bail
# after a default of ten seconds.

def main ():
    args: [str] = sys.argv
    args.pop (0)
    if "--Timeout" in args:
        i = args.index ("--Timeout")
        timeout = int (args[i+1])
        args.pop (i)
        args.pop (i)
    else:
        timeout = 10
    args.insert (0, "dot")
    proc = subprocess.Popen (args)
    try:
        outs, errs = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        sys.stderr.write ("Timeout -- dot hung\n")
        proc.terminate()
        outs, errs = proc.communicate()
    except KeyboardInterrupt:
        sys.exit (0)

main()

