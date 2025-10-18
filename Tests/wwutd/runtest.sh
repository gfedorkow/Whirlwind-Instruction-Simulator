#!/bin/bash
# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

test_file=102663328_fb131-0-2690_new_decoders_3of4

echo "Universal Tape Decoder tests:"
if [ "$1" == "--Accept" ];
then
	echo "Accepting..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp wwutd.log ${test_file}_gs001.tcore TestRefs/
else
	asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"		# Use quotes since can't resolve backslash yet -- it's needed for file name translation
	sim="$PYTHONPATH/../../Py/Sim/wwsim.py"
	wwutd="$PYTHONPATH/../../Py/Tape-Decode/wwutd.py"
	rm -f ${test_file}_gs001.tcore  wwutd.log tmp-wwutd.log tmp-ref-wwutd.log 
	python $wwutd ${test_file}.7ch  >&wwutd.log

	diff -s wwutd.log TestRefs/wwutd.log
	status1=$?
	diff -s ${test_file}_gs001.tcore TestRefs/${test_file}_gs001.tcore
	status2=$?

	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
		rm wwutd.log ${test_file}_gs001.tcore
	else
		echo "Test FAILED"
	fi
fi


