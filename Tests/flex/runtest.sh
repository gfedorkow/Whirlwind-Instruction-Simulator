#!/bin/bash

echo "Flex code translation test:"

# cd to the dir with this file, to facilitate external control
thisfile=$0
cd ${thisfile%/*}/

if [ "$1" == "--Accept" ];
then
	echo "Accepting..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp flex.log TestRefs/
else
	flex="$PYTHONPATH/../../Py/Common/wwflex.py"

	echo "Test translation of Flascii to flex code and back again."
	echo "This uses test text built-in to wwflex.py..."
	rm -f flex.log
	python $flex >&flex.log

   	diff -s TestRefs/flex.log flex.log
	status1=$?
	if [ "$status1" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	status2=0
	status3=0
	status4=0
	status5=0
	
	status=$(($status1 + $status2 + $status3 + $status4 + $status5))
	if [ "$status" == "0" ];
	then
		echo "Flex Test PASSED"
	else
		echo "Flex Test FAILED"
	fi
fi

