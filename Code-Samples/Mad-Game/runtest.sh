#!/bin/bash

echo "Mad Game Test:"

# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

if [ "$1" == "--Accept" ];
then
	echo "Accepting..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp wwasm.log wwsim.log TestRefs/
else
	asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"		# Use quotes since can't resolve backslash yet -- it's needed for file name translation
	sim="$PYTHONPATH/../../Py/Sim/wwsim.py"
	rm mad-game-annotated.acore mad-game-annotated.lst wwsim.log wwasm.log
	python $asm mad-game-annotated.ww |& egrep "Warning|Error" >&wwasm.log
	python $sim -v --CycleLimit 10000  mad-game-annotated.acore |& egrep -v "cycles" >&wwsim.log
	diff -s TestRefs/wwasm.log wwasm.log
	status1=$?
	diff -s TestRefs/wwsim.log wwsim.log
	status2=$?
	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
		# rm wwsim.log wwasm.log
	else
		echo "Test FAILED"
	fi
fi
