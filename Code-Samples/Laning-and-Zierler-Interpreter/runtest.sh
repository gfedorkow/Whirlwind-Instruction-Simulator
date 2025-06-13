#!/bin/bash
# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

sim="$PYTHONPATH/../../Py/Sim/wwsim.py"
asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"
asmp="$PYTHONPATH/../../Py/Common/wwasmparser.py"
asml="$PYTHONPATH/../../Py/Assembler/wwlzparser.py"
asmc="$PYTHONPATH/../../Py/Assembler/cwparser.py"
ascflx="$PYTHONPATH/../../Py/Tools/ww-ASCII-to-Flexo.py"

if [ "$1" == "--Accept" ];
then
	echo "Accepting L&Z Tests..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp fl-wwasm.log fl-wwsim.log lz-wwsim1.log lz-wwsim2.log lz-wwsim3.log lz-music-wwsim.log TestRefs/
elif [ "$1" == "--Build" ];
then
 	echo "L&Z ww already built"
	# This cycle of editing the lz transcript and producing the ww is
	# over. The ww now is edited directly.
	# python $asml L-and-Z-Transcript-With-Repairs-Tab.txt -o l-and-z.ww
	echo "Frac printer already built"
	# Ditto for the frac printer. This morphed into modern-frac-30-0-0-print.ww.
	# python $asml frac-30-0-0-print-transcript.txt -o frac-30-0-0-print.ww
else
	rm -f fl-wwasm.log fl-wwsim.log lz-wwsim1.log lz-wwsim2.log help-me lz-tmp.pet
	echo "Testing floatlib..."
	python $asm --CommentColumn 25 --CommentWidth 50 --OmitAutoComment test-float-lib.ww >&fl-wwasm.log
	# We'll assume the "notes" test is the default run by the floatlib test code
	python $sim -q test-float-lib.acore | grep xxxxxx >&fl-wwsim.log
	diff -s fl-wwsim.log TestRefs/fl-wwsim.log
	status1=$?	
	if [ "$status1" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	echo "Testing L&Z programs..."
	python $asm --CommentColumn 25 --CommentWidth 50 --OmitAutoComment --DecimalAddresses l-and-z.ww

	echo "Testing L&Z program 1..."
	(python $ascflx -r -i - <<-EOF
		x = 42 + 57,
		y = 86 + 99,
		z = xy,
		PRINT z.
		STOP
		EOF
	) >lz-tmp.pet
	python $sim -q --PETRAfile lz-tmp.pet l-and-z.acore >&lz-wwsim1.log
	diff -s lz-wwsim1.log TestRefs/lz-wwsim1.log
	status2=$?
	if [ "$status2" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	echo "Testing L&Z program 2..."
	(python $ascflx -r -i - <<-EOF
		x = 1.059463094,
		y = xx,
		z = -x,
		PRINT yz.
		STOP
		EOF
 	) >lz-tmp.pet
	python $sim -q --PETRAfile lz-tmp.pet  l-and-z.acore >&lz-wwsim2.log
	diff -s lz-wwsim2.log TestRefs/lz-wwsim2.log
	status3=$?
	if [ "$status3" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	echo "Testing L&Z program 3..."
	(python $ascflx -r -i - <<-EOF
		x = (3.14159 + 42)(2.718 + 57),
		PRINT x.
		STOP
		EOF
  	) >lz-tmp.pet
	python $sim -q --PETRAfile lz-tmp.pet l-and-z.acore >&lz-wwsim3.log
	diff -s lz-wwsim3.log TestRefs/lz-wwsim3.log
	status4=$?
	if [ "$status4" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	echo "Testing L&Z program music-notes.lzt..."

	python $ascflx -r -i music-notes.lzt -o music-notes.pet
	# Note this does not bring up a FlexoWin...
	python $sim -q --PETRAfile music-notes.pet l-and-z.acore >&lz-music-wwsim.log
	# ...but this does
	# python $sim -q -p --FlexoWin --PETRAfile music-notes.pet l-and-z.acore
	diff -s lz-music-wwsim.log TestRefs/lz-music-wwsim.log
	status5=$?
	if [ "$status5" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	status=$(($status1 + $status2 + $status3 + $status4 + $status5))
	if [ "$status" == "0" ];
	then
		echo "L&Z Test PASSED"
	else
		echo "L&Z Test FAILED"
	fi
fi

