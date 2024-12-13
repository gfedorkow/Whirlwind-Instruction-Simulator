
# How do we set path commonly in unix, cygwin, macos, etc.?
PATH=$PATH:$PYTHONPATH/../../Win-Binary
echo "Assembler Parse Test:"
if [ "$1" == "--Accept" ];
then
	echo "Accepting..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp FilteredErrorTest.log FilteredTest2.log TestRefs/
else
	asmp="$PYTHONPATH/../../Py/Assembler/wwasmparser.py"		# Use quotes since can't resolve backslash yet -- it's needed for file name translation
	python $asmp -v ErrorTest.ww >&ErrorTest.log
	python $asmp -v test2.ww >&test2.log
	grep -v "AsmExpr-" ErrorTest.log >FilteredErrorTest.log
	grep -v "AsmExpr-" test2.log >FilteredTest2.log
	diff -s FilteredErrorTest.log TestRefs/FilteredErrorTest.log
	status1=$?
	diff -s FilteredTest2.log TestRefs/Filteredtest2.log
	status2=$?
	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi
fi

