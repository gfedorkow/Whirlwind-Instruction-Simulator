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

if [ "$1" == "--Accept" ];
then
	echo "Accepting Change-problem Tests..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp wwasm.log wwsim.log TestRefs/
elif [ "$1" == "--Build" ];
then
	echo "Nothing to build"
else

	# To run for real, need to interact with panel. RIght now can't
	# automate that, so do this by hand:

	# python $sim -p --FlexoWin change.acore
	
	echo "Testing Change-problem..."
	python $asm --CommentColumn 25 --CommentWidth 50 --OmitAutoComment change.ww >&wwasm.log
	python $sim -c 10000 change.acore >&wwsim.log
	diff -s TestRefs/wwasm.log wwasm.log
	status1=$?
	if [ "$status1" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi
	diff -s TestRefs/wwsim.log wwsim.log
	status2=$?
	if [ "$status2" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Change-problem Test PASSED"
	else
		echo "Change-problem Test FAILED"
	fi
fi

