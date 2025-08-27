
# use code-correlate to search for a pattern in the tape corpus
# This script takes quite a while to finish...
# fedorkow, Aug 16, 2025
#
# PROBE=`cygpath -w /cygdrive/c/Users/guyfe/Documents/guy/WW/Code-Samples-Local/Utility-Control/util-ctrl.acore`
PROBE=`cygpath -w /cygdrive/c/Users/guyfe/Documents/guy/WW/GitHub/Code-Samples/Laning-and-Zierler-Interpreter/float-lib.acore`
LOG=~/tmp/tape-search.log
WWCOR=${PYTHONPATH}\\..\\Tools\\code-correlate.py

find ../Magnetic-Tapes ../Paper-Tapes -name "*.tcore" -exec python ${WWCOR} -q -p ${PROBE} "{}" ";"  -exec echoerr "{}" ';' > ${LOG}

