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
utd="$PYTHONPATH/../../Py/Tape-Decode/wwutd.py"
dis="$PYTHONPATH/../../Py/Disassembler/wwdisasm.py"
wwdot="$PYTHONPATH/../../Py/Tools/wwdot.py"

testtapepath=$PYTHONPATH/../../Recovered-Tapes/Source-Images/Paper-Tapes/
test_file_base=102766758_fc131-204-10_watson
tapepath=$PYTHONPATH/../../Recovered-Tapes/Source-Images/

arglist=$*

checkarg () {
	for item in $arglist
	do
		if [ "$1" == "$item" ]; then
			echo 0
			return 0
		fi
	done
	echo 1
}

if [ "$1" == "" ];
then
	echo "Bare test"
	exit
elif [ "$1" == "--Accept" ];
then
	echo "Tape-Dev Tests..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp  ${test_file_base}.fc wwutd.log TestRefs/
	exit
elif [ "$1" == "--Build" ];
then
 	echo "Nothing to build yet"
	exit
fi
if [ $(checkarg "--Test1") == 0 ];
then
	echo "Test 1!!!"
	exit
fi
if [ $(checkarg "--Test2") == 0 ];
then
	echo "Test 2!!!"
	./runtest.sh --Test1
	exit
fi
if [ $(checkarg "--CopyTapes") == 0 ];
then
	 echo "Copying all tapes to tmp..."
	 /bin/find $tapepath \( -name "*.7ch" -o -name "*.7CH" -o -name "*.tap" \) -print -exec cp -i {} tmp/ \;
fi
if [ $(checkarg "--ReadTapes") == 0 ];
then
	echo "Producing tcore, ocore, or fc files from all tapes in tmp, writing to tmp..."
	cd tmp
	time /bin/find .  \( -name "*.7ch" -o -name "*.7CH" -o -name "*.tap" \) -exec python $utd {} \; >&tapelog
	cd ..
fi
if [ $(checkarg "--DisAsm") == 0 ];
then
	echo "Disassembling tcore files..."
	cd tmp
	rm -f disasmlog
	for file in `ls *.tcore` ; do
		echo "Disassembling " $file
		python $dis -n $file &>>disasmlog
	done
	cd ..
fi
if [ $(checkarg "--Asm") == 0 ];
then
	echo "Assembling ww files, with flowgraphs..."
	cd tmp
	rm -f asmlog
	for file in `ls *.ww` ; do
		echo "Assembling " $file
		python $asm -f $file &>>asmlog
	done
	cd ..
fi
if [ $(checkarg "--Dot") == 0 ];
then
	echo "Dotting gv files..."
	cd tmp
	for file in `ls *.gv` ; do
		echo "Dotting " $file
		python $wwdot $file | gvpack -m0  | neato -s -n2 -Tsvg > ${file}.svg
	done
	cd ..
fi

#else
#	rm -f wwutd.log ${test_file_base}.fc
#	
#	echo "Testing wwutd..."
#	test_path=$testtapepath/2018_01/${test_file_base}.7ch
#	# By default output file stays in current wd
#	echo $test_path
#	python $utd $test_path --Ch7Format >&wwutd.log
#	diff -s TestRefs/wwutd.log wwutd.log
#	status1=$?	
#	diff -s TestRefs/${test_file_base}.fc ${test_file_base}.fc
#	status2=$?
#	status=$(($status1 + $status2))
#	if [ "$status" == "0" ];
#	then
#		echo "Test PASSED"
#	else
#		echo "Test FAILED"
#	fi
#
#	status3=0
#	status4=0
#	status5=0
#	status=$(($status1 + $status2 + $status3 + $status4 + $status5))
#	if [ "$status" == "0" ];
#	then
#		echo "TapeDev Test PASSED"
#	else
#		echo "TapeDev Test FAILED"
#	fi
# fi

# $PYTHONPATH/../../Recovered-Tapes/Source-Images/Paper-Tapes/2018_01/102766758_fc131-204-10_watson.7ch
# $PYTHONPATH/../../Recovered-Tapes/Translated-Files/Paper-Tapes/2018_01/102766758_fc131-204-10_watson.fc
# python $utd ${test_file}.7ch  >&wwutd.log
