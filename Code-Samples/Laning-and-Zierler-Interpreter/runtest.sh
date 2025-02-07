
# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

sim="$PYTHONPATH/../../Py/Sim/wwsim.py"
asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"
asmp="$PYTHONPATH/../../Py/Common/wwasmparser.py"
asml="$PYTHONPATH/../../Py/Assembler/wwlzparser.py"
asmc="$PYTHONPATH/../../Py/Assembler/cwparser.py"

if [ "$1" == "--Accept" ];
then
	echo "Accepting L&Z Tests..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp fl-wwasm.log fl-wwsim.log TestRefs/
elif [ "$1" == "--Build" ];
then
 	echo "L&Z ww already built"
	# This cycle of editing the lz transcript and producing the ww is
	# over. The ww now is edited directly.
	# python $asml L-and-Z-Transcript-With-Repairs-Tab.txt -o las-l-and-z.ww
else
	echo "Testing floatlib..."
	python $asm --CommentColumn 25 --CommentWidth 50 --OmitAutoComment las-float-lib.ww >&fl-wwasm.log
	# We'll assume the "notes" test is the default run by the floatlib
	python $sim -q las-float-lib.acore | grep xxxxxx >&fl-wwsim.log
	diff -s fl-wwsim.log TestRefs/fl-wwsim.log
	status1=$?	
	status2=$?
	status3=$?	
	status4=$?
	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	# Not testing lz proper yet
	# python $sim -q --PETRAfile L-and-Z.petrA las-l-and-z.acore
	# python $asm --CommentColumn 25 --CommentWidth 50 --OmitAutoComment --DecimalAddresses las-l-and-z.ww

	status=$(($status1 + $status2 + $status3 + $status4))
	if [ "$status" == "0" ];
	then
		echo "L&Z Test PASSED"
	else
		echo "L&Z Test FAILED"
	fi
fi

