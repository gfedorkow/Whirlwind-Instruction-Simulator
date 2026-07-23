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
	echo "Accepting Counter Tests..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp two-loop-counter-wwsim.log unrolled-loop-counter-wwsim.log TestRefs/
else
	rm -f two-loop-counter-wwsim.log unrolled-loop-counter-wwsim.log
	rm -f two-loop-counter.acore unrolled-loop-counter.acore
	echo "Testing Counters..."
	echo "Testing Two-Loop Counter..."
	python $asm --CommentColumn 25 --CommentWidth 50 --OmitAutoComment two-loop-counter.ww
	python $sim -v two-loop-counter.acore | grep "Total cycles" | sed -e "s/last PC.*usec,//" >&two-loop-counter-wwsim.log
	cat two-loop-counter-wwsim.log
	diff -s TestRefs/two-loop-counter-wwsim.log two-loop-counter-wwsim.log
	status1=$?
	echo "Testing Unrolled Loop Counter..."
	python $asm --CommentColumn 25 --CommentWidth 50 --OmitAutoComment unrolled-loop-counter.ww
	python $sim -v unrolled-loop-counter.acore | grep "Total cycles" | sed -e "s/last PC.*usec,//" >&unrolled-loop-counter-wwsim.log
	cat unrolled-loop-counter-wwsim.log
	diff -s TestRefs/unrolled-loop-counter-wwsim.log unrolled-loop-counter-wwsim.log
	status2=$?
	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi
fi

