
# Tape Image Translation
# guy, Jul 11, 2025

# this top-level script walks all the mag tape source files and calls wwutd to translate them
# into tcore, ocore, fc or whatever objects are found within.

while getopts "pm" opt; do
  case "$opt" in
    p) echo "Converting Paper Tape" ; TYPE=Paper-Tapes; EXT=.7ch ;;
    m) echo "Converting Magnetic Tape" ; TYPE=Magnetic-Tapes; EXT=.tap ;;
    *) echo "Invalid option: use -p or -m for Paper or Magnetic tape" ; exit 1 ;;
  esac
done
shift "$((OPTIND - 1))" # Remove parsed options from argument list
#  echo "Remaining positional arguments: $@"

if [ -z "${EXT}" ] ; then
  echo "Stop!  Use -p or -m for Paper or Magnetic tape" 
  exit 1
fi

#TYPE=Magnetic-Tapes
#EXT=.tap
#TYPE=Paper-Tapes
#EXT=.7ch

SRC=${WWROOT}/Recovered-Tapes/Source-Images/${TYPE}
DST=${WWROOT}/Recovered-Tapes/Translated-Files/${TYPE}
SCR=${WWROOT}/Recovered-Tapes/Translated-Files/Scripts
LOG=${DST}/Translation-Output.log

rm -f ${LOG}
cd $SRC
find * -type d -exec mkdir ${DST}/{} ";"
find * -type f -name "*${EXT}" -exec sh ${SCR}/one-tape.sh ${SRC} "{}" ${EXT} ${DST}  ";"  > ${LOG} 2>&1


