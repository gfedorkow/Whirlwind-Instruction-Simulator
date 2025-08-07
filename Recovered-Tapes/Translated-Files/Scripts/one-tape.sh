
# Tape Image Translation
# guy, Jul 11, 2025

# this tiny script assembles arguments to call the python tape decoder tool

# $1 - source path root
# $2 - file name and local path
# $3 - file type - .7ch or .tap
# $4 - destination path root

IF=$1/$2
OF=$4/`echo $2 | sed -e s/$3//`

if  wwutd `cygpath -w ${IF}` -o `cygpath -w ${OF}` ; then

  echo "Command succeeded"
else
  echo "Command failed"
  sleep 60
fi