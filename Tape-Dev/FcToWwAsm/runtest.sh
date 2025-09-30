#!/bin/bash
# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

sim="$PYTHONPATH/../../Py/Sim/wwsim.py"
simf="$PYTHONPATH/../../Py/Sim/wwsim.py --FlexoWin"
asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"
asmp="$PYTHONPATH/../../Py/Common/wwasmparser.py"
asml="$PYTHONPATH/../../Py/Assembler/wwlzparser.py"
asmc="$PYTHONPATH/../../Py/Assembler/cwparser.py"
ascflx="$PYTHONPATH/../../Py/Tools/ww-ASCII-to-Flexo.py"
utd="$PYTHONPATH/../../Py/Tape-Decode/wwutd.py"

# tapepath=$PYTHONPATH/../../Recovered-Tapes/Source-Images/Paper-Tapes/
test_file_base=102766758_fc131-204-10_watson
tapepath=$PYTHONPATH/../../Recovered-Tapes/Source-Images/

if [ "$1" == "--Accept" ];
then
	echo "Accepting fc-to-wwasm Tests..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp  ${test_file_base}.fc wwutd.log TestRefs/
elif [ "$1" == "--Build" ];
then
 	echo "Nothing to build yet"
elif [ "$1" == "--CopyTapes" ];
then
	 echo "Copying all tapes to tmp..."
	 find $tapepath \( -name "*.7ch" -o -name "*.7CH" -o -name "*.tap" \) -print -exec cp -i {} tmp/ \;
elif [ "$1" == "--ReadTapes" ];
then
	echo "Producing tcore, ocore, or fc files from all tapes in tmp, writing to tmp..."
	cd tmp
	time find .  \( -name "*.7ch" -o -name "*.7CH" -o -name "*.tap" \) -exec $utd {} \; >&tapelog
	cd ..
else
	rm -f wwutd.log ${test_file_base}.fc
	
	echo "Testing wwutd..."
	test_path=$tapepath/2018_01/${test_file_base}.7ch
	# By default output file stays in current wd
	echo $test_path
	python $utd $test_path --Ch7Format >&wwutd.log
	diff -s TestRefs/wwutd.log wwutd.log
	status1=$?	
	diff -s TestRefs/${test_file_base}.fc ${test_file_base}.fc
	status2=$?
	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	status3=0
	status4=0
	status5=0
	status=$(($status1 + $status2 + $status3 + $status4 + $status5))
	if [ "$status" == "0" ];
	then
		echo "Fc-to-wwasm Test PASSED"
	else
		echo "Fc-to-wwasm Test FAILED"
	fi
fi

# $PYTHONPATH/../../Recovered-Tapes/Source-Images/Paper-Tapes/2018_01/102766758_fc131-204-10_watson.7ch
# $PYTHONPATH/../../Recovered-Tapes/Translated-Files/Paper-Tapes/2018_01/102766758_fc131-204-10_watson.fc
# python $utd ${test_file}.7ch  >&wwutd.log
