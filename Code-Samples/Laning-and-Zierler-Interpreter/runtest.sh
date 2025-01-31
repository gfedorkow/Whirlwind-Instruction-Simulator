
# This test is the *new* asm, even though we haven't marked it .n
#
# In this test we don't run any sims, just generate and compare. The
# parsing test compares parse trees.

# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

sim="$PYTHONPATH/../../Py/Sim/wwsim.py"
asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"
asmp="$PYTHONPATH/../../Py/Assembler/wwasmparser.py"	   
asmn="$PYTHONPATH/../../Py/Assembler/wwasm.new.py"
asml="$PYTHONPATH/../../Py/Assembler/wwlzparser.py"
asmc="$PYTHONPATH/../../Py/Assembler/cwparser.py"

if [ "$1" == "--Accept" ];
then
	echo "Accepting L&Z Tests..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp ErrorTest.log FilteredTest1.log FilteredTest2.log TestRefs/
elif [ "$1" == "--Build" ];
then
 	 echo "Building L&Z ww..."
	 python $asml L-and-Z-Transcript-With-Repairs-Tab.txt -o las-l-and-z.ww
else

	# python $sim -q --PETRAfile L-and-Z.petrA las-l-and-z.ncore
	# python $asmn --CommentColumn 25 --CommentWidth 50 --OmitAutoComment --DecimalAddresses las-l-and-z.ww
	
	# Test parsing and some eval-ing, only
	echo "Test Parsing..."
	python $asmp -v test1.ww >&test1.log		# Should produce an eval error and that's ok so it's in the log
	python $asmp -v test2.ww >&test2.log

	grep -v "AsmExpr-" test1.log >FilteredTest1.log
	grep -v "AsmExpr-" test2.log >FilteredTest2.log

	diff -s FilteredTest1.log TestRefs/FilteredTest1.log
	status1=$?
	diff -s FilteredTest2.log TestRefs/FilteredTest2.log
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
	rm -f test3.nlst test3.nlst.nlst
	python $asmn test3.ww >&test3.log
	cp test3.nlst test3.nlst.ww
	python $asmn test3.nlst.ww &>>test3.log
	diff -s test3.nlst test3.nlst.nlst
	status3=$?

	if [ "$status3" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	# Error message test.
	echo "Test asm error messages. The ww program has an error in each line..."
	python $asmn ErrorTest.ww >&ErrorTest.log
	diff -s ErrorTest.log TestRefs/ErrorTest.log
	status4=$?

	if [ "$status4" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	status=$(($status1 + $status2 + $status3 + $status4))
	if [ "$status" == "0" ];
	then
		echo "Assembler Test PASSED"
	else
		echo "Assembler Test FAILED"
	fi
fi

