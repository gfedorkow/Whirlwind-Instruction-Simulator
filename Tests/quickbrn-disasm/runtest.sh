#!/bin/bash
# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

echo "Disassembly Test:"
if [ "$1" == "--Accept" ];
then
	echo "Accepting..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp wwdisasm.log quickbrn.ww TestRefs/
else
	asm="$PYTHONPATH/../../Py/Assembler/wwasm.py"		# Use quotes since can't resolve backslash yet -- it's needed for file name translation
	disasm="$PYTHONPATH/../../Py/Disassembler/wwdisasm.py"
	sim="$PYTHONPATH/../../Py/Sim/wwsim.py"
	rm -f wwdisasm.log quickbrn.ww 
	python $disasm quickbrn.acore >&wwdisasm.log
	diff -s TestRefs/wwdisasm.log wwdisasm.log
	status1=$?
	diff -s TestRefs/quickbrn.ww quickbrn.ww
	status2=$?
	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi
fi
