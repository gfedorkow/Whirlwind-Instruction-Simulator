#!/bin/bash
# This test is the *new* asm, even though we haven't marked it .n
#
# In this test we don't run any sims, just generate and compare. The
# parsing test compares parse trees.

echo "Assembler Test:"

# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

if [ "$1" == "--Accept" ];
then
	echo "Accepting..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp ErrorTest.log FilteredTest1.log FilteredTest2.log inc1.lst flextest.lst flextest.sim.log last-word.sim.log last-word.lst TestRefs/
else
	asmp="$PYTHONPATH/../../Py/Common/wwasmparser.py"		# Use quotes since can't resolve backslash yet -- it's needed for file name translation
	asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"
	sim="$PYTHONPATH/../../Py/Sim/wwsim.py"

	# Test parsing and some eval-ing, only
	echo "Test Parsing..."
	python $asmp -v test1.ww >&test1.log		# Should produce an eval error and that's ok so it's in the log
	python $asmp -v test2.ww >&test2.log
	grep -v "AsmExpr-" test1.log >FilteredTest1.log
	grep -v "AsmExpr-" test2.log >FilteredTest2.log

	diff -s TestRefs/FilteredTest1.log FilteredTest1.log
	status1=$?
	diff -s TestRefs/FilteredTest2.log FilteredTest2.log
	status2=$?

	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	# Idempotency
	echo "Test idempotency: Run a listing back through asm and assure it produces the same listing..."
	rm -f test3.lst test3.lst.lst
	python $asm test3.ww >&test3.log
	cp test3.lst test3.lst.ww
	python $asm test3.lst.ww &>>test3.log
	diff -s test3.lst test3.lst.lst
	status3=$?
	if [ "$status3" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	# Error message test.
	echo "Test asm error messages. The ww program has an error in each line..."
	python $asm ErrorTest.ww >&ErrorTest.log
	diff -s TestRefs/ErrorTest.log ErrorTest.log
	status4=$?
	if [ "$status4" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	# .include test
	echo "Test .include..."
	rm -f inc1.acore inc1.lst includetest.log
	python $asm --OmitAutoComment inc1.ww >&includetest.log
   	diff -s TestRefs/inc1.lst inc1.lst
	status5=$?
	if [ "$status5" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi


	# .flex test
	echo "Test .flexh and .flexl..."
	rm -f flextest.lst flextest.acore flextest.sim.log 
	python $asm --OmitAutoComment flextest.ww >&flextest.asm.log
	python $sim flextest.acore |& grep -v cycles >flextest.sim.log 
   	diff -s TestRefs/flextest.lst flextest.lst
	status6=$?
	diff -s flextest.sim.log TestRefs/flextest.sim.log
	status7=$?
	status=$(($status6 + $status7))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	# last-word test
	echo "Test use of last memory word"
	rm -f last-word.lst last-word.acore last-word.sim.log  last-word.asm.log
	python $asm --OmitAutoComment last-word.ww >&last-word.asm.log
	python $sim -q last-word.acore |& grep -v cycles >last-word.sim.log 
   	diff -s last-word.lst TestRefs/last-word.lst
	status8=$?
	diff -s last-word.sim.log TestRefs/last-word.sim.log
	status9=$?
	status=$(($status8 + $status9))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	status=$(($status1 + $status2 + $status3 + $status4 + $status5 \
                       + $status6 + $status7 + $status8 + $status9))
	if [ "$status" == "0" ];
	then
		echo "Assembler Test PASSED"
	else
		echo "Assembler Test FAILED"
	fi
fi

