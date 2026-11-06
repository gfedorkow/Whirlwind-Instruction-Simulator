
# use code-correlate to search for a pattern in the tape corpus
# This script takes quite a while to finish...
# fedorkow, Aug 16, 2025
#
# PROBE=`cygpath -w /cygdrive/c/Users/guyfe/Documents/guy/WW/Code-Samples-Local/Utility-Control/util-ctrl.acore`

LOG=~/tmp/tape-search.log
WWCOR=${PYTHONPATH}\\..\\Tools\\code-correlate.py

rm ${LOG}
find ../Magnetic-Tapes ../Paper-Tapes -name "*core" > ~file_list.txt 

for f in `cat list-of-executables.txt`
  do
  echo $f
  python ${WWCOR} -q -t 12 -p  `cygpath -w $f` -f ~file_list.txt >> ${LOG}
  echo ""
done
