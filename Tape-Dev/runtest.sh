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

dotest () {
	rm -f wwutd.log ${test_file_base}.fc
	
	echo "Testing wwutd..."
	test_path=$testtapepath/2018_01/${test_file_base}.7ch
	# By default output file stays in current wd
	echo $test_path
	python $utd $test_path --Ch7Format |& egrep -v "FileName|input file" >&wwutd.log
	diff -s TestRefs/wwutd.log wwutd.log
	status1=$?	
	diff -s TestRefs/${test_file_base}.fc ${test_file_base}.fc
	status2=$?
	status=$(($status1 + $status2))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	# This is a dup of mad-game in Code-Samples, in this case running
	# straight through from the tape, so it's a good test.
	echo "Testing hurvitz's mad game..."
	test_path=$testtapepath/062302422_box63/102684113_mad_game_m_hurvitz.7ch
	echo $test_path
	python $utd $test_path --Ch7Format |& egrep -v "FileName|input file" >&wwutd.hmg.log
	diff -s TestRefs/wwutd.hmg.log wwutd.hmg.log
	status3=$?	
	diff -s TestRefs/${test_file_base}.fc ${test_file_base}.fc
	status4=$?
	python $sim -c 10000 -v 102684113_mad_game_m_hurvitz_gs001_fb0.tcore |& egrep -v "Cycles" >&wwsim.hmg.log
	diff -s TestRefs/wwsim.hmg.log wwsim.hmg.log
	status5=$?
	status=$(($status3 + $status4 + $status5))
	if [ "$status" == "0" ];
	then
		echo "Test PASSED"
	else
		echo "Test FAILED"
	fi

	status=$(($status1 + $status2 + $status3 + $status4 + $status5))
	if [ "$status" == "0" ];
	then
		echo "TapeDev Test PASSED"
	else
		echo "TapeDev Test FAILED"
	fi
}

if [ "$1" == "" ];
then
	dotest
	exit
elif [ "$1" == "--Accept" ];
then
	echo "Accepting Tape-Dev Tests..."
	rm -rf TestRefs/
	mkdir TestRefs
	cp  ${test_file_base}.fc wwutd.log wwutd.hmg.log wwsim.hmg.log TestRefs/
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
if [ $(checkarg "--ReadTapes") == 0 ];
then
	echo "Producing tcore, ocore, or fc files from all tapes, writing to tmp..."
	cd tmp
	time /bin/find $tapepath  \( -name "*.7ch" -o -name "*.7CH" -o -name "*.tap" \) -exec python $utd {} \; >&tapelog
	cd ..
fi
if [ $(checkarg "--ShortReadTapes") == 0 ];
then
	# Paper-Tapes/2018_14/102782444_fc156-91-55_11-25-57.7ch --> 102782444_fc156-91-55_11-25-57.fc
	# Magnetic-Tapes/68/t68.tap --> t68_gs012_fb100-0-110.tcore
	# Magnetic-Tapes/88/t88.tap --> t88_gs298.ocore
	file1=${tapepath}/Paper-Tapes/2018_14/102782444_fc156-91-55_11-25-57.7ch
	file2=${tapepath}/Magnetic-Tapes/68/t68.tap
	file3=${tapepath}/Magnetic-Tapes/88/t88.tap
	echo "Producing a small number of tcore, ocore, or fc files from all tapes, writing to tmp..."
	cd tmp
	time /bin/find {$file1,$file2,$file3} -print -exec python $utd {} \; >&tapelog
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
	rm -rf jpg
	mkdir jpg
	for file in `ls *.gv` ; do
		# Only dot the file if the gv is of non-zero length
		if [ -s ${file} ];
		then
			echo "Dotting " $file
			python $wwdot $file | gvpack -m0  | neato -s -n2 -Tsvg > ${file}.svg
			python $wwdot $file | gvpack -m0  | neato -s -n2 -Tjpg > jpg/${file}.jpg
		fi
		# Dump zero-length jpgs
		if [ -s jpg/${file}.jpg ];
		then
			dummy=1
		else
			echo "Delete jpg/${file}.jpg"
			rm -f jpg/${file}.jpg
		fi
	done
	cd ..
fi

# $PYTHONPATH/../../Recovered-Tapes/Source-Images/Paper-Tapes/2018_01/102766758_fc131-204-10_watson.7ch
# $PYTHONPATH/../../Recovered-Tapes/Translated-Files/Paper-Tapes/2018_01/102766758_fc131-204-10_watson.fc
# python $utd ${test_file}.7ch  >&wwutd.log
