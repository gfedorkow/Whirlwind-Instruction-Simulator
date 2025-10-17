#!/bin/bash
# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

echo "Test proc call:"
if [ "$1" == "--Accept" ];
then
	echo "Accepting..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp wwasm-proc.log wwsim-proc.log wwasm-frame.log wwsim-frame.log TestRefs/
else
	asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"		# Use quotes since can't resolve backslash yet -- it's needed for file name translation
	sim="$PYTHONPATH/../../Py/Sim/wwsim.py"

	rm proc-call.acore proc-call.lst
	rm 	wwasm-proc.log wwsim-proc.log wwasm-frame.log wwsim-frame.log
	python $asm proc-call.ww  >&wwasm-proc.log
	python $sim -q --CycleLimit 7700 proc-call.acore >&wwsim-proc.log
	egrep "Warning|Error" wwasm-proc.log >&tmp-wwasm.log
	egrep "Warning|Error" TestRefs/wwasm-proc.log >&tmp-ref-wwasm.log
	grep proc-call-test wwsim-proc.log >&tmp-wwsim.log
	grep proc-call-test TestRefs/wwsim-proc.log >&tmp-ref-wwsim.log
	diff -s tmp-ref-wwasm.log tmp-wwasm.log
	status1=$?
	diff -s tmp-ref-wwsim.log tmp-wwsim.log
	status2=$?

	rm stack-frame-rel-addr-lib.acore stack-frame-rel-addr-lib.lst
	python $asm stack-frame-rel-addr-lib.ww >&wwasm-frame.log
	python $sim -q --CycleLimit 7700 stack-frame-rel-addr-lib.acore >&wwsim-frame.log
	egrep "Warning|Error" wwasm-frame.log >&tmp-wwasm.log
	egrep "Warning|Error" TestRefs/wwasm-frame.log >&tmp-ref-wwasm.log
	grep proc-call-test wwsim-frame.log >&tmp-wwsim.log
	grep proc-call-test TestRefs/wwsim-frame.log >&tmp-ref-wwsim.log
	diff -s tmp-ref-wwasm.log tmp-wwasm.log
	status3=$?
	diff -s tmp-ref-wwsim.log tmp-wwsim.log
	status4=$?

	status=$(($status1 + $status2 + $status3 + $status4))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
		rm tmp-ref-wwasm.log tmp-ref-wwsim.log tmp-wwasm.log tmp-wwsim.log
	else
		echo "Test FAILED"
	fi
fi
