
echo "CRT-Test-Guy Test:"
if [ "$1" == "--Accept" ];
then
	echo "Accepting..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp wwasm.log wwsim.log TestRefs/
else
	asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"		# Use quotes since can't resolve backslash yet -- it's needed for file name translation
	sim="$PYTHONPATH/../../Py/Sim/wwsim.py"
	rm crt-test.acore wwsim.log wwasm.log
	python $asm crt-test.ww -o crt-test >&wwasm.log
	python $sim --CycleLimit 7700 crt-test.acore >&wwsim.log
	egrep "Warning|Error" wwasm.log >&tmp-wwasm.log
	egrep "Warning|Error" TestRefs/wwasm.log >&tmp-ref-wwasm.log
	grep ww_draw_point wwsim.log >&tmp-wwsim.log
	grep ww_draw_point TestRefs/wwsim.log >&tmp-ref-wwsim.log
	diff -s tmp-wwasm.log tmp-ref-wwasm.log
	status1=$?
	diff -s tmp-wwsim.log tmp-ref-wwsim.log
	status2=$?
	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
		rm tmp-ref-wwasm.log tmp-ref-wwsim.log tmp-wwasm.log tmp-wwsim.log
	else
		echo "Test FAILED"
	fi
fi
